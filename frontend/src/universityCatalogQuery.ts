import type { CatalogMeta } from './types'

export const UNIVERSITY_SORTS = ['name', 'city', 'monitoring_status', 'program_count', 'updated_at'] as const
export const SORT_ORDERS = ['asc', 'desc'] as const

export type UniversitySort = typeof UNIVERSITY_SORTS[number]
export type SortOrder = typeof SORT_ORDERS[number]
export type CatalogBoolean = boolean | undefined

export interface UniversityCatalogQuery {
  q: string
  city?: string
  region?: string
  ownership_type?: string
  institution_kind?: string
  category?: string
  monitoring_status?: string
  has_admissions_url: CatalogBoolean
  has_programs: CatalogBoolean
  online_monitoring: CatalogBoolean
  sort: UniversitySort
  order: SortOrder
  page: number
}

export const DEFAULT_CATALOG_QUERY: UniversityCatalogQuery = {
  q: '',
  has_admissions_url: undefined,
  has_programs: undefined,
  online_monitoring: undefined,
  sort: 'name',
  order: 'asc',
  page: 1,
}

const textValue = (params: URLSearchParams, key: string, maximum: number) => {
  const value = params.get(key)?.trim().slice(0, maximum)
  return value || undefined
}

const booleanValue = (params: URLSearchParams, key: string): CatalogBoolean => {
  const value = params.get(key)
  if (value === 'true') return true
  if (value === 'false') return false
  return undefined
}

export function parseUniversityCatalogQuery(params: URLSearchParams): UniversityCatalogQuery {
  const sortCandidate = params.get('sort')
  const orderCandidate = params.get('order')
  const pageCandidate = Number(params.get('page'))

  return {
    q: textValue(params, 'q', 200) ?? '',
    city: textValue(params, 'city', 200),
    region: textValue(params, 'region', 200),
    ownership_type: textValue(params, 'ownership_type', 100),
    institution_kind: textValue(params, 'institution_kind', 100),
    category: textValue(params, 'category', 100),
    monitoring_status: textValue(params, 'monitoring_status', 100),
    has_admissions_url: booleanValue(params, 'has_admissions_url'),
    has_programs: booleanValue(params, 'has_programs'),
    online_monitoring: booleanValue(params, 'online_monitoring'),
    sort: UNIVERSITY_SORTS.includes(sortCandidate as UniversitySort)
      ? sortCandidate as UniversitySort
      : DEFAULT_CATALOG_QUERY.sort,
    order: SORT_ORDERS.includes(orderCandidate as SortOrder)
      ? orderCandidate as SortOrder
      : DEFAULT_CATALOG_QUERY.order,
    page: Number.isInteger(pageCandidate) && pageCandidate >= 1 ? pageCandidate : 1,
  }
}

export function serializeUniversityCatalogQuery(query: UniversityCatalogQuery): URLSearchParams {
  const params = new URLSearchParams()
  if (query.q) params.set('q', query.q)
  if (query.city) params.set('city', query.city)
  if (query.region) params.set('region', query.region)
  if (query.ownership_type) params.set('ownership_type', query.ownership_type)
  if (query.institution_kind) params.set('institution_kind', query.institution_kind)
  if (query.category) params.set('category', query.category)
  if (query.monitoring_status) params.set('monitoring_status', query.monitoring_status)
  if (query.has_admissions_url !== undefined) params.set('has_admissions_url', String(query.has_admissions_url))
  if (query.has_programs !== undefined) params.set('has_programs', String(query.has_programs))
  if (query.online_monitoring !== undefined) params.set('online_monitoring', String(query.online_monitoring))
  if (query.sort !== DEFAULT_CATALOG_QUERY.sort) params.set('sort', query.sort)
  if (query.order !== DEFAULT_CATALOG_QUERY.order) params.set('order', query.order)
  if (query.page !== 1) params.set('page', String(query.page))
  return params
}

export function validateUniversityCatalogQuery(
  query: UniversityCatalogQuery,
  meta: CatalogMeta,
): UniversityCatalogQuery {
  const inOptions = (value: string | undefined, options: string[]) => (
    value && options.includes(value) ? value : undefined
  )
  return {
    ...query,
    city: inOptions(query.city, meta.cities),
    region: inOptions(query.region, meta.regions),
    ownership_type: inOptions(query.ownership_type, meta.ownership_types),
    institution_kind: inOptions(query.institution_kind, meta.institution_kinds),
    category: inOptions(query.category, meta.categories.map((item) => item.code)),
    monitoring_status: inOptions(query.monitoring_status, meta.monitoring_statuses),
  }
}

export function universityCatalogQueriesEqual(
  left: UniversityCatalogQuery,
  right: UniversityCatalogQuery,
) {
  return serializeUniversityCatalogQuery(left).toString() === serializeUniversityCatalogQuery(right).toString()
}

export function buildUniversityApiParams(query: UniversityCatalogQuery, pageSize: number) {
  const params = serializeUniversityCatalogQuery(query)
  params.set('page', String(query.page))
  params.set('page_size', String(pageSize))
  params.set('sort', query.sort)
  params.set('order', query.order)
  return params
}

export function clearUniversityCatalogFilters(query: UniversityCatalogQuery): UniversityCatalogQuery {
  return {
    ...DEFAULT_CATALOG_QUERY,
    sort: query.sort,
    order: query.order,
  }
}

export function hasUniversityCatalogFilters(query: UniversityCatalogQuery) {
  return Boolean(
    query.q || query.city || query.region || query.ownership_type || query.institution_kind
    || query.category || query.monitoring_status || query.has_admissions_url !== undefined
    || query.has_programs !== undefined || query.online_monitoring !== undefined
  )
}

export function compactPageNumbers(current: number, total: number): Array<number | string> {
  if (total <= 7) return Array.from({ length: total }, (_, index) => index + 1)
  const pages = new Set([1, total, current - 1, current, current + 1])
  const available = [...pages].filter((page) => page >= 1 && page <= total).sort((a, b) => a - b)
  const result: Array<number | string> = []
  available.forEach((page, index) => {
    if (index > 0 && page - available[index - 1] > 1) result.push(`ellipsis-${page}`)
    result.push(page)
  })
  return result
}
