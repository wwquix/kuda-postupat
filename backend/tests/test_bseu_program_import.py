from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from alembic import command
from app import bseu_program_import as importer
from app.bseu_program_import import (
    AUDIT_PATH,
    AUDIT_SCHEMA_PATH,
    EXPECTED_CONFIRMED,
    EXPECTED_NEEDS_REVIEW,
    EXPECTED_PROGRAMS,
    run_bseu_program_import,
)
from app.catalog_import_service import CatalogConflictError, CatalogValidationError
from app.catalog_models import Program, ProgramOffering, University
from app.cli import _parser
from app.schema import make_alembic_config

CORE_REVISION = "0002_core_catalog_schema"


def _sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.resolve().as_posix()}"


def _upgrade(path: Path, revision: str = "head") -> None:
    command.upgrade(make_alembic_config(_sqlite_url(path)), revision)


def _insert_legacy_monitoring_fixture(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        specialty_id = connection.execute(
            """
            INSERT INTO specialties (
                normalized_name, display_name, study_form, funding_type, source_url, active
            ) VALUES (?, ?, ?, ?, ?, 1)
            """,
            (
                "экономическая информатика",
                "Экономическая информатика",
                "дневная",
                "платная",
                "https://bseu.by/abiturient/xml/1.xml",
            ),
        ).lastrowid
        connection.execute(
            """
            INSERT INTO admission_snapshots (
                specialty_id, fetched_at, source_updated_at, admission_plan,
                applications_total, competition, estimated_cutoff_min,
                estimated_cutoff_max, user_score, estimated_user_position,
                user_status, distribution_json, raw_data_hash
            ) VALUES (?, ?, ?, 60, 72, 1.2, 270, 280, 276, 42, ?, ?, ?)
            """,
            (
                specialty_id,
                "2026-07-16 18:01:00",
                "2026-07-16 18:00:00",
                "borderline",
                "{}",
                "a" * 64,
            ),
        )


def _seed_preservation_relationships(path: Path) -> dict[str, int]:
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        program_id = connection.execute("SELECT id FROM programs WHERE slug='economic-informatics'").fetchone()[0]
        offering_id = connection.execute(
            """
            SELECT id FROM program_offerings
            WHERE program_id=? AND admission_year=2026
              AND study_form='full_time' AND funding_type='paid'
            """,
            (program_id,),
        ).fetchone()[0]
        snapshot_id = connection.execute("SELECT id FROM admission_snapshots").fetchone()[0]
        profile_id = connection.execute(
            "INSERT INTO anonymous_profiles (token_hash, personal_score) VALUES (?, 276)",
            ("b" * 64,),
        ).lastrowid
        connection.execute(
            "INSERT INTO saved_programs (profile_id, program_id) VALUES (?, ?)",
            (profile_id, program_id),
        )
        watch_id = connection.execute(
            """
            INSERT INTO program_watches (
                profile_id, program_id, enabled, last_evaluated_snapshot_id
            ) VALUES (?, ?, 1, ?)
            """,
            (profile_id, program_id, snapshot_id),
        ).lastrowid
        event_id = connection.execute(
            """
            INSERT INTO program_watch_events (
                watch_id, source_snapshot_id, event_kind, previous_value, current_value
            ) VALUES (?, ?, 'applications_total_changed', '70', '72')
            """,
            (watch_id, snapshot_id),
        ).lastrowid
        link_id = connection.execute(
            "INSERT INTO telegram_profile_links (profile_id, telegram_chat_id) VALUES (?, ?)",
            (profile_id, "123456"),
        ).lastrowid
        delivery_id = connection.execute(
            """
            INSERT INTO telegram_watch_deliveries (
                watch_event_id, profile_link_id, state, attempt_count,
                last_attempt_at, confirmed_at
            ) VALUES (?, ?, 'confirmed', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (event_id, link_id),
        ).lastrowid
        connection.execute(
            "INSERT INTO notification_logs (fingerprint, sent_at, message) VALUES (?, CURRENT_TIMESTAMP, ?)",
            ("c" * 64, "preserved owner notification"),
        )
        return {
            "program_id": program_id,
            "offering_id": offering_id,
            "snapshot_id": snapshot_id,
            "profile_id": profile_id,
            "watch_id": watch_id,
            "event_id": event_id,
            "link_id": link_id,
            "delivery_id": delivery_id,
        }


@pytest.fixture
def fresh_database(tmp_path: Path) -> Path:
    database = tmp_path / "fresh.db"
    _upgrade(database)
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("DELETE FROM legacy_specialty_mappings")
        connection.execute("DELETE FROM program_offerings")
        connection.execute("DELETE FROM programs")
    return database


@pytest.fixture
def production_database(tmp_path: Path) -> tuple[Path, dict[str, int]]:
    database = tmp_path / "production-style.db"
    _upgrade(database, CORE_REVISION)
    _insert_legacy_monitoring_fixture(database)
    _upgrade(database)
    return database, _seed_preservation_relationships(database)


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _database_dump(path: Path) -> tuple[str, ...]:
    with sqlite3.connect(path) as connection:
        return tuple(connection.iterdump())


def _counts(path: Path) -> tuple[int, int]:
    with sqlite3.connect(path) as connection:
        return (
            connection.execute("SELECT COUNT(*) FROM programs").fetchone()[0],
            connection.execute("SELECT COUNT(*) FROM program_offerings").fetchone()[0],
        )


def test_json_schema_validation_happens_before_database_access(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bad_audit = tmp_path / "bad-audit.json"
    data = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    del data["source"]["structure"]
    bad_audit.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def forbidden_engine(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("database must not be opened before JSON/schema validation")

    monkeypatch.setattr(importer, "_database_engine", forbidden_engine)
    with pytest.raises(CatalogValidationError, match="JSON Schema validation failed"):
        run_bseu_program_import(
            tmp_path / "must-not-be-opened.db",
            audit_path=bad_audit,
            schema_path=AUDIT_SCHEMA_PATH,
        )


def test_dry_run_is_default_and_performs_zero_sqlite_writes(fresh_database: Path) -> None:
    before_digest = _file_digest(fresh_database)
    before_sidecars = sorted(path.name for path in fresh_database.parent.iterdir())

    summary = run_bseu_program_import(fresh_database)

    assert summary.as_dict() == {
        "confirmed_candidates": EXPECTED_CONFIRMED,
        "needs_review_skipped": EXPECTED_NEEDS_REVIEW,
        "program_identities_expected": EXPECTED_PROGRAMS,
        "programs_created": 17,
        "programs_reused": 0,
        "offerings_created": 57,
        "offerings_reused": 0,
        "conflicts": 0,
        "writes_applied": False,
    }
    assert _file_digest(fresh_database) == before_digest
    assert sorted(path.name for path in fresh_database.parent.iterdir()) == before_sidecars
    assert _counts(fresh_database) == (0, 0)


def test_fresh_database_creates_exact_scope_and_keeps_monitoring_reference_only(
    fresh_database: Path,
) -> None:
    with sqlite3.connect(fresh_database) as connection:
        source_count = connection.execute("SELECT COUNT(*) FROM data_sources").fetchone()[0]

    summary = run_bseu_program_import(fresh_database, apply=True)

    assert (summary.programs_created, summary.offerings_created) == (17, 57)
    assert (summary.programs_reused, summary.offerings_reused) == (0, 0)
    assert summary.writes_applied is True
    with sqlite3.connect(fresh_database) as connection:
        assert _counts(fresh_database) == (17, 57)
        assert connection.execute("SELECT COUNT(*) FROM data_sources").fetchone()[0] == source_count
        assert (
            connection.execute("SELECT COUNT(*) FROM program_offerings WHERE monitoring_supported != 0").fetchone()[0]
            == 0
        )
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM program_offerings WHERE monitoring_status != 'reference_only'"
            ).fetchone()[0]
            == 0
        )
        assert (
            connection.execute(
                """
                SELECT COUNT(*) FROM programs
                WHERE name IN (
                    'Бухгалтерский учет, анализ и аудит',
                    'Правоведение',
                    'Экономика и управление'
                )
                """
            ).fetchone()[0]
            == 0
        )


def test_production_fixture_reuses_ids_and_preserves_all_relationships(
    production_database: tuple[Path, dict[str, int]],
) -> None:
    database, ids = production_database
    preserved_queries = {
        "mapping": "SELECT * FROM legacy_specialty_mappings",
        "snapshot": "SELECT * FROM admission_snapshots",
        "favorite": "SELECT * FROM saved_programs",
        "watch": "SELECT * FROM program_watches",
        "event": "SELECT * FROM program_watch_events",
        "link": "SELECT * FROM telegram_profile_links",
        "delivery": "SELECT * FROM telegram_watch_deliveries",
        "owner_notification": "SELECT * FROM notification_logs",
        "source": "SELECT * FROM data_sources",
    }
    with sqlite3.connect(database) as connection:
        before = {name: connection.execute(query).fetchall() for name, query in preserved_queries.items()}

    summary = run_bseu_program_import(database, apply=True)

    assert (summary.programs_created, summary.programs_reused) == (16, 1)
    assert (summary.offerings_created, summary.offerings_reused) == (56, 1)
    with sqlite3.connect(database) as connection:
        assert (
            connection.execute("SELECT id FROM programs WHERE slug='economic-informatics'").fetchone()[0]
            == ids["program_id"]
        )
        assert (
            connection.execute(
                """
            SELECT id FROM program_offerings
            WHERE program_id=? AND admission_year=2026
              AND study_form='full_time' AND funding_type='paid'
            """,
                (ids["program_id"],),
            ).fetchone()[0]
            == ids["offering_id"]
        )
        after = {name: connection.execute(query).fetchall() for name, query in preserved_queries.items()}
    assert after == before


def test_second_apply_is_fully_idempotent(
    production_database: tuple[Path, dict[str, int]],
) -> None:
    database, _ = production_database
    first = run_bseu_program_import(database, apply=True)
    before_second = _database_dump(database)

    second = run_bseu_program_import(database, apply=True)

    assert (first.programs_created, first.offerings_created) == (16, 56)
    assert second.as_dict() == {
        "confirmed_candidates": 57,
        "needs_review_skipped": 20,
        "program_identities_expected": 17,
        "programs_created": 0,
        "programs_reused": 17,
        "offerings_created": 0,
        "offerings_reused": 57,
        "conflicts": 0,
        "writes_applied": True,
    }
    assert _database_dump(database) == before_second


def test_ambiguous_existing_economic_informatics_identity_fails_closed(
    production_database: tuple[Path, dict[str, int]],
) -> None:
    database, ids = production_database
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE programs SET code=NULL WHERE id=?", (ids["program_id"],))
        connection.execute(
            """
            INSERT INTO programs (
                university_id, code, slug, name, qualification, faculty_name,
                official_url, active, source_checked_at
            )
            SELECT university_id, ?, 'economic-informatics-conflict', name, qualification,
                   faculty_name, official_url, active, source_checked_at
            FROM programs WHERE id=?
            """,
            (importer.ECONOMIC_INFORMATICS_CODE, ids["program_id"]),
        )
    before = _database_dump(database)

    with pytest.raises(CatalogConflictError, match="code and slug"):
        run_bseu_program_import(database, apply=True)

    assert _database_dump(database) == before


def test_conflicting_canonical_identity_rolls_back_complete_import(fresh_database: Path) -> None:
    audit = importer.load_bseu_program_audit()
    conflicting = next(program for program in audit.programs if program.code is None)
    engine = create_engine(_sqlite_url(fresh_database))
    try:
        with Session(engine) as session, session.begin():
            university = session.scalar(select(University).where(University.code == "bseu"))
            assert university is not None
            session.add(
                Program(
                    university_id=university.id,
                    code=None,
                    slug=conflicting.slug,
                    name="Конфликтующее название",
                    qualification=None,
                    faculty_name=conflicting.faculty_name,
                    education_level=None,
                    duration_years=None,
                    description=None,
                    admission_subjects_json=None,
                    career_fields_json=None,
                    category_tags_json=None,
                    official_url=conflicting.official_url,
                    active=True,
                    source_checked_at=conflicting.source_checked_at,
                    verified_at=None,
                )
            )
    finally:
        engine.dispose()
    before = _database_dump(fresh_database)

    with pytest.raises(CatalogConflictError, match="conflicting name"):
        run_bseu_program_import(fresh_database, apply=True)

    assert _database_dump(fresh_database) == before
    assert _counts(fresh_database) == (1, 0)


def test_injected_mid_import_failure_rolls_back_every_row(
    fresh_database: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = _database_dump(fresh_database)
    real_add = importer._add_offering
    calls = 0

    def fail_midway(session: Session, offering: ProgramOffering) -> None:
        nonlocal calls
        calls += 1
        if calls == 12:
            raise RuntimeError("injected failure")
        real_add(session, offering)

    monkeypatch.setattr(importer, "_add_offering", fail_midway)
    with pytest.raises(RuntimeError, match="injected failure"):
        run_bseu_program_import(fresh_database, apply=True)

    assert calls == 12
    assert _database_dump(fresh_database) == before
    assert _counts(fresh_database) == (0, 0)


def test_integrity_and_foreign_keys_after_production_import(
    production_database: tuple[Path, dict[str, int]],
) -> None:
    database, _ = production_database
    run_bseu_program_import(database, apply=True)

    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert (
            connection.execute("SELECT COUNT(*) FROM program_offerings WHERE monitoring_status='online'").fetchone()[0]
            == 1
        )
        assert (
            connection.execute("SELECT COUNT(*) FROM program_offerings WHERE monitoring_supported=1").fetchone()[0] == 1
        )
        assert connection.execute("SELECT COUNT(*) FROM data_sources").fetchone()[0] == 1


def test_cli_database_argument_is_required_and_apply_is_opt_in() -> None:
    with pytest.raises(SystemExit):
        _parser().parse_args(["import-bseu-programs"])
    args = _parser().parse_args(["import-bseu-programs", "--database", "fixture.db"])
    assert args.database == Path("fixture.db")
    assert args.apply is False
