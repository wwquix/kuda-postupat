from __future__ import annotations

import os
import socket
import subprocess
import sys
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, event, select, text
from sqlalchemy.orm import Session, sessionmaker
from test_bseu_backfill import sqlite_url
from test_university_catalog_import import _seed_bseu

from app.catalog_api import router
from app.catalog_import_service import seed_universities
from app.catalog_models import FundingType, MonitoringStatus, Program, ProgramOffering, StudyForm, University
from app.database import get_db
from app.schema import expected_head


@pytest.fixture
def catalog_client(tmp_path: Path, test_engine_factory) -> Iterator[tuple[TestClient, Engine, Path]]:
    database = tmp_path / "catalog-search-api.db"
    engine = test_engine_factory(sqlite_url(database))
    with Session(engine) as session, session.begin():
        _seed_bseu(session)
        seed_universities(session)
        session.execute(
            select(University).where(University.code == "brsu").with_for_update()
        ).scalar_one().full_name = "Университет Ёлка — Тест"
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"
        )
        connection.exec_driver_sql(
            "INSERT INTO alembic_version (version_num) VALUES (?)",
            (expected_head(),),
        )

    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    yield client, engine, database
    app.dependency_overrides.clear()


def test_university_pagination_boundaries_and_deterministic_sorting(catalog_client) -> None:  # type: ignore[no-untyped-def]
    client, _engine, _database = catalog_client
    first = client.get("/api/universities")
    assert first.status_code == 200
    payload = first.json()
    assert payload["pagination"] == {
        "page": 1,
        "page_size": 20,
        "total_items": 47,
        "total_pages": 3,
        "has_next": True,
        "has_previous": False,
    }

    pages = [client.get(f"/api/universities?page={page}").json()["items"] for page in (1, 2, 3)]
    ids = [item["id"] for page in pages for item in page]
    assert len(ids) == len(set(ids)) == 47
    assert [item["id"] for item in first.json()["items"]] == [
        item["id"] for item in client.get("/api/universities").json()["items"]
    ]

    beyond = client.get("/api/universities?page=99")
    assert beyond.status_code == 200
    assert beyond.json()["items"] == []
    assert beyond.json()["pagination"]["total_items"] == 47

    program_sort = client.get("/api/universities?sort=program_count&order=desc")
    assert program_sort.status_code == 200
    assert program_sort.json()["items"][0]["code"] == "bseu"
    assert program_sort.json()["items"][0]["program_count"] == 1

    for query in ("page=0", "page_size=0", "page_size=101", "sort=unsafe", "order=sideways"):
        assert client.get(f"/api/universities?{query}").status_code == 422


def test_university_search_normalizes_unicode_whitespace_dashes_and_escapes_wildcards(
    catalog_client,
) -> None:  # type: ignore[no-untyped-def]
    client, _engine, _database = catalog_client
    cases = {
        "бгэу": "bseu",
        "  университет   елка - тест  ": "brsu",
        "экономическая информатика": "bseu",
        "6‑05‑0311‑05": "bseu",
        "экономический": "bseu",
    }
    for query, expected_code in cases.items():
        response = client.get("/api/universities", params={"q": query})
        assert response.status_code == 200
        assert expected_code in {item["code"] for item in response.json()["items"]}

    assert client.get("/api/universities", params={"q": "%"}).json()["pagination"]["total_items"] == 0
    underscore = client.get("/api/universities", params={"q": "_"}).json()
    assert underscore["pagination"]["total_items"] == 1
    assert underscore["items"][0]["code"] == "ucp"


@pytest.mark.parametrize(
    ("params", "expected_total"),
    [
        ({"ownership_type": "state"}, 43),
        ({"ownership_type": "private"}, 4),
        ({"region": "Брестская область"}, 4),
        ({"institution_kind": "military_academy"}, 2),
        ({"category": "private"}, 4),
        ({"monitoring_status": "reference_only"}, 25),
        ({"has_admissions_url": "true"}, 33),
        ({"has_admissions_url": "false"}, 14),
        ({"has_programs": "true"}, 1),
        ({"has_programs": "false"}, 46),
        ({"online_monitoring": "true"}, 1),
        ({"online_monitoring": "false"}, 46),
        ({"active": "true"}, 47),
        ({"active": "false"}, 0),
        ({"city": "Минск", "ownership_type": "private"}, 3),
    ],
)
def test_every_university_filter_and_combined_filters(
    catalog_client, params: dict[str, str], expected_total: int
) -> None:  # type: ignore[no-untyped-def]
    client, _engine, _database = catalog_client
    response = client.get("/api/universities", params=params)
    assert response.status_code == 200
    assert response.json()["pagination"]["total_items"] == expected_total


def test_university_details_sources_and_missing_program_coverage_are_honest(catalog_client) -> None:  # type: ignore[no-untyped-def]
    client, _engine, _database = catalog_client
    university = client.get("/api/universities/brsu")
    assert university.status_code == 200
    payload = university.json()
    assert payload["program_count"] == payload["offering_count"] == 0
    assert payload["coverage"]["programs"] == "not_imported"
    assert payload["coverage"]["online_monitoring"] == "not_implemented"
    assert "не означает" in payload["coverage"]["note"]
    assert payload["sources"]
    assert payload["programs"] == []
    assert all(set(source) == {"source_type", "source_url", "checked_at"} for source in payload["sources"])
    response_text = university.text.lower()
    for forbidden in ("etag", "last_modified", "last_error", "filesystem", "telegram_bot_token"):
        assert forbidden not in response_text

    bseu = client.get("/api/universities/bseu").json()
    assert bseu["program_count"] == bseu["offering_count"] == 1
    assert bseu["coverage"]["online_monitoring"] == "available"
    assert bseu["short_name"] == "БГЭУ"
    assert bseu["city"] == bseu["region"] == "Минск"
    assert bseu["categories"] == [{"code": "economic", "label_ru": "Экономический"}]
    assert len(bseu["programs"]) == 1
    assert bseu["programs"][0]["name"] == "Экономическая информатика"
    assert bseu["programs"][0]["offerings"][0]["admission_year"] == 2026
    assert bseu["programs"][0]["offerings"][0]["study_form"] == "full_time"
    assert bseu["programs"][0]["offerings"][0]["funding_type"] == "paid"
    assert client.get("/api/universities/unknown").status_code == 404

    missing_programs = client.get("/api/universities/brsu/programs")
    assert missing_programs.status_code == 200
    assert missing_programs.json()["items"] == []
    assert "пустой список не означает" in missing_programs.json()["coverage"]["note"]

    imported_programs = client.get("/api/universities/bseu/programs")
    assert imported_programs.status_code == 200
    assert imported_programs.json()["items"][0]["id"] == 1
    assert client.get("/api/universities/unknown/programs").status_code == 404


def test_university_detail_nested_collections_are_deterministic(catalog_client) -> None:  # type: ignore[no-untyped-def]
    client, engine, _database = catalog_client
    checked_at = datetime(2026, 7, 12, 18, 14, 28, tzinfo=UTC)
    with Session(engine) as session, session.begin():
        university = session.scalar(select(University).where(University.code == "bseu"))
        assert university is not None
        alpha = Program(
            university_id=university.id,
            code="test-alpha",
            slug="test-alpha",
            name="Альфа — тест порядка",
            qualification=None,
            faculty_name=None,
            education_level=None,
            duration_years=None,
            description=None,
            admission_subjects_json=None,
            career_fields_json=None,
            category_tags_json=None,
            official_url="https://example.invalid/program-alpha",
            active=True,
            source_checked_at=checked_at,
            verified_at=None,
        )
        omega = Program(
            university_id=university.id,
            code="test-omega",
            slug="test-omega",
            name="Янтарь — тест порядка",
            qualification=None,
            faculty_name=None,
            education_level=None,
            duration_years=None,
            description=None,
            admission_subjects_json=None,
            career_fields_json=None,
            category_tags_json=None,
            official_url="https://example.invalid/program-omega",
            active=True,
            source_checked_at=checked_at,
            verified_at=None,
        )
        session.add_all([omega, alpha])
        session.flush()
        session.add_all([
            ProgramOffering(
                program_id=alpha.id,
                admission_year=2027,
                study_form=StudyForm.PART_TIME,
                funding_type=FundingType.PAID,
                places=None,
                application_deadline=None,
                monitoring_supported=False,
                monitoring_status=MonitoringStatus.REFERENCE_ONLY,
                official_url="https://example.invalid/offering-2027",
                source_url="https://example.invalid/offering-2027",
                source_checked_at=checked_at,
                verified_at=None,
            ),
            ProgramOffering(
                program_id=alpha.id,
                admission_year=2025,
                study_form=StudyForm.FULL_TIME,
                funding_type=FundingType.BUDGET,
                places=None,
                application_deadline=None,
                monitoring_supported=False,
                monitoring_status=MonitoringStatus.REFERENCE_ONLY,
                official_url="https://example.invalid/offering-2025",
                source_url="https://example.invalid/offering-2025",
                source_checked_at=checked_at,
                verified_at=None,
            ),
        ])

    first = client.get("/api/universities/bseu")
    second = client.get("/api/universities/bseu")
    assert first.status_code == second.status_code == 200
    first_programs = first.json()["programs"]
    second_programs = second.json()["programs"]
    assert first_programs == second_programs
    assert [item["name"] for item in first_programs] == [
        "Альфа — тест порядка",
        "Экономическая информатика",
        "Янтарь — тест порядка",
    ]
    assert [item["admission_year"] for item in first_programs[0]["offerings"]] == [2025, 2027]


def test_university_detail_is_read_only_and_performs_no_external_request(
    catalog_client, monkeypatch: pytest.MonkeyPatch
) -> None:  # type: ignore[no-untyped-def]
    client, engine, _database = catalog_client
    tracked_tables = (
        "universities",
        "programs",
        "program_offerings",
        "data_sources",
        "admission_snapshots",
        "scraper_runs",
        "notification_logs",
    )

    def counts() -> dict[str, int]:
        with engine.connect() as connection:
            return {
                table: int(connection.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar_one())
                for table in tracked_tables
            }

    def block_network(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("university detail must not open network connections")

    monkeypatch.setattr(socket, "create_connection", block_network)
    writes: list[str] = []

    def capture(_connection, _cursor, statement, _parameters, _context, _executemany) -> None:  # type: ignore[no-untyped-def]
        if statement.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "REPLACE")):
            writes.append(statement)

    before = counts()
    event.listen(engine, "before_cursor_execute", capture)
    try:
        response = client.get("/api/universities/bseu")
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert response.status_code == 200
    assert writes == []
    assert counts() == before


@pytest.mark.parametrize(
    "params",
    [
        {"q": "экономическая информатика"},
        {"university": "bseu"},
        {"city": "минск"},
        {"admission_year": "2026"},
        {"study_form": "full_time"},
        {"funding_type": "paid"},
        {"monitoring_status": "online"},
        {"has_offerings": "true"},
    ],
)
def test_program_search_and_every_supported_filter(catalog_client, params: dict[str, str]) -> None:  # type: ignore[no-untyped-def]
    client, _engine, _database = catalog_client
    response = client.get("/api/programs", params=params)
    assert response.status_code == 200
    assert response.json()["pagination"]["total_items"] == 1
    assert response.json()["items"][0]["id"] == 1


def test_program_list_details_coverage_and_validation(catalog_client) -> None:  # type: ignore[no-untyped-def]
    client, _engine, _database = catalog_client
    response = client.get("/api/programs")
    assert response.status_code == 200
    payload = response.json()
    assert payload["coverage"]["universities_total"] == 47
    assert payload["coverage"]["universities_with_imported_programs"] == 1
    assert payload["coverage"]["programs_total"] == payload["coverage"]["offerings_total"] == 1
    assert payload["coverage"]["state"] == "partial"

    detail = client.get("/api/programs/1")
    assert detail.status_code == 200
    assert detail.json()["university"]["code"] == "bseu"
    assert detail.json()["offerings"][0]["admission_year"] == 2026
    assert "history" not in detail.json()
    assert client.get("/api/programs/999999").status_code == 404

    assert client.get("/api/programs?admission_year=2025").json()["items"] == []
    assert client.get("/api/programs?has_offerings=false").json()["items"] == []
    assert client.get("/api/programs?page=99").json()["items"] == []
    for query in ("page=0", "page_size=101", "sort=unsafe", "study_form=unsafe"):
        assert client.get(f"/api/programs?{query}").status_code == 422


def test_nested_program_detail_uses_slug_ownership_and_deterministic_offerings(
    catalog_client,
) -> None:  # type: ignore[no-untyped-def]
    client, engine, _database = catalog_client
    checked_at = datetime(2026, 7, 12, 18, 14, 28, tzinfo=UTC)
    with Session(engine) as session, session.begin():
        bseu_program = session.scalar(select(Program).where(Program.id == 1))
        brsu = session.scalar(select(University).where(University.code == "brsu"))
        assert bseu_program is not None
        assert brsu is not None
        session.add_all([
            ProgramOffering(
                program_id=bseu_program.id,
                admission_year=2027,
                study_form=StudyForm.PART_TIME,
                funding_type=FundingType.PAID,
                places=None,
                application_deadline=None,
                monitoring_supported=False,
                monitoring_status=MonitoringStatus.REFERENCE_ONLY,
                official_url="https://example.invalid/offering-2027",
                source_url="https://example.invalid/offering-2027",
                source_checked_at=checked_at,
                verified_at=None,
            ),
            ProgramOffering(
                program_id=bseu_program.id,
                admission_year=2025,
                study_form=StudyForm.FULL_TIME,
                funding_type=FundingType.BUDGET,
                places=None,
                application_deadline=None,
                monitoring_supported=False,
                monitoring_status=MonitoringStatus.REFERENCE_ONLY,
                official_url="https://example.invalid/offering-2025",
                source_url="https://example.invalid/offering-2025",
                source_checked_at=checked_at,
                verified_at=None,
            ),
            Program(
                university_id=brsu.id,
                code=None,
                slug="test-program-without-offerings",
                name="Тестовая программа без импортированных наборов",
                qualification=None,
                faculty_name=None,
                education_level=None,
                duration_years=None,
                description=None,
                admission_subjects_json=None,
                career_fields_json=None,
                category_tags_json=None,
                official_url="https://example.invalid/program-without-offerings",
                active=True,
                source_checked_at=checked_at,
                verified_at=None,
            ),
        ])
        program_slug = bseu_program.slug

    response = client.get(f"/api/universities/bseu/programs/{program_slug}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["slug"] == program_slug
    assert payload["university"] == {"id": 1, "code": "bseu", "slug": "bseu", "short_name": "БГЭУ"}
    assert payload["offering_count"] == 3
    assert [item["admission_year"] for item in payload["offerings"]] == [2025, 2026, 2027]
    assert "history" not in payload

    empty = client.get("/api/universities/brsu/programs/test-program-without-offerings")
    assert empty.status_code == 200
    assert empty.json()["offering_count"] == 0
    assert empty.json()["offerings"] == []

    assert client.get(f"/api/universities/brsu/programs/{program_slug}").status_code == 404
    assert client.get(f"/api/universities/unknown/programs/{program_slug}").status_code == 404
    assert client.get("/api/universities/bseu/programs/unknown").status_code == 404


def test_nested_program_detail_is_read_only_and_performs_no_external_request(
    catalog_client, monkeypatch: pytest.MonkeyPatch
) -> None:  # type: ignore[no-untyped-def]
    client, engine, _database = catalog_client

    def block_network(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("program detail must not open network connections")

    monkeypatch.setattr(socket, "create_connection", block_network)
    writes: list[str] = []

    def capture(_connection, _cursor, statement, _parameters, _context, _executemany) -> None:  # type: ignore[no-untyped-def]
        if statement.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "REPLACE")):
            writes.append(statement)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        response = client.get("/api/universities/bseu/programs/economic-informatics")
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert response.status_code == 200
    assert writes == []


def test_catalog_metadata_and_health_use_database_values_without_internal_details(catalog_client) -> None:  # type: ignore[no-untyped-def]
    client, _engine, _database = catalog_client
    meta = client.get("/api/catalog/meta")
    assert meta.status_code == 200
    payload = meta.json()
    assert payload["counts"] == {
        "universities": 47,
        "programs": 1,
        "offerings": 1,
        "universities_with_programs": 1,
        "universities_with_admissions_url": 33,
    }
    assert len(payload["cities"]) == 11
    assert payload["pagination"] == {"default_page_size": 20, "maximum_page_size": 100}
    assert payload["admission_years"] == [2026]
    assert payload["study_forms"] == ["full_time"]
    assert payload["funding_types"] == ["paid"]

    health = client.get("/api/catalog/health")
    assert health.status_code == 200
    assert health.json() == {
        "status": "healthy",
        "database_reachable": True,
        "alembic_at_head": True,
        "counts": payload["counts"],
        "bseu_identity_exists": True,
        "duplicate_identities_absent": True,
    }
    health_text = health.text.lower()
    for forbidden in ("path", "trace", "error", "etag", "last_modified", "secret"):
        assert forbidden not in health_text


def test_catalog_openapi_contains_public_contract(catalog_client) -> None:  # type: ignore[no-untyped-def]
    client, _engine, _database = catalog_client
    schema = client.get("/openapi.json")
    assert schema.status_code == 200
    paths = schema.json()["paths"]
    for path in (
        "/api/universities",
        "/api/universities/{slug}",
        "/api/universities/{slug}/programs",
        "/api/universities/{university_slug}/programs/{program_slug}",
        "/api/programs",
        "/api/programs/{program_id}",
        "/api/catalog/meta",
        "/api/catalog/health",
    ):
        assert path in paths
    university_schema = schema.json()["components"]["schemas"]["UniversityResponse"]
    assert university_schema["properties"]["programs"]["items"]["$ref"].endswith(
        "/ProgramResponse"
    )
    assert "programs" in university_schema["required"]
    nested_program_schema = paths["/api/universities/{university_slug}/programs/{program_slug}"]["get"]
    assert nested_program_schema["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/ProgramResponse"
    )


def test_primary_list_and_detail_queries_are_bounded(catalog_client) -> None:  # type: ignore[no-untyped-def]
    client, engine, _database = catalog_client

    def count_queries(path: str) -> int:
        statements: list[str] = []

        def capture(_connection, _cursor, statement, _parameters, _context, _executemany) -> None:  # type: ignore[no-untyped-def]
            if statement.lstrip().upper().startswith("SELECT"):
                statements.append(statement)

        event.listen(engine, "before_cursor_execute", capture)
        try:
            assert client.get(path).status_code == 200
        finally:
            event.remove(engine, "before_cursor_execute", capture)
        return len(statements)

    assert count_queries("/api/universities") <= 3
    assert count_queries("/api/universities/bseu") <= 4
    assert count_queries("/api/programs") <= 4
    assert count_queries("/api/programs/1") <= 3
    assert count_queries("/api/universities/bseu/programs/economic-informatics") <= 4


def test_importing_catalog_router_and_creating_test_app_have_no_runtime_side_effects(
    tmp_path: Path,
) -> None:
    isolated_database = tmp_path / "router-import-must-not-create.db"
    main_database = Path(__file__).resolve().parents[1] / "data" / "admission.db"
    before = main_database.stat() if main_database.exists() else None
    code = f"""
import sys
from pathlib import Path
target = Path({str(isolated_database)!r})
from fastapi import FastAPI
from app.catalog_api import router
app = FastAPI()
app.include_router(router)
app.openapi()
assert 'app.main' not in sys.modules
assert 'apscheduler' not in sys.modules
assert not target.exists()
"""
    environment = os.environ.copy()
    environment.update(
        {
            "DATABASE_URL": sqlite_url(isolated_database),
            "TELEGRAM_ENABLED": "false",
            "MANUAL_REFRESH_TOKEN": "catalog-test-only",
        }
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert not isolated_database.exists()
    after = main_database.stat() if main_database.exists() else None
    assert before == after
