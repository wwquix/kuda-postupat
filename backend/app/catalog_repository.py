from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import and_, desc, exists, func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from .catalog_models import (
    DataSource,
    InstitutionKind,
    LegacySpecialtyMapping,
    MonitoringStatus,
    OwnershipType,
    Program,
    ProgramOffering,
    University,
    UniversityCategory,
    UniversityCategoryLink,
)
from .catalog_search import escape_like
from .models import AdmissionSnapshot, HttpCacheState


@dataclass(frozen=True)
class PageResult[T]:
    items: list[T]
    total_items: int


@dataclass(frozen=True)
class UniversityQuery:
    query: str | None = None
    city: str | None = None
    region: str | None = None
    ownership_type: OwnershipType | None = None
    institution_kind: InstitutionKind | None = None
    category: str | None = None
    monitoring_status: MonitoringStatus | None = None
    has_admissions_url: bool | None = None
    has_programs: bool | None = None
    online_monitoring: bool | None = None
    active: bool | None = None


@dataclass(frozen=True)
class ProgramQuery:
    query: str | None = None
    university: str | None = None
    city: str | None = None
    admission_year: int | None = None
    study_form: str | None = None
    funding_type: str | None = None
    monitoring_status: str | None = None
    has_offerings: bool | None = None


@dataclass(frozen=True)
class UniversityRow:
    university: University
    program_count: int
    offering_count: int
    has_online_adapter: bool


@dataclass(frozen=True)
class ProgramRow:
    program: Program
    offering_count: int


@dataclass(frozen=True)
class CatalogCounts:
    universities: int
    programs: int
    offerings: int
    universities_with_programs: int
    universities_with_admissions_url: int


def _normalized(column):  # type: ignore[no-untyped-def]
    return func.catalog_normalize(column)


def _university_program_count():  # type: ignore[no-untyped-def]
    return (
        select(func.count(Program.id))
        .where(Program.university_id == University.id)
        .correlate(University)
        .scalar_subquery()
    )


def _university_offering_count():  # type: ignore[no-untyped-def]
    return (
        select(func.count(ProgramOffering.id))
        .join(Program, Program.id == ProgramOffering.program_id)
        .where(Program.university_id == University.id)
        .correlate(University)
        .scalar_subquery()
    )


def _online_adapter_exists():  # type: ignore[no-untyped-def]
    return exists(
        select(DataSource.id).where(
            DataSource.university_id == University.id,
            DataSource.enabled.is_(True),
            DataSource.adapter_name.is_not(None),
            func.length(func.trim(DataSource.adapter_name)) > 0,
        )
    )


def _university_predicates(filters: UniversityQuery) -> list:  # type: ignore[type-arg]
    predicates = []
    program_count = _university_program_count()
    online_condition = and_(
        University.monitoring_status == MonitoringStatus.ONLINE,
        _online_adapter_exists(),
    )
    if filters.query:
        pattern = f"%{escape_like(filters.query)}%"
        university_fields = (
            University.short_name,
            University.full_name,
            University.code,
            University.slug,
            University.city,
            University.region,
        )
        category_match = exists(
            select(UniversityCategoryLink.university_id)
            .join(UniversityCategory, UniversityCategory.id == UniversityCategoryLink.category_id)
            .where(
                UniversityCategoryLink.university_id == University.id,
                or_(
                    _normalized(UniversityCategory.code).like(pattern, escape="\\"),
                    _normalized(UniversityCategory.label_ru).like(pattern, escape="\\"),
                ),
            )
        )
        program_match = exists(
            select(Program.id).where(
                Program.university_id == University.id,
                or_(
                    _normalized(Program.name).like(pattern, escape="\\"),
                    _normalized(Program.code).like(pattern, escape="\\"),
                    _normalized(Program.slug).like(pattern, escape="\\"),
                ),
            )
        )
        predicates.append(
            or_(
                *(_normalized(field).like(pattern, escape="\\") for field in university_fields),
                category_match,
                program_match,
            )
        )
    if filters.city:
        predicates.append(_normalized(University.city) == filters.city)
    if filters.region:
        predicates.append(_normalized(University.region) == filters.region)
    if filters.ownership_type is not None:
        predicates.append(University.ownership_type == filters.ownership_type)
    if filters.institution_kind is not None:
        predicates.append(University.institution_kind == filters.institution_kind)
    if filters.category:
        predicates.append(
            exists(
                select(UniversityCategoryLink.university_id)
                .join(UniversityCategory, UniversityCategory.id == UniversityCategoryLink.category_id)
                .where(
                    UniversityCategoryLink.university_id == University.id,
                    or_(
                        _normalized(UniversityCategory.code) == filters.category,
                        _normalized(UniversityCategory.label_ru) == filters.category,
                    ),
                )
            )
        )
    if filters.monitoring_status is not None:
        predicates.append(University.monitoring_status == filters.monitoring_status)
    if filters.has_admissions_url is not None:
        has_url = and_(
            University.admissions_url.is_not(None),
            func.length(func.trim(University.admissions_url)) > 0,
        )
        predicates.append(has_url if filters.has_admissions_url else ~has_url)
    if filters.has_programs is not None:
        predicates.append(program_count > 0 if filters.has_programs else program_count == 0)
    if filters.online_monitoring is not None:
        predicates.append(online_condition if filters.online_monitoring else ~online_condition)
    if filters.active is not None:
        predicates.append(University.active.is_(filters.active))
    return predicates


def list_universities(
    session: Session,
    filters: UniversityQuery,
    *,
    page: int,
    page_size: int,
    sort: str,
    order: str,
) -> PageResult[UniversityRow]:
    program_count = _university_program_count()
    offering_count = _university_offering_count()
    adapter_exists = _online_adapter_exists()
    predicates = _university_predicates(filters)
    total = session.scalar(select(func.count()).select_from(University).where(*predicates)) or 0
    sort_expressions = {
        "name": _normalized(University.full_name),
        "city": _normalized(University.city),
        "region": _normalized(University.region),
        "ownership": University.ownership_type,
        "monitoring_status": University.monitoring_status,
        "program_count": program_count,
        "updated_at": University.updated_at,
    }
    sort_expression = sort_expressions[sort]
    ordering = sort_expression.desc() if order == "desc" else sort_expression.asc()
    rows = session.execute(
        select(
            University,
            program_count.label("program_count"),
            offering_count.label("offering_count"),
            adapter_exists.label("has_online_adapter"),
        )
        .where(*predicates)
        .options(selectinload(University.categories))
        .order_by(ordering, University.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return PageResult(
        items=[
            UniversityRow(
                university=row[0],
                program_count=int(row[1]),
                offering_count=int(row[2]),
                has_online_adapter=bool(row[3]),
            )
            for row in rows
        ],
        total_items=int(total),
    )


def university_detail_by_slug(session: Session, slug: str) -> UniversityRow | None:
    program_count = _university_program_count()
    offering_count = _university_offering_count()
    adapter_exists = _online_adapter_exists()
    row = session.execute(
        select(
            University,
            program_count.label("program_count"),
            offering_count.label("offering_count"),
            adapter_exists.label("has_online_adapter"),
        )
        .where(University.slug == slug, University.active.is_(True))
        .options(
            selectinload(University.categories),
            selectinload(University.data_sources),
        )
    ).one_or_none()
    if row is None:
        return None
    return UniversityRow(
        university=row[0],
        program_count=int(row[1]),
        offering_count=int(row[2]),
        has_online_adapter=bool(row[3]),
    )


def university_by_slug(session: Session, slug: str) -> University | None:
    return session.scalar(select(University).where(University.slug == slug, University.active.is_(True)))


def _program_offering_count():  # type: ignore[no-untyped-def]
    return (
        select(func.count(ProgramOffering.id))
        .where(ProgramOffering.program_id == Program.id)
        .correlate(Program)
        .scalar_subquery()
    )


def _program_predicates(filters: ProgramQuery) -> list:  # type: ignore[type-arg]
    predicates = []
    offering_count = _program_offering_count()
    if filters.query:
        pattern = f"%{escape_like(filters.query)}%"
        predicates.append(
            or_(
                _normalized(Program.name).like(pattern, escape="\\"),
                _normalized(Program.code).like(pattern, escape="\\"),
                _normalized(Program.slug).like(pattern, escape="\\"),
                _normalized(University.short_name).like(pattern, escape="\\"),
                _normalized(University.full_name).like(pattern, escape="\\"),
            )
        )
    if filters.university:
        predicates.append(
            or_(
                _normalized(University.code) == filters.university,
                _normalized(University.slug) == filters.university,
            )
        )
    if filters.city:
        predicates.append(_normalized(University.city) == filters.city)
    offering_predicates = []
    if filters.admission_year is not None:
        offering_predicates.append(ProgramOffering.admission_year == filters.admission_year)
    if filters.study_form is not None:
        offering_predicates.append(ProgramOffering.study_form == filters.study_form)
    if filters.funding_type is not None:
        offering_predicates.append(ProgramOffering.funding_type == filters.funding_type)
    if filters.monitoring_status is not None:
        offering_predicates.append(ProgramOffering.monitoring_status == filters.monitoring_status)
    if offering_predicates:
        predicates.append(
            exists(
                select(ProgramOffering.id).where(
                    ProgramOffering.program_id == Program.id,
                    *offering_predicates,
                )
            )
        )
    if filters.has_offerings is not None:
        predicates.append(offering_count > 0 if filters.has_offerings else offering_count == 0)
    return predicates


def list_programs(
    session: Session,
    filters: ProgramQuery,
    *,
    page: int,
    page_size: int,
    sort: str,
    order: str,
) -> PageResult[ProgramRow]:
    offering_count = _program_offering_count()
    predicates = _program_predicates(filters)
    total = (
        session.scalar(
            select(func.count()).select_from(Program).join(University).where(Program.active.is_(True), *predicates)
        )
        or 0
    )
    sort_expressions = {
        "name": _normalized(Program.name),
        "university": _normalized(University.full_name),
        "city": _normalized(University.city),
        "offering_count": offering_count,
        "updated_at": Program.updated_at,
    }
    sort_expression = sort_expressions[sort]
    ordering = sort_expression.desc() if order == "desc" else sort_expression.asc()
    rows = session.execute(
        select(Program, offering_count.label("offering_count"))
        .join(University)
        .where(Program.active.is_(True), *predicates)
        .options(joinedload(Program.university), selectinload(Program.offerings))
        .order_by(ordering, Program.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return PageResult(
        items=[ProgramRow(program=row[0], offering_count=int(row[1])) for row in rows],
        total_items=int(total),
    )


def program_by_id(session: Session, program_id: int) -> ProgramRow | None:
    offering_count = _program_offering_count()
    row = session.execute(
        select(Program, offering_count.label("offering_count"))
        .where(Program.id == program_id, Program.active.is_(True))
        .options(joinedload(Program.university), selectinload(Program.offerings))
    ).one_or_none()
    if row is None:
        return None
    return ProgramRow(program=row[0], offering_count=int(row[1]))


def catalog_counts(session: Session) -> CatalogCounts:
    row = session.execute(
        select(
            select(func.count()).select_from(University).scalar_subquery(),
            select(func.count()).select_from(Program).scalar_subquery(),
            select(func.count()).select_from(ProgramOffering).scalar_subquery(),
            select(func.count(func.distinct(Program.university_id))).scalar_subquery(),
            select(func.count())
            .select_from(University)
            .where(
                University.admissions_url.is_not(None),
                func.length(func.trim(University.admissions_url)) > 0,
            )
            .scalar_subquery(),
        )
    ).one()
    return CatalogCounts(
        universities=int(row[0]),
        programs=int(row[1]),
        offerings=int(row[2]),
        universities_with_programs=int(row[3]),
        universities_with_admissions_url=int(row[4]),
    )


def distinct_university_values(session: Session, column) -> list:  # type: ignore[no-untyped-def,type-arg]
    return list(
        session.scalars(
            select(column).where(column.is_not(None)).distinct().order_by(column)
        ).all()
    )


def catalog_categories(session: Session) -> list[UniversityCategory]:
    return list(session.scalars(select(UniversityCategory).order_by(UniversityCategory.code)).all())


def distinct_offering_values(session: Session, column) -> list:  # type: ignore[no-untyped-def,type-arg]
    return list(session.scalars(select(column).distinct().order_by(column)).all())


def duplicate_identities_absent(session: Session) -> bool:
    duplicate_statements = (
        select(University.code).group_by(University.code).having(func.count() > 1),
        select(University.slug).group_by(University.slug).having(func.count() > 1),
        select(Program.university_id, Program.slug)
        .group_by(Program.university_id, Program.slug)
        .having(func.count() > 1),
        select(
            ProgramOffering.program_id,
            ProgramOffering.admission_year,
            ProgramOffering.study_form,
            ProgramOffering.funding_type,
        )
        .group_by(
            ProgramOffering.program_id,
            ProgramOffering.admission_year,
            ProgramOffering.study_form,
            ProgramOffering.funding_type,
        )
        .having(func.count() > 1),
        select(DataSource.university_id, DataSource.source_type, DataSource.source_url)
        .group_by(DataSource.university_id, DataSource.source_type, DataSource.source_url)
        .having(func.count() > 1),
    )
    return all(session.execute(statement.limit(1)).first() is None for statement in duplicate_statements)


def bseu_identity_exists(session: Session) -> bool:
    identity_count = session.scalar(
        select(func.count())
        .select_from(University)
        .join(Program, Program.university_id == University.id)
        .join(ProgramOffering, ProgramOffering.program_id == Program.id)
        .where(
            University.id == 1,
            University.code == "bseu",
            University.slug == "bseu",
            University.monitoring_status == MonitoringStatus.ONLINE,
            Program.id == 1,
            ProgramOffering.id == 1,
            ProgramOffering.monitoring_supported.is_(True),
            exists(
                select(DataSource.id).where(
                    DataSource.university_id == University.id,
                    DataSource.source_type == "admission_xml",
                    DataSource.adapter_name == "legacy_admission_scraper",
                )
            ),
        )
    )
    return identity_count == 1


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
