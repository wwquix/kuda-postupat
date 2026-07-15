from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker

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
    SourceHealth,
    StudyForm,
    University,
    UniversityCategory,
    UniversityCategoryLink,
)
from app.config import Settings, get_settings
from app.database import get_db
from app.models import AdmissionSnapshot, Specialty
from app.profile_models import AnonymousProfile
from app.recommendation_api import router


@pytest.fixture
def recommendation_api(
    tmp_path: Path,
    test_engine_factory: Callable[[str], Engine],
) -> tuple[TestClient, sessionmaker[Session], Engine, dict[str, int]]:
    database = tmp_path / "recommendations.db"
    engine = test_engine_factory(f"sqlite:///{database.as_posix()}")
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    now = datetime.now(UTC)

    with session_factory() as session:
        economics = UniversityCategory(code="economics", label_ru="Экономика")
        technical = UniversityCategory(code="technical", label_ru="Технические")
        creative = UniversityCategory(code="creative", label_ru="Творческие")
        universities = [
            University(
                code="bseu",
                slug="bseu",
                short_name="БГЭУ",
                full_name="Белорусский государственный экономический университет",
                institution_kind=InstitutionKind.UNIVERSITY,
                ownership_type=OwnershipType.STATE,
                city="Минск",
                region="Минск",
                official_site_url="https://bseu.test",
                monitoring_status=MonitoringStatus.ONLINE,
                source_url="https://bseu.test/source",
                source_checked_at=now,
            ),
            University(
                code="alpha",
                slug="alpha-academy",
                short_name="Альфа",
                full_name="Академия Альфа",
                institution_kind=InstitutionKind.ACADEMY,
                ownership_type=OwnershipType.PRIVATE,
                city="Брест",
                region="Брестская область",
                official_site_url="https://alpha.test",
                monitoring_status=MonitoringStatus.REFERENCE_ONLY,
                source_url="https://alpha.test/source",
                source_checked_at=now,
            ),
            University(
                code="beta",
                slug="beta-institute",
                short_name="Бета",
                full_name="Институт Бета",
                institution_kind=InstitutionKind.INSTITUTE,
                ownership_type=OwnershipType.MIXED,
                city="Гомель",
                region="Гомельская область",
                official_site_url="https://beta.test",
                monitoring_status=MonitoringStatus.UNSUPPORTED,
                source_url="https://beta.test/source",
                source_checked_at=now,
            ),
            University(
                code="gamma",
                slug="gamma-university",
                short_name="Гамма",
                full_name="Университет Гамма",
                institution_kind=InstitutionKind.UNIVERSITY,
                ownership_type=OwnershipType.STATE,
                city="Витебск",
                region="Витебская область",
                official_site_url="https://gamma.test",
                monitoring_status=MonitoringStatus.NEEDS_REVIEW,
                source_url="https://gamma.test/source",
                source_checked_at=now,
            ),
        ]
        session.add_all([economics, technical, creative, *universities])
        session.flush()
        bseu, alpha, beta, gamma = universities
        session.add_all(
            [
                UniversityCategoryLink(university=bseu, category=economics),
                UniversityCategoryLink(university=alpha, category=technical),
                UniversityCategoryLink(university=beta, category=creative),
            ]
        )
        programs = [
            Program(
                university=bseu,
                code="6-05-0311-05",
                slug="economic-informatics",
                name="Экономическая информатика",
                official_url="https://bseu.test/economic-informatics",
                source_checked_at=now,
            ),
            Program(
                university=alpha,
                slug="software-engineering",
                name="Программная инженерия",
                official_url="https://alpha.test/software-engineering",
                source_checked_at=now,
            ),
            Program(
                university=beta,
                slug="design",
                name="Дизайн",
                official_url="https://beta.test/design",
                source_checked_at=now,
            ),
        ]
        session.add_all(programs)
        session.flush()
        bseu_program, alpha_program, beta_program = programs
        bseu_offering = ProgramOffering(
            program=bseu_program,
            admission_year=2026,
            study_form=StudyForm.FULL_TIME,
            funding_type=FundingType.PAID,
            places=3,
            monitoring_supported=True,
            monitoring_status=MonitoringStatus.ONLINE,
            official_url="https://bseu.test/offering",
            source_url="https://bseu.test/offering",
            source_checked_at=now,
        )
        alpha_offering = ProgramOffering(
            program=alpha_program,
            admission_year=2026,
            study_form=StudyForm.PART_TIME,
            funding_type=FundingType.BUDGET,
            places=None,
            monitoring_supported=False,
            monitoring_status=MonitoringStatus.UNSUPPORTED,
            official_url="https://alpha.test/offering",
            source_url="https://alpha.test/offering",
            source_checked_at=now,
        )
        specialty = Specialty(
            normalized_name="экономическая информатика",
            display_name="Экономическая информатика",
            study_form="дневная",
            funding_type="платная",
            source_url="https://bseu.test/admission.xml",
            active=True,
        )
        source = DataSource(
            university=bseu,
            source_type="admission_xml",
            source_url="https://bseu.test/admission.xml",
            adapter_name="legacy_admission_scraper",
            enabled=True,
            last_attempt_at=now,
            last_success_at=now,
            health_status=SourceHealth.HEALTHY,
        )
        session.add_all([bseu_offering, alpha_offering, specialty, source])
        session.flush()
        session.add(
            LegacySpecialtyMapping(
                legacy_specialty_id=specialty.id,
                program_id=bseu_program.id,
                program_offering_id=bseu_offering.id,
                mapping_version=1,
            )
        )
        distribution = {"300-309": 1, "290-299": 2, "280-289": 2}
        snapshot = AdmissionSnapshot(
            specialty_id=specialty.id,
            program_offering_id=bseu_offering.id,
            fetched_at=now,
            source_updated_at=None,
            admission_plan=3,
            applications_total=5,
            competition=1.67,
            estimated_cutoff_min=290,
            estimated_cutoff_max=299,
            user_score=276,
            estimated_user_position=6,
            user_status="Пока не проходит",
            distribution_json=json.dumps(distribution),
            raw_data_hash="a" * 64,
        )
        session.add(snapshot)
        session.commit()
        ids = {
            "snapshot": snapshot.id,
            "bseu_program": bseu_program.id,
            "beta_program": beta_program.id,
            "gamma_university": gamma.id,
        }

    def override_db() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,
        database_url=f"sqlite:///{database.as_posix()}",
        stale_after_minutes=30,
        development_safe_mode=True,
    )
    return TestClient(app), session_factory, engine, ids


def _program_slugs(payload: dict) -> list[str]:
    return [item["program"]["slug"] for item in payload["programs"]["items"]]


def _university_slugs(payload: dict) -> list[str]:
    return [item["university"]["slug"] for item in payload["universities"]["items"]]


def test_score_validation_zero_and_public_access(
    recommendation_api: tuple[TestClient, sessionmaker[Session], Engine, dict[str, int]],
) -> None:
    client, session_factory, _engine, _ids = recommendation_api
    assert client.get("/api/recommendations?score=-1").status_code == 422
    assert client.get("/api/recommendations?score=501").status_code == 422

    response = client.get("/api/recommendations?score=0")
    assert response.status_code == 200
    assert {"parameter": "score", "value": "0"} in response.json()["applied_parameters"]
    assert response.request.headers.get("authorization") is None
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(AnonymousProfile)) == 0


@pytest.mark.parametrize(
    ("query", "expected_programs", "expected_universities"),
    [
        ("city=%D0%91%D1%80%D0%B5%D1%81%D1%82", ["software-engineering"], ["alpha-academy"]),
        (
            "region=%D0%91%D1%80%D0%B5%D1%81%D1%82%D1%81%D0%BA%D0%B0%D1%8F+"
            "%D0%BE%D0%B1%D0%BB%D0%B0%D1%81%D1%82%D1%8C",
            ["software-engineering"],
            ["alpha-academy"],
        ),
        ("ownership_type=private", ["software-engineering"], ["alpha-academy"]),
        ("institution_kind=academy", ["software-engineering"], ["alpha-academy"]),
        ("category=technical", ["software-engineering"], ["alpha-academy"]),
        ("study_form=part_time", ["software-engineering"], ["alpha-academy"]),
        ("funding_type=budget", ["software-engineering"], ["alpha-academy"]),
        ("online_monitoring=true", ["economic-informatics"], ["bseu"]),
        (
            "online_monitoring=false",
            ["software-engineering", "design"],
            ["alpha-academy", "beta-institute", "gamma-university"],
        ),
    ],
)
def test_each_supported_filter_is_server_side(
    recommendation_api: tuple[TestClient, sessionmaker[Session], Engine, dict[str, int]],
    query: str,
    expected_programs: list[str],
    expected_universities: list[str],
) -> None:
    client, _session_factory, _engine, _ids = recommendation_api
    payload = client.get(f"/api/recommendations?{query}").json()
    assert _program_slugs(payload) == expected_programs
    assert _university_slugs(payload) == expected_universities


def test_combined_filters_reasons_deterministic_order_and_pagination(
    recommendation_api: tuple[TestClient, sessionmaker[Session], Engine, dict[str, int]],
) -> None:
    client, _session_factory, _engine, _ids = recommendation_api
    combined = client.get(
        "/api/recommendations?city=%D0%91%D1%80%D0%B5%D1%81%D1%82"
        "&ownership_type=private&institution_kind=academy&category=technical"
        "&study_form=part_time&funding_type=budget"
    )
    assert combined.status_code == 200
    item = combined.json()["programs"]["items"][0]
    assert item["program"]["slug"] == "software-engineering"
    assert [reason["parameter"] for reason in item["match_reasons"]] == [
        "city",
        "ownership_type",
        "institution_kind",
        "category",
        "study_form",
        "funding_type",
    ]

    first = client.get("/api/recommendations?score=292&page_size=2").json()
    second = client.get("/api/recommendations?score=292&page_size=2").json()
    assert first == second
    assert [item["result_class"] for item in first["programs"]["items"]] == [
        "MONITORED_STATUS",
        "PARAMETER_MATCH",
    ]
    assert first["programs"]["pagination"] == {
        "page": 1,
        "page_size": 2,
        "total_items": 3,
        "total_pages": 2,
        "has_next": True,
        "has_previous": False,
    }
    page_two = client.get("/api/recommendations?score=292&page=2&page_size=2").json()
    assert _program_slugs(page_two) == ["design"]
    assert page_two["universities"]["pagination"]["total_items"] == 4
    assert len(page_two["universities"]["items"]) == 2


def test_monitored_status_reuses_existing_calculation_and_stale_is_not_monitored(
    recommendation_api: tuple[TestClient, sessionmaker[Session], Engine, dict[str, int]],
) -> None:
    client, session_factory, _engine, ids = recommendation_api
    payload = client.get("/api/recommendations?score=292").json()
    monitored = payload["programs"]["items"][0]
    expected = calculate_metrics(3, 5, {"300-309": 1, "290-299": 2, "280-289": 2}, 292)
    assert monitored["result_class"] == "MONITORED_STATUS"
    assert monitored["admission_evaluation"] == expected.status
    assert monitored["monitoring"]["estimated_user_position"] == expected.estimated_user_position
    assert monitored["monitoring"]["estimated_cutoff_min"] == expected.cutoff_min
    assert monitored["monitoring"]["estimated_cutoff_max"] == expected.cutoff_max

    stale_at = datetime.now(UTC) - timedelta(hours=2)
    with session_factory() as session:
        snapshot = session.get(AdmissionSnapshot, ids["snapshot"])
        assert snapshot is not None
        snapshot.fetched_at = stale_at
        source = session.scalar(select(DataSource).where(DataSource.source_type == "admission_xml"))
        assert source is not None
        source.last_attempt_at = stale_at
        session.commit()
    stale = client.get("/api/recommendations?score=292&online_monitoring=true").json()
    result = stale["programs"]["items"][0]
    assert result["result_class"] == "PARAMETER_MATCH"
    assert result["monitoring_state"] == "temporarily_unavailable"
    assert result["monitoring"] is None
    assert result["admission_evaluation"] == "Недостаточно данных для оценки поступления"


def test_parameter_match_insufficient_coverage_and_no_fabricated_claims(
    recommendation_api: tuple[TestClient, sessionmaker[Session], Engine, dict[str, int]],
) -> None:
    client, _session_factory, _engine, _ids = recommendation_api
    payload = client.get("/api/recommendations?score=292").json()
    by_slug = {item["program"]["slug"]: item for item in payload["programs"]["items"]}
    parameter_match = by_slug["software-engineering"]
    assert parameter_match["result_class"] == "PARAMETER_MATCH"
    assert parameter_match["result_label"] == "Совпадает с выбранными параметрами"
    assert parameter_match["admission_evaluation"] == "Недостаточно данных для оценки поступления"

    insufficient = by_slug["design"]
    assert insufficient["result_class"] == "INSUFFICIENT_COVERAGE"
    assert "ещё не импортированы" in " ".join(insufficient["coverage_notes"])
    gamma = next(
        item
        for item in payload["universities"]["items"]
        if item["university"]["slug"] == "gamma-university"
    )
    assert gamma["result_class"] == "INSUFFICIENT_COVERAGE"
    assert "не означает" in " ".join(gamma["coverage_notes"])

    response_text = json.dumps(payload, ensure_ascii=False).lower()
    for fabricated in ("вероятност", "процент шанс", "гарантирован", "точно проходите", "eligib"):
        assert fabricated not in response_text


def test_get_performs_no_writes_or_external_http(
    recommendation_api: tuple[TestClient, sessionmaker[Session], Engine, dict[str, int]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session_factory, engine, _ids = recommendation_api
    writes: list[str] = []

    @event.listens_for(engine, "before_cursor_execute")
    def capture_sql(
        _connection: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: bool,
    ) -> None:
        if statement.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "REPLACE")):
            writes.append(statement)

    async def forbidden_http(*_args: object, **_kwargs: object) -> httpx.Response:
        raise AssertionError("recommendations must not perform external HTTP")

    monkeypatch.setattr(httpx.AsyncClient, "request", forbidden_http)
    with session_factory() as session:
        before = {
            "universities": session.scalar(select(func.count()).select_from(University)),
            "programs": session.scalar(select(func.count()).select_from(Program)),
            "snapshots": session.scalar(select(func.count()).select_from(AdmissionSnapshot)),
            "profiles": session.scalar(select(func.count()).select_from(AnonymousProfile)),
        }
    response = client.get("/api/recommendations?score=292&city=%D0%9C%D0%B8%D0%BD%D1%81%D0%BA")
    assert response.status_code == 200
    with session_factory() as session:
        after = {
            "universities": session.scalar(select(func.count()).select_from(University)),
            "programs": session.scalar(select(func.count()).select_from(Program)),
            "snapshots": session.scalar(select(func.count()).select_from(AdmissionSnapshot)),
            "profiles": session.scalar(select(func.count()).select_from(AnonymousProfile)),
        }
    assert writes == []
    assert after == before
