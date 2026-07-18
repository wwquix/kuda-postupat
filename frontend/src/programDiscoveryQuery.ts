import type { ImportedProgram, OfferingSummary } from './types'

export const PROGRAM_DISCOVERY_PARAM_KEYS = [
  'program_query',
  'study_form',
  'funding_type',
  'monitoring_status',
] as const

export interface ProgramDiscoveryQuery {
  program_query: string
  study_form?: string
  funding_type?: string
  monitoring_status?: string
}

export interface ProgramDiscoveryOptions {
  studyForms: string[]
  fundingTypes: string[]
  monitoringStatuses: string[]
}

export interface ProgramDiscoveryItem {
  program: ImportedProgram
  offerings: OfferingSummary[]
}

export interface ProgramDiscoveryResult {
  items: ProgramDiscoveryItem[]
  shownPrograms: number
  totalPrograms: number
  shownOfferings: number
  totalOfferings: number
}

export const DEFAULT_PROGRAM_DISCOVERY_QUERY: ProgramDiscoveryQuery = {
  program_query: '',
}

const normalizeWhitespace = (value: string) => value
  .normalize('NFKC')
  .trim()
  .replace(/\s+/gu, ' ')

const normalizeSearch = (value: string) => normalizeWhitespace(value).toLocaleLowerCase('ru-BY')

const availableValue = (value: string | null, options: string[]) => (
  value && options.includes(value) ? value : undefined
)

const uniqueSorted = (values: string[]) => [...new Set(values)].sort((left, right) => (
  left.localeCompare(right, 'ru-BY')
))

export function deriveProgramDiscoveryOptions(programs: ImportedProgram[]): ProgramDiscoveryOptions {
  const offerings = programs.flatMap((program) => program.offerings)
  return {
    studyForms: uniqueSorted(offerings.map((offering) => offering.study_form)),
    fundingTypes: uniqueSorted(offerings.map((offering) => offering.funding_type)),
    monitoringStatuses: uniqueSorted(offerings.map((offering) => offering.monitoring_status)),
  }
}

export function parseProgramDiscoveryQuery(
  params: URLSearchParams,
  options: ProgramDiscoveryOptions,
): ProgramDiscoveryQuery {
  return {
    program_query: normalizeWhitespace(params.get('program_query') ?? '').slice(0, 200),
    study_form: availableValue(params.get('study_form'), options.studyForms),
    funding_type: availableValue(params.get('funding_type'), options.fundingTypes),
    monitoring_status: availableValue(params.get('monitoring_status'), options.monitoringStatuses),
  }
}

export function serializeProgramDiscoveryQuery(
  query: ProgramDiscoveryQuery,
  currentParams = new URLSearchParams(),
) {
  const params = new URLSearchParams(currentParams)
  PROGRAM_DISCOVERY_PARAM_KEYS.forEach((key) => params.delete(key))
  const programQuery = normalizeWhitespace(query.program_query).slice(0, 200)
  if (programQuery) params.set('program_query', programQuery)
  if (query.study_form) params.set('study_form', query.study_form)
  if (query.funding_type) params.set('funding_type', query.funding_type)
  if (query.monitoring_status) params.set('monitoring_status', query.monitoring_status)
  return params
}

export function hasProgramDiscoveryFilters(query: ProgramDiscoveryQuery) {
  return Boolean(
    query.program_query || query.study_form || query.funding_type || query.monitoring_status,
  )
}

const offeringMatches = (offering: OfferingSummary, query: ProgramDiscoveryQuery) => (
  (!query.study_form || offering.study_form === query.study_form)
  && (!query.funding_type || offering.funding_type === query.funding_type)
  && (!query.monitoring_status || offering.monitoring_status === query.monitoring_status)
)

const programMatchesSearch = (program: ImportedProgram, query: string) => {
  const normalizedQuery = normalizeSearch(query)
  if (!normalizedQuery) return true
  return [program.name, program.code ?? ''].some((value) => normalizeSearch(value).includes(normalizedQuery))
}

export function filterProgramsForDiscovery(
  programs: ImportedProgram[],
  query: ProgramDiscoveryQuery,
): ProgramDiscoveryResult {
  const offeringFiltersActive = Boolean(
    query.study_form || query.funding_type || query.monitoring_status,
  )
  const items = programs.flatMap((program): ProgramDiscoveryItem[] => {
    if (!programMatchesSearch(program, query.program_query)) return []
    const offerings = offeringFiltersActive
      ? program.offerings.filter((offering) => offeringMatches(offering, query))
      : [...program.offerings]
    if (offeringFiltersActive && offerings.length === 0) return []
    return [{ program, offerings }]
  })
  return {
    items,
    shownPrograms: items.length,
    totalPrograms: programs.length,
    shownOfferings: items.reduce((total, item) => total + item.offerings.length, 0),
    totalOfferings: programs.reduce((total, program) => total + program.offerings.length, 0),
  }
}

const pluralRules = new Intl.PluralRules('ru-BY')

export function formatRussianCount(
  value: number,
  forms: { one: string; few: string; many: string },
) {
  const category = pluralRules.select(value)
  const label = category === 'one' ? forms.one : category === 'few' ? forms.few : forms.many
  return `${value} ${label}`
}

export function formatProgramDiscoverySummary(result: ProgramDiscoveryResult) {
  const programs = formatRussianCount(result.shownPrograms, {
    one: 'программа',
    few: 'программы',
    many: 'программ',
  })
  const offerings = formatRussianCount(result.shownOfferings, {
    one: 'вариант обучения',
    few: 'варианта обучения',
    many: 'вариантов обучения',
  })
  return `Показано: ${programs} из ${result.totalPrograms} · ${offerings} из ${result.totalOfferings}`
}
