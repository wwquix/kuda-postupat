"""Add anonymous BSEU Program watches and in-app events."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_anonymous_program_watchlist"
down_revision: str | None = "0004_anonymous_admission_list"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EVENT_KINDS = (
    "applications_total_changed",
    "estimated_cutoff_changed",
    "user_position_changed",
    "user_status_changed",
)


def upgrade() -> None:
    op.create_table(
        "program_watches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("program_id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("last_evaluated_snapshot_id", sa.Integer(), nullable=True),
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
        sa.CheckConstraint("enabled IN (0, 1)", name=op.f("ck_program_watches_enabled_boolean")),
        sa.ForeignKeyConstraint(
            ["last_evaluated_snapshot_id"],
            ["admission_snapshots.id"],
            name=op.f("fk_program_watches_last_evaluated_snapshot_id_admission_snapshots"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["anonymous_profiles.id"],
            name=op.f("fk_program_watches_profile_id_anonymous_profiles"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["program_id"],
            ["programs.id"],
            name=op.f("fk_program_watches_program_id_programs"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_program_watches")),
        sa.UniqueConstraint(
            "profile_id",
            "program_id",
            name="uq_program_watches_profile_program",
        ),
    )
    op.create_index(
        "ix_program_watches_profile_enabled",
        "program_watches",
        ["profile_id", "enabled"],
        unique=False,
    )
    op.create_index(
        "ix_program_watches_program_enabled",
        "program_watches",
        ["program_id", "enabled"],
        unique=False,
    )
    op.create_table(
        "program_watch_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("watch_id", sa.Integer(), nullable=False),
        sa.Column("source_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("event_kind", sa.String(length=64), nullable=False),
        sa.Column("previous_value", sa.JSON(), nullable=False),
        sa.Column("current_value", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "event_kind IN (" + ", ".join(f"'{kind}'" for kind in EVENT_KINDS) + ")",
            name=op.f("ck_program_watch_events_event_kind_supported"),
        ),
        sa.ForeignKeyConstraint(
            ["source_snapshot_id"],
            ["admission_snapshots.id"],
            name=op.f("fk_program_watch_events_source_snapshot_id_admission_snapshots"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["watch_id"],
            ["program_watches.id"],
            name=op.f("fk_program_watch_events_watch_id_program_watches"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_program_watch_events")),
        sa.UniqueConstraint(
            "watch_id",
            "source_snapshot_id",
            "event_kind",
            name="uq_program_watch_events_watch_snapshot_kind",
        ),
    )
    op.create_index(
        "ix_program_watch_events_source_snapshot_id",
        "program_watch_events",
        ["source_snapshot_id"],
        unique=False,
    )
    op.create_index(
        "ix_program_watch_events_watch_created",
        "program_watch_events",
        ["watch_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_program_watch_events_watch_created", table_name="program_watch_events")
    op.drop_index(
        "ix_program_watch_events_source_snapshot_id", table_name="program_watch_events"
    )
    op.drop_table("program_watch_events")
    op.drop_index("ix_program_watches_program_enabled", table_name="program_watches")
    op.drop_index("ix_program_watches_profile_enabled", table_name="program_watches")
    op.drop_table("program_watches")
