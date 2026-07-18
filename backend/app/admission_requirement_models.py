from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .catalog_models import Program, University, enum_type, utc_now
from .models import Base


class AssessmentKind(str, Enum):
    EXTERNAL_STANDARDIZED = "external_standardized"
    INTERNAL_WRITTEN_EXAMINATION = "internal_written_examination"
    INTERNAL_ORAL_EXAMINATION = "internal_oral_examination"
    OTHER = "other"


def validate_subject_group_options(*, choose_count: int, option_count: int) -> None:
    """Validate the cross-row invariant before an importer persists a group."""
    if choose_count <= 0:
        raise ValueError("choose_count must be positive")
    if option_count <= 0:
        raise ValueError("a requirement subject group must have at least one option")
    if choose_count > option_count:
        raise ValueError("choose_count cannot exceed the number of subject options")


class AdmissionSubject(Base):
    __tablename__ = "admission_subjects"
    __table_args__ = (
        CheckConstraint("length(trim(normalized_key)) > 0", name="normalized_key_not_blank"),
        CheckConstraint("length(trim(official_label_ru)) > 0", name="official_label_ru_not_blank"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    normalized_key: Mapped[str] = mapped_column(String(150), unique=True)
    official_label_ru: Mapped[str] = mapped_column(String(300))
    official_label_be: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, server_default=text("CURRENT_TIMESTAMP")
    )


class AdmissionRequirementSource(Base):
    __tablename__ = "admission_requirement_sources"
    __table_args__ = (
        UniqueConstraint("university_id", "source_key", name="uq_admission_requirement_sources_identity"),
        CheckConstraint("length(trim(source_key)) > 0", name="source_key_not_blank"),
        CheckConstraint("length(trim(official_url)) > 0", name="official_url_not_blank"),
        CheckConstraint("length(trim(official_title)) > 0", name="official_title_not_blank"),
        CheckConstraint("length(trim(publisher)) > 0", name="publisher_not_blank"),
        CheckConstraint("length(trim(source_type)) > 0", name="source_type_not_blank"),
        CheckConstraint(
            "publication_year IS NULL OR (publication_year >= 2000 AND publication_year <= 2100)",
            name="publication_year_range",
        ),
        CheckConstraint(
            "admission_year IS NULL OR (admission_year >= 2000 AND admission_year <= 2100)",
            name="admission_year_range",
        ),
        Index("ix_admission_requirement_sources_university_id", "university_id"),
        Index("ix_admission_requirement_sources_admission_year", "admission_year"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    university_id: Mapped[int] = mapped_column(ForeignKey("universities.id", ondelete="RESTRICT"))
    source_key: Mapped[str] = mapped_column(String(200))
    official_url: Mapped[str] = mapped_column(String(1000))
    official_title: Mapped[str] = mapped_column(String(1000))
    publisher: Mapped[str] = mapped_column(String(500))
    source_type: Mapped[str] = mapped_column(String(100))
    publication_year: Mapped[int | None] = mapped_column(Integer)
    admission_year: Mapped[int | None] = mapped_column(Integer)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    content_hash: Mapped[str | None] = mapped_column(String(128))
    evidence_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, server_default=text("CURRENT_TIMESTAMP")
    )

    university: Mapped[University] = relationship()


class ProgramAdmissionRequirementSet(Base):
    __tablename__ = "program_admission_requirement_sets"
    __table_args__ = (
        UniqueConstraint(
            "program_id",
            "admission_year",
            "stable_key",
            name="uq_program_admission_requirement_sets_business_key",
        ),
        CheckConstraint("length(trim(stable_key)) > 0", name="stable_key_not_blank"),
        CheckConstraint("length(trim(pathway_code)) > 0", name="pathway_code_not_blank"),
        CheckConstraint("length(trim(pathway_label)) > 0", name="pathway_label_not_blank"),
        CheckConstraint("admission_year >= 2000 AND admission_year <= 2100", name="admission_year_range"),
        Index("ix_program_admission_requirement_sets_program_id", "program_id"),
        Index("ix_program_admission_requirement_sets_admission_year", "admission_year"),
        Index(
            "ix_program_admission_requirement_sets_program_year",
            "program_id",
            "admission_year",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    program_id: Mapped[int] = mapped_column(ForeignKey("programs.id", ondelete="RESTRICT"))
    stable_key: Mapped[str] = mapped_column(String(300))
    admission_year: Mapped[int] = mapped_column(Integer)
    pathway_code: Mapped[str] = mapped_column(String(150))
    pathway_label: Mapped[str] = mapped_column(String(300))
    study_form: Mapped[str | None] = mapped_column(String(100))
    study_form_label: Mapped[str | None] = mapped_column(String(300))
    funding_applicability: Mapped[str | None] = mapped_column(String(300))
    education_basis: Mapped[str | None] = mapped_column(String(200))
    track_description: Mapped[str | None] = mapped_column(String(300))
    applicability_note: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("1"))
    source_checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, server_default=text("CURRENT_TIMESTAMP")
    )

    program: Mapped[Program] = relationship()
    subject_groups: Mapped[list[AdmissionRequirementSubjectGroup]] = relationship(
        back_populates="requirement_set",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="AdmissionRequirementSubjectGroup.position",
    )
    evidence_links: Mapped[list[AdmissionRequirementEvidenceLink]] = relationship(
        back_populates="requirement_set",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class AdmissionRequirementSubjectGroup(Base):
    __tablename__ = "admission_requirement_subject_groups"
    __table_args__ = (
        UniqueConstraint(
            "requirement_set_id",
            "stable_key",
            name="uq_admission_requirement_subject_groups_stable_key",
        ),
        UniqueConstraint(
            "requirement_set_id",
            "position",
            name="uq_admission_requirement_subject_groups_position",
        ),
        CheckConstraint("length(trim(stable_key)) > 0", name="stable_key_not_blank"),
        CheckConstraint("position > 0", name="position_positive"),
        CheckConstraint("choose_count > 0", name="choose_count_positive"),
        Index("ix_admission_requirement_subject_groups_requirement_set_id", "requirement_set_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    requirement_set_id: Mapped[int] = mapped_column(
        ForeignKey("program_admission_requirement_sets.id", ondelete="CASCADE")
    )
    stable_key: Mapped[str] = mapped_column(String(150))
    position: Mapped[int] = mapped_column(Integer)
    choose_count: Mapped[int] = mapped_column(Integer)
    assessment_kind: Mapped[AssessmentKind] = mapped_column(
        enum_type(AssessmentKind, "admission_assessment_kind")
    )
    official_assessment_label: Mapped[str | None] = mapped_column(String(300))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=text("CURRENT_TIMESTAMP")
    )

    requirement_set: Mapped[ProgramAdmissionRequirementSet] = relationship(back_populates="subject_groups")
    subject_options: Mapped[list[AdmissionRequirementSubjectOption]] = relationship(
        back_populates="subject_group",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="AdmissionRequirementSubjectOption.position",
    )


class AdmissionRequirementSubjectOption(Base):
    __tablename__ = "admission_requirement_subject_options"
    __table_args__ = (
        UniqueConstraint(
            "subject_group_id",
            "position",
            name="uq_admission_requirement_subject_options_position",
        ),
        CheckConstraint("position > 0", name="position_positive"),
        Index("ix_admission_requirement_subject_options_subject_id", "subject_id"),
    )

    subject_group_id: Mapped[int] = mapped_column(
        ForeignKey("admission_requirement_subject_groups.id", ondelete="CASCADE"),
        primary_key=True,
    )
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("admission_subjects.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    position: Mapped[int] = mapped_column(Integer)

    subject_group: Mapped[AdmissionRequirementSubjectGroup] = relationship(back_populates="subject_options")
    subject: Mapped[AdmissionSubject] = relationship()


class AdmissionRequirementEvidenceLink(Base):
    __tablename__ = "admission_requirement_evidence_links"
    __table_args__ = (Index("ix_admission_requirement_evidence_links_source_id", "source_id"),)

    requirement_set_id: Mapped[int] = mapped_column(
        ForeignKey("program_admission_requirement_sets.id", ondelete="CASCADE"),
        primary_key=True,
    )
    source_id: Mapped[int] = mapped_column(
        ForeignKey("admission_requirement_sources.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    locator: Mapped[str | None] = mapped_column(String(500))
    evidence_note: Mapped[str | None] = mapped_column(Text)

    requirement_set: Mapped[ProgramAdmissionRequirementSet] = relationship(back_populates="evidence_links")
    source: Mapped[AdmissionRequirementSource] = relationship()
