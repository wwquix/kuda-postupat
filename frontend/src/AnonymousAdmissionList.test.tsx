import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import App from './App'
import { ProfileProvider } from './ProfileContext'
import { SaveControl } from './components/SaveControl'
import { PROFILE_TOKEN_STORAGE_KEY } from './profileStorage'
import type {
  CatalogMeta,
  ImportedProgram,
  ProgramWatch,
  ProgramWatchEvent,
  SavedAdmissionList,
  UniversityDetail,
  UniversityListItem,
} from './types'

const university: UniversityListItem = {
  id: 1,
  code: 'bseu',
  slug: 'bseu',
  short_name: 'БГЭУ',
  full_name: 'Белорусский государственный экономический университет',
  institution_kind: 'university',
  ownership_type: 'state',
  city: 'Минск',
  region: 'Минск',
  official_site_url: 'https://bseu.by/',
  admissions_url: 'https://bseu.by/abiturient/',
  monitoring_status: 'online',
  active: true,
  categories: [{ code: 'economic', label_ru: 'Экономический' }],
  program_count: 1,
  offering_count: 1,
  coverage: {
    programs: 'available',
    offerings: 'available',
    online_monitoring: 'available',
    note: 'Покрытие доступно.',
  },
}

const unsupportedUniversity: UniversityListItem = {
  ...university,
  id: 2,
  code: 'alpha',
  slug: 'alpha',
  short_name: 'Альфа',
  full_name: 'Альфа университет',
  city: 'Брест',
  region: 'Брестская область',
  monitoring_status: 'reference_only',
  program_count: 1,
  offering_count: 0,
  coverage: {
    programs: 'available',
    offerings: 'not_imported',
    online_monitoring: 'not_implemented',
    note: 'Мониторинг не реализован.',
  },
}

const program: ImportedProgram = {
  id: 1,
  university_id: 1,
  university: { id: 1, code: 'bseu', slug: 'bseu', short_name: 'БГЭУ' },
  code: '6-05-0311-05',
  slug: 'economic-informatics',
  name: 'Экономическая информатика',
  qualification: 'Экономист. Информатик',
  faculty_name: 'Факультет цифровой экономики',
  education_level: null,
  duration_years: null,
  official_url: 'https://bseu.by/program',
  active: true,
  source_checked_at: '2026-07-15T14:00:00Z',
  verified_at: null,
  updated_at: '2026-07-15T14:00:00Z',
  offering_count: 1,
  offerings: [{
    id: 1,
    admission_year: 2026,
    study_form: 'full_time',
    funding_type: 'paid',
    places: 60,
    monitoring_supported: true,
    monitoring_status: 'online',
    official_url: 'https://bseu.by/offering',
    source_url: 'https://bseu.by/offering',
    source_checked_at: '2026-07-15T14:00:00Z',
  }],
  coverage_state: 'available',
}

const unsupportedProgram: ImportedProgram = {
  ...program,
  id: 2,
  university_id: 2,
  university: { id: 2, code: 'alpha', slug: 'alpha', short_name: 'Альфа' },
  code: null,
  slug: 'accounting',
  name: 'Бухгалтерский учёт',
  offering_count: 0,
  offerings: [],
}

const universityDetail: UniversityDetail = {
  ...university,
  description: null,
  source_url: 'https://edu.gov.by/registry',
  source_checked_at: '2026-07-15T14:00:00Z',
  data_verified_at: '2026-07-15T14:00:00Z',
  updated_at: '2026-07-15T14:00:00Z',
  sources: [],
  programs: [program],
}

const meta: CatalogMeta = {
  cities: ['Минск'],
  regions: ['Минск'],
  ownership_types: ['state'],
  institution_kinds: ['university'],
  categories: [{ code: 'economic', label_ru: 'Экономический' }],
  monitoring_statuses: ['online'],
  admission_years: [2026],
  study_forms: ['full_time'],
  funding_types: ['paid'],
  counts: {
    universities: 1,
    programs: 1,
    offerings: 1,
    universities_with_programs: 1,
    universities_with_admissions_url: 1,
  },
  pagination: { default_page_size: 20, maximum_page_size: 100 },
  coverage: {
    universities_total: 1,
    universities_with_imported_programs: 1,
    programs_total: 1,
    offerings_total: 1,
    state: 'partial',
    note: 'Покрытие неполное.',
  },
}

const emptyList = (): SavedAdmissionList => ({
  profile: {
    personal_score: null,
    created_at: '2026-07-15T14:00:00Z',
    updated_at: '2026-07-15T14:00:00Z',
  },
  universities: [],
  programs: [],
})

const populatedList = (): SavedAdmissionList => ({
  profile: {
    personal_score: 292,
    created_at: '2026-07-15T14:00:00Z',
    updated_at: '2026-07-15T14:10:00Z',
  },
  universities: [
    { saved_at: '2026-07-15T14:05:00Z', university },
    { saved_at: '2026-07-15T14:05:00Z', university: unsupportedUniversity },
  ],
  programs: [
    {
      saved_at: '2026-07-15T14:05:00Z',
      program,
      monitoring_state: 'available',
      watch_supported: true,
      monitoring: {
        offering_id: 1,
        snapshot_id: 8,
        fetched_at: '2026-07-15T14:09:00Z',
        status: 'Пограничная ситуация',
        competition: 1.67,
        estimated_cutoff_min: 290,
        estimated_cutoff_max: 299,
        estimated_user_position: 3,
        margin_min: -7,
        margin_max: 2,
        has_competition: true,
      },
    },
    {
      saved_at: '2026-07-15T14:06:00Z',
      program: unsupportedProgram,
      monitoring_state: 'unsupported',
      monitoring: null,
      watch_supported: false,
    },
  ],
})

const fetchMock = vi.fn<typeof fetch>()
let serverList: SavedAdmissionList
let acceptedToken: string
let failMutation = false
let failWatchMutation = false
let serverWatches: ProgramWatch[]
let serverWatchEvents: ProgramWatchEvent[]

function response(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status >= 400 ? 'Request failed' : 'OK',
    json: async () => body,
  } as Response
}

async function handleRequest(input: RequestInfo | URL, init?: RequestInit) {
  const url = new URL(String(input), 'http://localhost')
  const method = init?.method ?? 'GET'
  const authorization = new Headers(init?.headers).get('Authorization')
  if (url.pathname === '/api/catalog/meta') return response(meta)
  if (url.pathname === '/api/universities' && method === 'GET') {
    return response({
      items: [university],
      pagination: {
        page: 1,
        page_size: 20,
        total_items: 1,
        total_pages: 1,
        has_next: false,
        has_previous: false,
      },
    })
  }
  if (url.pathname === '/api/universities/bseu/programs/economic-informatics') return response(program)
  if (url.pathname === '/api/universities/bseu') return response(universityDetail)
  if (url.pathname === '/api/profile' && method === 'POST') {
    acceptedToken = 'created-profile-token'
    return response({ token: acceptedToken, ...serverList }, 201)
  }
  if (url.pathname === '/api/profile/saved' && method === 'GET') {
    if (authorization !== `Bearer ${acceptedToken}`) return response({ detail: 'invalid' }, 401)
    return response(serverList)
  }
  if (url.pathname === '/api/profile/watches' && method === 'GET') {
    if (authorization !== `Bearer ${acceptedToken}`) return response({ detail: 'invalid' }, 401)
    return response(serverWatches)
  }
  if (url.pathname === '/api/profile/watch-events' && method === 'GET') {
    if (authorization !== `Bearer ${acceptedToken}`) return response({ detail: 'invalid' }, 401)
    return response(serverWatchEvents)
  }
  if (url.pathname === '/api/profile/score' && method === 'PATCH') {
    const body = JSON.parse(String(init?.body)) as { score: number | null }
    serverList = {
      ...serverList,
      profile: { ...serverList.profile, personal_score: body.score },
    }
    return response(serverList)
  }
  if (url.pathname === '/api/profile/universities/bseu') {
    if (failMutation) return response({ detail: 'raw failure' }, 500)
    serverList = {
      ...serverList,
      universities: method === 'DELETE'
        ? serverList.universities.filter((item) => item.university.slug !== 'bseu')
        : [{ saved_at: '2026-07-15T14:05:00Z', university }],
    }
    return response(serverList)
  }
  if (url.pathname === '/api/profile/programs/bseu/economic-informatics') {
    serverList = {
      ...serverList,
      programs: method === 'DELETE'
        ? serverList.programs.filter((item) => item.program.slug !== program.slug)
        : [{
          saved_at: '2026-07-15T14:05:00Z',
          program,
          monitoring_state: serverList.profile.personal_score === null ? 'score_required' : 'available',
          monitoring: null,
          watch_supported: true,
        }],
    }
    return response(serverList)
  }
  if (url.pathname === '/api/profile/watches/bseu/economic-informatics') {
    if (failWatchMutation) return response({ detail: 'watch failure' }, 500)
    if (method === 'PUT') {
      const watch: ProgramWatch = {
        enabled: true,
        created_at: '2026-07-15T14:20:00Z',
        updated_at: '2026-07-15T14:20:00Z',
        university: {
          slug: university.slug,
          short_name: university.short_name,
          full_name: university.full_name,
        },
        program: { slug: program.slug, name: program.name },
      }
      serverWatches = [watch]
      return response(watch)
    }
    serverWatches = []
    return response({
      university_slug: university.slug,
      program_slug: program.slug,
      enabled: false,
    })
  }
  throw new Error(`Unexpected mocked request: ${method} ${url.pathname}`)
}

function installStorage() {
  const values = new Map<string, string>()
  const storage: Storage = {
    get length() { return values.size },
    clear: () => values.clear(),
    getItem: (key) => values.get(key) ?? null,
    key: (index) => [...values.keys()][index] ?? null,
    removeItem: (key) => { values.delete(key) },
    setItem: (key, value) => { values.set(key, value) },
  }
  Object.defineProperty(window, 'localStorage', { configurable: true, value: storage })
  return storage
}

function renderRoute(route: string, basename?: string) {
  return render(<MemoryRouter basename={basename} initialEntries={[route]}><App /></MemoryRouter>)
}

beforeEach(() => {
  installStorage()
  serverList = emptyList()
  acceptedToken = 'restored-profile-token'
  failMutation = false
  failWatchMutation = false
  serverWatches = []
  serverWatchEvents = []
  fetchMock.mockReset()
  fetchMock.mockImplementation(handleRequest)
  vi.stubGlobal('fetch', fetchMock)
})

describe('anonymous profile bootstrap and save controls', () => {
  it('creates the profile lazily and saves from a university catalog card', async () => {
    const user = userEvent.setup()
    renderRoute('/universities')
    await screen.findByRole('heading', { name: university.full_name })
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false)

    await user.click(screen.getByRole('button', { name: `Сохранить — ${university.full_name}` }))

    expect(await screen.findByText('Сохранено')).toBeInTheDocument()
    expect(localStorage.getItem(PROFILE_TOKEN_STORAGE_KEY)).toBe('created-profile-token')
    expect(fetchMock.mock.calls.filter(([input, init]) => (
      String(input).endsWith('/api/profile') && init?.method === 'POST'
    ))).toHaveLength(1)
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/profile/universities/bseu',
      expect.objectContaining({ method: 'PUT' }),
    )
  })

  it.each([
    ['/universities/bseu', university.full_name, '/api/profile/universities/bseu'],
    ['/universities/bseu/programs/economic-informatics', program.name, '/api/profile/programs/bseu/economic-informatics'],
  ])('exposes a working save control on %s', async (route, label, mutationPath) => {
    const user = userEvent.setup()
    renderRoute(route)
    await screen.findByRole('heading', { level: 1, name: label })
    await user.click(screen.getByRole('button', { name: `Сохранить — ${label}` }))
    await screen.findByText('Сохранено')
    expect(fetchMock.mock.calls.some(([input, init]) => (
      String(input) === mutationPath && init?.method === 'PUT'
    ))).toBe(true)
  })

  it('prevents duplicate concurrent profile creation requests', async () => {
    let resolveCreate: ((value: Response) => void) | undefined
    fetchMock.mockImplementation((input, init) => {
      if (String(input).endsWith('/api/profile') && init?.method === 'POST') {
        return new Promise((resolve) => { resolveCreate = resolve })
      }
      return handleRequest(input, init)
    })
    render(<ProfileProvider>
      <SaveControl kind="university" label="БГЭУ" universitySlug="bseu" />
      <SaveControl kind="program" label="Экономическая информатика" programSlug="economic-informatics" universitySlug="bseu" />
    </ProfileProvider>)

    fireEvent.click(screen.getByRole('button', { name: 'Сохранить — БГЭУ' }))
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить — Экономическая информатика' }))
    await waitFor(() => expect(resolveCreate).toBeDefined())
    expect(fetchMock.mock.calls.filter(([input, init]) => (
      String(input).endsWith('/api/profile') && init?.method === 'POST'
    ))).toHaveLength(1)
    resolveCreate?.(response({ token: 'created-profile-token', ...serverList }, 201))
    await waitFor(() => expect(fetchMock.mock.calls.filter(([, init]) => init?.method === 'PUT')).toHaveLength(2))
  })

  it('keeps saved state after refresh and supports /bseu/my-list directly', async () => {
    acceptedToken = 'restored-profile-token'
    serverList = populatedList()
    serverWatches = [{
      enabled: true,
      created_at: '2026-07-15T14:20:00Z',
      updated_at: '2026-07-15T14:20:00Z',
      university: {
        slug: university.slug,
        short_name: university.short_name,
        full_name: university.full_name,
      },
      program: { slug: program.slug, name: program.name },
    }]
    serverWatchEvents = [{
      event_kind: 'applications_total_changed',
      description: 'Количество заявлений изменилось: 5 → 6.',
      created_at: '2026-07-15T14:25:00Z',
      university: {
        slug: university.slug,
        short_name: university.short_name,
        full_name: university.full_name,
      },
      program: { slug: program.slug, name: program.name },
    }]
    localStorage.setItem(PROFILE_TOKEN_STORAGE_KEY, acceptedToken)
    const { container } = renderRoute('/bseu/my-list', '/bseu')

    expect(await screen.findByRole('heading', { level: 1, name: 'Мой список поступления' })).toBeInTheDocument()
    expect((await screen.findAllByRole('link', { name: university.full_name })).some((link) => (
      link.getAttribute('href') === '/bseu/universities/bseu'
    ))).toBe(true)
    expect(screen.getByRole('link', { name: 'Мой список' })).toHaveAttribute('href', '/bseu/my-list')
    expect(container.querySelectorAll('h1')).toHaveLength(1)
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false)
    expect(screen.getByText('Наблюдение включено')).toBeInTheDocument()
    expect(screen.getByText('Количество заявлений изменилось: 5 → 6.')).toBeInTheDocument()
  })

  it('clears an invalid restored token and creates a replacement only after an action', async () => {
    localStorage.setItem(PROFILE_TOKEN_STORAGE_KEY, 'invalid-token')
    const user = userEvent.setup()
    renderRoute('/my-list')

    expect(await screen.findByText(/Сохранённый доступ устарел/)).toBeInTheDocument()
    expect(localStorage.getItem(PROFILE_TOKEN_STORAGE_KEY)).toBeNull()
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false)
    await user.type(screen.getByRole('spinbutton', { name: 'Балл для поступления' }), '292')
    await user.click(screen.getByRole('button', { name: 'Сохранить балл' }))
    expect(await screen.findByText('Личный балл сохранён.')).toBeInTheDocument()
    expect(localStorage.getItem(PROFILE_TOKEN_STORAGE_KEY)).toBe('created-profile-token')
  })
})

describe('/my-list behavior and truthful monitoring', () => {
  it('renders the empty state and validates score before creating a profile', async () => {
    const user = userEvent.setup()
    const { container } = renderRoute('/my-list')
    expect(screen.getByRole('heading', { level: 1, name: 'Мой список поступления' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Список пока пуст' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Перейти к вузам' })).toHaveAttribute('href', '/universities')
    expect(container.querySelectorAll('h1')).toHaveLength(1)

    await user.type(screen.getByRole('spinbutton', { name: 'Балл для поступления' }), '501')
    await user.click(screen.getByRole('button', { name: 'Сохранить балл' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Введите целое число от 0 до 500.')
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false)
  })

  it('renders server-provided BSEU status and unsupported wording without monitor API calculations', async () => {
    serverList = populatedList()
    localStorage.setItem(PROFILE_TOKEN_STORAGE_KEY, acceptedToken)
    renderRoute('/my-list')

    expect(await screen.findByText('Пограничная ситуация')).toBeInTheDocument()
    expect(screen.getByText('290–299')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getAllByText('Мониторинг пока недоступен').length).toBeGreaterThan(0)
    expect(screen.getByRole('link', { name: 'Подробнее в мониторе' })).toHaveAttribute('href', '/monitor')
    const requestedUrls = fetchMock.mock.calls.map(([input]) => String(input))
    expect(requestedUrls).toEqual([
      '/api/profile/saved',
      '/api/profile/watches',
      '/api/profile/watch-events',
    ])
    expect(requestedUrls.some((url) => url.includes('/latest') || url.includes('score-distribution'))).toBe(false)
  })

  it('enables and disables a watch only after confirmed backend responses', async () => {
    const user = userEvent.setup()
    serverList = populatedList()
    localStorage.setItem(PROFILE_TOKEN_STORAGE_KEY, acceptedToken)
    renderRoute('/my-list')

    const enable = await screen.findByRole('button', { name: 'Включить наблюдение' })
    expect(screen.queryByText('Наблюдение включено')).not.toBeInTheDocument()
    await user.click(enable)
    expect(await screen.findByText('Наблюдение включено')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Отключить наблюдение' }))
    expect(await screen.findByRole('button', { name: 'Включить наблюдение' })).toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([input, init]) => (
      String(input) === '/api/profile/watches/bseu/economic-informatics'
      && init?.method === 'PUT'
    ))).toBe(true)
    expect(fetchMock.mock.calls.some(([input, init]) => (
      String(input) === '/api/profile/watches/bseu/economic-informatics'
      && init?.method === 'DELETE'
    ))).toBe(true)
  })

  it('shows pending and retryable watch-operation failure states without optimistic enablement', async () => {
    const user = userEvent.setup()
    serverList = populatedList()
    localStorage.setItem(PROFILE_TOKEN_STORAGE_KEY, acceptedToken)
    let resolveMutation: ((value: Response) => void) | undefined
    fetchMock.mockImplementation((input, init) => {
      if (
        String(input) === '/api/profile/watches/bseu/economic-informatics'
        && init?.method === 'PUT'
      ) {
        return new Promise((resolve) => { resolveMutation = resolve })
      }
      return handleRequest(input, init)
    })
    renderRoute('/my-list')
    await user.click(await screen.findByRole('button', { name: 'Включить наблюдение' }))
    expect(screen.getByRole('button', { name: 'Включаем…' })).toBeDisabled()
    expect(screen.queryByText('Наблюдение включено')).not.toBeInTheDocument()
    resolveMutation?.(response({ enabled: true }))
    await waitFor(() => expect(resolveMutation).toBeDefined())

    failWatchMutation = true
    fetchMock.mockImplementation(handleRequest)
    await waitFor(() => expect(screen.getByRole('button', { name: 'Включить наблюдение' })).toBeEnabled())
    await user.click(screen.getByRole('button', { name: 'Включить наблюдение' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Не удалось изменить наблюдение')
    expect(screen.getByRole('button', { name: 'Включить наблюдение' })).toBeInTheDocument()
  })

  it('renders empty and populated event history with real links and score guidance', async () => {
    serverList = populatedList()
    serverList = {
      ...serverList,
      profile: { ...serverList.profile, personal_score: null },
      programs: serverList.programs.map((item) => (
        item.program.slug === program.slug
          ? { ...item, monitoring_state: 'score_required', monitoring: null }
          : item
      )),
    }
    localStorage.setItem(PROFILE_TOKEN_STORAGE_KEY, acceptedToken)
    const { unmount } = renderRoute('/my-list')
    expect(await screen.findByText('Изменений пока нет')).toBeInTheDocument()
    expect(screen.getByText(/Изменения позиции и статуса появятся/)).toBeInTheDocument()
    unmount()

    serverWatchEvents = [{
      event_kind: 'user_status_changed',
      description: 'Статус для вашего балла изменился: «Пограничная ситуация» → «Пока не проходит».',
      created_at: '2026-07-15T14:25:00Z',
      university: {
        slug: university.slug,
        short_name: university.short_name,
        full_name: university.full_name,
      },
      program: { slug: program.slug, name: program.name },
    }]
    renderRoute('/my-list')
    expect(await screen.findByText(/Статус для вашего балла изменился/)).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: program.name }).some((link) => (
      link.getAttribute('href') === '/universities/bseu/programs/economic-informatics'
    ))).toBe(true)
    expect(screen.getByRole('link', { name: 'Открыть программу' })).toHaveAttribute(
      'href',
      '/universities/bseu/programs/economic-informatics',
    )
    expect(screen.getAllByRole('link', { name: 'Открыть монитор' }).some((link) => (
      link.getAttribute('href') === '/monitor'
    ))).toBe(true)
  })

  it('keeps the saved UI when a save/remove mutation fails and allows retry', async () => {
    failMutation = true
    const user = userEvent.setup()
    renderRoute('/universities')
    await screen.findByRole('heading', { name: university.full_name })
    const saveButton = screen.getByRole('button', { name: `Сохранить — ${university.full_name}` })
    await user.click(saveButton)
    expect(await screen.findByRole('alert')).toHaveTextContent('Не удалось изменить список')
    expect(screen.getByRole('button', { name: `Сохранить — ${university.full_name}` })).toBeInTheDocument()

    failMutation = false
    await user.click(screen.getByRole('button', { name: `Сохранить — ${university.full_name}` }))
    expect(await screen.findByText('Сохранено')).toBeInTheDocument()
    failMutation = true
    await user.click(screen.getByRole('button', { name: `Удалить из списка — ${university.full_name}` }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Не удалось изменить список')
    expect(screen.getByText('Сохранено')).toBeInTheDocument()
  })
})
