export interface Specialty { id: number; display_name: string; study_form: string; funding_type: string; source_url: string }
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
