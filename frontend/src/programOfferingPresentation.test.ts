import { describe, expect, it } from 'vitest'

import {
  fundingTypeLabel,
  groupOfferingsByStudyForm,
  offeringMonitoringPresentation,
  summarizeOfferings,
} from './programOfferingPresentation'
import type { OfferingSummary } from './types'

const offering = (
  id: number,
  studyForm: string,
  fundingType: string,
  admissionYear: number,
  monitoringStatus = 'reference_only',
  monitoringSupported = false,
): OfferingSummary => ({
  id,
  admission_year: admissionYear,
  study_form: studyForm,
  funding_type: fundingType,
  places: null,
  monitoring_supported: monitoringSupported,
  monitoring_status: monitoringStatus,
  official_url: `https://example.test/offerings/${id}`,
  source_url: `https://example.test/offerings/${id}`,
  source_checked_at: '2026-07-16T18:00:00Z',
})

describe('offering grouping and summaries', () => {
  const offerings = [
    offering(4, 'weekend', 'employer_grant', 2026, 'experimental_mode'),
    offering(3, 'part_time', 'paid', 2026),
    offering(2, 'full_time', 'paid', 2026, 'online', true),
    offering(1, 'full_time', 'budget', 2025),
  ]

  it('groups by study form without merging distinct Offering records', () => {
    const groups = groupOfferingsByStudyForm(offerings)
    expect(groups.map((group) => [group.studyForm, group.offerings.map((item) => item.id)])).toEqual([
      ['full_time', [2, 1]],
      ['part_time', [3]],
      ['weekend', [4]],
    ])
  })

  it('uses deterministic group and Offering order regardless of API order', () => {
    const forward = groupOfferingsByStudyForm(offerings)
    const reversed = groupOfferingsByStudyForm([...offerings].reverse())
    expect(reversed).toEqual(forward)
    expect(offerings.map((item) => item.id)).toEqual([4, 3, 2, 1])
  })

  it('counts total, budget, paid, study forms, and truly live Offerings', () => {
    expect(summarizeOfferings(offerings)).toEqual({
      total: 4,
      budget: 1,
      paid: 2,
      live: 1,
      studyForms: ['full_time', 'part_time', 'weekend'],
    })
  })

  it('presents budget and paid prominently while delegating additional values to apiValueLabel', () => {
    expect(fundingTypeLabel('budget')).toBe('Бюджет')
    expect(fundingTypeLabel('paid')).toBe('Платно')
    expect(fundingTypeLabel('employer_grant')).toBe('Employer grant')
  })
})

describe('offering monitoring presentation', () => {
  it('requires both supported=true and online status for the live state', () => {
    expect(offeringMonitoringPresentation(offering(1, 'full_time', 'paid', 2026, 'online', true))).toMatchObject({
      kind: 'live',
      title: 'Доступен live-мониторинг',
    })
    expect(offeringMonitoringPresentation(offering(2, 'full_time', 'paid', 2026, 'online', false)).kind).toBe('neutral')
  })

  it('describes reference-only data as catalog data and handles additional states neutrally', () => {
    const reference = offeringMonitoringPresentation(offering(1, 'full_time', 'paid', 2026))
    expect(reference.kind).toBe('reference')
    expect(reference.description).toContain('доступен в каталоге')
    expect(reference.description).toContain('не отслеживается автоматически')

    const additional = offeringMonitoringPresentation(offering(2, 'weekend', 'employer_grant', 2026, 'experimental_mode'))
    expect(additional).toMatchObject({ kind: 'neutral', title: 'Experimental mode' })
  })
})
