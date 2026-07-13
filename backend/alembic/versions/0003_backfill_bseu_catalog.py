"""Backfill BSEU catalog identity and link the legacy monitoring domain."""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "0003_backfill_bseu_catalog"
down_revision: str | None = "0002_core_catalog_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


REGISTRY_URL = (
    "https://edu.gov.by/urovni-obrazovaniya/vysshee-obrazovanie/"
    "zakazchikam-spetsialistov/uchrezhdeniya-vysshego-obrazovaniya/g-minsk/index.php"
)
OFFICIAL_SITE_URL = "https://bseu.by/"
ADMISSIONS_URL = "https://bseu.by/abiturient/"
PROGRAM_CATALOG_URL = "https://bseu.by/russian/teaching/specialities.htm"
ADMISSION_PLAN_URL = "https://bseu.by/russian/abiturient/tsp2026.pdf"
ADMISSION_XML_URL = "https://bseu.by/abiturient/xml/1.xml"
SOURCE_CHECKED_AT = datetime(2026, 7, 12, 18, 14, 28, tzinfo=UTC)


def _mapping(row: sa.RowMapping | None) -> dict[str, object] | None:
    return dict(row) if row is not None else None


def _one(connection: sa.Connection, statement: str, parameters: dict[str, object]) -> dict[str, object] | None:
    return _mapping(connection.execute(sa.text(statement), parameters).mappings().one_or_none())


def _require_equal(entity: str, row: dict[str, object], expected: dict[str, object]) -> None:
    conflicts = [key for key, value in expected.items() if row.get(key) != value]
    if conflicts:
        raise RuntimeError(
            f"Conflicting existing {entity}; fields do not match the reviewed BSEU seed: "
            + ", ".join(conflicts)
        )


def _ensure_university(connection: sa.Connection) -> int:
    expected = {
        "code": "bseu",
        "slug": "bseu",
        "short_name": "БГЭУ",
        "full_name": "Белорусский государственный экономический университет",
        "institution_kind": "university",
        "ownership_type": "state",
        "city": "Минск",
        "region": "Минск",
        "official_site_url": OFFICIAL_SITE_URL,
        "admissions_url": ADMISSIONS_URL,
        "monitoring_status": "online",
        "source_url": REGISTRY_URL,
    }
    by_code = _one(connection, "SELECT * FROM universities WHERE code = :code", {"code": "bseu"})
    by_slug = _one(connection, "SELECT * FROM universities WHERE slug = :slug", {"slug": "bseu"})
    if by_code is not None and by_slug is not None and by_code["id"] != by_slug["id"]:
        raise RuntimeError("Conflicting BSEU code and slug belong to different university rows")
    row = by_code or by_slug
    if row is not None:
        _require_equal("university", row, expected)
        return int(row["id"])
    result = connection.execute(
        sa.text(
            """
            INSERT INTO universities (
                code, slug, short_name, full_name, institution_kind, ownership_type,
                city, region, official_site_url, admissions_url, description,
                monitoring_status, active, source_url, source_checked_at, data_verified_at
            ) VALUES (
                :code, :slug, :short_name, :full_name, :institution_kind, :ownership_type,
                :city, :region, :official_site_url, :admissions_url, NULL,
                :monitoring_status, 1, :source_url, :source_checked_at, NULL
            )
            """
        ),
        expected | {"source_checked_at": SOURCE_CHECKED_AT},
    )
    return int(result.lastrowid)


def _ensure_category(connection: sa.Connection, university_id: int) -> int:
    row = _one(connection, "SELECT * FROM university_categories WHERE code = :code", {"code": "economic"})
    if row is None:
        result = connection.execute(
            sa.text("INSERT INTO university_categories (code, label_ru) VALUES (:code, :label)"),
            {"code": "economic", "label": "Экономика"},
        )
        category_id = int(result.lastrowid)
    else:
        _require_equal("university category", row, {"code": "economic", "label_ru": "Экономика"})
        category_id = int(row["id"])
    connection.execute(
        sa.text(
            """
            INSERT INTO university_category_links (university_id, category_id)
            SELECT :university_id, :category_id
            WHERE NOT EXISTS (
                SELECT 1 FROM university_category_links
                WHERE university_id = :university_id AND category_id = :category_id
            )
            """
        ),
        {"university_id": university_id, "category_id": category_id},
    )
    return category_id


def _ensure_program(connection: sa.Connection, university_id: int) -> int:
    expected = {
        "university_id": university_id,
        "code": "6-05-0311-05",
        "slug": "economic-informatics",
        "name": "Экономическая информатика",
        "qualification": "Экономист. Информатик",
        "faculty_name": "Факультет цифровой экономики",
        "official_url": PROGRAM_CATALOG_URL,
    }
    row = _one(
        connection,
        "SELECT * FROM programs WHERE university_id = :university_id AND slug = :slug",
        {"university_id": university_id, "slug": expected["slug"]},
    )
    by_code = _one(
        connection,
        "SELECT * FROM programs WHERE university_id = :university_id AND code = :code",
        {"university_id": university_id, "code": expected["code"]},
    )
    if row is not None and by_code is not None and row["id"] != by_code["id"]:
        raise RuntimeError("Conflicting BSEU program code and slug belong to different rows")
    row = row or by_code
    if row is not None:
        _require_equal("program", row, expected)
        return int(row["id"])
    result = connection.execute(
        sa.text(
            """
            INSERT INTO programs (
                university_id, code, slug, name, qualification, faculty_name,
                education_level, duration_years, description, admission_subjects_json,
                career_fields_json, category_tags_json, official_url, active,
                source_checked_at, verified_at
            ) VALUES (
                :university_id, :code, :slug, :name, :qualification, :faculty_name,
                NULL, NULL, NULL, NULL, NULL, NULL, :official_url, 1,
                :source_checked_at, NULL
            )
            """
        ),
        expected | {"source_checked_at": SOURCE_CHECKED_AT},
    )
    return int(result.lastrowid)


def _ensure_offering(connection: sa.Connection, program_id: int) -> int:
    expected = {
        "program_id": program_id,
        "admission_year": 2026,
        "study_form": "full_time",
        "funding_type": "paid",
        "places": 60,
        "monitoring_supported": 1,
        "monitoring_status": "online",
        "official_url": ADMISSION_PLAN_URL,
        "source_url": ADMISSION_PLAN_URL,
    }
    row = _one(
        connection,
        """
        SELECT * FROM program_offerings
        WHERE program_id = :program_id AND admission_year = :admission_year
          AND study_form = :study_form AND funding_type = :funding_type
        """,
        expected,
    )
    if row is not None:
        _require_equal("program offering", row, expected)
        return int(row["id"])
    result = connection.execute(
        sa.text(
            """
            INSERT INTO program_offerings (
                program_id, admission_year, study_form, funding_type, places,
                application_deadline, monitoring_supported, monitoring_status,
                official_url, source_url, source_checked_at, verified_at
            ) VALUES (
                :program_id, :admission_year, :study_form, :funding_type, :places,
                NULL, :monitoring_supported, :monitoring_status,
                :official_url, :source_url, :source_checked_at, NULL
            )
            """
        ),
        expected | {"source_checked_at": SOURCE_CHECKED_AT},
    )
    return int(result.lastrowid)


def _legacy_source_state(connection: sa.Connection) -> dict[str, object]:
    cache = _one(
        connection,
        "SELECT etag, last_modified, checked_at FROM http_cache_state WHERE url = :url",
        {"url": ADMISSION_XML_URL},
    ) or {"etag": None, "last_modified": None, "checked_at": None}
    last_run = _one(connection, "SELECT * FROM scraper_runs ORDER BY id DESC LIMIT 1", {})
    last_success = _one(
        connection,
        """
        SELECT * FROM scraper_runs
        WHERE status IN ('success', 'not_modified')
        ORDER BY id DESC LIMIT 1
        """,
        {},
    )
    statuses = connection.execute(sa.text("SELECT status FROM scraper_runs ORDER BY id DESC")).scalars()
    consecutive_failures = 0
    for status in statuses:
        if status != "error":
            break
        consecutive_failures += 1
    latest_is_error = last_run is not None and last_run["status"] == "error"
    return {
        "last_attempt_at": last_run["finished_at"] if last_run else cache["checked_at"],
        "last_success_at": last_success["finished_at"] if last_success else cache["checked_at"],
        "last_error_type": last_run["error_type"] if latest_is_error else None,
        "last_error_message": last_run["error_message"] if latest_is_error else None,
        "consecutive_failures": consecutive_failures,
        "health_status": "degraded" if latest_is_error else ("healthy" if last_success else "unknown"),
        "etag": cache["etag"],
        "last_modified": cache["last_modified"],
    }


def _ensure_data_source(connection: sa.Connection, university_id: int) -> int:
    identity = {
        "university_id": university_id,
        "source_type": "admission_xml",
        "source_url": ADMISSION_XML_URL,
    }
    row = _one(
        connection,
        """
        SELECT * FROM data_sources
        WHERE university_id = :university_id AND source_type = :source_type AND source_url = :source_url
        """,
        identity,
    )
    runtime = _legacy_source_state(connection)
    if row is None:
        result = connection.execute(
            sa.text(
                """
                INSERT INTO data_sources (
                    university_id, source_type, source_url, adapter_name,
                    refresh_interval_minutes, enabled, last_attempt_at, last_success_at,
                    last_error_type, last_error_message, consecutive_failures,
                    health_status, etag, last_modified
                ) VALUES (
                    :university_id, :source_type, :source_url, 'legacy_admission_scraper',
                    10, 1, :last_attempt_at, :last_success_at,
                    :last_error_type, :last_error_message, :consecutive_failures,
                    :health_status, :etag, :last_modified
                )
                """
            ),
            identity | runtime,
        )
        return int(result.lastrowid)
    _require_equal("data source", row, identity)
    connection.execute(
        sa.text(
            """
            UPDATE data_sources
            SET last_attempt_at = :last_attempt_at,
                last_success_at = :last_success_at,
                last_error_type = :last_error_type,
                last_error_message = :last_error_message,
                consecutive_failures = :consecutive_failures,
                health_status = :health_status,
                etag = :etag,
                last_modified = :last_modified
            WHERE id = :id
            """
        ),
        runtime | {"id": row["id"]},
    )
    return int(row["id"])


def _ensure_legacy_links(
    connection: sa.Connection, program_id: int, offering_id: int, data_source_id: int
) -> None:
    specialties = connection.execute(
        sa.text(
            """
            SELECT * FROM specialties
            WHERE normalized_name = 'экономическая информатика'
              AND study_form = 'дневная' AND funding_type = 'платная'
            """
        )
    ).mappings().all()
    if len(specialties) > 1:
        raise RuntimeError("BSEU legacy specialty identity is ambiguous")
    if specialties:
        specialty_id = int(specialties[0]["id"])
        existing = _one(
            connection,
            "SELECT * FROM legacy_specialty_mappings WHERE legacy_specialty_id = :legacy_id",
            {"legacy_id": specialty_id},
        )
        expected = {
            "legacy_specialty_id": specialty_id,
            "program_id": program_id,
            "program_offering_id": offering_id,
            "mapping_version": 1,
        }
        if existing is None:
            connection.execute(
                sa.text(
                    """
                    INSERT INTO legacy_specialty_mappings (
                        legacy_specialty_id, program_id, program_offering_id,
                        mapping_version, mapped_at, verified_at, notes
                    ) VALUES (
                        :legacy_specialty_id, :program_id, :program_offering_id,
                        :mapping_version, CURRENT_TIMESTAMP, NULL,
                        'BSEU 2026 full-time paid compatibility mapping'
                    )
                    """
                ),
                expected,
            )
        else:
            _require_equal("legacy specialty mapping", existing, expected)
        conflicting = connection.execute(
            sa.text(
                """
                SELECT id FROM admission_snapshots
                WHERE specialty_id = :legacy_id AND program_offering_id IS NOT NULL
                  AND program_offering_id != :offering_id
                """
            ),
            {"legacy_id": specialty_id, "offering_id": offering_id},
        ).first()
        if conflicting:
            raise RuntimeError("A legacy BSEU snapshot is linked to a conflicting offering")
        connection.execute(
            sa.text(
                """
                UPDATE admission_snapshots SET program_offering_id = :offering_id
                WHERE specialty_id = :legacy_id AND program_offering_id IS NULL
                """
            ),
            {"legacy_id": specialty_id, "offering_id": offering_id},
        )
    if connection.execute(
        sa.text("SELECT 1 FROM admission_snapshots WHERE program_offering_id IS NULL LIMIT 1")
    ).first():
        raise RuntimeError("Cannot backfill: at least one legacy snapshot has no reviewed BSEU offering mapping")
    if connection.execute(
        sa.text(
            "SELECT 1 FROM scraper_runs WHERE data_source_id IS NOT NULL AND data_source_id != :source_id LIMIT 1"
        ),
        {"source_id": data_source_id},
    ).first():
        raise RuntimeError("Cannot backfill: a legacy scraper run has a conflicting data source")
    connection.execute(
        sa.text("UPDATE scraper_runs SET data_source_id = :source_id WHERE data_source_id IS NULL"),
        {"source_id": data_source_id},
    )


def backfill_bseu(connection: sa.Connection) -> dict[str, int]:
    """Idempotently create the reviewed BSEU identities and additive legacy links."""
    university_id = _ensure_university(connection)
    _ensure_category(connection, university_id)
    program_id = _ensure_program(connection, university_id)
    offering_id = _ensure_offering(connection, program_id)
    data_source_id = _ensure_data_source(connection, university_id)
    _ensure_legacy_links(connection, program_id, offering_id, data_source_id)
    return {
        "university_id": university_id,
        "program_id": program_id,
        "program_offering_id": offering_id,
        "data_source_id": data_source_id,
    }


def _preflight_upgrade(connection: sa.Connection) -> None:
    """Fail before SQLite DDL when an existing identity would make the seed ambiguous."""
    by_code = _one(connection, "SELECT * FROM universities WHERE code = 'bseu'", {})
    by_slug = _one(connection, "SELECT * FROM universities WHERE slug = 'bseu'", {})
    if by_code is not None and by_slug is not None and by_code["id"] != by_slug["id"]:
        raise RuntimeError("Conflicting BSEU code and slug belong to different university rows")
    university = by_code or by_slug
    if university is not None:
        _require_equal(
            "university",
            university,
            {
                "code": "bseu",
                "slug": "bseu",
                "short_name": "БГЭУ",
                "full_name": "Белорусский государственный экономический университет",
                "institution_kind": "university",
                "ownership_type": "state",
            },
        )
        program_by_slug = _one(
            connection,
            "SELECT * FROM programs WHERE university_id = :id AND slug = 'economic-informatics'",
            {"id": university["id"]},
        )
        program_by_code = _one(
            connection,
            "SELECT * FROM programs WHERE university_id = :id AND code = '6-05-0311-05'",
            {"id": university["id"]},
        )
        if (
            program_by_slug is not None
            and program_by_code is not None
            and program_by_slug["id"] != program_by_code["id"]
        ):
            raise RuntimeError("Conflicting BSEU program code and slug belong to different rows")
        program = program_by_slug or program_by_code
        if program is not None:
            _require_equal(
                "program",
                program,
                {
                    "university_id": university["id"],
                    "code": "6-05-0311-05",
                    "slug": "economic-informatics",
                    "name": "Экономическая информатика",
                },
            )
            offering = _one(
                connection,
                """
                SELECT * FROM program_offerings
                WHERE program_id = :program_id AND admission_year = 2026
                  AND study_form = 'full_time' AND funding_type = 'paid'
                """,
                {"program_id": program["id"]},
            )
            if offering is not None:
                _require_equal(
                    "program offering",
                    offering,
                    {
                        "program_id": program["id"],
                        "admission_year": 2026,
                        "study_form": "full_time",
                        "funding_type": "paid",
                        "places": 60,
                    },
                )
        conflicting_source = _one(
            connection,
            """
            SELECT * FROM data_sources
            WHERE university_id = :id AND source_url = :url
            """,
            {"id": university["id"], "url": ADMISSION_XML_URL},
        )
        if conflicting_source is not None and conflicting_source["source_type"] != "admission_xml":
            raise RuntimeError("Conflicting BSEU XML data source type")
    category = _one(connection, "SELECT * FROM university_categories WHERE code = 'economic'", {})
    if category is not None:
        _require_equal(
            "university category", category, {"code": "economic", "label_ru": "Экономика"}
        )
    unmatched_snapshots = connection.execute(
        sa.text(
            """
            SELECT COUNT(*) FROM admission_snapshots AS snapshot
            JOIN specialties AS specialty ON specialty.id = snapshot.specialty_id
            WHERE specialty.normalized_name != 'экономическая информатика'
               OR specialty.study_form != 'дневная'
               OR specialty.funding_type != 'платная'
            """
        )
    ).scalar_one()
    if unmatched_snapshots:
        raise RuntimeError("Cannot backfill: legacy snapshots include an unreviewed specialty identity")


def upgrade() -> None:
    _preflight_upgrade(op.get_bind())
    op.create_table(
        "legacy_specialty_mappings",
        sa.Column("legacy_specialty_id", sa.Integer(), nullable=False),
        sa.Column("program_id", sa.Integer(), nullable=False),
        sa.Column("program_offering_id", sa.Integer(), nullable=False),
        sa.Column("mapping_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("mapped_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint("mapping_version >= 1", name="mapping_version_positive"),
        sa.ForeignKeyConstraint(["legacy_specialty_id"], ["specialties.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["program_id"], ["programs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["program_offering_id"], ["program_offerings.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("legacy_specialty_id"),
        sa.UniqueConstraint("program_offering_id", name="uq_legacy_specialty_mappings_offering"),
    )
    op.create_index(
        "ix_legacy_specialty_mappings_program_id", "legacy_specialty_mappings", ["program_id"], unique=False
    )
    with op.batch_alter_table("admission_snapshots") as batch_op:
        batch_op.add_column(sa.Column("program_offering_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_admission_snapshots_program_offering_id_program_offerings",
            "program_offerings",
            ["program_offering_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_index(
            "ix_admission_snapshots_program_offering_id_fetched_at",
            ["program_offering_id", "fetched_at"],
            unique=False,
        )
    with op.batch_alter_table("scraper_runs") as batch_op:
        batch_op.add_column(sa.Column("data_source_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_scraper_runs_data_source_id_data_sources",
            "data_sources",
            ["data_source_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "ix_scraper_runs_data_source_id_started_at", ["data_source_id", "started_at"], unique=False
        )
    backfill_bseu(op.get_bind())


def downgrade() -> None:
    connection = op.get_bind()
    university = _one(connection, "SELECT * FROM universities WHERE code = 'bseu'", {})
    if university is None:
        raise RuntimeError("Guarded BSEU downgrade refused: seeded university is missing")
    university_id = int(university["id"])
    _require_equal(
        "university",
        university,
        {
            "code": "bseu",
            "slug": "bseu",
            "short_name": "БГЭУ",
            "full_name": "Белорусский государственный экономический университет",
        },
    )
    program = _one(
        connection,
        "SELECT * FROM programs WHERE university_id = :id AND code = '6-05-0311-05'",
        {"id": university_id},
    )
    if program is None:
        raise RuntimeError("Guarded BSEU downgrade refused: seeded program is missing")
    offering = _one(
        connection,
        """
        SELECT * FROM program_offerings
        WHERE program_id = :program_id AND admission_year = 2026
          AND study_form = 'full_time' AND funding_type = 'paid'
        """,
        {"program_id": program["id"]},
    )
    source = _one(
        connection,
        """
        SELECT * FROM data_sources
        WHERE university_id = :university_id AND source_type = 'admission_xml' AND source_url = :url
        """,
        {"university_id": university_id, "url": ADMISSION_XML_URL},
    )
    if offering is None or source is None:
        raise RuntimeError("Guarded BSEU downgrade refused: seeded offering or data source is missing")
    guarded_counts = {
        "programs": ("university_id", university_id, 1),
        "data_sources": ("university_id", university_id, 1),
        "program_offerings": ("program_id", int(program["id"]), 1),
    }
    for table, (column, value, expected_count) in guarded_counts.items():
        count = connection.execute(
            sa.text(f'SELECT COUNT(*) FROM "{table}" WHERE "{column}" = :value'), {"value": value}
        ).scalar_one()
        if count != expected_count:
            raise RuntimeError(f"Guarded BSEU downgrade refused: unexpected dependent rows in {table}")
    if connection.execute(
        sa.text(
            """
            SELECT 1 FROM legacy_specialty_mappings
            WHERE program_id != :program_id OR program_offering_id != :offering_id LIMIT 1
            """
        ),
        {"program_id": program["id"], "offering_id": offering["id"]},
    ).first():
        raise RuntimeError("Guarded BSEU downgrade refused: non-seed mappings exist")
    connection.execute(
        sa.text("UPDATE admission_snapshots SET program_offering_id = NULL WHERE program_offering_id = :id"),
        {"id": offering["id"]},
    )
    connection.execute(
        sa.text("UPDATE scraper_runs SET data_source_id = NULL WHERE data_source_id = :id"),
        {"id": source["id"]},
    )
    connection.execute(sa.text("DELETE FROM legacy_specialty_mappings"))
    connection.execute(sa.text("DELETE FROM data_sources WHERE id = :id"), {"id": source["id"]})
    connection.execute(sa.text("DELETE FROM program_offerings WHERE id = :id"), {"id": offering["id"]})
    connection.execute(sa.text("DELETE FROM programs WHERE id = :id"), {"id": program["id"]})
    connection.execute(
        sa.text("DELETE FROM university_category_links WHERE university_id = :id"), {"id": university_id}
    )
    connection.execute(sa.text("DELETE FROM universities WHERE id = :id"), {"id": university_id})
    category = _one(connection, "SELECT id FROM university_categories WHERE code = 'economic'", {})
    if category is not None:
        linked = connection.execute(
            sa.text("SELECT 1 FROM university_category_links WHERE category_id = :id LIMIT 1"),
            {"id": category["id"]},
        ).first()
        if not linked:
            connection.execute(
                sa.text("DELETE FROM university_categories WHERE id = :id"), {"id": category["id"]}
            )
    op.drop_index("ix_legacy_specialty_mappings_program_id", table_name="legacy_specialty_mappings")
    op.drop_table("legacy_specialty_mappings")
    with op.batch_alter_table("scraper_runs") as batch_op:
        batch_op.drop_index("ix_scraper_runs_data_source_id_started_at")
        batch_op.drop_constraint("fk_scraper_runs_data_source_id_data_sources", type_="foreignkey")
        batch_op.drop_column("data_source_id")
    with op.batch_alter_table("admission_snapshots") as batch_op:
        batch_op.drop_index("ix_admission_snapshots_program_offering_id_fetched_at")
        batch_op.drop_constraint(
            "fk_admission_snapshots_program_offering_id_program_offerings", type_="foreignkey"
        )
        batch_op.drop_column("program_offering_id")
