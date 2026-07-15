from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict

from .catalog_schemas import (
    CatalogCoverageResponse,
    PaginationResponse,
    ProgramResponse,
    UniversityListItemResponse,
)
from .profile_schemas import PersonalAdmissionStatusResponse


class RecommendationSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class RecommendationResultClass(str, Enum):
    MONITORED_STATUS = "MONITORED_STATUS"
    PARAMETER_MATCH = "PARAMETER_MATCH"
    INSUFFICIENT_COVERAGE = "INSUFFICIENT_COVERAGE"


class RecommendationReasonResponse(RecommendationSchema):
    parameter: Literal[
        "catalog",
        "score",
        "city",
        "region",
        "ownership_type",
        "institution_kind",
        "category",
        "study_form",
        "funding_type",
        "online_monitoring",
    ]
    value: str


class ProgramRecommendationResponse(RecommendationSchema):
    result_class: RecommendationResultClass
    result_label: str
    admission_evaluation: str
    match_reasons: list[RecommendationReasonResponse]
    coverage_notes: list[str]
    monitoring_state: Literal[
        "available",
        "score_required",
        "temporarily_unavailable",
        "unsupported",
    ]
    monitoring: PersonalAdmissionStatusResponse | None
    program: ProgramResponse


class UniversityRecommendationResponse(RecommendationSchema):
    result_class: RecommendationResultClass
    result_label: str
    admission_evaluation: str
    match_reasons: list[RecommendationReasonResponse]
    coverage_notes: list[str]
    university: UniversityListItemResponse


class ProgramRecommendationCollection(RecommendationSchema):
    items: list[ProgramRecommendationResponse]
    pagination: PaginationResponse


class UniversityRecommendationCollection(RecommendationSchema):
    items: list[UniversityRecommendationResponse]
    pagination: PaginationResponse


class RecommendationResponse(RecommendationSchema):
    applied_parameters: list[RecommendationReasonResponse]
    programs: ProgramRecommendationCollection
    universities: UniversityRecommendationCollection
    coverage: CatalogCoverageResponse
