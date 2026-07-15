import type {
  CatalogMeta,
  CollectorStatus,
  Snapshot,
  Specialty,
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

export const api = {
  catalogMeta: (signal?: AbortSignal) => json<CatalogMeta>(
    `${apiBase}/catalog/meta`,
    signal ? { signal } : undefined,
  ),
  universities: (params: URLSearchParams, signal: AbortSignal) => json<UniversityListResponse>(
    `${apiBase}/universities?${params.toString()}`,
    { signal },
  ),
  university: (slug: string, signal: AbortSignal) => json<UniversityDetail>(
    `${apiBase}/universities/${encodeURIComponent(slug)}`,
    { signal },
  ),
  specialties: () => json<Specialty[]>(`${apiBase}/specialties`),
  latest: (id: number) => json<Snapshot>(`${apiBase}/specialties/${id}/latest`),
  history: (id: number) => json<Snapshot[]>(`${apiBase}/specialties/${id}/history?limit=200`),
  status: () => json<CollectorStatus>(`${apiBase}/status`),
  refresh: (token: string) => json<{ status: string }>(`${apiBase}/refresh`, { method: 'POST', headers: { 'X-Refresh-Token': token } }),
}
