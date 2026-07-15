import {
  type ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'

import { api, ApiError } from './api'
import {
  ProfileContext,
  type ProfileContextValue,
  type ProfileLoadStatus,
} from './profileContextValue'
import { readProfileToken, removeProfileToken, storeProfileToken } from './profileStorage'
import type { ProgramWatch, ProgramWatchEvent, SavedAdmissionList } from './types'

export function ProfileProvider({ children }: { children: ReactNode }) {
  const [initialToken] = useState(readProfileToken)
  const tokenRef = useRef<string | null>(initialToken)
  const createRequest = useRef<Promise<string> | null>(null)
  const [data, setData] = useState<SavedAdmissionList | null>(null)
  const [watches, setWatches] = useState<ProgramWatch[]>([])
  const [watchEvents, setWatchEvents] = useState<ProgramWatchEvent[]>([])
  const [status, setStatus] = useState<ProfileLoadStatus>(initialToken ? 'loading' : 'idle')
  const [invalidTokenRecovered, setInvalidTokenRecovered] = useState(false)
  const [hasProfileToken, setHasProfileToken] = useState(Boolean(initialToken))

  const applyList = useCallback((next: SavedAdmissionList) => {
    setData(next)
    setStatus('ready')
    setInvalidTokenRecovered(false)
    setHasProfileToken(true)
  }, [])

  const applyLoadedProfile = useCallback((
    next: SavedAdmissionList,
    nextWatches: ProgramWatch[],
    nextEvents: ProgramWatchEvent[],
  ) => {
    setWatches(nextWatches)
    setWatchEvents(nextEvents)
    applyList(next)
  }, [applyList])

  const clearInvalidToken = useCallback((expectedToken: string) => {
    if (tokenRef.current !== expectedToken) return false
    removeProfileToken()
    tokenRef.current = null
    setData(null)
    setWatches([])
    setWatchEvents([])
    setStatus('idle')
    setInvalidTokenRecovered(true)
    setHasProfileToken(false)
    return true
  }, [])

  useEffect(() => {
    const restoredToken = initialToken
    if (!restoredToken) return undefined
    const controller = new AbortController()
    Promise.all([
      api.savedAdmissionList(restoredToken, controller.signal),
      api.watches(restoredToken, controller.signal),
      api.watchEvents(restoredToken, controller.signal),
    ])
      .then(([next, nextWatches, nextEvents]) => {
        if (!controller.signal.aborted && tokenRef.current === restoredToken) {
          applyLoadedProfile(next, nextWatches, nextEvents)
        }
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted || tokenRef.current !== restoredToken) return
        if (error instanceof ApiError && error.status === 401) {
          clearInvalidToken(restoredToken)
          return
        }
        setStatus('error')
      })
    return () => controller.abort()
  }, [applyLoadedProfile, clearInvalidToken, initialToken])

  const ensureProfile = useCallback(async () => {
    if (tokenRef.current) return tokenRef.current
    if (createRequest.current) return createRequest.current
    const request = api.createProfile().then((created) => {
      const { token, ...savedList } = created
      tokenRef.current = token
      storeProfileToken(token)
      setWatches([])
      setWatchEvents([])
      applyList(savedList)
      return token
    })
    createRequest.current = request
    try {
      return await request
    } finally {
      createRequest.current = null
    }
  }, [applyList])

  const withProfile = useCallback(async <T,>(
    operation: (token: string) => Promise<T>,
  ): Promise<T> => {
    let token = await ensureProfile()
    try {
      return await operation(token)
    } catch (error) {
      if (!(error instanceof ApiError) || error.status !== 401) throw error
      clearInvalidToken(token)
      token = await ensureProfile()
      return operation(token)
    }
  }, [clearInvalidToken, ensureProfile])

  const mutate = useCallback(async (
    operation: (token: string) => Promise<SavedAdmissionList>,
  ) => {
    const next = await withProfile(operation)
    applyList(next)
  }, [applyList, withProfile])

  const retry = useCallback(async () => {
    const token = tokenRef.current
    if (!token) {
      setStatus('idle')
      return
    }
    setStatus('loading')
    try {
      const [next, nextWatches, nextEvents] = await Promise.all([
        api.savedAdmissionList(token),
        api.watches(token),
        api.watchEvents(token),
      ])
      applyLoadedProfile(next, nextWatches, nextEvents)
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        clearInvalidToken(token)
        return
      }
      setStatus('error')
    }
  }, [applyLoadedProfile, clearInvalidToken])

  const mutateWatch = useCallback(async (
    operation: (token: string) => Promise<unknown>,
  ) => {
    const loaded = await withProfile(async (token) => {
      await operation(token)
      const [nextWatches, nextEvents] = await Promise.all([
        api.watches(token),
        api.watchEvents(token),
      ])
      return { nextWatches, nextEvents }
    })
    setWatches(loaded.nextWatches)
    setWatchEvents(loaded.nextEvents)
  }, [withProfile])

  const value = useMemo<ProfileContextValue>(() => ({
    data,
    watches,
    watchEvents,
    status,
    invalidTokenRecovered,
    hasProfileToken,
    retry,
    updateScore: (score) => mutate((token) => api.updateProfileScore(token, score)),
    saveUniversity: (slug) => mutate((token) => api.saveUniversity(token, slug)),
    removeUniversity: (slug) => mutate((token) => api.removeUniversity(token, slug)),
    saveProgram: (universitySlug, programSlug) => mutate(
      (token) => api.saveProgram(token, universitySlug, programSlug),
    ),
    removeProgram: (universitySlug, programSlug) => mutate(
      (token) => api.removeProgram(token, universitySlug, programSlug),
    ),
    enableWatch: (universitySlug, programSlug) => mutateWatch(
      (token) => api.enableWatch(token, universitySlug, programSlug),
    ),
    disableWatch: (universitySlug, programSlug) => mutateWatch(
      (token) => api.disableWatch(token, universitySlug, programSlug),
    ),
  }), [
    data,
    hasProfileToken,
    invalidTokenRecovered,
    mutate,
    mutateWatch,
    retry,
    status,
    watchEvents,
    watches,
  ])

  return <ProfileContext.Provider value={value}>{children}</ProfileContext.Provider>
}
