from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .catalog_models import Program, utc_now
from .models import AdmissionSnapshot, Base
from .profile_models import AnonymousProfile

if TYPE_CHECKING:
    from .telegram_watch_models import TelegramWatchDelivery

WATCH_EVENT_KINDS = (
    "applications_total_changed",
    "estimated_cutoff_changed",
    "user_position_changed",
    "user_status_changed",
)


class ProgramWatch(Base):
    __tablename__ = "program_watches"
    __table_args__ = (
        UniqueConstraint("profile_id", "program_id", name="uq_program_watches_profile_program"),
        CheckConstraint("enabled IN (0, 1)", name="enabled_boolean"),
        Index("ix_program_watches_program_enabled", "program_id", "enabled"),
        Index("ix_program_watches_profile_enabled", "profile_id", "enabled"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("anonymous_profiles.id", ondelete="CASCADE")
    )
    program_id: Mapped[int] = mapped_column(ForeignKey("programs.id", ondelete="RESTRICT"))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("1"))
    last_evaluated_snapshot_id: Mapped[int | None] = mapped_column(
        ForeignKey("admission_snapshots.id", ondelete="RESTRICT"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    profile: Mapped[AnonymousProfile] = relationship(back_populates="program_watches")
    program: Mapped[Program] = relationship()
    last_evaluated_snapshot: Mapped[AdmissionSnapshot | None] = relationship(
        foreign_keys=[last_evaluated_snapshot_id]
    )
    events: Mapped[list["ProgramWatchEvent"]] = relationship(
        back_populates="watch", cascade="all, delete-orphan", passive_deletes=True
    )


class ProgramWatchEvent(Base):
    __tablename__ = "program_watch_events"
    __table_args__ = (
        UniqueConstraint(
            "watch_id",
            "source_snapshot_id",
            "event_kind",
            name="uq_program_watch_events_watch_snapshot_kind",
        ),
        CheckConstraint(
            "event_kind IN ("
            + ", ".join(f"'{kind}'" for kind in WATCH_EVENT_KINDS)
            + ")",
            name="event_kind_supported",
        ),
        Index("ix_program_watch_events_watch_created", "watch_id", "created_at"),
        Index("ix_program_watch_events_source_snapshot_id", "source_snapshot_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    watch_id: Mapped[int] = mapped_column(
        ForeignKey("program_watches.id", ondelete="CASCADE")
    )
    source_snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("admission_snapshots.id", ondelete="RESTRICT")
    )
    event_kind: Mapped[str] = mapped_column(String(64))
    previous_value: Mapped[object] = mapped_column(JSON)
    current_value: Mapped[object] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=text("CURRENT_TIMESTAMP")
    )

    watch: Mapped[ProgramWatch] = relationship(back_populates="events")
    source_snapshot: Mapped[AdmissionSnapshot] = relationship()
    telegram_deliveries: Mapped[list["TelegramWatchDelivery"]] = relationship(
        back_populates="watch_event", cascade="all, delete-orphan", passive_deletes=True
    )
