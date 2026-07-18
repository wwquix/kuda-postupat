import { describe, expect, it } from 'vitest'

import {
  DEFAULT_PROGRAM_DISCOVERY_QUERY,
  deriveProgramDiscoveryOptions,
  filterProgramsForDiscovery,
  parseProgramDiscoveryQuery,
  serializeProgramDiscoveryQuery,
} from './programDiscoveryQuery'
import type { ImportedProgram, OfferingSummary } from './types'

const offering = (
  id: number,
  studyForm: string,
  fundingType: string,
  monitoringStatus: string,
): OfferingSummary => ({
  id,
  admission_year: 2026,
  study_form: studyForm,
  funding_type: fundingType,
  places: 10,
  monitoring_supported: monitoringStatus === 'online',
  monitoring_status: monitoringStatus,
  official_url: `https://example.test/offerings/${id}`,
  source_url: 'https://example.test/source',
  source_checked_at: '2026-07-16T18:00:00Z',
})

const program = (
  id: number,
  name: string,
  code: string | null,
  offerings: OfferingSummary[],
): ImportedProgram => ({
  id,
  university_id: 1,
  university: { id: 1, code: 'bseu', slug: 'bseu', short_name: 'БГЭУ' },
  code,
  slug: `program-${id}`,
  name,
  qualification: null,
  faculty_name: null,
  education_level: null,
  duration_years: null,
  official_url: `https://example.test/programs/${id}`,
  active: true,
  source_checked_at: '2026-07-16T18:00:00Z',
  verified_at: null,
  updated_at: '2026-07-16T18:00:00Z',
  offering_count: offerings.length,
  offerings,
  coverage_state: 'available',
})

const programs = [
  program(1, 'Экономическая информатика', '6-05-0311-05', [
    offering(1, 'full_time', 'paid', 'online'),
    offering(2, 'full_time', 'budget', 'reference_only'),
  ]),
  program(2, 'Менеджмент', null, [
    offering(3, 'part_time', 'paid', 'reference_only'),
    offering(4, 'full_time', 'budget', 'reference_only'),
  ]),
  program(3, 'Маркетинг', '6-05-0412-02', [
    offering(5, 'distance', 'paid', 'unsupported'),
  ]),
]

const find = (query: Parameters<typeof filterProgramsForDiscovery>[1]) => (
  filterProgramsForDiscovery(programs, query)
)

describe('program discovery matching', () => {
  it('searches by full and partial Program name', () => {
    expect(find({ program_query: 'Экономическая информатика' }).items.map((item) => item.program.id)).toEqual([1])
    expect(find({ program_query: 'информат' }).items.map((item) => item.program.id)).toEqual([1])
  })

  it('searches by specialty code', () => {
    expect(find({ program_query: '0311-05' }).items.map((item) => item.program.id)).toEqual([1])
  })

  it('normalizes whitespace and performs case-insensitive Cyrillic search', () => {
    expect(find({ program_query: '  ЭКОНОМИЧЕСКАЯ   ИНФОРМАТИКА ' }).items.map((item) => item.program.id)).toEqual([1])
  })

  it('filters by study form', () => {
    const result = find({ program_query: '', study_form: 'part_time' })
    expect(result.items.map((item) => item.program.id)).toEqual([2])
    expect(result.shownOfferings).toBe(1)
  })

  it('filters by funding type', () => {
    const result = find({ program_query: '', funding_type: 'budget' })
    expect(result.items.map((item) => item.program.id)).toEqual([1, 2])
    expect(result.shownOfferings).toBe(2)
  })

  it('filters by monitoring status', () => {
    const result = find({ program_query: '', monitoring_status: 'online' })
    expect(result.items.map((item) => item.program.id)).toEqual([1])
    expect(result.shownOfferings).toBe(1)
  })

  it('combines search and Offering filters with AND semantics', () => {
    expect(find({
      program_query: 'менеджмент',
      study_form: 'part_time',
      funding_type: 'paid',
      monitoring_status: 'reference_only',
    }).items.map((item) => item.program.id)).toEqual([2])
    expect(find({
      program_query: 'менеджмент',
      study_form: 'part_time',
      funding_type: 'budget',
    }).items).toEqual([])
  })

  it('keeps a Program visible when at least one Offering matches', () => {
    const result = find({ program_query: '', funding_type: 'paid', monitoring_status: 'online' })
    expect(result.items.map((item) => item.program.id)).toEqual([1])
  })

  it('hides nonmatching Offerings without mutating API data', () => {
    const result = find({ program_query: '', funding_type: 'budget' })
    expect(result.items[0].offerings.map((item) => item.id)).toEqual([2])
    expect(programs[0].offerings.map((item) => item.id)).toEqual([1, 2])
  })

  it('keeps every Offering when only search is active', () => {
    const result = find({ program_query: 'экономическая' })
    expect(result.items[0].offerings.map((item) => item.id)).toEqual([1, 2])
    expect(result.shownOfferings).toBe(2)
  })
})

describe('program discovery URL query', () => {
  const options = deriveProgramDiscoveryOptions(programs)

  it('parses known values and normalizes the initial search query', () => {
    const query = parseProgramDiscoveryQuery(new URLSearchParams(
      'program_query=%20%D0%AD%D0%9A%D0%9E%D0%9D%D0%9E%D0%9C%D0%98%D0%9A%D0%90%20%20&study_form=full_time&funding_type=paid&monitoring_status=online',
    ), options)
    expect(query).toEqual({
      program_query: 'ЭКОНОМИКА',
      study_form: 'full_time',
      funding_type: 'paid',
      monitoring_status: 'online',
    })
  })

  it('serializes compact parameters while preserving unrelated University query state', () => {
    const params = serializeProgramDiscoveryQuery({
      program_query: '  менеджмент  ',
      study_form: 'part_time',
      funding_type: 'paid',
    }, new URLSearchParams('from=catalog'))
    expect(params.toString()).toBe('from=catalog&program_query=%D0%BC%D0%B5%D0%BD%D0%B5%D0%B4%D0%B6%D0%BC%D0%B5%D0%BD%D1%82&study_form=part_time&funding_type=paid')
  })

  it('drops unknown URL filter values safely', () => {
    expect(parseProgramDiscoveryQuery(new URLSearchParams(
      'study_form=telepathy&funding_type=unknown&monitoring_status=missing',
    ), options)).toEqual(DEFAULT_PROGRAM_DISCOVERY_QUERY)
  })

  it('reset removes only discovery parameters', () => {
    const params = serializeProgramDiscoveryQuery(
      DEFAULT_PROGRAM_DISCOVERY_QUERY,
      new URLSearchParams('from=catalog&program_query=test&study_form=full_time'),
    )
    expect(params.toString()).toBe('from=catalog')
  })
})
