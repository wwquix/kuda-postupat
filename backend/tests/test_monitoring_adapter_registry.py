from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import sessionmaker

import app.main as main_module
import app.scraper as scraper_module
from app.adapters import (
    BSEU_ADAPTER_KEY,
    DuplicateMonitoringAdapterKeyError,
    MonitoringAdapterRegistry,
    UnknownMonitoringAdapterError,
    build_bseu_monitoring_registry,
)
from app.catalog_models import (
    DataSource,
    FundingType,
    InstitutionKind,
    MonitoringStatus,
    OwnershipType,
    Program,
    ProgramOffering,
    StudyForm,
    University,
)
from app.config import Settings
from app.models import AdmissionSnapshot, NotificationLog, ScraperRun
from app.parser import ParserError
from app.scraper import AdmissionScraper


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        source_data_url="https://example.test/data.xml",
        source_page_url="https://example.test/",
        target_specialties="Экономическая информатика",
        study_form="дневная",
        funding_type="платная",
        request_retries=1,
    )


@pytest.fixture
def monitoring_session_factory(tmp_path: Path, monkeypatch, test_engine_factory):
    engine: Engine = test_engine_factory(f"sqlite:///{tmp_path / 'monitoring.db'}")
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    settings = _settings()
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
                source_url=settings.data_url,
                enabled=True,
            )
        )
        session.commit()
    monkeypatch.setattr(scraper_module, "SessionLocal", factory)
    return factory


def _response(content: bytes) -> httpx.Response:
    return httpx.Response(
        200,
        content=content,
        headers={"content-type": "text/xml", "etag": '"adapter-etag"'},
        request=httpx.Request("GET", "https://example.test/data.xml"),
    )


def test_bseu_is_the_only_registered_operational_adapter(fixtures_dir: Path) -> None:
    settings = _settings()
    registry = build_bseu_monitoring_registry(settings)

    assert registry.keys == (BSEU_ADAPTER_KEY,)
    adapter = registry.get(BSEU_ADAPTER_KEY)
    assert adapter.university_code == "bseu"
    assert adapter.source_url == settings.data_url
    parsed = adapter.parse((fixtures_dir / "live_shape.xml").read_bytes(), "text/xml")
    assert len(parsed.rows) == 1
    assert len(parsed.selected) == 1
    assert parsed.selected[0].display_name == "Экономическая информатика"

    for unsupported_key in ("bsu", "bntu", "bspu"):
        with pytest.raises(UnknownMonitoringAdapterError):
            registry.get(unsupported_key)


def test_registry_rejects_duplicate_keys() -> None:
    adapter = build_bseu_monitoring_registry(_settings()).get(BSEU_ADAPTER_KEY)
    with pytest.raises(DuplicateMonitoringAdapterKeyError, match=BSEU_ADAPTER_KEY):
        MonitoringAdapterRegistry((adapter, adapter))


@pytest.mark.asyncio
async def test_unknown_key_finalizes_run_without_snapshot_or_telegram(
    monitoring_session_factory, monkeypatch
) -> None:
    settings = _settings()
    scraper = AdmissionScraper(settings, MonitoringAdapterRegistry(()))
    send_mock = AsyncMock()
    monkeypatch.setattr(scraper_module, "send_once", send_mock)

    with pytest.raises(UnknownMonitoringAdapterError, match="missing"):
        await scraper.refresh("missing", force=True)

    with monitoring_session_factory() as session:
        run = session.scalar(select(ScraperRun))
        source = session.scalar(select(DataSource))
        assert run is not None
        assert source is not None
        assert run.status == "error"
        assert run.finished_at is not None
        assert run.error_type == "UnknownMonitoringAdapterError"
        assert run.data_source_id is None
        assert source.last_attempt_at is None
        assert source.consecutive_failures == 0
        assert session.query(AdmissionSnapshot).count() == 0
        assert session.query(NotificationLog).count() == 0
    send_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_success_duplicate_and_telegram_decision_parity(
    monitoring_session_factory, fixtures_dir: Path, monkeypatch
) -> None:
    settings = _settings()
    scraper = AdmissionScraper(settings, build_bseu_monitoring_registry(settings))
    original = (fixtures_dir / "live_shape.xml").read_bytes()
    changed = original.replace(b'AllCount="8"', b'AllCount="9"')
    fetch_mock = AsyncMock(side_effect=[_response(original), _response(changed), _response(changed)])
    send_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(scraper, "_fetch", fetch_mock)
    monkeypatch.setattr(scraper_module, "send_once", send_mock)

    first = await scraper.refresh(BSEU_ADAPTER_KEY, force=True)
    second = await scraper.refresh(BSEU_ADAPTER_KEY, force=True)
    duplicate = await scraper.refresh(BSEU_ADAPTER_KEY, force=True)

    assert first["snapshot_created"] is True
    assert second["snapshot_created"] is True
    assert duplicate == {
        "status": "success",
        "changed": False,
        "snapshot_created": False,
        "created": 0,
        "rows_found": 1,
    }
    with monitoring_session_factory() as session:
        assert session.query(AdmissionSnapshot).count() == 2
        assert session.query(ScraperRun).count() == 3
        assert {run.status for run in session.scalars(select(ScraperRun))} == {"success"}
        assert session.query(NotificationLog).count() == 0
    send_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_parser_and_transport_failures_preserve_run_lifecycle(
    monitoring_session_factory, monkeypatch
) -> None:
    settings = _settings()
    scraper = AdmissionScraper(settings, build_bseu_monitoring_registry(settings))
    malformed = _response(b"x" * 101)
    request = httpx.Request("GET", settings.data_url)
    fetch_mock = AsyncMock(side_effect=[malformed, httpx.ReadTimeout("timeout", request=request)])
    send_mock = AsyncMock()
    monkeypatch.setattr(scraper, "_fetch", fetch_mock)
    monkeypatch.setattr(scraper_module, "send_once", send_mock)

    with pytest.raises(ParserError):
        await scraper.refresh(BSEU_ADAPTER_KEY, force=True)
    with pytest.raises(httpx.ReadTimeout):
        await scraper.refresh(BSEU_ADAPTER_KEY, force=True)

    with monitoring_session_factory() as session:
        runs = session.scalars(select(ScraperRun).order_by(ScraperRun.id)).all()
        assert [run.status for run in runs] == ["error", "error"]
        assert [run.error_type for run in runs] == ["ParserError", "ReadTimeout"]
        assert all(run.finished_at is not None for run in runs)
        assert session.query(AdmissionSnapshot).count() == 0
        assert session.query(NotificationLog).count() == 0
    send_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_scheduler_and_manual_refresh_use_the_same_registry_key(monkeypatch) -> None:
    refresh = AsyncMock(return_value={"status": "success"})
    settings = _settings()
    settings.manual_refresh_token = "registry-test-token"
    monkeypatch.setattr(main_module, "settings", settings)
    monkeypatch.setattr(main_module.scraper, "refresh", refresh)

    await main_module.scheduled_refresh()
    manual_result = await main_module.manual_refresh(
        authorization=None,
        x_refresh_token=settings.manual_refresh_token,
    )

    assert manual_result == {"status": "success"}
    assert refresh.await_args_list[0].args == (BSEU_ADAPTER_KEY,)
    assert refresh.await_args_list[1].args == (BSEU_ADAPTER_KEY,)
