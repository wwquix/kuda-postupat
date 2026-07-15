from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class WatchSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class WatchUniversityResponse(WatchSchema):
    slug: str
    short_name: str
    full_name: str


class WatchProgramResponse(WatchSchema):
    slug: str
    name: str


class ProgramWatchResponse(WatchSchema):
    enabled: bool
    created_at: datetime
    updated_at: datetime
    university: WatchUniversityResponse
    program: WatchProgramResponse


class ProgramWatchMutationResponse(WatchSchema):
    university_slug: str
    program_slug: str
    enabled: bool


class ProgramWatchEventResponse(WatchSchema):
    event_kind: Literal[
        "applications_total_changed",
        "estimated_cutoff_changed",
        "user_position_changed",
        "user_status_changed",
    ]
    description: str
    created_at: datetime
    university: WatchUniversityResponse
    program: WatchProgramResponse
