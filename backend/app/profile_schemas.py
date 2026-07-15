from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .admission_score import MAX_ADMISSION_SCORE, MIN_ADMISSION_SCORE
from .catalog_schemas import ProgramResponse, UniversityListItemResponse


class ProfileSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class AnonymousProfileResponse(ProfileSchema):
    personal_score: int | None
    created_at: datetime
    updated_at: datetime


class ProfileScoreUpdate(ProfileSchema):
    score: int | None = Field(default=None, ge=MIN_ADMISSION_SCORE, le=MAX_ADMISSION_SCORE)


class PersonalAdmissionStatusResponse(ProfileSchema):
    offering_id: int
    snapshot_id: int
    fetched_at: datetime
    status: str
    competition: float
    estimated_cutoff_min: int | None
    estimated_cutoff_max: int | None
    estimated_user_position: int | None
    margin_min: int | None
    margin_max: int | None
    has_competition: bool


class SavedUniversityResponse(ProfileSchema):
    saved_at: datetime
    university: UniversityListItemResponse


class SavedProgramResponse(ProfileSchema):
    saved_at: datetime
    program: ProgramResponse
    monitoring_state: Literal[
        "available",
        "score_required",
        "temporarily_unavailable",
        "unsupported",
    ]
    monitoring: PersonalAdmissionStatusResponse | None
    watch_supported: bool


class SavedAdmissionListResponse(ProfileSchema):
    profile: AnonymousProfileResponse
    universities: list[SavedUniversityResponse]
    programs: list[SavedProgramResponse]


class AnonymousProfileCreatedResponse(SavedAdmissionListResponse):
    token: str
