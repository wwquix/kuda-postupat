from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from alembic import command
from app.bseu_mapping import verify_bseu_backfill
from app.schema import make_alembic_config

CORE = "0002_core_catalog_schema"
HEAD = "0006_telegram_watch_notifications"
LEGACY_COLUMNS = {
    "specialties": "id, normalized_name, display_name, study_form, funding_type, source_url, active",
    "admission_snapshots": (
        "id, specialty_id, fetched_at, source_updated_at, admission_plan, applications_total, competition, "
        "estimated_cutoff_min, estimated_cutoff_max, user_score, estimated_user_position, user_status, "
        "distribution_json, raw_data_hash"
    ),
    "scraper_runs": (
        "id, started_at, finished_at, status, http_status, error_type, error_message, rows_found, content_hash"
    ),
    "notification_logs": "id, fingerprint, sent_at, message",
    "http_cache_state": "url, etag, last_modified, checked_at",
}


def sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.resolve().as_posix()}"


def legacy_rows(path: Path) -> dict[str, list[tuple[object, ...]]]:
    with sqlite3.connect(path) as connection:
        return {
            table: list(
                connection.execute(f'SELECT {columns} FROM "{table}" ORDER BY rowid')
            )
            for table, columns in LEGACY_COLUMNS.items()
        }


def seed_core_database(path: Path) -> dict[str, list[tuple[object, ...]]]:
    command.upgrade(make_alembic_config(sqlite_url(path)), CORE)
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(
            """
            INSERT INTO specialties
                (id, normalized_name, display_name, study_form, funding_type, source_url, active)
            VALUES
                (17, 'экономическая информатика', 'Экономическая информатика',
                 'дневная', 'платная', 'https://bseu.by/abiturient/', 1)
            """
        )
        snapshots = (
            (
                71,
                "2026-07-12 12:13:54.573894",
                "2026-07-12 15:00:00.000000",
                11,
                "f80613b949ae2480b79cb375a9463efe11ea28e43ac015a912968b1a8a77e5f1",
            ),
            (
                72,
                "2026-07-13 12:09:34.510968",
                "2026-07-13 15:00:00.000000",
                25,
                "2cd36ba0a73f8ed76b44057ab097caaeb2d80dc7825a86d2b04a1222437defc0",
            ),
        )
        for snapshot_id, fetched_at, source_updated_at, applications, raw_hash in snapshots:
            connection.execute(
                """
                INSERT INTO admission_snapshots (
                    id, specialty_id, fetched_at, source_updated_at, admission_plan,
                    applications_total, competition, estimated_cutoff_min,
                    estimated_cutoff_max, user_score, estimated_user_position,
                    user_status, distribution_json, raw_data_hash
                ) VALUES (?, 17, ?, ?, 60, ?, ?, NULL, NULL, 276, 1,
                          'Уверенно проходит', '{"270-279": 11}', ?)
                """,
                (snapshot_id, fetched_at, source_updated_at, applications, applications / 60, raw_hash),
            )
        connection.execute(
            """
            INSERT INTO scraper_runs (
                id, started_at, finished_at, status, http_status, error_type,
                error_message, rows_found, content_hash
            ) VALUES (91, '2026-07-13 12:09:33', '2026-07-13 12:09:34',
                      'success', 200, NULL, NULL, 77, 'content-hash')
            """
        )
        connection.execute(
            """
            INSERT INTO notification_logs (id, fingerprint, sent_at, message)
            VALUES (31, 'fingerprint', '2026-07-13 12:10:00', 'legacy message')
            """
        )
        connection.execute(
            """
            INSERT INTO http_cache_state (url, etag, last_modified, checked_at)
            VALUES ('https://bseu.by/abiturient/xml/1.xml', 'etag-value',
                    'Mon, 13 Jul 2026 15:00:00 GMT', '2026-07-13 12:09:34')
            """
        )
        connection.commit()
    return legacy_rows(path)


def catalog_rows(path: Path) -> dict[str, list[tuple[object, ...]]]:
    tables = (
        "universities",
        "university_categories",
        "university_category_links",
        "programs",
        "program_offerings",
        "data_sources",
        "legacy_specialty_mappings",
    )
    with sqlite3.connect(path) as connection:
        return {
            table: list(connection.execute(f'SELECT * FROM "{table}" ORDER BY rowid'))
            for table in tables
        }


def load_migration_module():  # type: ignore[no-untyped-def]
    path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0003_backfill_bseu_catalog.py"
    spec = importlib.util.spec_from_file_location("migration_0003", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_backfill_links_catalog_and_preserves_every_legacy_field(tmp_path: Path) -> None:
    database = tmp_path / "legacy-core.db"
    expected_legacy = seed_core_database(database)

    command.upgrade(make_alembic_config(sqlite_url(database)), "head")

    assert legacy_rows(database) == expected_legacy
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == HEAD
        assert connection.execute("SELECT code, slug FROM universities").fetchall() == [("bseu", "bseu")]
        assert connection.execute("SELECT code, label_ru FROM university_categories").fetchall() == [
            ("economic", "Экономика")
        ]
        assert connection.execute("SELECT code, name FROM programs").fetchall() == [
            ("6-05-0311-05", "Экономическая информатика")
        ]
        offering_id = connection.execute(
            "SELECT id FROM program_offerings WHERE admission_year=2026 AND study_form='full_time' "
            "AND funding_type='paid' AND places=60"
        ).fetchone()[0]
        data_source_id = connection.execute(
            "SELECT id FROM data_sources WHERE source_type='admission_xml'"
        ).fetchone()[0]
        assert connection.execute(
            "SELECT legacy_specialty_id, program_offering_id FROM legacy_specialty_mappings"
        ).fetchall() == [(17, offering_id)]
        assert connection.execute(
            "SELECT DISTINCT program_offering_id FROM admission_snapshots"
        ).fetchall() == [(offering_id,)]
        assert connection.execute("SELECT DISTINCT data_source_id FROM scraper_runs").fetchall() == [
            (data_source_id,)
        ]
        assert connection.execute("SELECT etag FROM data_sources").fetchone()[0] == "etag-value"
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert list(connection.execute("PRAGMA foreign_key_check")) == []
    engine = create_engine(sqlite_url(database))
    with Session(engine) as session:
        result = verify_bseu_backfill(session)
    engine.dispose()
    assert result["legacy_mapping_count"] == 1
    assert result["unmapped_snapshots"] == 0
    assert result["unlinked_scraper_runs"] == 0


def test_backfill_function_is_idempotent(tmp_path: Path) -> None:
    database = tmp_path / "idempotent.db"
    seed_core_database(database)
    command.upgrade(make_alembic_config(sqlite_url(database)), "head")
    expected_catalog = catalog_rows(database)
    expected_legacy = legacy_rows(database)
    migration = load_migration_module()
    engine = create_engine(sqlite_url(database))
    with engine.begin() as connection:
        first_ids = migration.backfill_bseu(connection)
        second_ids = migration.backfill_bseu(connection)
    engine.dispose()
    assert first_ids == second_ids
    assert catalog_rows(database) == expected_catalog
    assert legacy_rows(database) == expected_legacy


def test_bseu_downgrade_preserves_legacy_rows(tmp_path: Path) -> None:
    database = tmp_path / "downgrade.db"
    expected_legacy = seed_core_database(database)
    config = make_alembic_config(sqlite_url(database))
    command.upgrade(config, "head")

    command.downgrade(config, CORE)

    assert legacy_rows(database) == expected_legacy
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == CORE
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(admission_snapshots)")
        }
        run_columns = {row[1] for row in connection.execute("PRAGMA table_info(scraper_runs)")}
        assert "program_offering_id" not in columns
        assert "data_source_id" not in run_columns
        assert connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='legacy_specialty_mappings'"
        ).fetchone()[0] == 0
        for table in (
            "universities",
            "university_categories",
            "university_category_links",
            "programs",
            "program_offerings",
            "data_sources",
        ):
            assert connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] == 0
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert list(connection.execute("PRAGMA foreign_key_check")) == []


def test_conflicting_bseu_identity_fails_before_sqlite_ddl(tmp_path: Path) -> None:
    database = tmp_path / "conflict.db"
    config = make_alembic_config(sqlite_url(database))
    command.upgrade(config, CORE)
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            INSERT INTO universities (
                code, slug, short_name, full_name, institution_kind, ownership_type,
                official_site_url, monitoring_status, active, source_url, source_checked_at
            ) VALUES (
                'bseu', 'conflicting-slug', 'БГЭУ',
                'Белорусский государственный экономический университет',
                'university', 'state', 'https://bseu.by/', 'online', 1,
                'https://official.test/registry', '2026-07-12 18:14:28'
            )
            """
        )
        connection.commit()

    with pytest.raises(RuntimeError, match="fields do not match"):
        command.upgrade(config, "head")

    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == CORE
        assert connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='legacy_specialty_mappings'"
        ).fetchone()[0] == 0
        assert "program_offering_id" not in {
            row[1] for row in connection.execute("PRAGMA table_info(admission_snapshots)")
        }
