from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CatalogSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CategoryResponse(CatalogSchema):
    code: str
    label_ru: str


class UniversityResponse(CatalogSchema):
    id: int
    code: str
    slug: str
    short_name: str
    full_name: str
    institution_kind: str
    ownership_type: str
    city: str | None
    region: str | None
    official_site_url: str
    admissions_url: str | None
    monitoring_status: str
    active: bool
    source_url: str
    source_checked_at: datetime
    categories: list[CategoryResponse]


class OfferingSummaryResponse(CatalogSchema):
    id: int
    admission_year: int
    study_form: str
    funding_type: str
    places: int | None
    monitoring_supported: bool
    monitoring_status: str
    official_url: str
    source_url: str
    source_checked_at: datetime


class ProgramResponse(CatalogSchema):
    id: int
    university_id: int
    code: str | None
    slug: str
    name: str
    qualification: str | None
    faculty_name: str | None
    official_url: str
    source_checked_at: datetime
    offerings: list[OfferingSummaryResponse]


class SourceProvenanceResponse(CatalogSchema):
    id: int
    source_type: str
    source_url: str
    adapter_name: str | None
    refresh_interval_minutes: int | None
    enabled: bool
    health_status: str
    checked_at: datetime | None
    last_success_at: datetime | None


class ProgramIdentityResponse(CatalogSchema):
    id: int
    code: str | None
    slug: str
    name: str


class UniversityIdentityResponse(CatalogSchema):
    id: int
    code: str
    slug: str
    short_name: str


class ProgramOfferingResponse(OfferingSummaryResponse):
    program: ProgramIdentityResponse
    university: UniversityIdentityResponse
    source: SourceProvenanceResponse | None


class CatalogSnapshotResponse(CatalogSchema):
    id: int
    program_offering_id: int
    legacy_specialty_id: int
    fetched_at: datetime
    source_updated_at: datetime | None
    admission_plan: int
    applications_total: int
    competition: float
    estimated_cutoff_min: int | None
    estimated_cutoff_max: int | None
    no_competition: bool
    distribution: dict[str, int]
    legacy_user_score: int
    legacy_estimated_user_position: int | None
    legacy_user_status: str
    source: SourceProvenanceResponse | None
    last_checked_at: datetime | None = None
    is_stale: bool | None = None


class ScoreDistributionItem(CatalogSchema):
    range: str
    count: int


class CatalogScoreDistributionResponse(CatalogSchema):
    program_offering_id: int
    snapshot_id: int
    fetched_at: datetime
    distribution: list[ScoreDistributionItem]
    source: SourceProvenanceResponse | None
