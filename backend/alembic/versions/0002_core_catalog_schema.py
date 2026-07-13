"""Create empty core catalog tables without changing legacy data."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_core_catalog_schema"
down_revision: str | None = "0001_legacy_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


institution_kind = sa.Enum(
    "university", "academy", "institute", "conservatory", "military_academy", "other",
    name="institution_kind", native_enum=False, create_constraint=True,
)
ownership_type = sa.Enum(
    "state", "private", "mixed", "unknown", name="ownership_type", native_enum=False, create_constraint=True,
)
monitoring_status = sa.Enum(
    "online", "partial", "periodic", "reference_only", "unsupported", "broken", "needs_review",
    name="monitoring_status", native_enum=False, create_constraint=True,
)
study_form = sa.Enum(
    "full_time", "part_time", "distance", "evening", "other",
    name="study_form", native_enum=False, create_constraint=True,
)
funding_type = sa.Enum(
    "budget", "paid", "targeted", "separate_competition", "other",
    name="funding_type", native_enum=False, create_constraint=True,
)
source_health = sa.Enum(
    "healthy", "stale", "degraded", "unavailable", "unknown",
    name="source_health", native_enum=False, create_constraint=True,
)


def upgrade() -> None:
    op.create_table(
        "universities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("slug", sa.String(length=200), nullable=False),
        sa.Column("short_name", sa.String(length=300), nullable=False),
        sa.Column("full_name", sa.String(length=500), nullable=False),
        sa.Column("institution_kind", institution_kind, nullable=False),
        sa.Column("ownership_type", ownership_type, nullable=False),
        sa.Column("city", sa.String(length=200), nullable=True),
        sa.Column("region", sa.String(length=200), nullable=True),
        sa.Column("official_site_url", sa.String(length=1000), nullable=False),
        sa.Column("admissions_url", sa.String(length=1000), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("monitoring_status", monitoring_status, nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("source_url", sa.String(length=1000), nullable=False),
        sa.Column("source_checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.CheckConstraint("length(trim(code)) > 0", name="code_not_blank"),
        sa.CheckConstraint("length(trim(slug)) > 0", name="slug_not_blank"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_universities_city", "universities", ["city"], unique=False)
    op.create_index("ix_universities_region", "universities", ["region"], unique=False)
    op.create_index("ix_universities_monitoring_status", "universities", ["monitoring_status"], unique=False)
    op.create_index("ix_universities_active", "universities", ["active"], unique=False)

    op.create_table(
        "university_categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("label_ru", sa.String(length=300), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.CheckConstraint("length(trim(code)) > 0", name="code_not_blank"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "university_category_links",
        sa.Column("university_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["university_categories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["university_id"], ["universities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("university_id", "category_id"),
    )
    op.create_index(
        "ix_university_category_links_category_id", "university_category_links", ["category_id"], unique=False
    )

    op.create_table(
        "programs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("university_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=True),
        sa.Column("slug", sa.String(length=240), nullable=False),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("qualification", sa.String(length=300), nullable=True),
        sa.Column("faculty_name", sa.String(length=300), nullable=True),
        sa.Column("education_level", sa.String(length=100), nullable=True),
        sa.Column("duration_years", sa.Float(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("admission_subjects_json", sa.Text(), nullable=True),
        sa.Column("career_fields_json", sa.Text(), nullable=True),
        sa.Column("category_tags_json", sa.Text(), nullable=True),
        sa.Column("official_url", sa.String(length=1000), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("source_checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.CheckConstraint("length(trim(slug)) > 0", name="slug_not_blank"),
        sa.ForeignKeyConstraint(["university_id"], ["universities.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("university_id", "slug", name="uq_programs_university_slug"),
    )
    op.create_index("ix_programs_university_id", "programs", ["university_id"], unique=False)
    op.create_index("ix_programs_name", "programs", ["name"], unique=False)
    op.create_index("ix_programs_active", "programs", ["active"], unique=False)

    op.create_table(
        "program_offerings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("program_id", sa.Integer(), nullable=False),
        sa.Column("admission_year", sa.Integer(), nullable=False),
        sa.Column("study_form", study_form, nullable=False),
        sa.Column("funding_type", funding_type, nullable=False),
        sa.Column("places", sa.Integer(), nullable=True),
        sa.Column("application_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("monitoring_supported", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("monitoring_status", monitoring_status, nullable=False),
        sa.Column("official_url", sa.String(length=1000), nullable=False),
        sa.Column("source_url", sa.String(length=1000), nullable=False),
        sa.Column("source_checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.CheckConstraint("admission_year >= 2000 AND admission_year <= 2100", name="admission_year_range"),
        sa.CheckConstraint("places IS NULL OR places >= 0", name="places_non_negative"),
        sa.ForeignKeyConstraint(["program_id"], ["programs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "program_id", "admission_year", "study_form", "funding_type",
            name="uq_program_offerings_business_key",
        ),
    )
    op.create_index("ix_program_offerings_program_id", "program_offerings", ["program_id"], unique=False)
    op.create_index(
        "ix_program_offerings_admission_year", "program_offerings", ["admission_year"], unique=False
    )
    op.create_index("ix_program_offerings_study_form", "program_offerings", ["study_form"], unique=False)
    op.create_index("ix_program_offerings_funding_type", "program_offerings", ["funding_type"], unique=False)
    op.create_index(
        "ix_program_offerings_monitoring_status", "program_offerings", ["monitoring_status"], unique=False
    )

    op.create_table(
        "data_sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("university_id", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=100), nullable=False),
        sa.Column("source_url", sa.String(length=1000), nullable=False),
        sa.Column("adapter_name", sa.String(length=200), nullable=True),
        sa.Column("refresh_interval_minutes", sa.Integer(), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_type", sa.String(length=200), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("health_status", source_health, server_default="unknown", nullable=False),
        sa.Column("etag", sa.String(length=500), nullable=True),
        sa.Column("last_modified", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.CheckConstraint("length(trim(source_type)) > 0", name="source_type_not_blank"),
        sa.CheckConstraint(
            "refresh_interval_minutes IS NULL OR refresh_interval_minutes >= 5",
            name="refresh_interval_minimum",
        ),
        sa.CheckConstraint("consecutive_failures >= 0", name="consecutive_failures_non_negative"),
        sa.ForeignKeyConstraint(["university_id"], ["universities.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("university_id", "source_type", "source_url", name="uq_data_sources_identity"),
    )
    op.create_index("ix_data_sources_university_id", "data_sources", ["university_id"], unique=False)
    op.create_index("ix_data_sources_health_status", "data_sources", ["health_status"], unique=False)
    op.create_index("ix_data_sources_enabled", "data_sources", ["enabled"], unique=False)


def downgrade() -> None:
    connection = op.get_bind()
    catalog_tables = (
        "data_sources",
        "program_offerings",
        "programs",
        "university_category_links",
        "university_categories",
        "universities",
    )
    populated_tables = [
        table_name
        for table_name in catalog_tables
        if connection.exec_driver_sql(f'SELECT 1 FROM "{table_name}" LIMIT 1').first() is not None
    ]
    if populated_tables:
        raise RuntimeError(
            "Refusing to downgrade a non-empty catalog schema; populated tables: "
            + ", ".join(populated_tables)
        )

    op.drop_index("ix_data_sources_enabled", table_name="data_sources")
    op.drop_index("ix_data_sources_health_status", table_name="data_sources")
    op.drop_index("ix_data_sources_university_id", table_name="data_sources")
    op.drop_table("data_sources")
    op.drop_index("ix_program_offerings_monitoring_status", table_name="program_offerings")
    op.drop_index("ix_program_offerings_funding_type", table_name="program_offerings")
    op.drop_index("ix_program_offerings_study_form", table_name="program_offerings")
    op.drop_index("ix_program_offerings_admission_year", table_name="program_offerings")
    op.drop_index("ix_program_offerings_program_id", table_name="program_offerings")
    op.drop_table("program_offerings")
    op.drop_index("ix_programs_active", table_name="programs")
    op.drop_index("ix_programs_name", table_name="programs")
    op.drop_index("ix_programs_university_id", table_name="programs")
    op.drop_table("programs")
    op.drop_index("ix_university_category_links_category_id", table_name="university_category_links")
    op.drop_table("university_category_links")
    op.drop_table("university_categories")
    op.drop_index("ix_universities_active", table_name="universities")
    op.drop_index("ix_universities_monitoring_status", table_name="universities")
    op.drop_index("ix_universities_region", table_name="universities")
    op.drop_index("ix_universities_city", table_name="universities")
    op.drop_table("universities")
