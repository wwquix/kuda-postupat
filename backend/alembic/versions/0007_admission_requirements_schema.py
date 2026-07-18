"""Add normalized admission requirements schema."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007_admission_requirements_schema"
down_revision: str | None = "0006_telegram_watch_notifications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_TABLES = (
    "admission_requirement_evidence_links",
    "admission_requirement_subject_options",
    "admission_requirement_subject_groups",
    "program_admission_requirement_sets",
    "admission_requirement_sources",
    "admission_subjects",
)


def upgrade() -> None:
    op.create_table(
        "admission_subjects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("normalized_key", sa.String(length=150), nullable=False),
        sa.Column("official_label_ru", sa.String(length=300), nullable=False),
        sa.Column("official_label_be", sa.String(length=300), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(trim(normalized_key)) > 0",
            name=op.f("ck_admission_subjects_normalized_key_not_blank"),
        ),
        sa.CheckConstraint(
            "length(trim(official_label_ru)) > 0",
            name=op.f("ck_admission_subjects_official_label_ru_not_blank"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_admission_subjects")),
        sa.UniqueConstraint(
            "normalized_key",
            name=op.f("uq_admission_subjects_normalized_key"),
        ),
    )
    op.create_table(
        "admission_requirement_sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("university_id", sa.Integer(), nullable=False),
        sa.Column("source_key", sa.String(length=200), nullable=False),
        sa.Column("official_url", sa.String(length=1000), nullable=False),
        sa.Column("official_title", sa.String(length=1000), nullable=False),
        sa.Column("publisher", sa.String(length=500), nullable=False),
        sa.Column("source_type", sa.String(length=100), nullable=False),
        sa.Column("publication_year", sa.Integer(), nullable=True),
        sa.Column("admission_year", sa.Integer(), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_hash", sa.String(length=128), nullable=True),
        sa.Column("evidence_note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "admission_year IS NULL OR (admission_year >= 2000 AND admission_year <= 2100)",
            name=op.f("ck_admission_requirement_sources_admission_year_range"),
        ),
        sa.CheckConstraint(
            "length(trim(official_title)) > 0",
            name=op.f("ck_admission_requirement_sources_official_title_not_blank"),
        ),
        sa.CheckConstraint(
            "length(trim(official_url)) > 0",
            name=op.f("ck_admission_requirement_sources_official_url_not_blank"),
        ),
        sa.CheckConstraint(
            "length(trim(publisher)) > 0",
            name=op.f("ck_admission_requirement_sources_publisher_not_blank"),
        ),
        sa.CheckConstraint(
            "publication_year IS NULL OR (publication_year >= 2000 AND publication_year <= 2100)",
            name=op.f("ck_admission_requirement_sources_publication_year_range"),
        ),
        sa.CheckConstraint(
            "length(trim(source_key)) > 0",
            name=op.f("ck_admission_requirement_sources_source_key_not_blank"),
        ),
        sa.CheckConstraint(
            "length(trim(source_type)) > 0",
            name=op.f("ck_admission_requirement_sources_source_type_not_blank"),
        ),
        sa.ForeignKeyConstraint(
            ["university_id"],
            ["universities.id"],
            name=op.f("fk_admission_requirement_sources_university_id_universities"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_admission_requirement_sources")),
        sa.UniqueConstraint(
            "university_id",
            "source_key",
            name="uq_admission_requirement_sources_identity",
        ),
    )
    op.create_index(
        "ix_admission_requirement_sources_admission_year",
        "admission_requirement_sources",
        ["admission_year"],
        unique=False,
    )
    op.create_index(
        "ix_admission_requirement_sources_university_id",
        "admission_requirement_sources",
        ["university_id"],
        unique=False,
    )
    op.create_table(
        "program_admission_requirement_sets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("program_id", sa.Integer(), nullable=False),
        sa.Column("stable_key", sa.String(length=300), nullable=False),
        sa.Column("admission_year", sa.Integer(), nullable=False),
        sa.Column("pathway_code", sa.String(length=150), nullable=False),
        sa.Column("pathway_label", sa.String(length=300), nullable=False),
        sa.Column("study_form", sa.String(length=100), nullable=True),
        sa.Column("study_form_label", sa.String(length=300), nullable=True),
        sa.Column("funding_applicability", sa.String(length=300), nullable=True),
        sa.Column("education_basis", sa.String(length=200), nullable=True),
        sa.Column("track_description", sa.String(length=300), nullable=True),
        sa.Column("applicability_note", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("source_checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "admission_year >= 2000 AND admission_year <= 2100",
            name=op.f("ck_program_admission_requirement_sets_admission_year_range"),
        ),
        sa.CheckConstraint(
            "length(trim(pathway_code)) > 0",
            name=op.f("ck_program_admission_requirement_sets_pathway_code_not_blank"),
        ),
        sa.CheckConstraint(
            "length(trim(pathway_label)) > 0",
            name=op.f("ck_program_admission_requirement_sets_pathway_label_not_blank"),
        ),
        sa.CheckConstraint(
            "length(trim(stable_key)) > 0",
            name=op.f("ck_program_admission_requirement_sets_stable_key_not_blank"),
        ),
        sa.ForeignKeyConstraint(
            ["program_id"],
            ["programs.id"],
            name=op.f("fk_program_admission_requirement_sets_program_id_programs"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_program_admission_requirement_sets")),
        sa.UniqueConstraint(
            "program_id",
            "admission_year",
            "stable_key",
            name="uq_program_admission_requirement_sets_business_key",
        ),
    )
    op.create_index(
        "ix_program_admission_requirement_sets_admission_year",
        "program_admission_requirement_sets",
        ["admission_year"],
        unique=False,
    )
    op.create_index(
        "ix_program_admission_requirement_sets_program_id",
        "program_admission_requirement_sets",
        ["program_id"],
        unique=False,
    )
    op.create_index(
        "ix_program_admission_requirement_sets_program_year",
        "program_admission_requirement_sets",
        ["program_id", "admission_year"],
        unique=False,
    )
    op.create_table(
        "admission_requirement_subject_groups",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("requirement_set_id", sa.Integer(), nullable=False),
        sa.Column("stable_key", sa.String(length=150), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("choose_count", sa.Integer(), nullable=False),
        sa.Column(
            "assessment_kind",
            sa.Enum(
                "external_standardized",
                "internal_written_examination",
                "internal_oral_examination",
                "other",
                name="admission_assessment_kind",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("official_assessment_label", sa.String(length=300), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "choose_count > 0",
            name=op.f("ck_admission_requirement_subject_groups_choose_count_positive"),
        ),
        sa.CheckConstraint(
            "position > 0",
            name=op.f("ck_admission_requirement_subject_groups_position_positive"),
        ),
        sa.CheckConstraint(
            "length(trim(stable_key)) > 0",
            name=op.f("ck_admission_requirement_subject_groups_stable_key_not_blank"),
        ),
        sa.ForeignKeyConstraint(
            ["requirement_set_id"],
            ["program_admission_requirement_sets.id"],
            name=op.f(
                "fk_admission_requirement_subject_groups_requirement_set_id_"
                "program_admission_requirement_sets"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_admission_requirement_subject_groups")),
        sa.UniqueConstraint(
            "requirement_set_id",
            "position",
            name="uq_admission_requirement_subject_groups_position",
        ),
        sa.UniqueConstraint(
            "requirement_set_id",
            "stable_key",
            name="uq_admission_requirement_subject_groups_stable_key",
        ),
    )
    op.create_index(
        "ix_admission_requirement_subject_groups_requirement_set_id",
        "admission_requirement_subject_groups",
        ["requirement_set_id"],
        unique=False,
    )
    op.create_table(
        "admission_requirement_subject_options",
        sa.Column("subject_group_id", sa.Integer(), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "position > 0",
            name=op.f("ck_admission_requirement_subject_options_position_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["subject_group_id"],
            ["admission_requirement_subject_groups.id"],
            name=op.f(
                "fk_admission_requirement_subject_options_subject_group_id_"
                "admission_requirement_subject_groups"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"],
            ["admission_subjects.id"],
            name=op.f("fk_admission_requirement_subject_options_subject_id_admission_subjects"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "subject_group_id",
            "subject_id",
            name=op.f("pk_admission_requirement_subject_options"),
        ),
        sa.UniqueConstraint(
            "subject_group_id",
            "position",
            name="uq_admission_requirement_subject_options_position",
        ),
    )
    op.create_index(
        "ix_admission_requirement_subject_options_subject_id",
        "admission_requirement_subject_options",
        ["subject_id"],
        unique=False,
    )
    op.create_table(
        "admission_requirement_evidence_links",
        sa.Column("requirement_set_id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("locator", sa.String(length=500), nullable=True),
        sa.Column("evidence_note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["requirement_set_id"],
            ["program_admission_requirement_sets.id"],
            name=op.f(
                "fk_admission_requirement_evidence_links_requirement_set_id_"
                "program_admission_requirement_sets"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["admission_requirement_sources.id"],
            name=op.f(
                "fk_admission_requirement_evidence_links_source_id_admission_requirement_sources"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "requirement_set_id",
            "source_id",
            name=op.f("pk_admission_requirement_evidence_links"),
        ),
    )
    op.create_index(
        "ix_admission_requirement_evidence_links_source_id",
        "admission_requirement_evidence_links",
        ["source_id"],
        unique=False,
    )


def _refuse_nonempty_downgrade() -> None:
    connection = op.get_bind()
    nonempty = [
        table_name
        for table_name in NEW_TABLES
        if connection.execute(sa.text(f'SELECT 1 FROM "{table_name}" LIMIT 1')).first()
        is not None
    ]
    if nonempty:
        raise RuntimeError(
            "Refusing to downgrade admission requirements schema because data exists in: "
            + ", ".join(nonempty)
        )


def downgrade() -> None:
    _refuse_nonempty_downgrade()
    op.drop_index(
        "ix_admission_requirement_evidence_links_source_id",
        table_name="admission_requirement_evidence_links",
    )
    op.drop_table("admission_requirement_evidence_links")
    op.drop_index(
        "ix_admission_requirement_subject_options_subject_id",
        table_name="admission_requirement_subject_options",
    )
    op.drop_table("admission_requirement_subject_options")
    op.drop_index(
        "ix_admission_requirement_subject_groups_requirement_set_id",
        table_name="admission_requirement_subject_groups",
    )
    op.drop_table("admission_requirement_subject_groups")
    op.drop_index(
        "ix_program_admission_requirement_sets_program_year",
        table_name="program_admission_requirement_sets",
    )
    op.drop_index(
        "ix_program_admission_requirement_sets_program_id",
        table_name="program_admission_requirement_sets",
    )
    op.drop_index(
        "ix_program_admission_requirement_sets_admission_year",
        table_name="program_admission_requirement_sets",
    )
    op.drop_table("program_admission_requirement_sets")
    op.drop_index(
        "ix_admission_requirement_sources_university_id",
        table_name="admission_requirement_sources",
    )
    op.drop_index(
        "ix_admission_requirement_sources_admission_year",
        table_name="admission_requirement_sources",
    )
    op.drop_table("admission_requirement_sources")
    op.drop_table("admission_subjects")
