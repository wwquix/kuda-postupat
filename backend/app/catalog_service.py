import json
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from .catalog_models import DataSource, Program, ProgramOffering, University
from .catalog_repository import (
    cache_for_source,
    data_source_for_offering,
    offering_by_id,
    programs_for_university,
    snapshots_for_offering,
    university_by_slug,
)
from .catalog_schemas import (
    CatalogScoreDistributionResponse,
    CatalogSnapshotResponse,
    CategoryResponse,
    OfferingSummaryResponse,
    ProgramIdentityResponse,
    ProgramOfferingResponse,
    ProgramResponse,
    ScoreDistributionItem,
    SourceProvenanceResponse,
    UniversityIdentityResponse,
    UniversityResponse,
)
from .models import AdmissionSnapshot, HttpCacheState


class CatalogNotFoundError(LookupError):
    pass


def _value(value):  # type: ignore[no-untyped-def]
    return value.value if hasattr(value, "value") else value


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


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
        source_checked_at=offering.source_checked_at,
    )


def get_university(session: Session, slug: str) -> UniversityResponse:
    university = university_by_slug(session, slug)
    if university is None:
        raise CatalogNotFoundError("Университет не найден")
    return UniversityResponse(
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
        source_url=university.source_url,
        source_checked_at=university.source_checked_at,
        categories=[CategoryResponse(code=item.code, label_ru=item.label_ru) for item in university.categories],
    )


def list_programs(session: Session, slug: str) -> list[ProgramResponse]:
    university = university_by_slug(session, slug)
    if university is None:
        raise CatalogNotFoundError("Университет не найден")
    return [
        ProgramResponse(
            id=program.id,
            university_id=program.university_id,
            code=program.code,
            slug=program.slug,
            name=program.name,
            qualification=program.qualification,
            faculty_name=program.faculty_name,
            official_url=program.official_url,
            source_checked_at=program.source_checked_at,
            offerings=[_offering_summary(item) for item in program.offerings],
        )
        for program in programs_for_university(session, university.id)
    ]


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
