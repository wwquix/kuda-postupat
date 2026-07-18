from __future__ import annotations

import socket
import sqlite3
from pathlib import Path

import pytest

from alembic import command
from alembic.script import ScriptDirectory
from app.schema import make_alembic_config

PREVIOUS_HEAD = "0006_telegram_watch_notifications"
HEAD = "0007_admission_requirements_schema"
NEW_TABLES = {
    "admission_subjects",
    "admission_requirement_sources",
    "program_admission_requirement_sets",
    "admission_requirement_subject_groups",
    "admission_requirement_subject_options",
    "admission_requirement_evidence_links",
}


@pytest.fixture(autouse=True)
def block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("admission requirement migration tests must remain offline")

    monkeypatch.setattr(socket, "create_connection", refuse_network)
    monkeypatch.setattr(socket.socket, "connect", refuse_network)


def _sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.as_posix()}"


def _revision(path: Path) -> str | None:
    with sqlite3.connect(path) as connection:
        row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
    return row[0] if row else None


def _table_names(path: Path) -> set[str]:
    with sqlite3.connect(path) as connection:
        return {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        }


def _seed_linked_legacy_rows(path: Path) -> dict[str, list[tuple[object, ...]]]:
    with sqlite3.connect(path) as connection:
        program_id, offering_id = connection.execute(
            "SELECT p.id, po.id FROM programs AS p "
            "JOIN program_offerings AS po ON po.program_id = p.id "
            "WHERE p.slug = 'economic-informatics' AND po.funding_type = 'paid'"
        ).fetchone()
        connection.execute(
            "INSERT INTO specialties "
            "(id, normalized_name, display_name, study_form, funding_type, source_url, active) "
            "VALUES (91, 'экономическая информатика', 'Экономическая информатика', "
            "'дневная', 'платная', 'https://bseu.by/', 1)"
        )
        connection.execute(
            "INSERT INTO admission_snapshots "
            "(id, specialty_id, fetched_at, source_updated_at, admission_plan, applications_total, competition, "
            "estimated_cutoff_min, estimated_cutoff_max, user_score, estimated_user_position, user_status, "
            "distribution_json, raw_data_hash, program_offering_id) "
            "VALUES (92, 91, '2026-07-18 12:00:00', NULL, 60, 12, 0.2, NULL, NULL, 276, 5, "
            "'Уверенно проходит', '{\"270-279\": 12}', 'migration-test-hash', ?) ",
            (offering_id,),
        )
        connection.execute(
            "INSERT INTO legacy_specialty_mappings "
            "(legacy_specialty_id, program_id, program_offering_id, mapping_version, mapped_at, verified_at, notes) "
            "VALUES (91, ?, ?, 1, '2026-07-18 12:00:00', NULL, 'migration test')",
            (program_id, offering_id),
        )
        connection.commit()
        return {
            table: list(connection.execute(f'SELECT * FROM "{table}" ORDER BY 1'))
            for table in (
                "universities",
                "programs",
                "program_offerings",
                "legacy_specialty_mappings",
                "admission_snapshots",
            )
        }


def test_single_head_and_empty_upgrade_downgrade_reupgrade_cycle(tmp_path: Path) -> None:
    config = make_alembic_config()
    script = ScriptDirectory.from_config(config)
    assert script.get_heads() == [HEAD]

    database = tmp_path / "admission-requirements-cycle.db"
    config = make_alembic_config(_sqlite_url(database))
    command.upgrade(config, PREVIOUS_HEAD)
    previous_tables = _table_names(database)
    preserved_rows = _seed_linked_legacy_rows(database)

    command.upgrade(config, HEAD)

    assert _revision(database) == HEAD
    assert _table_names(database) == previous_tables | NEW_TABLES
    with sqlite3.connect(database) as connection:
        for table in NEW_TABLES:
            assert connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] == 0
        for table, expected in preserved_rows.items():
            assert list(connection.execute(f'SELECT * FROM "{table}" ORDER BY 1')) == expected
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert list(connection.execute("PRAGMA foreign_key_check")) == []

    command.downgrade(config, PREVIOUS_HEAD)

    assert _revision(database) == PREVIOUS_HEAD
    assert _table_names(database) == previous_tables
    with sqlite3.connect(database) as connection:
        for table, expected in preserved_rows.items():
            assert list(connection.execute(f'SELECT * FROM "{table}" ORDER BY 1')) == expected
        assert list(connection.execute("PRAGMA foreign_key_check")) == []

    command.upgrade(config, HEAD)
    assert _revision(database) == HEAD
    assert NEW_TABLES <= _table_names(database)
    with sqlite3.connect(database) as connection:
        assert all(
            connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] == 0
            for table in NEW_TABLES
        )
        assert list(connection.execute("PRAGMA foreign_key_check")) == []


def test_downgrade_refuses_to_discard_requirement_data(tmp_path: Path) -> None:
    database = tmp_path / "admission-requirements-nonempty.db"
    config = make_alembic_config(_sqlite_url(database))
    command.upgrade(config, HEAD)
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(
            "INSERT INTO admission_subjects (normalized_key, official_label_ru) "
            "VALUES ('mathematics', 'Математика')"
        )
        connection.commit()

    with pytest.raises(RuntimeError, match="Refusing to downgrade.*admission_subjects"):
        command.downgrade(config, PREVIOUS_HEAD)

    assert _revision(database) == HEAD
    assert NEW_TABLES <= _table_names(database)
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM admission_subjects").fetchone()[0] == 1
        assert list(connection.execute("PRAGMA foreign_key_check")) == []
