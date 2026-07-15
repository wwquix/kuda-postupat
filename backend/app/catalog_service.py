from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .catalog_models import (
    DataSource,
    FundingType,
    InstitutionKind,
    MonitoringStatus,
    OwnershipType,
    Program,
    ProgramOffering,
    StudyForm,
    University,
)
from .catalog_repository import (
    ProgramQuery,
    ProgramRow,
    UniversityQuery,
    UniversityRow,
    bseu_identity_exists,
    cache_for_source,
    catalog_categories,
    catalog_counts,
    data_source_for_offering,
    distinct_offering_values,
    distinct_university_values,
    duplicate_identities_absent,
    list_programs,
    list_universities,
    offering_by_id,
    program_by_id,
    snapshots_for_offering,
    university_by_slug,
    university_detail_by_slug,
)
from .catalog_schemas import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    CatalogCountsResponse,
    CatalogCoverageResponse,
    CatalogHealthResponse,
    CatalogMetaResponse,
    CatalogScoreDistributionResponse,
    CatalogSnapshotResponse,
    CategoryResponse,
    OfferingSummaryResponse,
    PaginationLimitsResponse,
    PaginationResponse,
    ProgramIdentityResponse,
    ProgramListResponse,
    ProgramOfferingResponse,
    ProgramResponse,
    PublicSourceResponse,
    ScoreDistributionItem,
    SourceProvenanceResponse,
    UniversityCoverageResponse,
    UniversityIdentityResponse,
    UniversityListItemResponse,
    UniversityListResponse,
    UniversityResponse,
)
from .catalog_search import normalize_search_text
from .models import AdmissionSnapshot, HttpCacheState
from .schema import current_revision, expected_head


class CatalogNotFoundError(LookupError):
    pass


def _value(value):  # type: ignore[no-untyped-def]
    return value.value if hasattr(value, "value") else value


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _pagination(page: int, page_size: int, total_items: int) -> PaginationResponse:
    total_pages = math.ceil(total_items / page_size) if total_items else 0
    return PaginationResponse(
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_previous=page > 1 and total_pages > 0,
    )


def _university_coverage(row: UniversityRow) -> UniversityCoverageResponse:
    programs_state = "available" if row.program_count else "not_imported"
    offerings_state = "available" if row.offering_count else "not_imported"
    online_state = (
        "available"
        if row.university.monitoring_status == MonitoringStatus.ONLINE and row.has_online_adapter
        else "not_implemented"
    )
    if row.program_count:
        note = "Показаны только программы, импортированные платформой."
    else:
        note = (
            "Программы этого вуза ещё не импортированы платформой; "
            "это не означает, что у вуза нет реальных программ."
        )
    return UniversityCoverageResponse(
        programs=programs_state,
        offerings=offerings_state,
        online_monitoring=online_state,
        note=note,
    )


def _university_list_item(row: UniversityRow) -> UniversityListItemResponse:
    university = row.university
    return UniversityListItemResponse(
        id=university.id,
        code=university.code,
        slug=university.slug,
        short_name=university.short_name,
        full_name=university.full_name,
        institution_kind=_value(university.institution_kind),
        ownership_type=_value(university.ownership_type),
        city=university.city,
        region=university.region,
        official_site_url=university.official_site_url,
        admissions_url=university.admissions_url,
        monitoring_status=_value(university.monitoring_status),
        active=university.active,
        categories=[
            CategoryResponse(code=item.code, label_ru=item.label_ru)
            for item in sorted(university.categories, key=lambda item: item.code)
        ],
        program_count=row.program_count,
        offering_count=row.offering_count,
        coverage=_university_coverage(row),
    )


def search_universities(
    session: Session,
    *,
    q: str | None,
    city: str | None,
    region: str | None,
    ownership_type: OwnershipType | None,
    institution_kind: InstitutionKind | None,
    category: str | None,
    monitoring_status: MonitoringStatus | None,
    has_admissions_url: bool | None,
    has_programs: bool | None,
    online_monitoring: bool | None,
    active: bool | None,
    page: int,
    page_size: int,
    sort: str,
    order: str,
) -> UniversityListResponse:
    result = list_universities(
        session,
        UniversityQuery(
            query=normalize_search_text(q) or None,
            city=normalize_search_text(city) or None,
            region=normalize_search_text(region) or None,
            ownership_type=ownership_type,
            institution_kind=institution_kind,
            category=normalize_search_text(category) or None,
            monitoring_status=monitoring_status,
            has_admissions_url=has_admissions_url,
            has_programs=has_programs,
            online_monitoring=online_monitoring,
            active=active,
        ),
        page=page,
        page_size=page_size,
        sort=sort,
        order=order,
    )
    return UniversityListResponse(
        items=[_university_list_item(item) for item in result.items],
        pagination=_pagination(page, page_size, result.total_items),
    )


def get_university(session: Session, slug: str) -> UniversityResponse:
    row = university_detail_by_slug(session, slug)
    if row is None:
        raise CatalogNotFoundError("Университет не найден")
    university = row.university
    public_sources = [
        PublicSourceResponse(
            source_type=source.source_type,
            source_url=source.source_url,
            checked_at=_as_utc(source.last_success_at or source.last_attempt_at or university.source_checked_at),
        )
        for source in sorted(university.data_sources, key=lambda item: (item.source_type, item.source_url))
    ]
    return UniversityResponse(
        **_university_list_item(row).model_dump(),
        description=university.description,
        source_url=university.source_url,
        source_checked_at=_as_utc(university.source_checked_at),
        data_verified_at=_as_utc(university.data_verified_at),
        updated_at=_as_utc(university.updated_at),
        sources=public_sources,
        programs=[
            _program_response(ProgramRow(program=program, offering_count=len(program.offerings)))
            for program in sorted(
                (program for program in university.programs if program.active),
                key=lambda item: (normalize_search_text(item.name), item.id),
            )
        ],
    )


def _offering_summary(offering: ProgramOffering) -> OfferingSummaryResponse:
    return OfferingSummaryResponse(
        id=offering.id,
        admission_year=offering.admission_year,
        study_form=_value(offering.study_form),
        funding_type=_value(offering.funding_type),
        places=offering.places,
        monitoring_supported=offering.monitoring_supported,
        monitoring_status=_value(offering.monitoring_status),
        official_url=offering.official_url,
        source_url=offering.source_url,
        source_checked_at=_as_utc(offering.source_checked_at),
    )


def _program_response(row: ProgramRow) -> ProgramResponse:
    program = row.program
    university = program.university
    return ProgramResponse(
        id=program.id,
        university_id=program.university_id,
        university=UniversityIdentityResponse(
            id=university.id,
            code=university.code,
            slug=university.slug,
            short_name=university.short_name,
        ),
        code=program.code,
        slug=program.slug,
        name=program.name,
        qualification=program.qualification,
        faculty_name=program.faculty_name,
        education_level=program.education_level,
        duration_years=program.duration_years,
        official_url=program.official_url,
        active=program.active,
        source_checked_at=_as_utc(program.source_checked_at),
        verified_at=_as_utc(program.verified_at),
        updated_at=_as_utc(program.updated_at),
        offering_count=row.offering_count,
        offerings=[
            _offering_summary(item)
            for item in sorted(
                program.offerings,
                key=lambda item: (item.admission_year, _value(item.study_form), _value(item.funding_type), item.id),
            )
        ],
    )


def _counts_response(counts) -> CatalogCountsResponse:  # type: ignore[no-untyped-def]
    return CatalogCountsResponse(
        universities=counts.universities,
        programs=counts.programs,
        offerings=counts.offerings,
        universities_with_programs=counts.universities_with_programs,
        universities_with_admissions_url=counts.universities_with_admissions_url,
    )


def _coverage_response(counts, *, note: str | None = None) -> CatalogCoverageResponse:  # type: ignore[no-untyped-def]
    return CatalogCoverageResponse(
        universities_total=counts.universities,
        universities_with_imported_programs=counts.universities_with_programs,
        programs_total=counts.programs,
        offerings_total=counts.offerings,
        note=note
        or (
            "Счётчики описывают только импортированное покрытие платформы, "
            "а не полный реальный каталог программ вузов."
        ),
    )


def search_programs(
    session: Session,
    *,
    q: str | None,
    university: str | None,
    city: str | None,
    admission_year: int | None,
    study_form: StudyForm | None,
    funding_type: FundingType | None,
    monitoring_status: MonitoringStatus | None,
    has_offerings: bool | None,
    page: int,
    page_size: int,
    sort: str,
    order: str,
    coverage_note: str | None = None,
) -> ProgramListResponse:
    result = list_programs(
        session,
        ProgramQuery(
            query=normalize_search_text(q) or None,
            university=normalize_search_text(university) or None,
            city=normalize_search_text(city) or None,
            admission_year=admission_year,
            study_form=study_form.value if study_form else None,
            funding_type=funding_type.value if funding_type else None,
            monitoring_status=monitoring_status.value if monitoring_status else None,
            has_offerings=has_offerings,
        ),
        page=page,
        page_size=page_size,
        sort=sort,
        order=order,
    )
    counts = catalog_counts(session)
    return ProgramListResponse(
        items=[_program_response(item) for item in result.items],
        pagination=_pagination(page, page_size, result.total_items),
        coverage=_coverage_response(counts, note=coverage_note),
    )


def list_university_programs(
    session: Session,
    slug: str,
    *,
    page: int,
    page_size: int,
) -> ProgramListResponse:
    university = university_by_slug(session, slug)
    if university is None:
        raise CatalogNotFoundError("Университет не найден")
    response = search_programs(
        session,
        q=None,
        university=university.slug,
        city=None,
        admission_year=None,
        study_form=None,
        funding_type=None,
        monitoring_status=None,
        has_offerings=None,
        page=page,
        page_size=page_size,
        sort="name",
        order="asc",
    )
    if response.pagination.total_items == 0:
        response.coverage.note = (
            "Программы этого вуза ещё не импортированы платформой; "
            "пустой список не означает отсутствия реальных программ."
        )
    return response


def get_program(session: Session, program_id: int) -> ProgramResponse:
    row = program_by_id(session, program_id)
    if row is None:
        raise CatalogNotFoundError("Программа не найдена")
    return _program_response(row)


def _enum_values(values: list) -> list[str]:  # type: ignore[type-arg]
    return sorted({_value(item) for item in values})


def get_catalog_meta(session: Session) -> CatalogMetaResponse:
    counts = catalog_counts(session)
    return CatalogMetaResponse(
        cities=[str(item) for item in distinct_university_values(session, University.city)],
        regions=[str(item) for item in distinct_university_values(session, University.region)],
        ownership_types=_enum_values(distinct_university_values(session, University.ownership_type)),
        institution_kinds=_enum_values(distinct_university_values(session, University.institution_kind)),
        categories=[
            CategoryResponse(code=item.code, label_ru=item.label_ru) for item in catalog_categories(session)
        ],
        monitoring_statuses=_enum_values(
            distinct_university_values(session, University.monitoring_status)
        ),
        admission_years=[
            int(item) for item in distinct_offering_values(session, ProgramOffering.admission_year)
        ],
        study_forms=_enum_values(distinct_offering_values(session, ProgramOffering.study_form)),
        funding_types=_enum_values(distinct_offering_values(session, ProgramOffering.funding_type)),
        counts=_counts_response(counts),
        pagination=PaginationLimitsResponse(
            default_page_size=DEFAULT_PAGE_SIZE,
            maximum_page_size=MAX_PAGE_SIZE,
        ),
        coverage=_coverage_response(counts),
    )


def get_catalog_health(session: Session) -> CatalogHealthResponse:
    try:
        session.scalar(select(1))
        counts = catalog_counts(session)
    except SQLAlchemyError:
        return CatalogHealthResponse(
            status="unhealthy",
            database_reachable=False,
            alembic_at_head=False,
            counts=None,
            bseu_identity_exists=False,
            duplicate_identities_absent=False,
        )

    try:
        alembic_at_head = current_revision(session.connection()) == expected_head()
    except Exception:  # health must not expose configuration or filesystem details
        alembic_at_head = False
    identity_ok = bseu_identity_exists(session)
    duplicates_ok = duplicate_identities_absent(session)
    status = "healthy" if alembic_at_head and identity_ok and duplicates_ok else "degraded"
    return CatalogHealthResponse(
        status=status,
        database_reachable=True,
        alembic_at_head=alembic_at_head,
        counts=_counts_response(counts),
        bseu_identity_exists=identity_ok,
        duplicate_identities_absent=duplicates_ok,
    )


def _source_response(
    source: DataSource | None, cache: HttpCacheState | None
) -> SourceProvenanceResponse | None:
    if source is None:
        return None
    checked_at = cache.checked_at if cache is not None else source.last_attempt_at
    return SourceProvenanceResponse(
        id=source.id,
        source_type=source.source_type,
        source_url=source.source_url,
        adapter_name=source.adapter_name,
        refresh_interval_minutes=source.refresh_interval_minutes,
        enabled=source.enabled,
        health_status=_value(source.health_status),
        checked_at=_as_utc(checked_at),
        last_success_at=_as_utc(source.last_success_at),
    )


def get_offering(session: Session, offering_id: int) -> ProgramOfferingResponse:
    offering = offering_by_id(session, offering_id)
    if offering is None:
        raise CatalogNotFoundError("Вариант поступления не найден")
    source = data_source_for_offering(session, offering)
    cache = cache_for_source(session, source) if source is not None else None
    program: Program = offering.program
    university: University = program.university
    return ProgramOfferingResponse(
        **_offering_summary(offering).model_dump(),
        program=ProgramIdentityResponse(id=program.id, code=program.code, slug=program.slug, name=program.name),
        university=UniversityIdentityResponse(
            id=university.id,
            code=university.code,
            slug=university.slug,
            short_name=university.short_name,
        ),
        source=_source_response(source, cache),
    )


def _snapshot_response(
    snapshot: AdmissionSnapshot,
    offering_id: int,
    source: DataSource | None,
    cache: HttpCacheState | None,
    *,
    include_freshness: bool,
    stale_after_minutes: int,
) -> CatalogSnapshotResponse:
    checked_at = cache.checked_at if cache is not None else (source.last_attempt_at if source else None)
    checked_at_utc = _as_utc(checked_at)
    is_stale: bool | None = None
    if include_freshness:
        freshness_anchor = checked_at_utc or _as_utc(snapshot.fetched_at)
        assert freshness_anchor is not None
        source_updated_at = snapshot.source_updated_at
        if source_updated_at is not None and source_updated_at.tzinfo is None:
            source_updated_at = source_updated_at.replace(tzinfo=ZoneInfo("Europe/Minsk"))
        anchors = [freshness_anchor]
        if source_updated_at is not None:
            anchors.append(source_updated_at.astimezone(UTC))
        is_stale = any(
            (datetime.now(UTC) - anchor).total_seconds() > stale_after_minutes * 60 for anchor in anchors
        )
    return CatalogSnapshotResponse(
        id=snapshot.id,
        program_offering_id=offering_id,
        legacy_specialty_id=snapshot.specialty_id,
        fetched_at=_as_utc(snapshot.fetched_at),
        source_updated_at=snapshot.source_updated_at,
        admission_plan=snapshot.admission_plan,
        applications_total=snapshot.applications_total,
        competition=snapshot.competition,
        estimated_cutoff_min=snapshot.estimated_cutoff_min,
        estimated_cutoff_max=snapshot.estimated_cutoff_max,
        no_competition=snapshot.applications_total <= snapshot.admission_plan,
        distribution=json.loads(snapshot.distribution_json),
        legacy_user_score=snapshot.user_score,
        legacy_estimated_user_position=snapshot.estimated_user_position,
        legacy_user_status=snapshot.user_status,
        source=_source_response(source, cache),
        last_checked_at=checked_at_utc if include_freshness else None,
        is_stale=is_stale,
    )


def offering_history(
    session: Session,
    offering_id: int,
    *,
    limit: int,
    stale_after_minutes: int,
    latest_only: bool = False,
) -> list[CatalogSnapshotResponse]:
    offering = offering_by_id(session, offering_id)
    if offering is None:
        raise CatalogNotFoundError("Вариант поступления не найден")
    _mapping, snapshots = snapshots_for_offering(session, offering_id, limit=1 if latest_only else limit)
    source = data_source_for_offering(session, offering)
    cache = cache_for_source(session, source) if source is not None else None
    return [
        _snapshot_response(
            snapshot,
            offering_id,
            source,
            cache,
            include_freshness=latest_only,
            stale_after_minutes=stale_after_minutes,
        )
        for snapshot in snapshots
    ]


def offering_latest(
    session: Session, offering_id: int, *, stale_after_minutes: int
) -> CatalogSnapshotResponse:
    snapshots = offering_history(
        session,
        offering_id,
        limit=1,
        stale_after_minutes=stale_after_minutes,
        latest_only=True,
    )
    if not snapshots:
        raise CatalogNotFoundError("Для варианта поступления еще нет корректных данных")
    return snapshots[0]


def offering_distribution(session: Session, offering_id: int) -> CatalogScoreDistributionResponse:
    offering = offering_by_id(session, offering_id)
    if offering is None:
        raise CatalogNotFoundError("Вариант поступления не найден")
    _mapping, snapshots = snapshots_for_offering(session, offering_id, limit=1)
    if not snapshots:
        raise CatalogNotFoundError("Для варианта поступления еще нет корректных данных")
    snapshot = snapshots[0]
    source = data_source_for_offering(session, offering)
    cache = cache_for_source(session, source) if source is not None else None
    distribution = json.loads(snapshot.distribution_json)
    return CatalogScoreDistributionResponse(
        program_offering_id=offering_id,
        snapshot_id=snapshot.id,
        fetched_at=_as_utc(snapshot.fetched_at),
        distribution=[
            ScoreDistributionItem(range=label.replace("-", "–"), count=count)
            for label, count in sorted(distribution.items(), key=lambda item: int(item[0].split("-")[0]))
        ],
        source=_source_response(source, cache),
    )
