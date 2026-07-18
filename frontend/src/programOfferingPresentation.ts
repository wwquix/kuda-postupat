import { apiValueLabel } from './catalogPresentation'
import type { OfferingSummary } from './types'

export interface OfferingGroup {
  studyForm: string
  studyFormLabel: string
  offerings: OfferingSummary[]
}

export interface OfferingCatalogSummary {
  total: number
  budget: number
  paid: number
  live: number
  studyForms: string[]
}

export interface OfferingMonitoringPresentation {
  kind: 'live' | 'reference' | 'neutral'
  title: string
  description: string
}

const studyFormOrder = ['full_time', 'part_time', 'distance', 'evening']
const fundingTypeOrder = ['budget', 'paid']
const pluralRules = new Intl.PluralRules('ru-BY')

const enumOrder = (value: string, preferredValues: string[]) => {
  const index = preferredValues.indexOf(value)
  return index === -1 ? preferredValues.length : index
}

const compareLabels = (left: string, right: string) => (
  apiValueLabel(left).localeCompare(apiValueLabel(right), 'ru-BY')
)

const compareStudyForms = (left: string, right: string) => (
  enumOrder(left, studyFormOrder) - enumOrder(right, studyFormOrder)
  || compareLabels(left, right)
  || left.localeCompare(right)
)

const compareOfferings = (left: OfferingSummary, right: OfferingSummary) => (
  right.admission_year - left.admission_year
  || enumOrder(left.funding_type, fundingTypeOrder) - enumOrder(right.funding_type, fundingTypeOrder)
  || compareLabels(left.funding_type, right.funding_type)
  || left.funding_type.localeCompare(right.funding_type)
  || left.id - right.id
)

export function groupOfferingsByStudyForm(offerings: OfferingSummary[]): OfferingGroup[] {
  const grouped = new Map<string, OfferingSummary[]>()
  offerings.forEach((offering) => {
    const group = grouped.get(offering.study_form) ?? []
    group.push(offering)
    grouped.set(offering.study_form, group)
  })
  return [...grouped.entries()]
    .sort(([left], [right]) => compareStudyForms(left, right))
    .map(([studyForm, group]) => ({
      studyForm,
      studyFormLabel: apiValueLabel(studyForm),
      offerings: [...group].sort(compareOfferings),
    }))
}

export function summarizeOfferings(offerings: OfferingSummary[]): OfferingCatalogSummary {
  const studyForms = [...new Set(offerings.map((offering) => offering.study_form))]
    .sort(compareStudyForms)
  return {
    total: offerings.length,
    budget: offerings.filter((offering) => offering.funding_type === 'budget').length,
    paid: offerings.filter((offering) => offering.funding_type === 'paid').length,
    live: offerings.filter((offering) => (
      offering.monitoring_supported && offering.monitoring_status === 'online'
    )).length,
    studyForms,
  }
}

export function fundingTypeLabel(value: string) {
  if (value === 'paid') return 'Платно'
  return apiValueLabel(value)
}

export function offeringMonitoringPresentation(
  offering: OfferingSummary,
): OfferingMonitoringPresentation {
  if (offering.monitoring_supported && offering.monitoring_status === 'online') {
    return {
      kind: 'live',
      title: 'Доступен live-мониторинг',
      description: 'Данные этого варианта автоматически отслеживаются платформой.',
    }
  }
  if (offering.monitoring_status === 'reference_only') {
    return {
      kind: 'reference',
      title: 'Только справочные данные',
      description: 'Вариант доступен в каталоге, но пока не отслеживается автоматически.',
    }
  }
  return {
    kind: 'neutral',
    title: apiValueLabel(offering.monitoring_status),
    description: offering.monitoring_supported
      ? 'Статус автоматического мониторинга указан для этого варианта.'
      : 'Автоматическое отслеживание для этого варианта пока недоступно.',
  }
}

function formatRussianCount(value: number, forms: [string, string, string]) {
  const category = pluralRules.select(value)
  const label = category === 'one' ? forms[0] : category === 'few' ? forms[1] : forms[2]
  return `${value} ${label}`
}

export const formatOfferingCount = (value: number) => formatRussianCount(
  value,
  ['вариант', 'варианта', 'вариантов'],
)

export const formatStudyFormCount = (value: number) => formatRussianCount(
  value,
  ['форма', 'формы', 'форм'],
)

export const formatPlaceCount = (value: number) => formatRussianCount(
  value,
  ['место', 'места', 'мест'],
)
