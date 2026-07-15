from __future__ import annotations

import ast
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from alembic import command
from alembic.runtime.migration import MigrationContext
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
    UniversityCategory,
    UniversityCategoryLink,
)
from app.schema import (
    SchemaNotCurrentError,
    assert_legacy_schema,
    legacy_schema_mismatches,
    make_alembic_config,
    prepare_database_for_setup,
)

BASELINE = "0001_legacy_baseline"
CORE = "0002_core_catalog_schema"
PREVIOUS_HEAD = "0003_backfill_bseu_catalog"
HEAD = "0004_anonymous_admission_list"
LEGACY_TABLES = {
    "admission_snapshots",
    "http_cache_state",
    "notification_logs",
    "scraper_runs",
    "specialties",
}
CATALOG_TABLES = {
    "data_sources",
    "program_offerings",
    "programs",
    "universities",
    "university_categories",
    "university_category_links",
}
BRIDGE_TABLES = {"legacy_specialty_mappings"}
PROFILE_TABLES = {"anonymous_profiles", "saved_programs", "saved_universities"}
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

FROZEN_LEGACY_DDL = """
CREATE TABLE specialties (
    id INTEGER NOT NULL,
    normalized_name VARCHAR(300) NOT NULL,
    display_name VARCHAR(300) NOT NULL,
    study_form VARCHAR(100) NOT NULL,
    funding_type VARCHAR(50) NOT NULL,
    source_url VARCHAR(1000) NOT NULL,
    active BOOLEAN NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_specialty UNIQUE (normalized_name, study_form, funding_type)
);
CREATE INDEX ix_specialties_normalized_name ON specialties (normalized_name);
CREATE TABLE admission_snapshots (
    id INTEGER NOT NULL,
    specialty_id INTEGER NOT NULL,
    fetched_at DATETIME NOT NULL,
    source_updated_at DATETIME,
    admission_plan INTEGER NOT NULL,
    applications_total INTEGER NOT NULL,
    competition FLOAT NOT NULL,
    estimated_cutoff_min INTEGER,
    estimated_cutoff_max INTEGER,
    user_score INTEGER NOT NULL,
    estimated_user_position INTEGER,
    user_status VARCHAR(100) NOT NULL,
    distribution_json TEXT NOT NULL,
    raw_data_hash VARCHAR(64) NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(specialty_id) REFERENCES specialties (id)
);
CREATE INDEX ix_admission_snapshots_specialty_id ON admission_snapshots (specialty_id);
CREATE INDEX ix_admission_snapshots_fetched_at ON admission_snapshots (fetched_at);
CREATE INDEX ix_admission_snapshots_raw_data_hash ON admission_snapshots (raw_data_hash);
CREATE TABLE scraper_runs (
    id INTEGER NOT NULL,
    started_at DATETIME NOT NULL,
    finished_at DATETIME,
    status VARCHAR(30) NOT NULL,
    http_status INTEGER,
    error_type VARCHAR(100),
    error_message TEXT,
    rows_found INTEGER NOT NULL,
    content_hash VARCHAR(64),
    PRIMARY KEY (id)
);
CREATE INDEX ix_scraper_runs_started_at ON scraper_runs (started_at);
CREATE INDEX ix_scraper_runs_status ON scraper_runs (status);
CREATE TABLE notification_logs (
    id INTEGER NOT NULL,
    fingerprint VARCHAR(64) NOT NULL,
    sent_at DATETIME NOT NULL,
    message TEXT NOT NULL,
    PRIMARY KEY (id)
);
CREATE UNIQUE INDEX ix_notification_logs_fingerprint ON notification_logs (fingerprint);
CREATE TABLE http_cache_state (
    url VARCHAR(1000) NOT NULL,
    etag VARCHAR(500),
    last_modified VARCHAR(500),
    checked_at DATETIME,
    PRIMARY KEY (url)
);
"""


def sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.resolve().as_posix()}"


def revision(path: Path) -> str | None:
    engine = create_engine(sqlite_url(path))
    try:
        with engine.connect() as connection:
            return MigrationContext.configure(connection).get_current_revision()
    finally:
        engine.dispose()


def table_names(path: Path) -> set[str]:
    engine = create_engine(sqlite_url(path))
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def legacy_rows(path: Path) -> dict[str, list[tuple[object, ...]]]:
    with sqlite3.connect(path) as connection:
        return {
            table: list(
                connection.execute(f'SELECT {LEGACY_COLUMNS[table]} FROM "{table}" ORDER BY rowid')
            )
            for table in sorted(LEGACY_TABLES)
        }


def assert_bseu_seed(connection: sqlite3.Connection, *, mapping_count: int) -> None:
    expected_counts = {
        "universities": 1,
        "university_categories": 1,
        "university_category_links": 1,
        "programs": 1,
        "program_offerings": 1,
        "data_sources": 1,
        "legacy_specialty_mappings": mapping_count,
    }
    for table, expected in expected_counts.items():
        assert connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] == expected
    assert connection.execute("SELECT code, slug FROM universities").fetchone() == ("bseu", "bseu")
    assert connection.execute("SELECT code, name FROM programs").fetchone() == (
        "6-05-0311-05",
        "Экономическая информатика",
    )
    assert connection.execute(
        "SELECT admission_year, study_form, funding_type, places FROM program_offerings"
    ).fetchone() == (2026, "full_time", "paid", 60)


def seed_legacy_database(path: Path) -> dict[str, list[tuple[object, ...]]]:
    fetched_at = "2026-07-12 12:13:54.573894"
    source_updated_at = "2026-07-12 15:00:00.000000"
    raw_hash = "f80613b949ae2480b79cb375a9463efe11ea28e43ac015a912968b1a8a77e5f1"
    distribution = '{"270-279": 11}'
    with sqlite3.connect(path) as connection:
        connection.executescript(FROZEN_LEGACY_DDL)
        connection.execute(
            "INSERT INTO specialties "
            "(id, normalized_name, display_name, study_form, funding_type, source_url, active) "
            "VALUES (1, ?, ?, ?, ?, ?, 1)",
            ("экономическая информатика", "Экономическая информатика", "дневная", "платная", "https://bseu.by/"),
        )
        connection.execute(
            "INSERT INTO admission_snapshots "
            "(id, specialty_id, fetched_at, source_updated_at, admission_plan, applications_total, competition, "
            "estimated_cutoff_min, estimated_cutoff_max, user_score, estimated_user_position, user_status, "
            "distribution_json, raw_data_hash) VALUES (7, 1, ?, ?, 60, 11, 0.18, NULL, NULL, 276, 5, ?, ?, ?)",
            (fetched_at, source_updated_at, "Уверенно проходит", distribution, raw_hash),
        )
        connection.execute(
            "INSERT INTO scraper_runs "
            "(id, started_at, finished_at, status, http_status, error_type, error_message, rows_found, content_hash) "
            "VALUES (9, ?, ?, 'success', 200, NULL, NULL, 77, ?)",
            (fetched_at, fetched_at, raw_hash),
        )
        connection.execute(
            "INSERT INTO http_cache_state (url, etag, last_modified, checked_at) VALUES (?, ?, ?, ?)",
            ("https://bseu.by/abiturient/xml/1.xml", '"etag"', "Sun, 12 Jul 2026 15:00:00 GMT", fetched_at),
        )
        connection.execute(
            "INSERT INTO notification_logs (id, fingerprint, sent_at, message) VALUES (3, ?, ?, ?)",
            (raw_hash, fetched_at, "test message"),
        )
        connection.commit()
    return legacy_rows(path)


def test_fresh_database_upgrade_head(tmp_path: Path) -> None:
    database = tmp_path / "fresh.db"
    command.upgrade(make_alembic_config(sqlite_url(database)), "head")

    assert revision(database) == HEAD
    assert (
        LEGACY_TABLES
        | CATALOG_TABLES
        | BRIDGE_TABLES
        | PROFILE_TABLES
        | {"alembic_version"}
        == table_names(database)
    )
    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert list(connection.execute("PRAGMA foreign_key_check")) == []
        assert_bseu_seed(connection, mapping_count=0)


def test_upgrade_from_previous_head_adds_only_anonymous_list_schema(tmp_path: Path) -> None:
    database = tmp_path / "previous-head.db"
    config = make_alembic_config(sqlite_url(database))
    command.upgrade(config, PREVIOUS_HEAD)
    before_tables = table_names(database)
    with sqlite3.connect(database) as connection:
        before_catalog_counts = {
            table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            for table in CATALOG_TABLES | BRIDGE_TABLES | LEGACY_TABLES
        }

    command.upgrade(config, "head")

    assert revision(database) == HEAD
    assert table_names(database) == before_tables | PROFILE_TABLES
    with sqlite3.connect(database) as connection:
        after_catalog_counts = {
            table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            for table in CATALOG_TABLES | BRIDGE_TABLES | LEGACY_TABLES
        }
        assert after_catalog_counts == before_catalog_counts
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert list(connection.execute("PRAGMA foreign_key_check")) == []
        assert connection.execute("SELECT COUNT(*) FROM anonymous_profiles").fetchone()[0] == 0
        university_foreign_keys = list(connection.execute("PRAGMA foreign_key_list(saved_universities)"))
        program_foreign_keys = list(connection.execute("PRAGMA foreign_key_list(saved_programs)"))
        assert {(row[2], row[6]) for row in university_foreign_keys} == {
            ("anonymous_profiles", "CASCADE"),
            ("universities", "RESTRICT"),
        }
        assert {(row[2], row[6]) for row in program_foreign_keys} == {
            ("anonymous_profiles", "CASCADE"),
            ("programs", "RESTRICT"),
        }


def test_baseline_matches_independent_legacy_fingerprint(tmp_path: Path) -> None:
    database = tmp_path / "baseline.db"
    command.upgrade(make_alembic_config(sqlite_url(database)), BASELINE)
    engine = create_engine(sqlite_url(database))
    with engine.connect() as connection:
        assert_legacy_schema(connection)
    engine.dispose()

    malformed_database = tmp_path / "malformed-legacy.db"
    with sqlite3.connect(malformed_database) as connection:
        connection.executescript(
            FROZEN_LEGACY_DDL.replace(
                "FOREIGN KEY(specialty_id) REFERENCES specialties (id)",
                "FOREIGN KEY(specialty_id) REFERENCES specialties (id) ON DELETE CASCADE",
            ).replace(
                "active BOOLEAN NOT NULL,\n    PRIMARY KEY (id)",
                "active BOOLEAN NOT NULL CHECK (active IN (0, 1)),\n    PRIMARY KEY (id)",
            ).replace(
                "normalized_name VARCHAR(300) NOT NULL",
                "normalized_name VARCHAR(300) COLLATE NOCASE NOT NULL",
            ).replace(
                "CREATE UNIQUE INDEX ix_notification_logs_fingerprint ON notification_logs (fingerprint);",
                "CREATE UNIQUE INDEX ix_notification_logs_fingerprint ON notification_logs (fingerprint) "
                "WHERE id > 10;",
            )
        )
        connection.execute("CREATE TABLE unexpected_user_table (id INTEGER PRIMARY KEY)")
    malformed_engine = create_engine(sqlite_url(malformed_database))
    with malformed_engine.connect() as connection:
        mismatches = legacy_schema_mismatches(connection)
    malformed_engine.dispose()
    assert "foreign key mismatch: admission_snapshots" in mismatches
    assert "check constraint mismatch: specialties" in mismatches
    assert "unexpected tables: unexpected_user_table" in mismatches
    assert "sqlite_master SQL mismatch: table:specialties" in mismatches
    assert "sqlite_master SQL mismatch: index:ix_notification_logs_fingerprint" in mismatches


def test_existing_legacy_database_stamp_and_upgrade_preserves_rows(tmp_path: Path) -> None:
    database = tmp_path / "legacy.db"
    expected_legacy_rows = seed_legacy_database(database)
    before_counts: dict[str, int]
    verification_engine = create_engine(sqlite_url(database))
    with verification_engine.connect() as verification_connection:
        assert_legacy_schema(verification_connection)
    verification_engine.dispose()
    with sqlite3.connect(database) as connection:
        before_counts = {
            table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            for table in LEGACY_TABLES
        }

    config = make_alembic_config(sqlite_url(database))
    command.stamp(config, BASELINE)
    command.upgrade(config, "head")

    assert revision(database) == HEAD
    with sqlite3.connect(database) as connection:
        after_counts = {
            table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            for table in LEGACY_TABLES
        }
        assert after_counts == before_counts
        assert_bseu_seed(connection, mapping_count=1)
        assert connection.execute(
            "SELECT program_offering_id FROM admission_snapshots"
        ).fetchall() == [(1,)]
        assert connection.execute("SELECT data_source_id FROM scraper_runs").fetchall() == [(1,)]
    assert legacy_rows(database) == expected_legacy_rows


def test_catalog_downgrade_and_reupgrade_preserve_legacy(tmp_path: Path) -> None:
    database = tmp_path / "cycle.db"
    seed_legacy_database(database)
    config = make_alembic_config(sqlite_url(database))
    command.stamp(config, BASELINE)
    command.upgrade(config, "head")
    command.downgrade(config, BASELINE)

    assert revision(database) == BASELINE
    assert table_names(database) == LEGACY_TABLES | {"alembic_version"}
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM admission_snapshots").fetchone()[0] == 1

    command.upgrade(config, "head")
    assert revision(database) == HEAD
    assert CATALOG_TABLES.issubset(table_names(database))


def test_baseline_downgrade_is_noop_for_legacy_data(tmp_path: Path) -> None:
    database = tmp_path / "baseline-noop.db"
    expected_legacy_rows = seed_legacy_database(database)
    config = make_alembic_config(sqlite_url(database))
    command.stamp(config, BASELINE)

    command.downgrade(config, "base")

    assert revision(database) is None
    assert LEGACY_TABLES.issubset(table_names(database))
    assert legacy_rows(database) == expected_legacy_rows


def test_runtime_schema_check_never_creates_tables(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app import database as database_module

    database = tmp_path / "unmigrated.db"
    engine = create_engine(sqlite_url(database))
    monkeypatch.setattr(database_module, "engine", engine)
    with pytest.raises(SchemaNotCurrentError, match="not current"):
        database_module.init_db()
    assert inspect(engine).get_table_names() == []
    engine.dispose()

    production_app = Path(__file__).resolve().parents[1] / "app"
    for source_path in production_app.rglob("*.py"):
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        create_all_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "create_all"
        ]
        assert create_all_calls == [], f"Production create_all call found in {source_path}"


def test_setup_upgrades_empty_but_refuses_unversioned_legacy(tmp_path: Path) -> None:
    empty_database = tmp_path / "setup-empty.db"
    assert prepare_database_for_setup(sqlite_url(empty_database)) == "upgraded"
    assert revision(empty_database) == HEAD
    assert prepare_database_for_setup(sqlite_url(empty_database)) == "current"

    legacy_database = tmp_path / "setup-legacy.db"
    seed_legacy_database(legacy_database)
    with pytest.raises(SchemaNotCurrentError, match="unversioned"):
        prepare_database_for_setup(sqlite_url(legacy_database))
    assert "alembic_version" not in table_names(legacy_database)

    unknown_database = tmp_path / "setup-unknown.db"
    with sqlite3.connect(unknown_database) as connection:
        connection.execute("CREATE TABLE unexpected (id INTEGER PRIMARY KEY)")
    with pytest.raises(SchemaNotCurrentError, match="unknown tables"):
        prepare_database_for_setup(sqlite_url(unknown_database))


def _migrated_engine(path: Path):
    command.upgrade(make_alembic_config(sqlite_url(path)), "head")
    engine = create_engine(sqlite_url(path))

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    return engine


def university(code: str, slug: str) -> University:
    now = datetime.now(UTC)
    return University(
        code=code,
        slug=slug,
        short_name=code.upper(),
        full_name=f"University {code}",
        institution_kind=InstitutionKind.UNIVERSITY,
        ownership_type=OwnershipType.STATE,
        official_site_url=f"https://{code}.test",
        monitoring_status=MonitoringStatus.REFERENCE_ONLY,
        source_url=f"https://{code}.test/source",
        source_checked_at=now,
    )


def program(owner: University, slug: str) -> Program:
    return Program(
        university=owner,
        slug=slug,
        name="Экономическая информатика",
        official_url="https://program.test",
        source_checked_at=datetime.now(UTC),
    )


def test_catalog_unique_constraints(tmp_path: Path) -> None:
    engine = _migrated_engine(tmp_path / "constraints.db")
    with Session(engine) as session:
        first = university("one", "one")
        second = university("two", "two")
        session.add_all([first, second])
        session.commit()

        session.add(university("one", "three"))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        session.add(university("three", "one"))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        category = UniversityCategory(code="economics", label_ru="Экономические")
        session.add(category)
        session.commit()
        session.add_all(
            [
                UniversityCategoryLink(university_id=first.id, category_id=category.id),
                UniversityCategoryLink(university_id=first.id, category_id=category.id),
            ]
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        first_program = program(first, "economics")
        session.add(first_program)
        session.commit()
        session.add(program(first, "economics"))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        second_program = program(second, "economics")
        session.add(second_program)
        session.commit()
        assert session.scalar(select(Program).where(Program.id == second_program.id)) is not None

        offering = ProgramOffering(
            program=first_program,
            admission_year=2026,
            study_form=StudyForm.FULL_TIME,
            funding_type=FundingType.PAID,
            monitoring_status=MonitoringStatus.ONLINE,
            official_url="https://offering.test",
            source_url="https://offering.test/source",
            source_checked_at=datetime.now(UTC),
        )
        session.add(offering)
        session.commit()
        duplicate = ProgramOffering(
            program=first_program,
            admission_year=2026,
            study_form=StudyForm.FULL_TIME,
            funding_type=FundingType.PAID,
            monitoring_status=MonitoringStatus.ONLINE,
            official_url="https://offering.test/duplicate",
            source_url="https://offering.test/source",
            source_checked_at=datetime.now(UTC),
        )
        session.add(duplicate)
        with pytest.raises(IntegrityError):
            session.commit()
    engine.dispose()


def test_bseu_downgrade_refuses_new_dependencies(tmp_path: Path) -> None:
    database = tmp_path / "non-empty-downgrade.db"
    engine = _migrated_engine(database)
    with Session(engine) as session:
        bseu = session.scalar(select(University).where(University.code == "bseu"))
        assert bseu is not None
        session.add(program(bseu, "unexpected"))
        session.commit()
    engine.dispose()

    with pytest.raises(RuntimeError, match="unexpected dependent rows in programs"):
        command.downgrade(make_alembic_config(sqlite_url(database)), CORE)

    assert revision(database) == PREVIOUS_HEAD
    assert PROFILE_TABLES.isdisjoint(table_names(database))
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT code FROM universities").fetchall() == [("bseu",)]
        assert connection.execute("SELECT COUNT(*) FROM programs").fetchone()[0] == 2


def test_catalog_delete_is_restricted_and_legacy_is_untouched(tmp_path: Path) -> None:
    database = tmp_path / "cascade.db"
    engine = _migrated_engine(database)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO specialties "
            "(id, normalized_name, display_name, study_form, funding_type, source_url, active) "
            "VALUES (1, 'legacy', 'Legacy', 'day', 'paid', 'https://legacy.test', 1)"
        )
        connection.execute(
            "INSERT INTO admission_snapshots "
            "(id, specialty_id, fetched_at, source_updated_at, admission_plan, applications_total, competition, "
            "estimated_cutoff_min, estimated_cutoff_max, user_score, estimated_user_position, user_status, "
            "distribution_json, raw_data_hash) VALUES "
            "(1, 1, '2026-07-12 12:00:00', '2026-07-12 18:00:00', 60, 11, 0.18, NULL, NULL, 276, 5, "
            "'Уверенно проходит', '{\"270-279\": 11}', "
            "'f80613b949ae2480b79cb375a9463efe11ea28e43ac015a912968b1a8a77e5f1')"
        )
        connection.commit()
        legacy_before = connection.execute("SELECT * FROM admission_snapshots WHERE id = 1").fetchone()
    with Session(engine) as session:
        owner = university("safe", "safe")
        session.add(owner)
        session.commit()
        session.add(program(owner, "protected"))
        session.commit()
        session.delete(owner)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        offering_owner = university("offering", "offering")
        offering_program = program(offering_owner, "protected-offering")
        offering = ProgramOffering(
            program=offering_program,
            admission_year=2026,
            study_form=StudyForm.FULL_TIME,
            funding_type=FundingType.PAID,
            monitoring_status=MonitoringStatus.ONLINE,
            official_url="https://offering.test",
            source_url="https://offering.test/source",
            source_checked_at=datetime.now(UTC),
        )
        session.add(offering)
        session.commit()
        session.delete(offering_program)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        source_owner = university("source", "source")
        source = DataSource(
            university=source_owner,
            source_type="xml",
            source_url="https://source.test/data.xml",
        )
        session.add(source)
        session.commit()
        session.delete(source_owner)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        linked_owner = university("linked", "linked")
        category = UniversityCategory(code="linked", label_ru="Связанная")
        linked_owner.category_links.append(UniversityCategoryLink(category=category))
        session.add(linked_owner)
        session.commit()
        linked_owner_id = linked_owner.id
        category_id = category.id
        session.delete(linked_owner)
        session.commit()
        assert session.get(UniversityCategoryLink, (linked_owner_id, category_id)) is None
        assert session.get(UniversityCategory, category_id) is not None
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT id FROM specialties").fetchall() == [(1,)]
        assert connection.execute("SELECT * FROM admission_snapshots WHERE id = 1").fetchone() == legacy_before
    engine.dispose()
