from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from .catalog_models import (
    DataSource,
    FundingType,
    LegacySpecialtyMapping,
    Program,
    ProgramOffering,
    StudyForm,
    University,
)
from .models import AdmissionSnapshot, ScraperRun, Specialty

BSEU_CODE = "bseu"
BSEU_PROGRAM_CODE = "6-05-0311-05"
BSEU_ADMISSION_YEAR = 2026
BSEU_LEGACY_NAME = "экономическая информатика"
BSEU_LEGACY_STUDY_FORM = "дневная"
BSEU_LEGACY_FUNDING_TYPE = "платная"


class BseuMappingError(RuntimeError):
    pass


def _canonical_target(session: Session) -> tuple[Program, ProgramOffering]:
    university = session.scalar(select(University).where(University.code == BSEU_CODE))
    if university is None:
        raise BseuMappingError("Canonical BSEU university is missing")
    program = session.scalar(
        select(Program).where(
            Program.university_id == university.id,
            Program.code == BSEU_PROGRAM_CODE,
        )
    )
    if program is None:
        raise BseuMappingError("Canonical BSEU Economic Informatics program is missing")
    offering = session.scalar(
        select(ProgramOffering).where(
            ProgramOffering.program_id == program.id,
            ProgramOffering.admission_year == BSEU_ADMISSION_YEAR,
            ProgramOffering.study_form == StudyForm.FULL_TIME,
            ProgramOffering.funding_type == FundingType.PAID,
        )
    )
    if offering is None:
        raise BseuMappingError("Canonical BSEU 2026 full-time paid offering is missing")
    return program, offering


def is_bseu_target_specialty(specialty: Specialty) -> bool:
    return (
        specialty.normalized_name == BSEU_LEGACY_NAME
        and specialty.study_form == BSEU_LEGACY_STUDY_FORM
        and specialty.funding_type == BSEU_LEGACY_FUNDING_TYPE
    )


def ensure_bseu_mapping_for_specialty(session: Session, specialty: Specialty) -> int | None:
    """Create only the additive legacy mapping needed by a fresh database first refresh."""
    if not is_bseu_target_specialty(specialty):
        return None
    program, offering = _canonical_target(session)
    mapping = session.get(LegacySpecialtyMapping, specialty.id)
    if mapping is None:
        target_mapping = session.scalar(
            select(LegacySpecialtyMapping).where(
                LegacySpecialtyMapping.program_offering_id == offering.id
            )
        )
        if target_mapping is not None:
            raise BseuMappingError("Canonical BSEU offering is already mapped to another legacy specialty")
        mapping = LegacySpecialtyMapping(
            legacy_specialty_id=specialty.id,
            program_id=program.id,
            program_offering_id=offering.id,
            mapping_version=1,
            notes="BSEU 2026 full-time paid compatibility mapping",
        )
        session.add(mapping)
        session.flush()
    elif mapping.program_id != program.id or mapping.program_offering_id != offering.id:
        raise BseuMappingError("Legacy BSEU specialty has a conflicting canonical mapping")
    conflict = session.scalar(
        select(AdmissionSnapshot.id).where(
            AdmissionSnapshot.specialty_id == specialty.id,
            AdmissionSnapshot.program_offering_id.is_not(None),
            AdmissionSnapshot.program_offering_id != offering.id,
        )
    )
    if conflict is not None:
        raise BseuMappingError("Legacy BSEU snapshot has a conflicting canonical offering")
    session.execute(
        update(AdmissionSnapshot)
        .where(
            AdmissionSnapshot.specialty_id == specialty.id,
            AdmissionSnapshot.program_offering_id.is_(None),
        )
        .values(program_offering_id=offering.id)
    )
    return offering.id


def verify_bseu_backfill(session: Session) -> dict[str, int]:
    """Read-only consistency check used by the CLI and tests."""
    program, offering = _canonical_target(session)
    university_id = program.university_id
    university_count = session.scalar(
        select(func.count()).select_from(University).where(University.code == BSEU_CODE)
    )
    offering_ids = session.scalars(
        select(ProgramOffering.id).where(
            ProgramOffering.program_id == program.id,
            ProgramOffering.admission_year == BSEU_ADMISSION_YEAR,
            ProgramOffering.study_form == StudyForm.FULL_TIME,
            ProgramOffering.funding_type == FundingType.PAID,
        )
    ).all()
    data_source_ids = session.scalars(
        select(DataSource.id).where(
            DataSource.university_id == university_id,
            DataSource.source_type == "admission_xml",
        )
    ).all()
    mapping_count = session.scalar(
        select(func.count()).select_from(LegacySpecialtyMapping).where(
            LegacySpecialtyMapping.program_offering_id == offering.id
        )
    )
    unmapped_snapshots = session.scalar(
        select(func.count()).select_from(AdmissionSnapshot).where(
            AdmissionSnapshot.program_offering_id.is_(None)
        )
    )
    unlinked_runs = session.scalar(
        select(func.count()).select_from(ScraperRun).where(ScraperRun.data_source_id.is_(None))
    )
    legacy_target_count = session.scalar(
        select(func.count()).select_from(Specialty).where(
            Specialty.normalized_name == BSEU_LEGACY_NAME,
            Specialty.study_form == BSEU_LEGACY_STUDY_FORM,
            Specialty.funding_type == BSEU_LEGACY_FUNDING_TYPE,
        )
    )
    if university_count != 1 or len(offering_ids) != 1 or len(data_source_ids) != 1:
        raise BseuMappingError("BSEU catalog identity is not unique")
    if legacy_target_count and mapping_count != 1:
        raise BseuMappingError("Legacy BSEU specialty is not mapped exactly once")
    if unmapped_snapshots or unlinked_runs:
        raise BseuMappingError("Legacy snapshots or scraper runs remain unlinked")
    return {
        "university_id": university_id,
        "program_id": program.id,
        "program_offering_id": offering.id,
        "data_source_id": data_source_ids[0],
        "legacy_mapping_count": int(mapping_count or 0),
        "unmapped_snapshots": int(unmapped_snapshots or 0),
        "unlinked_scraper_runs": int(unlinked_runs or 0),
    }
