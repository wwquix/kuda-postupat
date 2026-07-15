"""Add Telegram profile linking and WatchEvent delivery state."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_telegram_watch_notifications"
down_revision: str | None = "0005_anonymous_program_watchlist"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DELIVERY_STATES = ("pending", "retryable", "failed", "confirmed")


def upgrade() -> None:
    op.create_table(
        "telegram_profile_links",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("telegram_chat_id", sa.String(length=32), nullable=False),
        sa.Column(
            "linked_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("unlinked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["anonymous_profiles.id"],
            name=op.f("fk_telegram_profile_links_profile_id_anonymous_profiles"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_telegram_profile_links")),
    )
    op.create_index(
        "ix_telegram_profile_links_profile_linked",
        "telegram_profile_links",
        ["profile_id", "linked_at"],
        unique=False,
    )
    op.create_index(
        "uq_telegram_profile_links_active_profile",
        "telegram_profile_links",
        ["profile_id"],
        unique=True,
        sqlite_where=sa.text("unlinked_at IS NULL"),
    )
    op.create_index(
        "uq_telegram_profile_links_active_chat",
        "telegram_profile_links",
        ["telegram_chat_id"],
        unique=True,
        sqlite_where=sa.text("unlinked_at IS NULL"),
    )

    op.create_table(
        "telegram_link_challenges",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["anonymous_profiles.id"],
            name=op.f("fk_telegram_link_challenges_profile_id_anonymous_profiles"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_telegram_link_challenges")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_telegram_link_challenges_token_hash")),
    )
    op.create_index(
        "ix_telegram_link_challenges_profile_expiry",
        "telegram_link_challenges",
        ["profile_id", "expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_telegram_link_challenges_consumed_at",
        "telegram_link_challenges",
        ["consumed_at"],
        unique=False,
    )

    op.create_table(
        "telegram_watch_deliveries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("watch_event_id", sa.Integer(), nullable=False),
        sa.Column("profile_link_id", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=24), server_default="pending", nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_summary", sa.String(length=200), nullable=True),
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
            "state IN (" + ", ".join(f"'{state}'" for state in DELIVERY_STATES) + ")",
            name=op.f("ck_telegram_watch_deliveries_state_supported"),
        ),
        sa.CheckConstraint(
            "attempt_count >= 0 AND attempt_count <= 3",
            name=op.f("ck_telegram_watch_deliveries_attempt_count_range"),
        ),
        sa.ForeignKeyConstraint(
            ["profile_link_id"],
            ["telegram_profile_links.id"],
            name=op.f("fk_telegram_watch_deliveries_profile_link_id_telegram_profile_links"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["watch_event_id"],
            ["program_watch_events.id"],
            name=op.f("fk_telegram_watch_deliveries_watch_event_id_program_watch_events"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_telegram_watch_deliveries")),
        sa.UniqueConstraint(
            "watch_event_id",
            "profile_link_id",
            name="uq_telegram_watch_deliveries_event_link",
        ),
    )
    op.create_index(
        "ix_telegram_watch_deliveries_state_attempts",
        "telegram_watch_deliveries",
        ["state", "attempt_count"],
        unique=False,
    )
    op.create_index(
        "ix_telegram_watch_deliveries_event_id",
        "telegram_watch_deliveries",
        ["watch_event_id"],
        unique=False,
    )
    op.create_index(
        "ix_telegram_watch_deliveries_link_id",
        "telegram_watch_deliveries",
        ["profile_link_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_telegram_watch_deliveries_link_id", table_name="telegram_watch_deliveries")
    op.drop_index("ix_telegram_watch_deliveries_event_id", table_name="telegram_watch_deliveries")
    op.drop_index(
        "ix_telegram_watch_deliveries_state_attempts",
        table_name="telegram_watch_deliveries",
    )
    op.drop_table("telegram_watch_deliveries")
    op.drop_index(
        "ix_telegram_link_challenges_consumed_at",
        table_name="telegram_link_challenges",
    )
    op.drop_index(
        "ix_telegram_link_challenges_profile_expiry",
        table_name="telegram_link_challenges",
    )
    op.drop_table("telegram_link_challenges")
    op.drop_index(
        "uq_telegram_profile_links_active_chat",
        table_name="telegram_profile_links",
    )
    op.drop_index(
        "uq_telegram_profile_links_active_profile",
        table_name="telegram_profile_links",
    )
    op.drop_index(
        "ix_telegram_profile_links_profile_linked",
        table_name="telegram_profile_links",
    )
    op.drop_table("telegram_profile_links")
