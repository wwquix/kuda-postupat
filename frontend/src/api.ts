import type {
  CatalogMeta,
  CollectorStatus,
  AnonymousProfile,
  AnonymousProfileCreated,
  ImportedProgram,
  ProgramWatch,
  ProgramWatchEvent,
  ProgramWatchMutation,
  RecommendationResponse,
  SavedAdmissionList,
  Snapshot,
  Specialty,
  TelegramLinkChallenge,
  TelegramLinkStatus,
  UniversityDetail,
  UniversityListResponse,
} from './types'

const apiBase = `${import.meta.env.BASE_URL}api`.replace(/\/$/, '')

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message)
    this.name = 'ApiError'
  }
}

const json = async <T,>(url: string, init?: RequestInit): Promise<T> => {
  const response = await fetch(url, init)
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }))
    throw new ApiError(payload.detail || 'Ошибка запроса', response.status)
  }
  return response.json()
}

const profileJson = <T,>(token: string, url: string, init?: RequestInit) => json<T>(url, {
  ...init,
  headers: {
    ...init?.headers,
    Authorization: `Bearer ${token}`,
  },
})

export const api = {
  catalogMeta: (signal?: AbortSignal) => json<CatalogMeta>(
    `${apiBase}/catalog/meta`,
    signal ? { signal } : undefined,
  ),
  universities: (params: URLSearchParams, signal: AbortSignal) => json<UniversityListResponse>(
    `${apiBase}/universities?${params.toString()}`,
    { signal },
  ),
  recommendations: (params: URLSearchParams, signal: AbortSignal) => json<RecommendationResponse>(
    `${apiBase}/recommendations?${params.toString()}`,
    { signal },
  ),
  university: (slug: string, signal: AbortSignal) => json<UniversityDetail>(
    `${apiBase}/universities/${encodeURIComponent(slug)}`,
    { signal },
  ),
  program: (universitySlug: string, programSlug: string, signal: AbortSignal) => json<ImportedProgram>(
    `${apiBase}/universities/${encodeURIComponent(universitySlug)}/programs/${encodeURIComponent(programSlug)}`,
    { signal },
  ),
  specialties: () => json<Specialty[]>(`${apiBase}/specialties`),
  latest: (id: number) => json<Snapshot>(`${apiBase}/specialties/${id}/latest`),
  history: (id: number) => json<Snapshot[]>(`${apiBase}/specialties/${id}/history?limit=200`),
  status: () => json<CollectorStatus>(`${apiBase}/status`),
  refresh: (token: string) => json<{ status: string }>(`${apiBase}/refresh`, { method: 'POST', headers: { 'X-Refresh-Token': token } }),
  createProfile: () => json<AnonymousProfileCreated>(`${apiBase}/profile`, { method: 'POST' }),
  profile: (token: string, signal?: AbortSignal) => profileJson<AnonymousProfile>(
    token,
    `${apiBase}/profile`,
    signal ? { signal } : undefined,
  ),
  savedAdmissionList: (token: string, signal?: AbortSignal) => profileJson<SavedAdmissionList>(
    token,
    `${apiBase}/profile/saved`,
    signal ? { signal } : undefined,
  ),
  updateProfileScore: (token: string, score: number | null) => profileJson<SavedAdmissionList>(
    token,
    `${apiBase}/profile/score`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ score }),
    },
  ),
  saveUniversity: (token: string, slug: string) => profileJson<SavedAdmissionList>(
    token,
    `${apiBase}/profile/universities/${encodeURIComponent(slug)}`,
    { method: 'PUT' },
  ),
  removeUniversity: (token: string, slug: string) => profileJson<SavedAdmissionList>(
    token,
    `${apiBase}/profile/universities/${encodeURIComponent(slug)}`,
    { method: 'DELETE' },
  ),
  saveProgram: (token: string, universitySlug: string, programSlug: string) => profileJson<SavedAdmissionList>(
    token,
    `${apiBase}/profile/programs/${encodeURIComponent(universitySlug)}/${encodeURIComponent(programSlug)}`,
    { method: 'PUT' },
  ),
  removeProgram: (token: string, universitySlug: string, programSlug: string) => profileJson<SavedAdmissionList>(
    token,
    `${apiBase}/profile/programs/${encodeURIComponent(universitySlug)}/${encodeURIComponent(programSlug)}`,
    { method: 'DELETE' },
  ),
  watches: (token: string, signal?: AbortSignal) => profileJson<ProgramWatch[]>(
    token,
    `${apiBase}/profile/watches`,
    signal ? { signal } : undefined,
  ),
  watchEvents: (token: string, signal?: AbortSignal) => profileJson<ProgramWatchEvent[]>(
    token,
    `${apiBase}/profile/watch-events`,
    signal ? { signal } : undefined,
  ),
  enableWatch: (token: string, universitySlug: string, programSlug: string) => profileJson<ProgramWatch>(
    token,
    `${apiBase}/profile/watches/${encodeURIComponent(universitySlug)}/${encodeURIComponent(programSlug)}`,
    { method: 'PUT' },
  ),
  disableWatch: (token: string, universitySlug: string, programSlug: string) => profileJson<ProgramWatchMutation>(
    token,
    `${apiBase}/profile/watches/${encodeURIComponent(universitySlug)}/${encodeURIComponent(programSlug)}`,
    { method: 'DELETE' },
  ),
  telegramLinkStatus: (token: string, signal?: AbortSignal) => profileJson<TelegramLinkStatus>(
    token,
    `${apiBase}/profile/telegram`,
    signal ? { signal } : undefined,
  ),
  createTelegramLinkChallenge: (token: string) => profileJson<TelegramLinkChallenge>(
    token,
    `${apiBase}/profile/telegram/challenge`,
    { method: 'POST' },
  ),
  unlinkTelegram: (token: string) => profileJson<TelegramLinkStatus>(
    token,
    `${apiBase}/profile/telegram`,
    { method: 'DELETE' },
  ),
}
