from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .catalog_schemas import (
    CatalogScoreDistributionResponse,
    CatalogSnapshotResponse,
    ProgramOfferingResponse,
    ProgramResponse,
    UniversityResponse,
)
from .catalog_service import (
    CatalogNotFoundError,
    get_offering,
    get_university,
    list_programs,
    offering_distribution,
    offering_history,
    offering_latest,
)
from .config import get_settings
from .database import get_db

router = APIRouter(prefix="/api", tags=["catalog"])


def _not_found(exc: CatalogNotFoundError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


@router.get("/universities/{slug}", response_model=UniversityResponse)
def university_detail(slug: str, session: Session = Depends(get_db)) -> UniversityResponse:
    try:
        return get_university(session, slug)
    except CatalogNotFoundError as exc:
        raise _not_found(exc) from exc


@router.get("/universities/{slug}/programs", response_model=list[ProgramResponse])
def university_programs(slug: str, session: Session = Depends(get_db)) -> list[ProgramResponse]:
    try:
        return list_programs(session, slug)
    except CatalogNotFoundError as exc:
        raise _not_found(exc) from exc


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
