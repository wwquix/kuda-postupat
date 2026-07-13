from __future__ import annotations

import argparse
from dataclasses import dataclass

from sqlalchemy import Connection, Engine, create_engine, inspect

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

from .config import BACKEND_DIR, get_settings, resolve_database_url


class SchemaNotCurrentError(RuntimeError):
    pass


@dataclass(frozen=True)
class LegacyTableSpec:
    columns: tuple[tuple[str, str, bool], ...]
    primary_key: tuple[str, ...]
    foreign_keys: tuple[
        tuple[tuple[str, ...], str, tuple[str, ...], str | None, str | None], ...
    ] = ()
    indexes: tuple[tuple[str, tuple[str, ...], bool], ...] = ()
    unique_constraints: tuple[tuple[str | None, tuple[str, ...]], ...] = ()
    check_constraints: tuple[tuple[str | None, str], ...] = ()


LEGACY_SCHEMA: dict[str, LegacyTableSpec] = {
    "specialties": LegacyTableSpec(
        columns=(
            ("id", "INTEGER", False),
            ("normalized_name", "VARCHAR(300)", False),
            ("display_name", "VARCHAR(300)", False),
            ("study_form", "VARCHAR(100)", False),
            ("funding_type", "VARCHAR(50)", False),
            ("source_url", "VARCHAR(1000)", False),
            ("active", "BOOLEAN", False),
        ),
        primary_key=("id",),
        indexes=(("ix_specialties_normalized_name", ("normalized_name",), False),),
        unique_constraints=(("uq_specialty", ("normalized_name", "study_form", "funding_type")),),
    ),
    "admission_snapshots": LegacyTableSpec(
        columns=(
            ("id", "INTEGER", False),
            ("specialty_id", "INTEGER", False),
            ("fetched_at", "DATETIME", False),
            ("source_updated_at", "DATETIME", True),
            ("admission_plan", "INTEGER", False),
            ("applications_total", "INTEGER", False),
            ("competition", "FLOAT", False),
            ("estimated_cutoff_min", "INTEGER", True),
            ("estimated_cutoff_max", "INTEGER", True),
            ("user_score", "INTEGER", False),
            ("estimated_user_position", "INTEGER", True),
            ("user_status", "VARCHAR(100)", False),
            ("distribution_json", "TEXT", False),
            ("raw_data_hash", "VARCHAR(64)", False),
        ),
        primary_key=("id",),
        foreign_keys=((('specialty_id',), "specialties", ("id",), None, None),),
        indexes=(
            ("ix_admission_snapshots_fetched_at", ("fetched_at",), False),
            ("ix_admission_snapshots_raw_data_hash", ("raw_data_hash",), False),
            ("ix_admission_snapshots_specialty_id", ("specialty_id",), False),
        ),
    ),
    "scraper_runs": LegacyTableSpec(
        columns=(
            ("id", "INTEGER", False),
            ("started_at", "DATETIME", False),
            ("finished_at", "DATETIME", True),
            ("status", "VARCHAR(30)", False),
            ("http_status", "INTEGER", True),
            ("error_type", "VARCHAR(100)", True),
            ("error_message", "TEXT", True),
            ("rows_found", "INTEGER", False),
            ("content_hash", "VARCHAR(64)", True),
        ),
        primary_key=("id",),
        indexes=(
            ("ix_scraper_runs_started_at", ("started_at",), False),
            ("ix_scraper_runs_status", ("status",), False),
        ),
    ),
    "notification_logs": LegacyTableSpec(
        columns=(
            ("id", "INTEGER", False),
            ("fingerprint", "VARCHAR(64)", False),
            ("sent_at", "DATETIME", False),
            ("message", "TEXT", False),
        ),
        primary_key=("id",),
        indexes=(("ix_notification_logs_fingerprint", ("fingerprint",), True),),
    ),
    "http_cache_state": LegacyTableSpec(
        columns=(
            ("url", "VARCHAR(1000)", False),
            ("etag", "VARCHAR(500)", True),
            ("last_modified", "VARCHAR(500)", True),
            ("checked_at", "DATETIME", True),
        ),
        primary_key=("url",),
    ),
}


def _normalize_sql(sql: str) -> str:
    return " ".join(sql.split())


LEGACY_SQLITE_MASTER: dict[tuple[str, str, str], str] = {
    (object_type, name, table_name): _normalize_sql(sql)
    for object_type, name, table_name, sql in (
        (
            "table",
            "specialties",
            "specialties",
            """
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
            )
            """,
        ),
        (
            "table",
            "admission_snapshots",
            "admission_snapshots",
            """
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
            )
            """,
        ),
        (
            "table",
            "scraper_runs",
            "scraper_runs",
            """
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
            )
            """,
        ),
        (
            "table",
            "notification_logs",
            "notification_logs",
            """
            CREATE TABLE notification_logs (
                id INTEGER NOT NULL,
                fingerprint VARCHAR(64) NOT NULL,
                sent_at DATETIME NOT NULL,
                message TEXT NOT NULL,
                PRIMARY KEY (id)
            )
            """,
        ),
        (
            "table",
            "http_cache_state",
            "http_cache_state",
            """
            CREATE TABLE http_cache_state (
                url VARCHAR(1000) NOT NULL,
                etag VARCHAR(500),
                last_modified VARCHAR(500),
                checked_at DATETIME,
                PRIMARY KEY (url)
            )
            """,
        ),
        (
            "index",
            "ix_specialties_normalized_name",
            "specialties",
            "CREATE INDEX ix_specialties_normalized_name ON specialties (normalized_name)",
        ),
        (
            "index",
            "ix_admission_snapshots_specialty_id",
            "admission_snapshots",
            "CREATE INDEX ix_admission_snapshots_specialty_id ON admission_snapshots (specialty_id)",
        ),
        (
            "index",
            "ix_admission_snapshots_fetched_at",
            "admission_snapshots",
            "CREATE INDEX ix_admission_snapshots_fetched_at ON admission_snapshots (fetched_at)",
        ),
        (
            "index",
            "ix_admission_snapshots_raw_data_hash",
            "admission_snapshots",
            "CREATE INDEX ix_admission_snapshots_raw_data_hash ON admission_snapshots (raw_data_hash)",
        ),
        (
            "index",
            "ix_scraper_runs_started_at",
            "scraper_runs",
            "CREATE INDEX ix_scraper_runs_started_at ON scraper_runs (started_at)",
        ),
        (
            "index",
            "ix_scraper_runs_status",
            "scraper_runs",
            "CREATE INDEX ix_scraper_runs_status ON scraper_runs (status)",
        ),
        (
            "index",
            "ix_notification_logs_fingerprint",
            "notification_logs",
            "CREATE UNIQUE INDEX ix_notification_logs_fingerprint ON notification_logs (fingerprint)",
        ),
    )
}


def make_alembic_config(database_url: str | None = None) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    if database_url is not None:
        config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
        config.attributes["database_url_override"] = database_url
    return config


def expected_head() -> str:
    return ScriptDirectory.from_config(make_alembic_config()).get_current_head()


def current_revision(connection: Connection) -> str | None:
    return MigrationContext.configure(connection).get_current_revision()


def ensure_schema_current(engine: Engine) -> None:
    expected = expected_head()
    with engine.connect() as connection:
        current = current_revision(connection)
    if current != expected:
        raise SchemaNotCurrentError(
            f"Database schema is not current (current={current or 'unversioned'}, expected={expected}). "
            "Stop the service, create a backup, and run Alembic migrations explicitly."
        )


def legacy_schema_mismatches(connection: Connection) -> list[str]:
    inspector = inspect(connection)
    actual_tables = set(inspector.get_table_names())
    mismatches: list[str] = []
    unexpected_tables = actual_tables - set(LEGACY_SCHEMA) - {"alembic_version"}
    if unexpected_tables:
        mismatches.append("unexpected tables: " + ", ".join(sorted(unexpected_tables)))
    actual_sqlite_master = {
        (object_type, name, table_name): _normalize_sql(sql)
        for object_type, name, table_name, sql in connection.exec_driver_sql(
            "SELECT type, name, tbl_name, sql FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%' AND sql IS NOT NULL"
        )
        if not (object_type == "table" and name == "alembic_version")
    }
    missing_objects = set(LEGACY_SQLITE_MASTER) - set(actual_sqlite_master)
    unexpected_objects = set(actual_sqlite_master) - set(LEGACY_SQLITE_MASTER)
    if missing_objects:
        mismatches.append(
            "missing sqlite_master objects: "
            + ", ".join(f"{item[0]}:{item[1]}" for item in sorted(missing_objects))
        )
    if unexpected_objects:
        mismatches.append(
            "unexpected sqlite_master objects: "
            + ", ".join(f"{item[0]}:{item[1]}" for item in sorted(unexpected_objects))
        )
    for object_key in sorted(set(LEGACY_SQLITE_MASTER) & set(actual_sqlite_master)):
        if actual_sqlite_master[object_key] != LEGACY_SQLITE_MASTER[object_key]:
            mismatches.append(f"sqlite_master SQL mismatch: {object_key[0]}:{object_key[1]}")
    for table_name, spec in LEGACY_SCHEMA.items():
        if table_name not in actual_tables:
            mismatches.append(f"missing table: {table_name}")
            continue
        columns = tuple(
            (column["name"], str(column["type"]).upper(), bool(column["nullable"]))
            for column in inspector.get_columns(table_name)
        )
        if columns != spec.columns:
            mismatches.append(f"column mismatch: {table_name}")
        primary_key = tuple(inspector.get_pk_constraint(table_name).get("constrained_columns") or ())
        if primary_key != spec.primary_key:
            mismatches.append(f"primary key mismatch: {table_name}")
        foreign_keys = tuple(
            sorted(
                (
                    tuple(item.get("constrained_columns") or ()),
                    item.get("referred_table"),
                    tuple(item.get("referred_columns") or ()),
                    (item.get("options") or {}).get("ondelete"),
                    (item.get("options") or {}).get("onupdate"),
                )
                for item in inspector.get_foreign_keys(table_name)
            )
        )
        if foreign_keys != tuple(sorted(spec.foreign_keys)):
            mismatches.append(f"foreign key mismatch: {table_name}")
        indexes = tuple(
            sorted(
                (item["name"], tuple(item.get("column_names") or ()), bool(item.get("unique")))
                for item in inspector.get_indexes(table_name)
            )
        )
        if indexes != tuple(sorted(spec.indexes)):
            mismatches.append(f"index mismatch: {table_name}")
        uniques = tuple(
            sorted(
                (item.get("name"), tuple(item.get("column_names") or ()))
                for item in inspector.get_unique_constraints(table_name)
            )
        )
        if uniques != tuple(sorted(spec.unique_constraints)):
            mismatches.append(f"unique constraint mismatch: {table_name}")
        checks = tuple(
            sorted(
                (item.get("name"), " ".join(str(item.get("sqltext") or "").split()))
                for item in inspector.get_check_constraints(table_name)
            )
        )
        if checks != tuple(sorted(spec.check_constraints)):
            mismatches.append(f"check constraint mismatch: {table_name}")
        if any(column.get("default") is not None for column in inspector.get_columns(table_name)):
            mismatches.append(f"unexpected server default: {table_name}")
    return mismatches


def assert_legacy_schema(connection: Connection) -> None:
    mismatches = legacy_schema_mismatches(connection)
    if mismatches:
        raise SchemaNotCurrentError("Legacy schema verification failed: " + "; ".join(mismatches))


def prepare_database_for_setup(database_url: str | None = None) -> str:
    """Upgrade an empty or already-versioned DB; never stamp an unversioned legacy DB."""
    resolved_url = database_url or resolve_database_url(get_settings().database_url)
    engine = create_engine(resolved_url)
    try:
        with engine.connect() as connection:
            tables = set(inspect(connection).get_table_names())
            current = current_revision(connection)
            has_legacy = bool(set(LEGACY_SCHEMA) & tables)
            unmanaged_tables = tables - {"alembic_version"}
            if has_legacy and current is None:
                assert_legacy_schema(connection)
    finally:
        engine.dispose()

    if current is None and has_legacy:
        raise SchemaNotCurrentError(
            "Existing legacy database is unversioned. Create and verify a backup, run "
            "`python -m app.schema verify-legacy`, then stamp 0001_legacy_baseline explicitly."
        )
    if current is None and unmanaged_tables:
        raise SchemaNotCurrentError("Unversioned database contains unknown tables; automatic setup refused.")
    if current == expected_head():
        return "current"
    if current is not None or not unmanaged_tables:
        command.upgrade(make_alembic_config(resolved_url), "head")
        return "upgraded"
    raise SchemaNotCurrentError("Database state is not safe for automatic setup.")


def _verify_configured_legacy() -> None:
    database_url = resolve_database_url(get_settings().database_url)
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            assert_legacy_schema(connection)
    finally:
        engine.dispose()
    print("Legacy schema verification: PASS")


def main() -> None:
    parser = argparse.ArgumentParser(description="Safe schema verification helpers")
    parser.add_argument("command", choices=("verify-legacy", "setup"))
    args = parser.parse_args()
    if args.command == "verify-legacy":
        _verify_configured_legacy()
    elif args.command == "setup":
        result = prepare_database_for_setup()
        print(f"Database schema setup: {result}")


if __name__ == "__main__":
    main()
