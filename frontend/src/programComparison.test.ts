import { describe, expect, it } from 'vitest'

import {
  parseProgramComparisonSelection,
  programComparisonPath,
  programIdentityKey,
  sumKnownAdmissionPlaces,
  summarizeProgramForComparison,
} from './programComparison'
import type { ImportedProgram, OfferingSummary } from './types'

const offering = (id: number, places: number | null, fundingType = 'paid'): OfferingSummary => ({
  id,
  admission_year: 2026,
  study_form: id === 3 ? 'part_time' : 'full_time',
  funding_type: fundingType,
  places,
  monitoring_supported: id === 1,
  monitoring_status: id === 1 ? 'online' : 'reference_only',
  official_url: `https://example.test/offerings/${id}`,
  source_url: `https://example.test/offerings/${id}`,
  source_checked_at: '2026-07-17T12:00:00Z',
})

const program: ImportedProgram = {
  id: 1,
  university_id: 1,
  university: { id: 1, code: 'bseu', slug: 'bseu', short_name: 'БГЭУ' },
  code: '6-05-0311-05',
  slug: 'economic-informatics',
  name: 'Экономическая информатика',
  qualification: null,
  faculty_name: null,
  education_level: null,
  duration_years: null,
  official_url: 'https://example.test/program',
  active: true,
  source_checked_at: '2026-07-17T12:00:00Z',
  verified_at: null,
  updated_at: '2026-07-17T12:00:00Z',
  offering_count: 3,
  offerings: [offering(1, 60), offering(2, null, 'budget'), offering(3, 25)],
  coverage_state: 'available',
}

describe('Program comparison URL identities', () => {
  it('trims identities, removes duplicates, and preserves first occurrence order', () => {
    expect(parseProgramComparisonSelection(
      ' bseu : economic-informatics ,bseu:management,bseu:economic-informatics',
    ).map(programIdentityKey)).toEqual([
      'bseu:economic-informatics',
      'bseu:management',
    ])
  })

  it('removes malformed identities safely', () => {
    expect(parseProgramComparisonSelection(
      'missing-colon,:program,bseu:,BSEU:program,bseu:valid-program:extra,bseu:valid-program',
    ).map(programIdentityKey)).toEqual(['bseu:valid-program'])
  })

  it('truncates more than three identities deterministically', () => {
    expect(parseProgramComparisonSelection(
      'u:a,u:b,u:c,u:d',
    ).map(programIdentityKey)).toEqual(['u:a', 'u:b', 'u:c'])
  })

  it('serializes through URLSearchParams', () => {
    const identities = parseProgramComparisonSelection('bseu:economic-informatics,bseu:management')
    const path = programComparisonPath(identities)
    expect(path).toBe('/compare/programs?programs=bseu%3Aeconomic-informatics%2Cbseu%3Amanagement')
    expect(new URL(path, 'https://example.test').searchParams.get('programs')).toBe(
      'bseu:economic-informatics,bseu:management',
    )
  })
})

describe('Program comparison summaries', () => {
  it('sums known places only and keeps all-null places unknown', () => {
    expect(sumKnownAdmissionPlaces(program.offerings)).toBe(85)
    expect(sumKnownAdmissionPlaces([offering(4, null), offering(5, null)])).toBeNull()
  })

  it('uses the shared Offering summary semantics', () => {
    expect(summarizeProgramForComparison(program)).toEqual({
      totalOfferings: 3,
      studyForms: ['full_time', 'part_time'],
      budgetOfferings: 1,
      paidOfferings: 2,
      liveOfferings: 1,
      knownPlaces: 85,
    })
  })
})
