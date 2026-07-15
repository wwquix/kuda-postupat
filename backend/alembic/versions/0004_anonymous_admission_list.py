"""Add anonymous profiles and saved admission list targets."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_anonymous_admission_list"
down_revision: str | None = "0003_backfill_bseu_catalog"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "anonymous_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("personal_score", sa.Integer(), nullable=True),
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
            "personal_score IS NULL OR (personal_score >= 0 AND personal_score <= 500)",
            name=op.f("ck_anonymous_profiles_personal_score_range"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_anonymous_profiles")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_anonymous_profiles_token_hash")),
    )
    op.create_index(
        "ix_anonymous_profiles_updated_at", "anonymous_profiles", ["updated_at"], unique=False
    )
    op.create_table(
        "saved_universities",
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("university_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["anonymous_profiles.id"],
            name=op.f("fk_saved_universities_profile_id_anonymous_profiles"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["university_id"],
            ["universities.id"],
            name=op.f("fk_saved_universities_university_id_universities"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "profile_id", "university_id", name=op.f("pk_saved_universities")
        ),
    )
    op.create_index(
        "ix_saved_universities_university_id",
        "saved_universities",
        ["university_id"],
        unique=False,
    )
    op.create_table(
        "saved_programs",
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("program_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["anonymous_profiles.id"],
            name=op.f("fk_saved_programs_profile_id_anonymous_profiles"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["program_id"],
            ["programs.id"],
            name=op.f("fk_saved_programs_program_id_programs"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("profile_id", "program_id", name=op.f("pk_saved_programs")),
    )
    op.create_index(
        "ix_saved_programs_program_id", "saved_programs", ["program_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_saved_programs_program_id", table_name="saved_programs")
    op.drop_table("saved_programs")
    op.drop_index("ix_saved_universities_university_id", table_name="saved_universities")
    op.drop_table("saved_universities")
    op.drop_index("ix_anonymous_profiles_updated_at", table_name="anonymous_profiles")
    op.drop_table("anonymous_profiles")
