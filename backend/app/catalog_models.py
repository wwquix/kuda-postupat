from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy import (
    Enum as SqlEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .models import Base

if TYPE_CHECKING:
    from .models import AdmissionSnapshot, ScraperRun, Specialty


def utc_now() -> datetime:
    return datetime.now(UTC)


class InstitutionKind(str, Enum):
    UNIVERSITY = "university"
    ACADEMY = "academy"
    INSTITUTE = "institute"
    CONSERVATORY = "conservatory"
    MILITARY_ACADEMY = "military_academy"
    OTHER = "other"


class OwnershipType(str, Enum):
    STATE = "state"
    PRIVATE = "private"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class MonitoringStatus(str, Enum):
    ONLINE = "online"
    PARTIAL = "partial"
    PERIODIC = "periodic"
    REFERENCE_ONLY = "reference_only"
    UNSUPPORTED = "unsupported"
    BROKEN = "broken"
    NEEDS_REVIEW = "needs_review"


class StudyForm(str, Enum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    DISTANCE = "distance"
    EVENING = "evening"
    OTHER = "other"


class FundingType(str, Enum):
    BUDGET = "budget"
    PAID = "paid"
    TARGETED = "targeted"
    SEPARATE_COMPETITION = "separate_competition"
    OTHER = "other"


class SourceHealth(str, Enum):
    HEALTHY = "healthy"
    STALE = "stale"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


def enum_type(enum_class: type[Enum], name: str) -> SqlEnum:
    return SqlEnum(
        enum_class,
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        values_callable=lambda members: [item.value for item in members],
    )


class University(Base):
    __tablename__ = "universities"
    __table_args__ = (
        CheckConstraint("length(trim(code)) > 0", name="code_not_blank"),
        CheckConstraint("length(trim(slug)) > 0", name="slug_not_blank"),
        Index("ix_universities_city", "city"),
        Index("ix_universities_region", "region"),
        Index("ix_universities_monitoring_status", "monitoring_status"),
        Index("ix_universities_active", "active"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    slug: Mapped[str] = mapped_column(String(200), unique=True)
    short_name: Mapped[str] = mapped_column(String(300))
    full_name: Mapped[str] = mapped_column(String(500))
    institution_kind: Mapped[InstitutionKind] = mapped_column(enum_type(InstitutionKind, "institution_kind"))
    ownership_type: Mapped[OwnershipType] = mapped_column(enum_type(OwnershipType, "ownership_type"))
    city: Mapped[str | None] = mapped_column(String(200))
    region: Mapped[str | None] = mapped_column(String(200))
    official_site_url: Mapped[str] = mapped_column(String(1000))
    admissions_url: Mapped[str | None] = mapped_column(String(1000))
    description: Mapped[str | None] = mapped_column(Text)
    monitoring_status: Mapped[MonitoringStatus] = mapped_column(enum_type(MonitoringStatus, "monitoring_status"))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("1"))
    source_url: Mapped[str] = mapped_column(String(1000))
    source_checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    data_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, server_default=text("CURRENT_TIMESTAMP")
    )

    programs: Mapped[list["Program"]] = relationship(back_populates="university", passive_deletes=True)
    category_links: Mapped[list["UniversityCategoryLink"]] = relationship(
        back_populates="university", cascade="all, delete-orphan", passive_deletes=True
    )
    categories: Mapped[list["UniversityCategory"]] = relationship(
        secondary="university_category_links", back_populates="universities", viewonly=True
    )
    data_sources: Mapped[list["DataSource"]] = relationship(back_populates="university", passive_deletes=True)


class UniversityCategory(Base):
    __tablename__ = "university_categories"
    __table_args__ = (CheckConstraint("length(trim(code)) > 0", name="code_not_blank"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(100), unique=True)
    label_ru: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=text("CURRENT_TIMESTAMP")
    )

    university_links: Mapped[list["UniversityCategoryLink"]] = relationship(
        back_populates="category", cascade="all, delete-orphan", passive_deletes=True
    )
    universities: Mapped[list[University]] = relationship(
        secondary="university_category_links", back_populates="categories", viewonly=True
    )


class UniversityCategoryLink(Base):
    __tablename__ = "university_category_links"
    __table_args__ = (Index("ix_university_category_links_category_id", "category_id"),)

    university_id: Mapped[int] = mapped_column(
        ForeignKey("universities.id", ondelete="CASCADE"), primary_key=True
    )
    category_id: Mapped[int] = mapped_column(
        ForeignKey("university_categories.id", ondelete="CASCADE"), primary_key=True
    )

    university: Mapped[University] = relationship(back_populates="category_links")
    category: Mapped[UniversityCategory] = relationship(back_populates="university_links")


class Program(Base):
    __tablename__ = "programs"
    __table_args__ = (
        UniqueConstraint("university_id", "slug", name="uq_programs_university_slug"),
        CheckConstraint("length(trim(slug)) > 0", name="slug_not_blank"),
        Index("ix_programs_university_id", "university_id"),
        Index("ix_programs_name", "name"),
        Index("ix_programs_active", "active"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    university_id: Mapped[int] = mapped_column(ForeignKey("universities.id", ondelete="RESTRICT"))
    code: Mapped[str | None] = mapped_column(String(100))
    slug: Mapped[str] = mapped_column(String(240))
    name: Mapped[str] = mapped_column(String(500))
    qualification: Mapped[str | None] = mapped_column(String(300))
    faculty_name: Mapped[str | None] = mapped_column(String(300))
    education_level: Mapped[str | None] = mapped_column(String(100))
    duration_years: Mapped[float | None] = mapped_column(Float)
    description: Mapped[str | None] = mapped_column(Text)
    admission_subjects_json: Mapped[str | None] = mapped_column(Text)
    career_fields_json: Mapped[str | None] = mapped_column(Text)
    category_tags_json: Mapped[str | None] = mapped_column(Text)
    official_url: Mapped[str] = mapped_column(String(1000))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("1"))
    source_checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, server_default=text("CURRENT_TIMESTAMP")
    )

    university: Mapped[University] = relationship(back_populates="programs")
    offerings: Mapped[list["ProgramOffering"]] = relationship(back_populates="program", passive_deletes=True)
    legacy_mappings: Mapped[list["LegacySpecialtyMapping"]] = relationship(
        back_populates="program", passive_deletes=True
    )


class ProgramOffering(Base):
    __tablename__ = "program_offerings"
    __table_args__ = (
        UniqueConstraint(
            "program_id",
            "admission_year",
            "study_form",
            "funding_type",
            name="uq_program_offerings_business_key",
        ),
        CheckConstraint("admission_year >= 2000 AND admission_year <= 2100", name="admission_year_range"),
        CheckConstraint("places IS NULL OR places >= 0", name="places_non_negative"),
        Index("ix_program_offerings_program_id", "program_id"),
        Index("ix_program_offerings_admission_year", "admission_year"),
        Index("ix_program_offerings_study_form", "study_form"),
        Index("ix_program_offerings_funding_type", "funding_type"),
        Index("ix_program_offerings_monitoring_status", "monitoring_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    program_id: Mapped[int] = mapped_column(ForeignKey("programs.id", ondelete="RESTRICT"))
    admission_year: Mapped[int] = mapped_column(Integer)
    study_form: Mapped[StudyForm] = mapped_column(enum_type(StudyForm, "study_form"))
    funding_type: Mapped[FundingType] = mapped_column(enum_type(FundingType, "funding_type"))
    places: Mapped[int | None] = mapped_column(Integer)
    application_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    monitoring_supported: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("0"))
    monitoring_status: Mapped[MonitoringStatus] = mapped_column(enum_type(MonitoringStatus, "monitoring_status"))
    official_url: Mapped[str] = mapped_column(String(1000))
    source_url: Mapped[str] = mapped_column(String(1000))
    source_checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, server_default=text("CURRENT_TIMESTAMP")
    )

    program: Mapped[Program] = relationship(back_populates="offerings")
    legacy_mapping: Mapped["LegacySpecialtyMapping | None"] = relationship(
        back_populates="program_offering", uselist=False, passive_deletes=True
    )
    legacy_snapshots: Mapped[list["AdmissionSnapshot"]] = relationship(
        back_populates="program_offering", passive_deletes=True
    )


class DataSource(Base):
    __tablename__ = "data_sources"
    __table_args__ = (
        UniqueConstraint("university_id", "source_type", "source_url", name="uq_data_sources_identity"),
        CheckConstraint("length(trim(source_type)) > 0", name="source_type_not_blank"),
        CheckConstraint(
            "refresh_interval_minutes IS NULL OR refresh_interval_minutes >= 5",
            name="refresh_interval_minimum",
        ),
        CheckConstraint("consecutive_failures >= 0", name="consecutive_failures_non_negative"),
        Index("ix_data_sources_university_id", "university_id"),
        Index("ix_data_sources_health_status", "health_status"),
        Index("ix_data_sources_enabled", "enabled"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    university_id: Mapped[int] = mapped_column(ForeignKey("universities.id", ondelete="RESTRICT"))
    source_type: Mapped[str] = mapped_column(String(100))
    source_url: Mapped[str] = mapped_column(String(1000))
    adapter_name: Mapped[str | None] = mapped_column(String(200))
    refresh_interval_minutes: Mapped[int | None] = mapped_column(Integer)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("1"))
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_type: Mapped[str | None] = mapped_column(String(200))
    last_error_message: Mapped[str | None] = mapped_column(Text)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    health_status: Mapped[SourceHealth] = mapped_column(
        enum_type(SourceHealth, "source_health"), default=SourceHealth.UNKNOWN, server_default="unknown"
    )
    etag: Mapped[str | None] = mapped_column(String(500))
    last_modified: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, server_default=text("CURRENT_TIMESTAMP")
    )

    university: Mapped[University] = relationship(back_populates="data_sources")
    legacy_scraper_runs: Mapped[list["ScraperRun"]] = relationship(
        back_populates="data_source", passive_deletes=True
    )


class LegacySpecialtyMapping(Base):
    __tablename__ = "legacy_specialty_mappings"
    __table_args__ = (
        UniqueConstraint("program_offering_id", name="uq_legacy_specialty_mappings_offering"),
        CheckConstraint("mapping_version >= 1", name="mapping_version_positive"),
        Index("ix_legacy_specialty_mappings_program_id", "program_id"),
    )

    legacy_specialty_id: Mapped[int] = mapped_column(
        ForeignKey("specialties.id", ondelete="RESTRICT"), primary_key=True
    )
    program_id: Mapped[int] = mapped_column(ForeignKey("programs.id", ondelete="RESTRICT"))
    program_offering_id: Mapped[int] = mapped_column(
        ForeignKey("program_offerings.id", ondelete="RESTRICT")
    )
    mapping_version: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"))
    mapped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=text("CURRENT_TIMESTAMP")
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)

    legacy_specialty: Mapped["Specialty"] = relationship(back_populates="catalog_mapping")
    program: Mapped[Program] = relationship(back_populates="legacy_mappings")
    program_offering: Mapped[ProgramOffering] = relationship(back_populates="legacy_mapping")
