from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .catalog_models import FundingType, InstitutionKind, MonitoringStatus, OwnershipType, StudyForm
from .catalog_schemas import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    CatalogHealthResponse,
    CatalogMetaResponse,
    CatalogScoreDistributionResponse,
    CatalogSnapshotResponse,
    ProgramListResponse,
    ProgramOfferingResponse,
    ProgramResponse,
    ProgramSort,
    SortOrder,
    UniversityListResponse,
    UniversityResponse,
    UniversitySort,
)
from .catalog_service import (
    CatalogNotFoundError,
    get_catalog_health,
    get_catalog_meta,
    get_offering,
    get_program,
    get_university,
    get_university_program,
    list_university_programs,
    offering_distribution,
    offering_history,
    offering_latest,
    search_programs,
    search_universities,
)
from .config import get_settings
from .database import get_db

router = APIRouter(prefix="/api", tags=["catalog"])


def _not_found(exc: CatalogNotFoundError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


@router.get("/universities", response_model=UniversityListResponse)
def university_list(
    q: str | None = Query(default=None, max_length=200),
    city: str | None = Query(default=None, max_length=200),
    region: str | None = Query(default=None, max_length=200),
    ownership_type: OwnershipType | None = None,
    institution_kind: InstitutionKind | None = None,
    category: str | None = Query(default=None, max_length=100),
    monitoring_status: MonitoringStatus | None = None,
    has_admissions_url: bool | None = None,
    has_programs: bool | None = None,
    online_monitoring: bool | None = None,
    active: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    sort: UniversitySort = UniversitySort.NAME,
    order: SortOrder = SortOrder.ASC,
    session: Session = Depends(get_db),
) -> UniversityListResponse:
    return search_universities(
        session,
        q=q,
        city=city,
        region=region,
        ownership_type=ownership_type,
        institution_kind=institution_kind,
        category=category,
        monitoring_status=monitoring_status,
        has_admissions_url=has_admissions_url,
        has_programs=has_programs,
        online_monitoring=online_monitoring,
        active=active,
        page=page,
        page_size=page_size,
        sort=sort.value,
        order=order.value,
    )


@router.get("/universities/{slug}", response_model=UniversityResponse)
def university_detail(slug: str, session: Session = Depends(get_db)) -> UniversityResponse:
    try:
        return get_university(session, slug)
    except CatalogNotFoundError as exc:
        raise _not_found(exc) from exc


@router.get("/universities/{slug}/programs", response_model=ProgramListResponse)
def university_programs(
    slug: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    session: Session = Depends(get_db),
) -> ProgramListResponse:
    try:
        return list_university_programs(session, slug, page=page, page_size=page_size)
    except CatalogNotFoundError as exc:
        raise _not_found(exc) from exc


@router.get("/universities/{university_slug}/programs/{program_slug}", response_model=ProgramResponse)
def university_program_detail(
    university_slug: str,
    program_slug: str,
    session: Session = Depends(get_db),
) -> ProgramResponse:
    try:
        return get_university_program(session, university_slug, program_slug)
    except CatalogNotFoundError as exc:
        raise _not_found(exc) from exc


@router.get("/programs", response_model=ProgramListResponse)
def program_list(
    q: str | None = Query(default=None, max_length=200),
    university: str | None = Query(default=None, max_length=200),
    city: str | None = Query(default=None, max_length=200),
    admission_year: int | None = Query(default=None, ge=2000, le=2100),
    study_form: StudyForm | None = None,
    funding_type: FundingType | None = None,
    monitoring_status: MonitoringStatus | None = None,
    has_offerings: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    sort: ProgramSort = ProgramSort.NAME,
    order: SortOrder = SortOrder.ASC,
    session: Session = Depends(get_db),
) -> ProgramListResponse:
    return search_programs(
        session,
        q=q,
        university=university,
        city=city,
        admission_year=admission_year,
        study_form=study_form,
        funding_type=funding_type,
        monitoring_status=monitoring_status,
        has_offerings=has_offerings,
        page=page,
        page_size=page_size,
        sort=sort.value,
        order=order.value,
    )


@router.get("/programs/{program_id}", response_model=ProgramResponse)
def program_detail(program_id: int, session: Session = Depends(get_db)) -> ProgramResponse:
    try:
        return get_program(session, program_id)
    except CatalogNotFoundError as exc:
        raise _not_found(exc) from exc


@router.get("/catalog/meta", response_model=CatalogMetaResponse)
def catalog_meta(session: Session = Depends(get_db)) -> CatalogMetaResponse:
    return get_catalog_meta(session)


@router.get("/catalog/health", response_model=CatalogHealthResponse)
def catalog_health(session: Session = Depends(get_db)) -> CatalogHealthResponse:
    return get_catalog_health(session)


@router.get("/program-offerings/{offering_id}", response_model=ProgramOfferingResponse)
def program_offering(offering_id: int, session: Session = Depends(get_db)) -> ProgramOfferingResponse:
    try:
        return get_offering(session, offering_id)
    except CatalogNotFoundError as exc:
        raise _not_found(exc) from exc


@router.get("/program-offerings/{offering_id}/latest", response_model=CatalogSnapshotResponse)
def program_offering_latest(
    offering_id: int, session: Session = Depends(get_db)
) -> CatalogSnapshotResponse:
    try:
        return offering_latest(
            session, offering_id, stale_after_minutes=get_settings().stale_after_minutes
        )
    except CatalogNotFoundError as exc:
        raise _not_found(exc) from exc


@router.get("/program-offerings/{offering_id}/history", response_model=list[CatalogSnapshotResponse])
def program_offering_history(
    offering_id: int,
    limit: int = Query(default=100, ge=1, le=1000),
    session: Session = Depends(get_db),
) -> list[CatalogSnapshotResponse]:
    try:
        return offering_history(
            session,
            offering_id,
            limit=limit,
            stale_after_minutes=get_settings().stale_after_minutes,
        )
    except CatalogNotFoundError as exc:
        raise _not_found(exc) from exc


@router.get(
    "/program-offerings/{offering_id}/score-distribution",
    response_model=CatalogScoreDistributionResponse,
)
def program_offering_score_distribution(
    offering_id: int, session: Session = Depends(get_db)
) -> CatalogScoreDistributionResponse:
    try:
        return offering_distribution(session, offering_id)
    except CatalogNotFoundError as exc:
        raise _not_found(exc) from exc
