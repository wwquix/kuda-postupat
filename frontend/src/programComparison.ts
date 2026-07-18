import { summarizeOfferings } from './programOfferingPresentation'
import type { ImportedProgram, OfferingSummary } from './types'

export const MAX_COMPARED_PROGRAMS = 3

export interface ProgramIdentity {
  universitySlug: string
  programSlug: string
}

export interface ProgramComparisonSummary {
  totalOfferings: number
  studyForms: string[]
  budgetOfferings: number
  paidOfferings: number
  liveOfferings: number
  knownPlaces: number | null
}

const slugPattern = /^[a-z0-9]+(?:-[a-z0-9]+)*$/u

export function programIdentityKey(identity: ProgramIdentity) {
  return `${identity.universitySlug}:${identity.programSlug}`
}

export function programIdentityFor(program: ImportedProgram): ProgramIdentity {
  return {
    universitySlug: program.university.slug,
    programSlug: program.slug,
  }
}

export function parseProgramIdentity(value: string): ProgramIdentity | null {
  const parts = value.split(':')
  if (parts.length !== 2) return null
  const universitySlug = parts[0].trim()
  const programSlug = parts[1].trim()
  if (!slugPattern.test(universitySlug) || !slugPattern.test(programSlug)) return null
  return { universitySlug, programSlug }
}

export function normalizeProgramSelection(
  identities: ProgramIdentity[],
): ProgramIdentity[] {
  const unique: ProgramIdentity[] = []
  const keys = new Set<string>()
  for (const identity of identities) {
    const key = programIdentityKey(identity)
    if (keys.has(key)) continue
    keys.add(key)
    unique.push(identity)
    if (unique.length === MAX_COMPARED_PROGRAMS) break
  }
  return unique
}

export function parseProgramComparisonSelection(raw: string | null): ProgramIdentity[] {
  const parsed: ProgramIdentity[] = []
  for (const candidate of (raw ?? '').split(',')) {
    const identity = parseProgramIdentity(candidate.trim())
    if (identity) parsed.push(identity)
  }
  return normalizeProgramSelection(parsed)
}

export function programComparisonSearch(identities: ProgramIdentity[]) {
  const normalized = normalizeProgramSelection(identities)
  if (normalized.length === 0) return ''
  const params = new URLSearchParams()
  params.set('programs', normalized.map(programIdentityKey).join(','))
  return `?${params.toString()}`
}

export function programComparisonPath(identities: ProgramIdentity[]) {
  return `/compare/programs${programComparisonSearch(identities)}`
}

export function sumKnownAdmissionPlaces(offerings: OfferingSummary[]) {
  const known = offerings
    .map((offering) => offering.places)
    .filter((places): places is number => places !== null)
  return known.length > 0 ? known.reduce((total, places) => total + places, 0) : null
}

export function summarizeProgramForComparison(
  program: ImportedProgram,
): ProgramComparisonSummary {
  const offerings = summarizeOfferings(program.offerings)
  return {
    totalOfferings: offerings.total,
    studyForms: offerings.studyForms,
    budgetOfferings: offerings.budget,
    paidOfferings: offerings.paid,
    liveOfferings: offerings.live,
    knownPlaces: sumKnownAdmissionPlaces(program.offerings),
  }
}
