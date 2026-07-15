import { createContext } from 'react'

import type { ProgramWatch, ProgramWatchEvent, SavedAdmissionList } from './types'

export type ProfileLoadStatus = 'idle' | 'loading' | 'ready' | 'error'

export interface ProfileContextValue {
  data: SavedAdmissionList | null
  watches: ProgramWatch[]
  watchEvents: ProgramWatchEvent[]
  status: ProfileLoadStatus
  invalidTokenRecovered: boolean
  hasProfileToken: boolean
  retry: () => Promise<void>
  updateScore: (score: number | null) => Promise<void>
  saveUniversity: (slug: string) => Promise<void>
  removeUniversity: (slug: string) => Promise<void>
  saveProgram: (universitySlug: string, programSlug: string) => Promise<void>
  removeProgram: (universitySlug: string, programSlug: string) => Promise<void>
  enableWatch: (universitySlug: string, programSlug: string) => Promise<void>
  disableWatch: (universitySlug: string, programSlug: string) => Promise<void>
}

export const ProfileContext = createContext<ProfileContextValue | null>(null)
