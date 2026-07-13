from sqlalchemy import desc, select
from sqlalchemy.orm import Session, joinedload, selectinload

from .catalog_models import DataSource, LegacySpecialtyMapping, Program, ProgramOffering, University
from .models import AdmissionSnapshot, HttpCacheState


def university_by_slug(session: Session, slug: str) -> University | None:
    return session.scalar(
        select(University)
        .where(University.slug == slug, University.active.is_(True))
        .options(selectinload(University.categories))
    )


def programs_for_university(session: Session, university_id: int) -> list[Program]:
    return list(
        session.scalars(
            select(Program)
            .where(Program.university_id == university_id, Program.active.is_(True))
            .options(selectinload(Program.offerings))
            .order_by(Program.name)
        ).all()
    )


def offering_by_id(session: Session, offering_id: int) -> ProgramOffering | None:
    return session.scalar(
        select(ProgramOffering)
        .where(ProgramOffering.id == offering_id)
        .options(joinedload(ProgramOffering.program).joinedload(Program.university))
    )


def mapping_for_offering(session: Session, offering_id: int) -> LegacySpecialtyMapping | None:
    return session.scalar(
        select(LegacySpecialtyMapping)
        .where(LegacySpecialtyMapping.program_offering_id == offering_id)
        .options(joinedload(LegacySpecialtyMapping.legacy_specialty))
    )


def snapshots_for_offering(
    session: Session, offering_id: int, *, limit: int
) -> tuple[LegacySpecialtyMapping | None, list[AdmissionSnapshot]]:
    mapping = mapping_for_offering(session, offering_id)
    if mapping is None:
        return None, []
    snapshots = list(
        session.scalars(
            select(AdmissionSnapshot)
            .where(AdmissionSnapshot.specialty_id == mapping.legacy_specialty_id)
            .order_by(desc(AdmissionSnapshot.fetched_at))
            .limit(limit)
        ).all()
    )
    if any(snapshot.program_offering_id != offering_id for snapshot in snapshots):
        raise RuntimeError("Catalog mapping and snapshot offering links are inconsistent")
    return mapping, snapshots


def data_source_for_offering(session: Session, offering: ProgramOffering) -> DataSource | None:
    return session.scalar(
        select(DataSource)
        .where(
            DataSource.university_id == offering.program.university_id,
            DataSource.enabled.is_(True),
        )
        .order_by(DataSource.id)
        .limit(1)
    )


def cache_for_source(session: Session, source: DataSource) -> HttpCacheState | None:
    return session.get(HttpCacheState, source.source_url)
