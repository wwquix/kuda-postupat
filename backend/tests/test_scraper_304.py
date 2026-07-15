from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import sessionmaker

import app.main as main_module
import app.scraper as scraper_module
from app.adapters import BSEU_ADAPTER_KEY, build_bseu_monitoring_registry
from app.calculations import calculate_metrics
from app.catalog_models import (
    DataSource,
    FundingType,
    InstitutionKind,
    LegacySpecialtyMapping,
    MonitoringStatus,
    OwnershipType,
    Program,
    ProgramOffering,
    StudyForm,
    University,
)
from app.config import Settings
from app.models import AdmissionSnapshot, HttpCacheState, NotificationLog, ScraperRun
from app.parser import parse_document, select_specialties
from app.repository import get_or_create_specialty, save_snapshot_if_changed
from app.scraper import AdmissionScraper, NotModifiedWithoutSnapshotError


@pytest.fixture
def session_factory(tmp_path: Path, monkeypatch, test_engine_factory):
    engine: Engine = test_engine_factory(f"sqlite:///{tmp_path / 'test.db'}")
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        university = University(
            code="bseu",
            slug="bseu",
            short_name="БГЭУ",
            full_name="Белорусский государственный экономический университет",
            institution_kind=InstitutionKind.UNIVERSITY,
            ownership_type=OwnershipType.STATE,
            official_site_url="https://bseu.by/",
            monitoring_status=MonitoringStatus.ONLINE,
            source_url="https://official.test/registry",
            source_checked_at=datetime.now(UTC),
        )
        program = Program(
            university=university,
            code="6-05-0311-05",
            slug="economic-informatics",
            name="Экономическая информатика",
            official_url="https://official.test/program",
            source_checked_at=datetime.now(UTC),
        )
        session.add(
            ProgramOffering(
                program=program,
                admission_year=2026,
                study_form=StudyForm.FULL_TIME,
                funding_type=FundingType.PAID,
                places=60,
                monitoring_supported=True,
                monitoring_status=MonitoringStatus.ONLINE,
                official_url="https://official.test/plan",
                source_url="https://official.test/plan",
                source_checked_at=datetime.now(UTC),
            )
        )
        session.add(
            DataSource(
                university=university,
                source_type="admission_xml",
                source_url="https://example.test/data.xml",
                enabled=True,
            )
        )
        session.commit()
    monkeypatch.setattr(scraper_module, "SessionLocal", factory)
    return factory


def _settings() -> Settings:
    return Settings(
        source_data_url="https://example.test/data.xml",
        source_page_url="https://example.test/",
        target_specialties="Экономическая информатика",
        study_form="дневная",
        funding_type="платная",
        request_retries=1,
    )


def _scraper(settings: Settings) -> AdmissionScraper:
    return AdmissionScraper(settings, build_bseu_monitoring_registry(settings))


def _seed_snapshot(factory, fixture: Path, settings: Settings) -> tuple[int, str, datetime]:
    row = select_specialties(
        parse_document(fixture.read_bytes(), "text/xml"),
        settings.specialty_names,
        settings.study_form,
        settings.funding_type,
    )[0]
    metrics = calculate_metrics(row.admission_plan, row.applications_total, row.distribution, settings.user_score)
    with factory() as session:
        specialty = get_or_create_specialty(session, row, settings.source_page_url)
        snapshot, _, _ = save_snapshot_if_changed(session, specialty, row, settings.user_score, metrics)
        session.add(
            HttpCacheState(
                url=settings.data_url,
                etag='"existing-etag"',
                last_modified="Sat, 12 Jul 2026 12:00:00 GMT",
                checked_at=datetime.now(UTC) - timedelta(hours=1),
            )
        )
        session.commit()
        return specialty.id, snapshot.raw_data_hash, snapshot.source_updated_at


def _response(status_code: int, content: bytes = b"") -> httpx.Response:
    return httpx.Response(
        status_code,
        content=content,
        headers={"content-type": "text/xml", "etag": '"new-etag"'},
        request=httpx.Request("GET", "https://example.test/data.xml"),
    )


@pytest.mark.asyncio
async def test_304_after_snapshot_is_successful_and_silent(
    session_factory, fixtures_dir: Path, monkeypatch
) -> None:
    settings = _settings()
    _, original_hash, original_source_updated_at = _seed_snapshot(
        session_factory, fixtures_dir / "live_shape.xml", settings
    )
    scraper = _scraper(settings)
    monkeypatch.setattr(scraper, "_fetch", AsyncMock(return_value=_response(304)))
    send_mock = AsyncMock()
    evaluate_mock = Mock()
    monkeypatch.setattr(scraper_module, "send_once", send_mock)
    monkeypatch.setattr(scraper_module, "evaluate_program_watches", evaluate_mock)

    result = await scraper.refresh(BSEU_ADAPTER_KEY, force=True)

    assert result == {
        "status": "not_modified",
        "changed": False,
        "snapshot_created": False,
        "created": 0,
        "rows_found": 0,
        "message": "Источник доступен, данные не изменились",
    }
    with session_factory() as session:
        snapshots = session.scalars(select(AdmissionSnapshot)).all()
        last_run = session.scalar(select(ScraperRun).order_by(ScraperRun.id.desc()))
        cache = session.get(HttpCacheState, settings.data_url)
        assert len(snapshots) == 1
        assert snapshots[0].raw_data_hash == original_hash
        assert snapshots[0].source_updated_at == original_source_updated_at
        assert last_run is not None and last_run.status == "not_modified"
        assert last_run.http_status == 304
        assert cache is not None and cache.checked_at == last_run.finished_at
        assert session.query(NotificationLog).count() == 0
    send_mock.assert_not_awaited()
    evaluate_mock.assert_not_called()


@pytest.mark.asyncio
async def test_304_without_snapshot_retries_once_without_conditions_and_saves_data(
    session_factory, fixtures_dir: Path, monkeypatch
) -> None:
    settings = _settings()
    with session_factory() as session:
        session.add(HttpCacheState(url=settings.data_url, etag='"orphaned-etag"'))
        session.commit()
    responses = [_response(304), _response(200, (fixtures_dir / "live_shape.xml").read_bytes())]
    seen_headers: list[dict[str, str]] = []

    async def fetch(source_url: str, headers: dict[str, str]) -> httpx.Response:
        assert source_url == settings.data_url
        seen_headers.append(headers.copy())
        return responses.pop(0)

    scraper = _scraper(settings)
    evaluate_mock = Mock(return_value=0)
    monkeypatch.setattr(scraper, "_fetch", fetch)
    monkeypatch.setattr(scraper_module, "evaluate_program_watches", evaluate_mock)
    result = await scraper.refresh(BSEU_ADAPTER_KEY, force=True)

    assert result["status"] == "success"
    assert result["snapshot_created"] is True
    assert seen_headers == [{"If-None-Match": '"orphaned-etag"'}, {}]
    with session_factory() as session:
        snapshot = session.query(AdmissionSnapshot).one()
        run = session.query(ScraperRun).one()
        mapping = session.query(LegacySpecialtyMapping).one()
        source = session.query(DataSource).one()
        assert snapshot.program_offering_id == mapping.program_offering_id
        assert run.status == "success"
        assert run.data_source_id == source.id
        assert source.last_success_at == run.finished_at
        assert source.consecutive_failures == 0
        assert evaluate_mock.call_count == 1
        assert evaluate_mock.call_args.args[1] == [snapshot.id]


@pytest.mark.asyncio
async def test_repeated_304_without_snapshot_is_controlled_and_finite(session_factory, monkeypatch) -> None:
    settings = _settings()
    with session_factory() as session:
        session.add(HttpCacheState(url=settings.data_url, etag='"orphaned-etag"'))
        session.commit()
    fetch_mock = AsyncMock(side_effect=[_response(304), _response(304)])
    evaluate_mock = Mock()
    scraper = _scraper(settings)
    monkeypatch.setattr(scraper, "_fetch", fetch_mock)
    monkeypatch.setattr(scraper_module, "evaluate_program_watches", evaluate_mock)

    with pytest.raises(NotModifiedWithoutSnapshotError, match="сохраненных данных"):
        await scraper.refresh(BSEU_ADAPTER_KEY, force=True)

    assert fetch_mock.await_count == 2
    assert fetch_mock.await_args_list[1].args == (settings.data_url, {})
    with session_factory() as session:
        assert session.query(AdmissionSnapshot).count() == 0
        run = session.query(ScraperRun).one()
        assert run.status == "error"
        assert run.http_status == 304
    evaluate_mock.assert_not_called()


def test_manual_refresh_endpoint_returns_200_for_not_modified(
    session_factory, fixtures_dir: Path, monkeypatch
) -> None:
    settings = _settings()
    settings.manual_refresh_token = "unit-test-refresh-token"
    _seed_snapshot(session_factory, fixtures_dir / "live_shape.xml", settings)
    scraper = _scraper(settings)
    monkeypatch.setattr(scraper, "_fetch", AsyncMock(return_value=_response(304)))
    monkeypatch.setattr(main_module, "settings", settings)
    monkeypatch.setattr(main_module, "scraper", scraper)

    response = TestClient(main_module.app).post(
        "/api/refresh", headers={"X-Refresh-Token": settings.manual_refresh_token}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "not_modified"
    assert response.json()["snapshot_created"] is False


def test_manual_refresh_without_cached_data_hides_internal_error(monkeypatch) -> None:
    settings = _settings()
    settings.manual_refresh_token = "unit-test-refresh-token"
    scraper = AsyncMock()
    scraper.refresh.side_effect = NotModifiedWithoutSnapshotError("internal diagnostic")
    monkeypatch.setattr(main_module, "settings", settings)
    monkeypatch.setattr(main_module, "scraper", scraper)

    response = TestClient(main_module.app).post(
        "/api/refresh", headers={"X-Refresh-Token": settings.manual_refresh_token}
    )

    assert response.status_code == 502
    assert response.json() == {"detail": "Не удалось получить корректные данные от источника"}
    assert "internal diagnostic" not in response.text


@pytest.mark.asyncio
async def test_304_updates_check_time_but_preserves_stale_source_time(
    session_factory, fixtures_dir: Path, monkeypatch
) -> None:
    settings = _settings()
    specialty_id, _, original_source_updated_at = _seed_snapshot(
        session_factory, fixtures_dir / "live_shape.xml", settings
    )
    scraper = _scraper(settings)
    monkeypatch.setattr(scraper, "_fetch", AsyncMock(return_value=_response(304)))

    await scraper.refresh(BSEU_ADAPTER_KEY, force=True)

    with session_factory() as session:
        result = main_module.specialty_latest(specialty_id, session)
        assert result["last_checked_at"] > result["fetched_at"]
        assert result["source_updated_at"].replace(tzinfo=None) == original_source_updated_at.replace(tzinfo=None)
        assert result["data_age_seconds"] < 5
        assert result["source_age_seconds"] > settings.stale_after_minutes * 60
        assert result["is_stale"] is True
