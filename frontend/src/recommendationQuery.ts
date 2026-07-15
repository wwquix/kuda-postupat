import type { CatalogMeta } from './types'

export interface RecommendationQuery {
  applied: boolean
  score?: number
  city?: string
  region?: string
  ownership_type?: string
  institution_kind?: string
  category?: string
  study_form?: string
  funding_type?: string
  online_monitoring?: boolean
  page: number
}

export const DEFAULT_RECOMMENDATION_QUERY: RecommendationQuery = {
  applied: false,
  page: 1,
}

const cleanValue = (params: URLSearchParams, key: string) => params.get(key)?.trim() || undefined

const booleanValue = (value: string | null) => {
  if (value === 'true') return true
  if (value === 'false') return false
  return undefined
}

export function parseRecommendationQuery(params: URLSearchParams): RecommendationQuery {
  const scoreCandidate = Number(params.get('score'))
  const pageCandidate = Number(params.get('page'))
  const hasScore = params.has('score')
    && Number.isInteger(scoreCandidate)
    && scoreCandidate >= 0
    && scoreCandidate <= 500
  return {
    applied: params.get('applied') === 'true',
    score: hasScore ? scoreCandidate : undefined,
    city: cleanValue(params, 'city'),
    region: cleanValue(params, 'region'),
    ownership_type: cleanValue(params, 'ownership_type'),
    institution_kind: cleanValue(params, 'institution_kind'),
    category: cleanValue(params, 'category'),
    study_form: cleanValue(params, 'study_form'),
    funding_type: cleanValue(params, 'funding_type'),
    online_monitoring: booleanValue(params.get('online_monitoring')),
    page: Number.isInteger(pageCandidate) && pageCandidate >= 1 ? pageCandidate : 1,
  }
}

export function serializeRecommendationQuery(query: RecommendationQuery): URLSearchParams {
  const params = new URLSearchParams()
  if (query.applied) params.set('applied', 'true')
  if (query.score !== undefined) params.set('score', String(query.score))
  if (query.city) params.set('city', query.city)
  if (query.region) params.set('region', query.region)
  if (query.ownership_type) params.set('ownership_type', query.ownership_type)
  if (query.institution_kind) params.set('institution_kind', query.institution_kind)
  if (query.category) params.set('category', query.category)
  if (query.study_form) params.set('study_form', query.study_form)
  if (query.funding_type) params.set('funding_type', query.funding_type)
  if (query.online_monitoring !== undefined) {
    params.set('online_monitoring', String(query.online_monitoring))
  }
  if (query.page !== 1) params.set('page', String(query.page))
  return params
}

export function validateRecommendationQuery(
  query: RecommendationQuery,
  meta: CatalogMeta,
): RecommendationQuery {
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
    study_form: inOptions(query.study_form, meta.study_forms),
    funding_type: inOptions(query.funding_type, meta.funding_types),
  }
}

export function recommendationQueriesEqual(left: RecommendationQuery, right: RecommendationQuery) {
  return serializeRecommendationQuery(left).toString() === serializeRecommendationQuery(right).toString()
}

export function buildRecommendationApiParams(query: RecommendationQuery, pageSize = 20) {
  const params = serializeRecommendationQuery(query)
  params.delete('applied')
  params.set('page', String(query.page))
  params.set('page_size', String(pageSize))
  return params
}
