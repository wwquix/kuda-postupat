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
  type TelegramStatusLoadState,
} from './profileContextValue'
import { readProfileToken, removeProfileToken, storeProfileToken } from './profileStorage'
import type {
  ProgramWatch,
  ProgramWatchEvent,
  SavedAdmissionList,
  TelegramLinkChallenge,
  TelegramLinkStatus,
} from './types'

const notLinkedTelegramStatus: TelegramLinkStatus = {
  linked: false,
  linked_at: null,
  challenge_expires_at: null,
}

export function ProfileProvider({ children }: { children: ReactNode }) {
  const [initialToken] = useState(readProfileToken)
  const tokenRef = useRef<string | null>(initialToken)
  const createRequest = useRef<Promise<string> | null>(null)
  const telegramAvailabilityRequest = useRef<Promise<void> | null>(null)
  const telegramChallengeRequest = useRef<Promise<TelegramLinkChallenge> | null>(null)
  const telegramUnlinkRequest = useRef<Promise<void> | null>(null)
  const [data, setData] = useState<SavedAdmissionList | null>(null)
  const [watches, setWatches] = useState<ProgramWatch[]>([])
  const [watchEvents, setWatchEvents] = useState<ProgramWatchEvent[]>([])
  const [telegramLinkStatus, setTelegramLinkStatus] = useState<TelegramLinkStatus | null>(
    initialToken ? null : notLinkedTelegramStatus,
  )
  const [telegramLinkChallenge, setTelegramLinkChallenge] = useState<TelegramLinkChallenge | null>(null)
  const [telegramEnabled, setTelegramEnabled] = useState<boolean | null>(null)
  const [telegramStatusState, setTelegramStatusState] = useState<TelegramStatusLoadState>(
    initialToken ? 'loading' : 'ready',
  )
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
    setTelegramLinkStatus(notLinkedTelegramStatus)
    setTelegramLinkChallenge(null)
    setTelegramStatusState('ready')
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
      setTelegramLinkStatus(notLinkedTelegramStatus)
      setTelegramLinkChallenge(null)
      setTelegramStatusState('ready')
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

  const loadTelegramAvailability = useCallback((): Promise<void> => {
    if (telegramAvailabilityRequest.current) return telegramAvailabilityRequest.current
    setTelegramStatusState('loading')
    const request = (async () => {
      try {
        const publicConfig = await api.config()
        setTelegramEnabled(publicConfig.telegram_enabled)
        if (!publicConfig.telegram_enabled) {
          setTelegramLinkStatus(notLinkedTelegramStatus)
          setTelegramLinkChallenge(null)
          setTelegramStatusState('ready')
          return
        }

        const token = tokenRef.current
        if (!token) {
          setTelegramLinkStatus(notLinkedTelegramStatus)
          setTelegramStatusState('ready')
          return
        }
        try {
          const next = await api.telegramLinkStatus(token)
          if (tokenRef.current !== token) return
          setTelegramLinkStatus(next)
          if (next.linked) setTelegramLinkChallenge(null)
          setTelegramStatusState('ready')
        } catch (error) {
          if (error instanceof ApiError && error.status === 401) {
            clearInvalidToken(token)
            return
          }
          setTelegramStatusState('error')
        }
      } catch {
        setTelegramEnabled(null)
        setTelegramStatusState('error')
      }
    })().finally(() => {
      telegramAvailabilityRequest.current = null
    })
    telegramAvailabilityRequest.current = request
    return request
  }, [clearInvalidToken])

  const refreshTelegramLinkStatus = useCallback(async () => {
    if (telegramEnabled !== true) return
    const token = tokenRef.current
    if (!token) {
      setTelegramLinkStatus(notLinkedTelegramStatus)
      setTelegramStatusState('ready')
      return
    }
    setTelegramStatusState('loading')
    try {
      const next = await api.telegramLinkStatus(token)
      setTelegramLinkStatus(next)
      if (next.linked) setTelegramLinkChallenge(null)
      setTelegramStatusState('ready')
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        clearInvalidToken(token)
        return
      }
      setTelegramStatusState('error')
      throw error
    }
  }, [clearInvalidToken, telegramEnabled])

  const createTelegramLinkChallenge = useCallback((): Promise<TelegramLinkChallenge> => {
    if (telegramEnabled !== true) {
      return Promise.reject(new Error('Telegram notifications are unavailable'))
    }
    if (telegramChallengeRequest.current) return telegramChallengeRequest.current
    const request = withProfile((token) => api.createTelegramLinkChallenge(token))
      .then((challenge) => {
        setTelegramLinkChallenge(challenge)
        setTelegramLinkStatus({
          linked: false,
          linked_at: null,
          challenge_expires_at: challenge.expires_at,
        })
        setTelegramStatusState('ready')
        return challenge
      })
      .finally(() => {
        telegramChallengeRequest.current = null
      })
    telegramChallengeRequest.current = request
    return request
  }, [telegramEnabled, withProfile])

  const unlinkTelegram = useCallback((): Promise<void> => {
    if (telegramUnlinkRequest.current) return telegramUnlinkRequest.current
    const request = withProfile((token) => api.unlinkTelegram(token))
      .then((next) => {
        setTelegramLinkStatus(next)
        setTelegramLinkChallenge(null)
        setTelegramStatusState('ready')
      })
      .finally(() => {
        telegramUnlinkRequest.current = null
      })
    telegramUnlinkRequest.current = request
    return request
  }, [withProfile])

  const value = useMemo<ProfileContextValue>(() => ({
    data,
    watches,
    watchEvents,
    telegramLinkStatus,
    telegramLinkChallenge,
    telegramEnabled,
    telegramStatusState,
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
    loadTelegramAvailability,
    createTelegramLinkChallenge,
    refreshTelegramLinkStatus,
    unlinkTelegram,
  }), [
    createTelegramLinkChallenge,
    data,
    hasProfileToken,
    invalidTokenRecovered,
    loadTelegramAvailability,
    mutate,
    mutateWatch,
    retry,
    refreshTelegramLinkStatus,
    status,
    watchEvents,
    watches,
    telegramLinkChallenge,
    telegramLinkStatus,
    telegramEnabled,
    telegramStatusState,
    unlinkTelegram,
  ])

  return <ProfileContext.Provider value={value}>{children}</ProfileContext.Provider>
}
