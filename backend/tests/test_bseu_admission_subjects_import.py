from __future__ import annotations

import hashlib
import json
import shutil
import socket
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from alembic import command
from app import bseu_admission_subjects_import as importer
from app.bseu_admission_subjects_import import (
    AUDIT_PATH,
    EXPECTED_PROGRAMS,
    EXPECTED_REQUIREMENT_SETS,
    EXPECTED_SOURCES,
    EXPECTED_SUBJECTS,
    load_bseu_admission_audit,
    run_bseu_admission_subjects_import,
)
from app.bseu_program_import import run_bseu_program_import
from app.catalog_import_service import CatalogConflictError, CatalogValidationError
from app.cli import _parser, main
from app.schema import make_alembic_config

ROOT = Path(__file__).resolve().parents[2]
MAIN_DATABASE_PATH = ROOT / "backend" / "data" / "admission.db"
PREVIOUS_HEAD = "0006_telegram_watch_notifications"
CORE_REVISION = "0002_core_catalog_schema"
EXPECTED_GROUPS = 92
EXPECTED_OPTIONS = 119
EXPECTED_LINKS = 50
IMPORTED_TABLES = (
    "admission_subjects",
    "admission_requirement_sources",
    "program_admission_requirement_sets",
    "admission_requirement_subject_groups",
    "admission_requirement_subject_options",
    "admission_requirement_evidence_links",
)
PROTECTED_TABLES = (
    "programs",
    "program_offerings",
    "legacy_specialty_mappings",
    "admission_snapshots",
)


@pytest.fixture(autouse=True)
def block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("BSEU admission-subject importer tests must remain offline")

    monkeypatch.setattr(socket, "create_connection", refuse_network)
    monkeypatch.setattr(socket.socket, "connect", refuse_network)


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


@pytest.fixture(scope="session")
def imported_program_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("bseu-admission-subject-template") / "template.db"
    _upgrade(path, CORE_REVISION)
    _insert_legacy_monitoring_fixture(path)
    _upgrade(path)
    run_bseu_program_import(path, apply=True)
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM programs").fetchone() == (17,)
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    return path


@pytest.fixture
def database(tmp_path: Path, imported_program_template: Path) -> Path:
    path = tmp_path / "requirements.db"
    shutil.copy2(imported_program_template, path)
    return path


def _load_document() -> dict[str, Any]:
    value = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _write_document(path: Path, document: dict[str, Any]) -> Path:
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _dump(path: Path) -> tuple[str, ...]:
    with sqlite3.connect(path) as connection:
        return tuple(connection.iterdump())


def _table_rows(path: Path, tables: tuple[str, ...]) -> dict[str, list[tuple[object, ...]]]:
    with sqlite3.connect(path) as connection:
        return {table: connection.execute(f'SELECT * FROM "{table}" ORDER BY 1').fetchall() for table in tables}


def _sidecar_state(path: Path) -> dict[str, bytes | None]:
    paths = (path, path.with_name(f"{path.name}-wal"), path.with_name(f"{path.name}-shm"))
    return {item.name: item.read_bytes() if item.exists() else None for item in paths}


def _main_metadata() -> tuple[int, int, str] | None:
    if not MAIN_DATABASE_PATH.exists():
        return None
    stat = MAIN_DATABASE_PATH.stat()
    return stat.st_size, stat.st_mtime_ns, hashlib.sha256(MAIN_DATABASE_PATH.read_bytes()).hexdigest()


def _imported_counts(path: Path) -> tuple[int, int, int, int, int, int]:
    with sqlite3.connect(path) as connection:
        return tuple(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] for table in IMPORTED_TABLES)  # type: ignore[return-value]


def test_canonical_audit_passes_strict_validation_and_derives_exact_counts() -> None:
    before = _main_metadata()
    audit = load_bseu_admission_audit()

    assert len(audit.programs) == EXPECTED_PROGRAMS == 17
    assert len(audit.requirement_sets) == EXPECTED_REQUIREMENT_SETS == 37
    assert len(audit.subjects) == EXPECTED_SUBJECTS == 11
    assert len(audit.sources) == EXPECTED_SOURCES == 3
    assert len(audit.groups) == EXPECTED_GROUPS
    assert len(audit.options) == EXPECTED_OPTIONS
    assert len(audit.evidence_links) == EXPECTED_LINKS
    assert audit.sha256 == hashlib.sha256(AUDIT_PATH.read_bytes()).hexdigest()
    assert _main_metadata() == before


def test_invalid_unknown_and_semantically_inconsistent_audits_are_rejected(tmp_path: Path) -> None:
    cases: list[tuple[str, Any, str]] = [
        ("unknown", lambda data: data.__setitem__("invented_field", 0), "JSON Schema validation failed"),
        ("year", lambda data: data.__setitem__("admission_year", 2027), "expected constant 2026"),
        ("university", lambda data: data.__setitem__("university_code", "other"), "university_code"),
        (
            "duplicate-source",
            lambda data: data["sources"].append(dict(data["sources"][0])),
            "duplicate source identity",
        ),
        (
            "choose-count",
            lambda data: data["requirement_definitions"][0]["subject_groups"][0].__setitem__("choose_count", 3),
            "choose_count cannot exceed",
        ),
        (
            "missing-source",
            lambda data: data["programs"][0]["requirement_sets"][0]["source_ids"].append("missing-source"),
            "missing source reference",
        ),
        (
            "malformed-identity",
            lambda data: data["programs"][0].__setitem__("program_identity", "bseu|nearest-name|wrong"),
            "string does not match",
        ),
    ]
    for name, mutate, expected in cases:
        document = _load_document()
        mutate(document)
        path = _write_document(tmp_path / f"{name}.json", document)
        with pytest.raises(CatalogValidationError, match=expected):
            load_bseu_admission_audit(path)


def test_missing_migration_0007_fails_clearly_without_writes(tmp_path: Path) -> None:
    database = tmp_path / "previous-head.db"
    _upgrade(database, PREVIOUS_HEAD)
    before = _dump(database)

    with pytest.raises(CatalogValidationError, match="migration 0007 schema prerequisite failed"):
        run_bseu_admission_subjects_import(database, mode="dry-run")

    assert _dump(database) == before


def test_missing_bseu_university_aborts_apply_without_writes(database: Path) -> None:
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE universities SET code='not-bseu', slug='not-bseu' WHERE code='bseu'")
    before = _dump(database)

    with pytest.raises(CatalogConflictError, match="University with code bseu"):
        run_bseu_admission_subjects_import(database, mode="apply")

    assert _dump(database) == before
    assert _imported_counts(database) == (0, 0, 0, 0, 0, 0)


def test_missing_target_program_aborts_apply_without_writes(database: Path) -> None:
    with sqlite3.connect(database) as connection:
        program_id = connection.execute(
            "SELECT id FROM programs WHERE slug='bseu-audit-19efc40dc770e97239ef'"
        ).fetchone()[0]
        connection.execute("DELETE FROM program_offerings WHERE program_id=?", (program_id,))
        connection.execute("DELETE FROM programs WHERE id=?", (program_id,))
    before = _dump(database)

    with pytest.raises(CatalogConflictError, match="exact slug matched 0"):
        run_bseu_admission_subjects_import(database, mode="apply")

    assert _dump(database) == before
    assert _imported_counts(database) == (0, 0, 0, 0, 0, 0)


def test_duplicate_or_mismatched_program_identity_aborts_without_writes(database: Path) -> None:
    with sqlite3.connect(database) as connection:
        target = connection.execute("SELECT name FROM programs WHERE slug='economic-informatics'").fetchone()[0]
        connection.execute(
            "UPDATE programs SET name=? WHERE slug='bseu-audit-19efc40dc770e97239ef'", (target,)
        )
    before = _dump(database)

    with pytest.raises(CatalogConflictError, match="exact imported name is missing or duplicated"):
        run_bseu_admission_subjects_import(database, mode="apply")

    assert _dump(database) == before


def test_fuzzy_program_name_similarity_is_never_accepted(database: Path) -> None:
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE programs SET name=name || ' ' WHERE slug='economic-informatics'")
    before = _dump(database)

    with pytest.raises(CatalogConflictError, match="different name"):
        run_bseu_admission_subjects_import(database, mode="dry-run")

    assert _dump(database) == before


def test_dry_run_is_query_only_creates_no_rows_and_reports_exact_plan(database: Path) -> None:
    before = _sidecar_state(database)
    summary = run_bseu_admission_subjects_import(database, mode="dry-run")

    assert summary.as_dict() == {
        "mode": "dry-run",
        "database_path": str(database.resolve()),
        "audit_path": str(AUDIT_PATH.resolve()),
        "audit_sha256": hashlib.sha256(AUDIT_PATH.read_bytes()).hexdigest(),
        "admission_year": 2026,
        "university": "bseu",
        "programs_expected": 17,
        "programs_matched": 17,
        "subjects_created": 11,
        "subjects_reused": 0,
        "evidence_sources_created": 3,
        "evidence_sources_reused": 0,
        "requirement_sets_created": 37,
        "requirement_sets_reused": 0,
        "groups_created": 92,
        "groups_reused": 0,
        "subject_options_created": 119,
        "subject_options_reused": 0,
        "evidence_links_created": 50,
        "evidence_links_reused": 0,
        "unchanged_rows": 0,
        "conflicts": 0,
        "transaction_committed": False,
    }
    assert _imported_counts(database) == (0, 0, 0, 0, 0, 0)
    assert _sidecar_state(database) == before

    engine = importer._database_engine(database, readonly=True)
    try:
        with engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA query_only").scalar_one() == 1
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
    finally:
        engine.dispose()


def test_dry_run_sees_committed_rows_in_wal_without_modifying_any_file(database: Path) -> None:
    keeper = sqlite3.connect(database)
    try:
        assert keeper.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
        keeper.execute("PRAGMA wal_autocheckpoint=0")
        keeper.execute(
            "INSERT INTO admission_subjects (normalized_key, official_label_ru, official_label_be) "
            "VALUES ('accounting', 'Бухгалтерский учет', NULL)"
        )
        keeper.commit()
        wal_path = database.with_name(f"{database.name}-wal")
        assert wal_path.stat().st_size > 0
        immutable_uri = f"file:{database.resolve().as_posix()}?mode=ro&immutable=1"
        with sqlite3.connect(immutable_uri, uri=True) as main_only:
            assert main_only.execute("SELECT COUNT(*) FROM admission_subjects").fetchone() == (0,)
        before = _sidecar_state(database)

        summary = run_bseu_admission_subjects_import(database, mode="dry-run")

        assert (summary.subjects_created, summary.subjects_reused) == (10, 1)
        assert _sidecar_state(database) == before
        assert keeper.execute("SELECT COUNT(*) FROM admission_subjects").fetchone() == (1,)
    finally:
        keeper.close()


def test_apply_imports_exact_entities_and_preserves_semantics(database: Path) -> None:
    protected_before = _table_rows(database, PROTECTED_TABLES)
    legacy_json_before = _table_rows(database, ("programs",))["programs"]
    summary = run_bseu_admission_subjects_import(database, mode="apply")

    assert (summary.subjects_created, summary.evidence_sources_created) == (11, 3)
    assert (summary.requirement_sets_created, summary.groups_created) == (37, 92)
    assert (summary.subject_options_created, summary.evidence_links_created) == (119, 50)
    assert summary.transaction_committed is True
    assert _imported_counts(database) == (11, 3, 37, 92, 119, 50)
    assert _table_rows(database, PROTECTED_TABLES) == protected_before
    assert _table_rows(database, ("programs",))["programs"] == legacy_json_before

    with sqlite3.connect(database) as connection:
        alternatives = connection.execute(
            """
            SELECT rs.stable_key, g.position, g.choose_count,
                   group_concat(s.normalized_key, '|')
            FROM program_admission_requirement_sets AS rs
            JOIN admission_requirement_subject_groups AS g ON g.requirement_set_id=rs.id
            JOIN admission_requirement_subject_options AS o ON o.subject_group_id=g.id
            JOIN admission_subjects AS s ON s.id=o.subject_id
            WHERE g.stable_key IN ('language', 'profile_second')
            GROUP BY rs.id, g.id
            HAVING COUNT(*) > 1
            ORDER BY rs.stable_key, g.position
            """
        ).fetchall()
        assert alternatives
        assert all(row[2] == 1 for row in alternatives)
        assert {row[3] for row in alternatives} >= {
            "belarusian_language|russian_language",
            "history_belarus|history_belarus_world_context",
        }
        assert set(
            connection.execute(
                "SELECT DISTINCT pathway_code, track_description FROM program_admission_requirement_sets"
            ).fetchall()
        ) >= {
            ("general_competition", "full"),
            ("general_competition", "shortened"),
            ("targeted_training", "full"),
        }
        assert set(
            connection.execute(
                "SELECT DISTINCT assessment_kind, official_assessment_label "
                "FROM admission_requirement_subject_groups"
            ).fetchall()
        ) == {
            ("external_standardized", "ЦЭ/ЦТ"),
            ("internal_written_examination", "Внутренний письменный экзамен"),
            ("internal_oral_examination", "Внутренний устный экзамен"),
        }
        assert set(
            connection.execute(
                "SELECT DISTINCT study_form, study_form_label, education_basis, track_description "
                "FROM program_admission_requirement_sets"
            ).fetchall()
        ) >= {
            ("full_time", "Очная (дневная) форма", "full_track_eligible_basis", "full"),
            ("part_time", "Заочная форма", "corresponding_secondary_specialized_education", "shortened"),
        }
        assert connection.execute(
            "SELECT COUNT(*) FROM program_admission_requirement_sets AS rs "
            "WHERE NOT EXISTS (SELECT 1 FROM admission_requirement_evidence_links AS l "
            "WHERE l.requirement_set_id=rs.id)"
        ).fetchone() == (0,)
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_second_apply_creates_zero_rows_and_does_not_refresh_timestamps(database: Path) -> None:
    first = run_bseu_admission_subjects_import(database, mode="apply")
    timestamps_before = _table_rows(
        database,
        ("admission_subjects", "admission_requirement_sources", "program_admission_requirement_sets"),
    )
    semantic_before = _dump(database)

    second = run_bseu_admission_subjects_import(database, mode="apply")

    assert first.transaction_committed is True
    assert (
        second.subjects_created,
        second.evidence_sources_created,
        second.requirement_sets_created,
        second.groups_created,
        second.subject_options_created,
        second.evidence_links_created,
    ) == (0, 0, 0, 0, 0, 0)
    assert second.unchanged_rows == 312
    assert second.transaction_committed is True
    assert _table_rows(
        database,
        ("admission_subjects", "admission_requirement_sources", "program_admission_requirement_sets"),
    ) == timestamps_before
    assert _dump(database) == semantic_before


def test_partial_consistent_rows_are_reused_and_missing_rows_created(database: Path) -> None:
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO admission_subjects (normalized_key, official_label_ru, official_label_be) "
            "VALUES ('accounting', 'Бухгалтерский учет', NULL)"
        )

    summary = run_bseu_admission_subjects_import(database, mode="apply")

    assert (summary.subjects_created, summary.subjects_reused) == (10, 1)
    assert _imported_counts(database) == (11, 3, 37, 92, 119, 50)


@pytest.mark.parametrize(
    ("sql", "message"),
    [
        (
            "UPDATE admission_subjects SET official_label_ru='Конфликт' WHERE normalized_key='accounting'",
            "subject accounting has conflicting official_label_ru",
        ),
        (
            "UPDATE admission_requirement_sources SET official_url='https://example.invalid/' "
            "WHERE source_key='bseu-2026-admission-order'",
            "evidence source bseu-2026-admission-order has conflicting official_url",
        ),
        (
            "UPDATE program_admission_requirement_sets SET pathway_label='Конфликт' WHERE id=("
            "SELECT MIN(id) FROM program_admission_requirement_sets)",
            "requirement set",
        ),
        (
            "UPDATE admission_requirement_subject_groups SET choose_count=2 WHERE id=("
            "SELECT MIN(id) FROM admission_requirement_subject_groups)",
            "group",
        ),
        (
            "UPDATE admission_requirement_subject_options SET subject_id=("
            "SELECT id FROM admission_subjects WHERE normalized_key='mathematics') WHERE rowid=("
            "SELECT MIN(rowid) FROM admission_requirement_subject_options)",
            "option",
        ),
        (
            "UPDATE admission_requirement_evidence_links SET locator='Конфликт' WHERE rowid=("
            "SELECT MIN(rowid) FROM admission_requirement_evidence_links)",
            "evidence link",
        ),
    ],
)
def test_semantic_conflict_aborts_without_partial_commit(database: Path, sql: str, message: str) -> None:
    run_bseu_admission_subjects_import(database, mode="apply")
    with sqlite3.connect(database) as connection:
        connection.execute(sql)
    before = _dump(database)

    with pytest.raises(CatalogConflictError, match=message):
        run_bseu_admission_subjects_import(database, mode="apply")

    assert _dump(database) == before


def test_late_failure_rolls_back_every_new_row(
    database: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    protected_before = _table_rows(database, PROTECTED_TABLES)
    before = _dump(database)

    def fail_late(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("injected late integrity failure")

    monkeypatch.setattr(importer, "_verify_before_commit", fail_late)
    with pytest.raises(RuntimeError, match="injected late integrity failure"):
        run_bseu_admission_subjects_import(database, mode="apply")

    assert _dump(database) == before
    assert _imported_counts(database) == (0, 0, 0, 0, 0, 0)
    assert _table_rows(database, PROTECTED_TABLES) == protected_before


def test_program_fields_offerings_mappings_snapshots_and_legacy_json_remain_unchanged(database: Path) -> None:
    before = _table_rows(database, PROTECTED_TABLES)
    with sqlite3.connect(database) as connection:
        codes_before = connection.execute("SELECT slug, code FROM programs ORDER BY slug").fetchall()
        legacy_before = connection.execute(
            "SELECT slug, admission_subjects_json FROM programs ORDER BY slug"
        ).fetchall()

    run_bseu_admission_subjects_import(database, mode="apply")

    assert _table_rows(database, PROTECTED_TABLES) == before
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT slug, code FROM programs ORDER BY slug").fetchall() == codes_before
        assert (
            connection.execute("SELECT slug, admission_subjects_json FROM programs ORDER BY slug").fetchall()
            == legacy_before
        )
        assert sum(code is not None for _, code in codes_before) == 1


def test_focused_import_never_opens_main_database(
    database: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = _main_metadata()
    real_engine = importer._database_engine

    def guarded_engine(path: Path, *, readonly: bool):  # type: ignore[no-untyped-def]
        assert path.resolve() != MAIN_DATABASE_PATH.resolve()
        return real_engine(path, readonly=readonly)

    monkeypatch.setattr(importer, "_database_engine", guarded_engine)
    run_bseu_admission_subjects_import(database, mode="dry-run")
    assert _main_metadata() == before


def test_cli_requires_database_and_exactly_one_mode() -> None:
    with pytest.raises(SystemExit):
        _parser().parse_args(["import-bseu-admission-subjects", "--dry-run"])
    with pytest.raises(SystemExit):
        _parser().parse_args(["import-bseu-admission-subjects", "--database", "fixture.db"])
    with pytest.raises(SystemExit):
        _parser().parse_args(
            ["import-bseu-admission-subjects", "--database", "fixture.db", "--dry-run", "--apply"]
        )


def test_cli_output_is_deterministic_secret_free_and_errors_are_nonzero(
    database: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    args = [
        "import-bseu-admission-subjects",
        "--database",
        str(database),
        "--dry-run",
    ]
    assert main(args) == 0
    first = capsys.readouterr().out
    assert main(args) == 0
    second = capsys.readouterr().out
    assert first == second
    payload = json.loads(first)
    assert payload["mode"] == "dry-run"
    assert payload["transaction_committed"] is False
    assert "password" not in first.casefold()
    assert "sqlite:///" not in first

    invalid = _load_document()
    invalid["invented"] = True
    invalid_path = _write_document(tmp_path / "invalid.json", invalid)
    invalid_args = [
        "import-bseu-admission-subjects",
        "--database",
        str(database),
        "--audit-path",
        str(invalid_path),
        "--dry-run",
    ]
    assert main(invalid_args) == 2
    invalid_error = json.loads(capsys.readouterr().err)
    assert invalid_error["transaction_committed"] is False

    run_bseu_admission_subjects_import(database, mode="apply")
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE admission_subjects SET official_label_ru='Конфликт' WHERE normalized_key='accounting'"
        )
    conflict_args = [
        "import-bseu-admission-subjects",
        "--database",
        str(database),
        "--apply",
    ]
    assert main(conflict_args) == 2
    conflict_error = json.loads(capsys.readouterr().err)
    assert conflict_error["conflict_count"] >= 1
    assert conflict_error["transaction_committed"] is False
