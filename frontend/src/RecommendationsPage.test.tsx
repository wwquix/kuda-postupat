import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation, useNavigate } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import App from './App'
import { PROFILE_TOKEN_STORAGE_KEY } from './profileStorage'
import type {
  CatalogMeta,
  ImportedProgram,
  RecommendationResponse,
  SavedAdmissionList,
  UniversityListItem,
} from './types'

const meta: CatalogMeta = {
  cities: ['Брест', 'Минск'],
  regions: ['Брестская область', 'Минск'],
  ownership_types: ['private', 'state'],
  institution_kinds: ['academy', 'university'],
  categories: [
    { code: 'economic', label_ru: 'Экономический' },
    { code: 'technical', label_ru: 'Технический' },
  ],
  monitoring_statuses: ['online', 'reference_only'],
  admission_years: [2026],
  study_forms: ['full_time', 'part_time'],
  funding_types: ['budget', 'paid'],
  counts: {
    universities: 2,
    programs: 2,
    offerings: 2,
    universities_with_programs: 2,
    universities_with_admissions_url: 1,
  },
  pagination: { default_page_size: 20, maximum_page_size: 100 },
  coverage: {
    universities_total: 2,
    universities_with_imported_programs: 2,
    programs_total: 2,
    offerings_total: 2,
    state: 'partial',
    note: 'Покрытие платформы неполное.',
  },
}

const bseu: UniversityListItem = {
  id: 1,
  code: 'bseu',
  slug: 'bseu',
  short_name: 'БГЭУ',
  full_name: 'Белорусский государственный экономический университет',
  institution_kind: 'university',
  ownership_type: 'state',
  city: 'Минск',
  region: 'Минск',
  official_site_url: 'https://bseu.by',
  admissions_url: 'https://bseu.by/abiturient',
  monitoring_status: 'online',
  active: true,
  categories: [{ code: 'economic', label_ru: 'Экономический' }],
  program_count: 1,
  offering_count: 1,
  coverage: {
    programs: 'available',
    offerings: 'available',
    online_monitoring: 'available',
    note: 'Мониторинг доступен.',
  },
}

const alpha: UniversityListItem = {
  ...bseu,
  id: 2,
  code: 'alpha',
  slug: 'alpha',
  short_name: 'Альфа',
  full_name: 'Академия Альфа с очень длинным официальным названием',
  institution_kind: 'academy',
  ownership_type: 'private',
  city: 'Брест',
  region: 'Брестская область',
  monitoring_status: 'reference_only',
  categories: [{ code: 'technical', label_ru: 'Технический' }],
  offering_count: 0,
  coverage: {
    programs: 'available',
    offerings: 'not_imported',
    online_monitoring: 'not_implemented',
    note: 'Варианты ещё не импортированы.',
  },
}

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

const savedList = (score: number | null): SavedAdmissionList => ({
  profile: {
    personal_score: score,
    created_at: '2026-07-15T14:00:00Z',
    updated_at: '2026-07-15T14:00:00Z',
  },
  universities: [],
  programs: [],
})

const pagination = (totalItems: number) => ({
  page: 1,
  page_size: 20,
  total_items: totalItems,
  total_pages: totalItems > 0 ? 1 : 0,
  has_next: false,
  has_previous: false,
})

function recommendationResponse(empty = false): RecommendationResponse {
  return {
    applied_parameters: [],
    programs: {
      items: empty ? [] : [{
        result_class: 'MONITORED_STATUS',
        result_label: 'Статус рассчитан по данным мониторинга',
        admission_evaluation: 'Серверный статус без клиентского пересчёта',
        match_reasons: [{ parameter: 'score', value: '292' }],
        coverage_notes: [],
        monitoring_state: 'available',
        monitoring: {
          offering_id: 1,
          snapshot_id: 8,
          fetched_at: '2026-07-15T14:00:00Z',
          status: 'Серверный статус без клиентского пересчёта',
          competition: 1.67,
          estimated_cutoff_min: 290,
          estimated_cutoff_max: 299,
          estimated_user_position: 3,
          margin_min: -7,
          margin_max: 2,
          has_competition: true,
        },
        program,
      }, {
        result_class: 'PARAMETER_MATCH',
        result_label: 'Совпадает с выбранными параметрами',
        admission_evaluation: 'Недостаточно данных для оценки поступления',
        match_reasons: [{ parameter: 'city', value: 'Брест' }],
        coverage_notes: ['Текущего мониторинга нет.'],
        monitoring_state: 'unsupported',
        monitoring: null,
        program: {
          ...program,
          id: 2,
          university_id: 2,
          university: { id: 2, code: 'alpha', slug: 'alpha', short_name: 'Альфа' },
          slug: 'software-engineering',
          name: 'Программная инженерия',
          offering_count: 0,
          offerings: [],
        },
      }],
      pagination: pagination(empty ? 0 : 2),
    },
    universities: {
      items: empty ? [] : [{
        result_class: 'INSUFFICIENT_COVERAGE',
        result_label: 'Недостаточно импортированных данных',
        admission_evaluation: 'Недостаточно данных для оценки поступления',
        match_reasons: [{ parameter: 'catalog', value: 'active_university' }],
        coverage_notes: [
          'Варианты обучения ещё не импортированы; это не означает, что их нет в вузе.',
        ],
        university: alpha,
      }],
      pagination: pagination(empty ? 0 : 1),
    },
    coverage: meta.coverage,
  }
}

const fetchMock = vi.fn<typeof fetch>()
let serverList: SavedAdmissionList
let failRecommendations = false
let recommendationGate: Promise<Response> | null = null

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
  if (url.pathname === '/api/catalog/meta') return response(meta)
  if (url.pathname === '/api/recommendations') {
    if (recommendationGate) return recommendationGate
    if (failRecommendations) return response({ detail: 'internal' }, 500)
    return response(recommendationResponse(url.searchParams.get('city') === 'Брест'))
  }
  if (url.pathname === '/api/profile' && method === 'POST') {
    return response({ token: 'created-token', ...serverList }, 201)
  }
  if (url.pathname === '/api/profile/saved') return response(serverList)
  if (url.pathname === '/api/profile/watches') return response([])
  if (url.pathname === '/api/profile/watch-events') return response([])
  if (url.pathname === '/api/profile/telegram') {
    return response({ linked: false, linked_at: null, challenge_expires_at: null })
  }
  if (url.pathname === '/api/profile/score' && method === 'PATCH') {
    const body = JSON.parse(String(init?.body)) as { score: number }
    serverList = savedList(body.score)
    return response(serverList)
  }
  if (url.pathname === '/api/profile/programs/bseu/economic-informatics' && method === 'PUT') {
    serverList = {
      ...serverList,
      programs: [{
        saved_at: '2026-07-15T14:00:00Z',
        program,
        monitoring_state: 'available',
        monitoring: null,
        watch_supported: true,
      }],
    }
    return response(serverList)
  }
  throw new Error(`Unexpected request: ${method} ${url.pathname}`)
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

function LocationProbe() {
  const location = useLocation()
  return <output aria-label="Текущие параметры URL">{location.search}</output>
}

function HistoryControls() {
  const navigate = useNavigate()
  return <div>
    <button onClick={() => navigate(-1)} type="button">Тест: назад</button>
    <button onClick={() => navigate(1)} type="button">Тест: вперёд</button>
  </div>
}

function renderRecommendations(initialEntries = ['/recommendations'], initialIndex = initialEntries.length - 1) {
  return render(<MemoryRouter initialEntries={initialEntries} initialIndex={initialIndex}>
    <App />
    <LocationProbe />
    <HistoryControls />
  </MemoryRouter>)
}

const callsFor = (path: string) => fetchMock.mock.calls.filter(([input]) => (
  new URL(String(input), 'http://localhost').pathname === path
))

beforeEach(() => {
  installStorage()
  serverList = savedList(null)
  failRecommendations = false
  recommendationGate = null
  fetchMock.mockReset()
  fetchMock.mockImplementation(handleRequest)
  vi.stubGlobal('fetch', fetchMock)
})

describe('recommendations route, URL and profile score', () => {
  it('renders route/navigation and keeps the initial form read-only and profile-free', async () => {
    const { container } = renderRecommendations()
    expect(screen.getByRole('heading', { level: 1, name: 'Подбор вариантов поступления' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Подбор вариантов' })).toHaveAttribute('aria-current', 'page')
    expect(container.querySelectorAll('h1')).toHaveLength(1)
    expect(await screen.findByRole('heading', { name: 'Укажите важные параметры' })).toBeInTheDocument()
    expect(callsFor('/api/recommendations')).toHaveLength(0)
    expect(callsFor('/api/profile')).toHaveLength(0)
  })

  it('prefills an existing score, edits URL without overwrite, and saves only explicitly', async () => {
    localStorage.setItem(PROFILE_TOKEN_STORAGE_KEY, 'restored-token')
    serverList = savedList(292)
    const user = userEvent.setup()
    renderRecommendations()
    const score = await screen.findByLabelText('Балл')
    await waitFor(() => expect(score).toHaveValue(292))

    await user.clear(score)
    await user.type(score, '300')
    await user.click(screen.getByRole('button', { name: 'Подобрать варианты' }))
    await waitFor(() => expect(screen.getByLabelText('Текущие параметры URL')).toHaveTextContent('score=300'))
    expect(callsFor('/api/profile/score')).toHaveLength(0)
    expect(serverList.profile.personal_score).toBe(292)

    await user.click(screen.getByRole('button', { name: 'Сохранить балл в профиле' }))
    expect(await screen.findByText('Балл сохранён в профиле.')).toBeInTheDocument()
    expect(callsFor('/api/profile/score')).toHaveLength(1)
    expect(serverList.profile.personal_score).toBe(300)
  })

  it('restores score, filters and results on refresh and through Back/Forward', async () => {
    const user = userEvent.setup()
    renderRecommendations([
      '/recommendations?applied=true&score=0&city=Минск',
      '/recommendations?applied=true&score=292&city=Брест',
    ])
    expect(await screen.findByLabelText('Балл')).toHaveValue(292)
    expect(screen.getByLabelText('Город')).toHaveValue('Брест')
    expect(await screen.findByRole('heading', { name: 'Совпадений не найдено' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Тест: назад' }))
    await waitFor(() => expect(screen.getByLabelText('Балл')).toHaveValue(0))
    expect(screen.getByLabelText('Город')).toHaveValue('Минск')
    expect(await screen.findByText('Серверный статус без клиентского пересчёта')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Тест: вперёд' }))
    await waitFor(() => expect(screen.getByLabelText('Город')).toHaveValue('Брест'))
  })

  it('does not resurrect an applied draft after browser Back', async () => {
    const user = userEvent.setup()
    renderRecommendations(['/recommendations?applied=true&score=292'])
    await screen.findByText('Серверный статус без клиентского пересчёта')

    await user.selectOptions(screen.getByLabelText('Город'), 'Брест')
    await user.click(screen.getByRole('button', { name: 'Подобрать варианты' }))
    await waitFor(() => expect(screen.getByLabelText('Текущие параметры URL')).toHaveTextContent('city='))
    await user.click(screen.getByRole('button', { name: 'Тест: назад' }))
    await waitFor(() => expect(screen.getByLabelText('Текущие параметры URL')).not.toHaveTextContent('city='))
    expect(screen.getByLabelText('Город')).toHaveValue('')
  })
})

describe('recommendation result semantics and request states', () => {
  it('renders server classes, detail links, offerings, monitor and save controls', async () => {
    const user = userEvent.setup()
    renderRecommendations(['/recommendations?applied=true&score=292'])
    expect(await screen.findByText('Серверный статус без клиентского пересчёта')).toBeInTheDocument()
    expect(screen.getByText('Совпадает с выбранными параметрами')).toBeInTheDocument()
    expect(screen.getAllByText('Недостаточно данных для оценки поступления').length).toBeGreaterThan(0)
    expect(screen.getByText('Недостаточно импортированных данных')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: program.name })).toHaveAttribute(
      'href',
      '/universities/bseu/programs/economic-informatics',
    )
    expect(screen.getByRole('link', { name: 'БГЭУ — страница вуза' })).toHaveAttribute('href', '/universities/bseu')
    expect(screen.getByRole('link', { name: 'Монитор' })).toHaveAttribute('href', '/monitor')
    expect(screen.getByText('2026 · Дневная форма · Платная · 60 мест')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: `Сохранить — ${program.name}` }))
    expect(await screen.findByText('Сохранено')).toBeInTheDocument()
    expect(callsFor('/api/profile')).toHaveLength(1)
    expect(callsFor('/api/profile/programs/bseu/economic-informatics')).toHaveLength(1)
    expect(document.body.textContent).not.toMatch(/% шанс|гарантированно|точно проходите/i)
  })

  it('announces loading, ignores obsolete requests, and distinguishes no matches', async () => {
    let resolveRequest: ((value: Response) => void) | undefined
    recommendationGate = new Promise((resolve) => { resolveRequest = resolve })
    renderRecommendations(['/recommendations?applied=true&score=292'])
    expect(await screen.findByText('Подбираем варианты…')).toBeInTheDocument()
    resolveRequest?.(response(recommendationResponse()))
    expect(await screen.findByText('Серверный статус без клиентского пересчёта')).toBeInTheDocument()

    recommendationGate = null
    const user = userEvent.setup()
    await user.selectOptions(screen.getByLabelText('Город'), 'Брест')
    await user.click(screen.getByRole('button', { name: 'Подобрать варианты' }))
    expect(await screen.findByRole('heading', { name: 'Совпадений не найдено' })).toBeInTheDocument()
    expect(screen.queryByText('Не удалось загрузить рекомендации')).not.toBeInTheDocument()
  })

  it('shows retryable API error without presenting it as zero recommendations', async () => {
    failRecommendations = true
    const user = userEvent.setup()
    renderRecommendations(['/recommendations?applied=true&score=292'])
    expect(await screen.findByText('Не удалось загрузить рекомендации')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Совпадений не найдено' })).not.toBeInTheDocument()

    failRecommendations = false
    await user.click(screen.getByRole('button', { name: 'Повторить запрос' }))
    expect(await screen.findByText('Серверный статус без клиентского пересчёта')).toBeInTheDocument()
  })

  it('canonicalizes invalid URL values and sends only API-backed filters', async () => {
    renderRecommendations([
      '/recommendations?applied=true&score=bad&city=Unknown&study_form=magic&page=bad',
    ])
    await waitFor(() => expect(screen.getByLabelText('Текущие параметры URL')).toHaveTextContent('?applied=true'))
    await waitFor(() => expect(callsFor('/api/recommendations')).toHaveLength(1))
    const url = new URL(String(callsFor('/api/recommendations').at(-1)?.[0]), 'http://localhost')
    expect(url.searchParams.get('score')).toBeNull()
    expect(url.searchParams.get('city')).toBeNull()
    expect(url.searchParams.get('study_form')).toBeNull()
    expect(url.searchParams.get('page')).toBe('1')
    expect(url.searchParams.get('page_size')).toBe('20')
    expect(within(screen.getByRole('form', { name: 'Параметры подбора' })).getAllByRole('combobox')).toHaveLength(8)
  })
})
