from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, MetaData, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Specialty(Base):
    __tablename__ = "specialties"
    __table_args__ = (UniqueConstraint("normalized_name", "study_form", "funding_type", name="uq_specialty"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    normalized_name: Mapped[str] = mapped_column(String(300), index=True)
    display_name: Mapped[str] = mapped_column(String(300))
    study_form: Mapped[str] = mapped_column(String(100))
    funding_type: Mapped[str] = mapped_column(String(50))
    source_url: Mapped[str] = mapped_column(String(1000))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    snapshots: Mapped[list["AdmissionSnapshot"]] = relationship(
        back_populates="specialty", cascade="all, delete-orphan"
    )


class AdmissionSnapshot(Base):
    __tablename__ = "admission_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    specialty_id: Mapped[int] = mapped_column(ForeignKey("specialties.id"), index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    admission_plan: Mapped[int] = mapped_column(Integer)
    applications_total: Mapped[int] = mapped_column(Integer)
    competition: Mapped[float] = mapped_column(Float)
    estimated_cutoff_min: Mapped[int | None] = mapped_column(Integer)
    estimated_cutoff_max: Mapped[int | None] = mapped_column(Integer)
    user_score: Mapped[int] = mapped_column(Integer)
    estimated_user_position: Mapped[int | None] = mapped_column(Integer)
    user_status: Mapped[str] = mapped_column(String(100))
    distribution_json: Mapped[str] = mapped_column(Text)
    raw_data_hash: Mapped[str] = mapped_column(String(64), index=True)
    specialty: Mapped[Specialty] = relationship(back_populates="snapshots")


class ScraperRun(Base):
    __tablename__ = "scraper_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), index=True)
    http_status: Mapped[int | None] = mapped_column(Integer)
    error_type: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    rows_found: Mapped[int] = mapped_column(Integer, default=0)
    content_hash: Mapped[str | None] = mapped_column(String(64))


class NotificationLog(Base):
    __tablename__ = "notification_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    message: Mapped[str] = mapped_column(Text)


class HttpCacheState(Base):
    __tablename__ = "http_cache_state"

    url: Mapped[str] = mapped_column(String(1000), primary_key=True)
    etag: Mapped[str | None] = mapped_column(String(500))
    last_modified: Mapped[str | None] = mapped_column(String(500))
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
