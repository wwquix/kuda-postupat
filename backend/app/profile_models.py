from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .catalog_models import Program, University, utc_now
from .models import Base


class AnonymousProfile(Base):
    __tablename__ = "anonymous_profiles"
    __table_args__ = (
        CheckConstraint(
            "personal_score IS NULL OR (personal_score >= 0 AND personal_score <= 500)",
            name="personal_score_range",
        ),
        Index("ix_anonymous_profiles_updated_at", "updated_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    personal_score: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, server_default=text("CURRENT_TIMESTAMP")
    )

    saved_universities: Mapped[list["SavedUniversity"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan", passive_deletes=True
    )
    saved_programs: Mapped[list["SavedProgram"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan", passive_deletes=True
    )


class SavedUniversity(Base):
    __tablename__ = "saved_universities"
    __table_args__ = (Index("ix_saved_universities_university_id", "university_id"),)

    profile_id: Mapped[int] = mapped_column(
        ForeignKey("anonymous_profiles.id", ondelete="CASCADE"), primary_key=True
    )
    university_id: Mapped[int] = mapped_column(
        ForeignKey("universities.id", ondelete="RESTRICT"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=text("CURRENT_TIMESTAMP")
    )

    profile: Mapped[AnonymousProfile] = relationship(back_populates="saved_universities")
    university: Mapped[University] = relationship()


class SavedProgram(Base):
    __tablename__ = "saved_programs"
    __table_args__ = (Index("ix_saved_programs_program_id", "program_id"),)

    profile_id: Mapped[int] = mapped_column(
        ForeignKey("anonymous_profiles.id", ondelete="CASCADE"), primary_key=True
    )
    program_id: Mapped[int] = mapped_column(
        ForeignKey("programs.id", ondelete="RESTRICT"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=text("CURRENT_TIMESTAMP")
    )

    profile: Mapped[AnonymousProfile] = relationship(back_populates="saved_programs")
    program: Mapped[Program] = relationship()
