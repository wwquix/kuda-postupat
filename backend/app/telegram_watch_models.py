from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .catalog_models import utc_now
from .models import Base
from .profile_models import AnonymousProfile
from .watch_models import ProgramWatchEvent

TELEGRAM_DELIVERY_STATES = ("pending", "retryable", "failed", "confirmed")


class TelegramProfileLink(Base):
    __tablename__ = "telegram_profile_links"
    __table_args__ = (
        Index(
            "uq_telegram_profile_links_active_profile",
            "profile_id",
            unique=True,
            sqlite_where=text("unlinked_at IS NULL"),
        ),
        Index(
            "uq_telegram_profile_links_active_chat",
            "telegram_chat_id",
            unique=True,
            sqlite_where=text("unlinked_at IS NULL"),
        ),
        Index("ix_telegram_profile_links_profile_linked", "profile_id", "linked_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("anonymous_profiles.id", ondelete="CASCADE")
    )
    telegram_chat_id: Mapped[str] = mapped_column(String(32))
    linked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=text("CURRENT_TIMESTAMP")
    )
    unlinked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    profile: Mapped[AnonymousProfile] = relationship(back_populates="telegram_links")
    deliveries: Mapped[list["TelegramWatchDelivery"]] = relationship(
        back_populates="profile_link", cascade="all, delete-orphan", passive_deletes=True
    )


class TelegramLinkChallenge(Base):
    __tablename__ = "telegram_link_challenges"
    __table_args__ = (
        Index(
            "ix_telegram_link_challenges_profile_expiry",
            "profile_id",
            "expires_at",
        ),
        Index("ix_telegram_link_challenges_consumed_at", "consumed_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("anonymous_profiles.id", ondelete="CASCADE")
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=text("CURRENT_TIMESTAMP")
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    profile: Mapped[AnonymousProfile] = relationship(back_populates="telegram_link_challenges")


class TelegramWatchDelivery(Base):
    __tablename__ = "telegram_watch_deliveries"
    __table_args__ = (
        UniqueConstraint(
            "watch_event_id",
            "profile_link_id",
            name="uq_telegram_watch_deliveries_event_link",
        ),
        CheckConstraint(
            "state IN (" + ", ".join(f"'{state}'" for state in TELEGRAM_DELIVERY_STATES) + ")",
            name="state_supported",
        ),
        CheckConstraint(
            "attempt_count >= 0 AND attempt_count <= 3",
            name="attempt_count_range",
        ),
        Index("ix_telegram_watch_deliveries_state_attempts", "state", "attempt_count"),
        Index("ix_telegram_watch_deliveries_event_id", "watch_event_id"),
        Index("ix_telegram_watch_deliveries_link_id", "profile_link_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    watch_event_id: Mapped[int] = mapped_column(
        ForeignKey("program_watch_events.id", ondelete="CASCADE")
    )
    profile_link_id: Mapped[int] = mapped_column(
        ForeignKey("telegram_profile_links.id", ondelete="CASCADE")
    )
    state: Mapped[str] = mapped_column(String(24), default="pending", server_default="pending")
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_summary: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    watch_event: Mapped[ProgramWatchEvent] = relationship(back_populates="telegram_deliveries")
    profile_link: Mapped[TelegramProfileLink] = relationship(back_populates="deliveries")
