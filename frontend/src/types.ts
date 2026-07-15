export interface Specialty { id: number; display_name: string; study_form: string; funding_type: string; source_url: string }
export interface CatalogCategory { code: string; label_ru: string }
export interface CatalogCounts {
  universities: number
  programs: number
  offerings: number
  universities_with_programs: number
  universities_with_admissions_url: number
}
export interface CatalogMeta {
  cities: string[]
  regions: string[]
  ownership_types: string[]
  institution_kinds: string[]
  categories: CatalogCategory[]
  monitoring_statuses: string[]
  admission_years: number[]
  study_forms: string[]
  funding_types: string[]
  counts: CatalogCounts
  pagination: {
    default_page_size: number
    maximum_page_size: number
  }
  coverage: {
    universities_total: number
    universities_with_imported_programs: number
    programs_total: number
    offerings_total: number
    state: string
    note: string
  }
}
export interface UniversityCoverage {
  programs: 'available' | 'not_imported'
  offerings: 'available' | 'not_imported'
  online_monitoring: 'available' | 'not_implemented'
  note: string
}
export interface UniversityListItem {
  id: number
  code: string
  slug: string
  short_name: string
  full_name: string
  institution_kind: string
  ownership_type: string
  city: string | null
  region: string | null
  official_site_url: string
  admissions_url: string | null
  monitoring_status: string
  active: boolean
  categories: CatalogCategory[]
  program_count: number
  offering_count: number
  coverage: UniversityCoverage
}
export interface Pagination {
  page: number
  page_size: number
  total_items: number
  total_pages: number
  has_next: boolean
  has_previous: boolean
}
export interface UniversityListResponse {
  items: UniversityListItem[]
  pagination: Pagination
}
export interface PublicSource {
  source_type: string
  source_url: string
  checked_at: string
}
export interface OfferingSummary {
  id: number
  admission_year: number
  study_form: string
  funding_type: string
  places: number | null
  monitoring_supported: boolean
  monitoring_status: string
  official_url: string
  source_url: string
  source_checked_at: string
}
export interface ImportedProgram {
  id: number
  university_id: number
  university: {
    id: number
    code: string
    slug: string
    short_name: string
  }
  code: string | null
  slug: string
  name: string
  qualification: string | null
  faculty_name: string | null
  education_level: string | null
  duration_years: number | null
  official_url: string
  active: boolean
  source_checked_at: string
  verified_at: string | null
  updated_at: string
  offering_count: number
  offerings: OfferingSummary[]
  coverage_state: 'available'
}
export interface UniversityDetail extends UniversityListItem {
  description: string | null
  source_url: string
  source_checked_at: string
  data_verified_at: string | null
  updated_at: string
  sources: PublicSource[]
  programs: ImportedProgram[]
}
export interface Snapshot {
  id: number; specialty_id: number; specialty: string; study_form: string; funding_type: string;
  source_url: string; fetched_at: string; source_updated_at: string | null; admission_plan: number;
  applications_total: number; competition: number; estimated_cutoff_min: number | null;
  estimated_cutoff_max: number | null; estimated_cutoff: string | null; no_competition: boolean;
  user_score: number; estimated_user_position: number | null; user_status: string;
  distribution: Record<string, number>; data_age_seconds?: number; is_stale?: boolean;
  source_age_seconds?: number | null;
  last_checked_at?: string;
}
export interface CollectorStatus { state: string; consecutive_errors: number; next_run_at: string | null; last_run: null | { status: string; error_message: string | null; finished_at: string | null; rows_found: number } }

export interface AnonymousProfile {
  personal_score: number | null
  created_at: string
  updated_at: string
}

export interface PersonalAdmissionStatus {
  offering_id: number
  snapshot_id: number
  fetched_at: string
  status: string
  competition: number
  estimated_cutoff_min: number | null
  estimated_cutoff_max: number | null
  estimated_user_position: number | null
  margin_min: number | null
  margin_max: number | null
  has_competition: boolean
}

export interface SavedUniversity {
  saved_at: string
  university: UniversityListItem
}

export interface SavedProgram {
  saved_at: string
  program: ImportedProgram
  monitoring_state: 'available' | 'score_required' | 'temporarily_unavailable' | 'unsupported'
  monitoring: PersonalAdmissionStatus | null
  watch_supported: boolean
}

export interface SavedAdmissionList {
  profile: AnonymousProfile
  universities: SavedUniversity[]
  programs: SavedProgram[]
}

export interface AnonymousProfileCreated extends SavedAdmissionList {
  token: string
}

export interface ProgramWatch {
  enabled: boolean
  created_at: string
  updated_at: string
  university: {
    slug: string
    short_name: string
    full_name: string
  }
  program: {
    slug: string
    name: string
  }
}

export interface ProgramWatchEvent {
  event_kind:
    | 'applications_total_changed'
    | 'estimated_cutoff_changed'
    | 'user_position_changed'
    | 'user_status_changed'
  description: string
  created_at: string
  telegram_delivery_status: 'confirmed' | 'failed' | 'pending' | null
  university: {
    slug: string
    short_name: string
    full_name: string
  }
  program: {
    slug: string
    name: string
  }
}

export interface ProgramWatchMutation {
  university_slug: string
  program_slug: string
  enabled: boolean
}

export interface TelegramLinkStatus {
  linked: boolean
  linked_at: string | null
  challenge_expires_at: string | null
}

export interface TelegramLinkChallenge {
  deep_link: string
  expires_at: string
}

export type RecommendationResultClass =
  | 'MONITORED_STATUS'
  | 'PARAMETER_MATCH'
  | 'INSUFFICIENT_COVERAGE'

export interface RecommendationReason {
  parameter: string
  value: string
}

export interface ProgramRecommendation {
  result_class: RecommendationResultClass
  result_label: string
  admission_evaluation: string
  match_reasons: RecommendationReason[]
  coverage_notes: string[]
  monitoring_state: 'available' | 'score_required' | 'temporarily_unavailable' | 'unsupported'
  monitoring: PersonalAdmissionStatus | null
  program: ImportedProgram
}

export interface UniversityRecommendation {
  result_class: RecommendationResultClass
  result_label: string
  admission_evaluation: string
  match_reasons: RecommendationReason[]
  coverage_notes: string[]
  university: UniversityListItem
}

export interface RecommendationResponse {
  applied_parameters: RecommendationReason[]
  programs: {
    items: ProgramRecommendation[]
    pagination: Pagination
  }
  universities: {
    items: UniversityRecommendation[]
    pagination: Pagination
  }
  coverage: CatalogMeta['coverage']
}
