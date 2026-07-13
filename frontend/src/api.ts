import type { CatalogMeta, CollectorStatus, Snapshot, Specialty } from './types'

const apiBase = `${import.meta.env.BASE_URL}api`.replace(/\/$/, '')

const json = async <T,>(url: string, init?: RequestInit): Promise<T> => {
  const response = await fetch(url, init)
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(payload.detail || 'Ошибка запроса')
  }
  return response.json()
}

export const api = {
  catalogMeta: () => json<CatalogMeta>(`${apiBase}/catalog/meta`),
  specialties: () => json<Specialty[]>(`${apiBase}/specialties`),
  latest: (id: number) => json<Snapshot>(`${apiBase}/specialties/${id}/latest`),
  history: (id: number) => json<Snapshot[]>(`${apiBase}/specialties/${id}/history?limit=200`),
  status: () => json<CollectorStatus>(`${apiBase}/status`),
  refresh: (token: string) => json<{ status: string }>(`${apiBase}/refresh`, { method: 'POST', headers: { 'X-Refresh-Token': token } }),
}
