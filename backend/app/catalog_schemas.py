from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


class CatalogSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"


class UniversitySort(str, Enum):
    NAME = "name"
    CITY = "city"
    REGION = "region"
    OWNERSHIP = "ownership"
    MONITORING_STATUS = "monitoring_status"
    PROGRAM_COUNT = "program_count"
    UPDATED_AT = "updated_at"


class ProgramSort(str, Enum):
    NAME = "name"
    UNIVERSITY = "university"
    CITY = "city"
    OFFERING_COUNT = "offering_count"
    UPDATED_AT = "updated_at"


class PaginationResponse(CatalogSchema):
    page: int
    page_size: int
    total_items: int
    total_pages: int
    has_next: bool
    has_previous: bool


class CategoryResponse(CatalogSchema):
    code: str
    label_ru: str


class UniversityCoverageResponse(CatalogSchema):
    programs: Literal["available", "not_imported"]
    offerings: Literal["available", "not_imported"]
    online_monitoring: Literal["available", "not_implemented"]
    note: str


class PublicSourceResponse(CatalogSchema):
    source_type: str
    source_url: str
    checked_at: datetime


class UniversityListItemResponse(CatalogSchema):
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
    categories: list[CategoryResponse]
    program_count: int
    offering_count: int
    coverage: UniversityCoverageResponse


class UniversityResponse(UniversityListItemResponse):
    description: str | None
    source_url: str
    source_checked_at: datetime
    data_verified_at: datetime | None
    updated_at: datetime
    sources: list[PublicSourceResponse]


class UniversityListResponse(CatalogSchema):
    items: list[UniversityListItemResponse]
    pagination: PaginationResponse


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


class ProgramResponse(CatalogSchema):
    id: int
    university_id: int
    university: UniversityIdentityResponse
    code: str | None
    slug: str
    name: str
    qualification: str | None
    faculty_name: str | None
    education_level: str | None
    duration_years: float | None
    official_url: str
    active: bool
    source_checked_at: datetime
    verified_at: datetime | None
    updated_at: datetime
    offering_count: int
    offerings: list[OfferingSummaryResponse]
    coverage_state: Literal["available"] = "available"


class CatalogCoverageResponse(CatalogSchema):
    universities_total: int
    universities_with_imported_programs: int
    programs_total: int
    offerings_total: int
    state: Literal["partial"] = "partial"
    note: str


class ProgramListResponse(CatalogSchema):
    items: list[ProgramResponse]
    pagination: PaginationResponse
    coverage: CatalogCoverageResponse


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


class CatalogCountsResponse(CatalogSchema):
    universities: int
    programs: int
    offerings: int
    universities_with_programs: int
    universities_with_admissions_url: int


class PaginationLimitsResponse(CatalogSchema):
    default_page_size: int
    maximum_page_size: int


class CatalogMetaResponse(CatalogSchema):
    cities: list[str]
    regions: list[str]
    ownership_types: list[str]
    institution_kinds: list[str]
    categories: list[CategoryResponse]
    monitoring_statuses: list[str]
    admission_years: list[int]
    study_forms: list[str]
    funding_types: list[str]
    counts: CatalogCountsResponse
    pagination: PaginationLimitsResponse
    coverage: CatalogCoverageResponse


class CatalogHealthResponse(CatalogSchema):
    status: Literal["healthy", "degraded", "unhealthy"]
    database_reachable: bool
    alembic_at_head: bool
    counts: CatalogCountsResponse | None
    bseu_identity_exists: bool
    duplicate_identities_absent: bool
