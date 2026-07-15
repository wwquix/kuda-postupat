from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .admission_score import MAX_ADMISSION_SCORE, MIN_ADMISSION_SCORE
from .catalog_models import FundingType, InstitutionKind, OwnershipType, StudyForm
from .catalog_schemas import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from .config import Settings, get_settings
from .database import get_db
from .recommendation_schemas import RecommendationResponse
from .recommendation_service import get_recommendations

router = APIRouter(prefix="/api", tags=["recommendations"])


@router.get("/recommendations", response_model=RecommendationResponse)
def recommendations(
    score: int | None = Query(default=None, ge=MIN_ADMISSION_SCORE, le=MAX_ADMISSION_SCORE),
    city: str | None = Query(default=None, max_length=200),
    region: str | None = Query(default=None, max_length=200),
    ownership_type: OwnershipType | None = None,
    institution_kind: InstitutionKind | None = None,
    category: str | None = Query(default=None, max_length=100),
    study_form: StudyForm | None = None,
    funding_type: FundingType | None = None,
    online_monitoring: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RecommendationResponse:
    return get_recommendations(
        session,
        score=score,
        city=city,
        region=region,
        ownership_type=ownership_type,
        institution_kind=institution_kind,
        category=category,
        study_form=study_form,
        funding_type=funding_type,
        online_monitoring=online_monitoring,
        page=page,
        page_size=page_size,
        stale_after_minutes=settings.stale_after_minutes,
    )
