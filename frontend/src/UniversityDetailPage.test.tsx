import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation, useNavigate } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import App from './App'
import type { CatalogMeta, UniversityDetail, UniversityListResponse } from './types'

const meta: CatalogMeta = {
  cities: ['Минск'],
  regions: ['Минск'],
  ownership_types: ['state'],
  institution_kinds: ['university'],
  categories: [{ code: 'economic', label_ru: 'Экономический' }],
  monitoring_statuses: ['online', 'reference_only'],
  admission_years: [2026],
  study_forms: ['full_time'],
  funding_types: ['paid'],
  counts: { universities: 47, programs: 1, offerings: 1, universities_with_programs: 1, universities_with_admissions_url: 33 },
  pagination: { default_page_size: 20, maximum_page_size: 100 },
  coverage: { universities_total: 47, universities_with_imported_programs: 1, programs_total: 1, offerings_total: 1, state: 'partial', note: 'Покрытие платформы неполное.' },
}

const bseu: UniversityDetail = {
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
  coverage: { programs: 'available', offerings: 'available', online_monitoring: 'available', note: 'Показаны только импортированные программы.' },
  description: null,
  source_url: 'https://edu.gov.by/registry',
  source_checked_at: '2026-07-12T18:14:28Z',
  data_verified_at: '2026-07-12T18:14:28Z',
  updated_at: '2026-07-12T18:14:28Z',
  sources: [
    { source_type: 'official_registry', source_url: 'https://edu.gov.by/registry', checked_at: '2026-07-12T18:14:28Z' },
    { source_type: 'admission_xml', source_url: 'https://bseu.by/abiturient/xml/1.xml', checked_at: '2026-07-15T09:00:00Z' },
  ],
  programs: [{
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
    official_url: 'https://bseu.by/russian/teaching/specialities.htm',
    active: true,
    source_checked_at: '2026-07-12T18:14:28Z',
    verified_at: null,
    updated_at: '2026-07-12T18:14:28Z',
    offering_count: 1,
    offerings: [{
      id: 1,
      admission_year: 2026,
      study_form: 'full_time',
      funding_type: 'paid',
      places: 60,
      monitoring_supported: true,
      monitoring_status: 'online',
      official_url: 'https://bseu.by/russian/abiturient/tsp2026.pdf',
      source_url: 'https://bseu.by/russian/abiturient/tsp2026.pdf',
      source_checked_at: '2026-07-12T18:14:28Z',
    }],
    coverage_state: 'available',
  }],
}

const noPrograms: UniversityDetail = {
  ...bseu,
  id: 2,
  code: 'brsu',
  slug: 'brsu',
  short_name: 'БрГУ',
  full_name: 'Брестский государственный университет имени А.С. Пушкина',
  city: 'Брест',
  region: 'Брестская область',
  admissions_url: null,
  monitoring_status: 'reference_only',
  program_count: 0,
  offering_count: 0,
  coverage: { programs: 'not_imported', offerings: 'not_imported', online_monitoring: 'not_implemented', note: 'Программы ещё не импортированы.' },
  programs: [],
}

const fetchMock = vi.fn<typeof fetch>()

function response(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status >= 400 ? 'Request failed' : 'OK',
    json: async () => body,
  } as Response
}

function catalogResponse(url: URL): UniversityListResponse {
  const page = Number(url.searchParams.get('page') ?? 1)
  return {
    items: [bseu],
    pagination: { page, page_size: 20, total_items: 47, total_pages: 3, has_next: page < 3, has_previous: page > 1 },
  }
}

function installApiMock() {
  fetchMock.mockImplementation(async (input) => {
    const url = new URL(String(input), 'http://localhost')
    if (url.pathname === '/api/catalog/meta') return response(meta)
    if (url.pathname === '/api/universities') return response(catalogResponse(url))
    if (url.pathname === '/api/universities/bseu') return response(bseu)
    if (url.pathname === '/api/universities/brsu') return response(noPrograms)
    if (url.pathname === '/api/universities/slug-that-does-not-exist') return response({ detail: 'raw not found' }, 404)
    throw new Error(`Unexpected mocked request: ${url.pathname}`)
  })
}

function LocationProbe() {
  const location = useLocation()
  return <output aria-label="Текущий маршрут">{location.pathname}{location.search}</output>
}

function SlugControls() {
  const navigate = useNavigate()
  return <div>
    <button onClick={() => navigate('/universities/bseu')} type="button">Тест: открыть БГЭУ</button>
  </div>
}

function renderRoute(initialEntries: Parameters<typeof MemoryRouter>[0]['initialEntries']) {
  return render(<MemoryRouter initialEntries={initialEntries}>
    <App />
    <LocationProbe />
    <SlugControls />
  </MemoryRouter>)
}

beforeEach(() => {
  fetchMock.mockReset()
  installApiMock()
  vi.stubGlobal('fetch', fetchMock)
  document.title = 'Тест'
})

describe('university detail states and honest rendering', () => {
  it('announces initial loading and then renders stored university, program and offering data', async () => {
    let resolveDetail: ((value: Response) => void) | undefined
    fetchMock.mockImplementation((input) => {
      const url = new URL(String(input), 'http://localhost')
      if (url.pathname === '/api/universities/bseu') return new Promise((resolve) => { resolveDetail = resolve })
      return Promise.reject(new Error('Unexpected request'))
    })
    const { container } = renderRoute(['/universities/bseu'])

    expect(screen.getByRole('heading', { level: 1, name: 'Загружаем страницу вуза…' })).toBeInTheDocument()
    await waitFor(() => expect(resolveDetail).toBeDefined())
    resolveDetail?.(response(bseu))

    expect(await screen.findByRole('heading', { level: 1, name: bseu.full_name })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'О вузе' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Официальные ресурсы' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Мониторинг и покрытие источников' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Импортированные программы' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Экономическая информатика' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /2026 · Дневная форма · Платная/ })).toBeInTheDocument()
    expect(screen.getByText('60 мест')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Live-мониторинг БГЭУ' })).toHaveAttribute('href', '/monitor')
    expect(container.querySelectorAll('h1')).toHaveLength(1)
    expect(container.querySelector('a[href^="/programs/"]')).not.toBeInTheDocument()
    await waitFor(() => expect(document.title).toBe('БГЭУ · Куда поступать'))
  })

  it('shows safe API error separately and retries without exposing raw detail', async () => {
    let fail = true
    fetchMock.mockImplementation(async (input) => {
      const url = new URL(String(input), 'http://localhost')
      if (url.pathname !== '/api/universities/bseu') throw new Error('Unexpected request')
      if (fail) return response({ detail: 'raw database exception' }, 500)
      return response(bseu)
    })
    const user = userEvent.setup()
    renderRoute(['/universities/bseu'])

    expect(await screen.findByRole('heading', { name: 'Не удалось загрузить страницу вуза' })).toBeInTheDocument()
    expect(screen.queryByText('raw database exception')).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Университет не найден' })).not.toBeInTheDocument()
    fail = false
    await user.click(screen.getByRole('button', { name: 'Повторить запрос' }))
    expect(await screen.findByRole('heading', { level: 1, name: bseu.full_name })).toBeInTheDocument()
  })

  it('renders a distinct not-found state for HTTP 404', async () => {
    renderRoute(['/universities/slug-that-does-not-exist'])

    expect(await screen.findByRole('heading', { level: 1, name: 'Университет не найден' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Повторить запрос' })).not.toBeInTheDocument()
    expect(screen.queryByText('raw not found')).not.toBeInTheDocument()
  })

  it('uses exact honest wording for missing program and admissions coverage', async () => {
    renderRoute(['/universities/brsu'])

    expect(await screen.findByRole('heading', { level: 1, name: noPrograms.full_name })).toBeInTheDocument()
    expect(screen.getAllByText('Каталог программ ещё не импортирован')).toHaveLength(2)
    expect(screen.getByText('Ссылка для абитуриентов пока не добавлена')).toBeInTheDocument()
    expect(screen.queryByText('Специальностей нет')).not.toBeInTheDocument()
    expect(screen.queryByText(/Импортировано программ: 0/)).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Live-мониторинг БГЭУ' })).not.toBeInTheDocument()
  })
})

describe('catalog return navigation and obsolete requests', () => {
  it('preserves the exact originating catalog URL through the card link and return action', async () => {
    const origin = '/universities?q=%D0%91%D0%93%D0%AD%D0%A3&city=%D0%9C%D0%B8%D0%BD%D1%81%D0%BA&sort=program_count&order=desc&page=2'
    const user = userEvent.setup()
    renderRoute([origin])

    const detailLink = await screen.findByRole('link', { name: bseu.full_name })
    expect(detailLink).toHaveAttribute('href', '/universities/bseu')
    await user.click(detailLink)
    expect(await screen.findByRole('heading', { level: 1, name: bseu.full_name })).toBeInTheDocument()
    const backLink = screen.getByRole('link', { name: 'Назад к каталогу' })
    expect(backLink).toHaveAttribute('href', origin)
    await user.click(backLink)
    await waitFor(() => expect(screen.getByLabelText('Текущий маршрут')).toHaveTextContent(origin))
  })

  it('falls back to /universities on direct opening without navigation state', async () => {
    renderRoute(['/universities/bseu'])
    await screen.findByRole('heading', { level: 1, name: bseu.full_name })

    expect(screen.getByRole('link', { name: 'Назад к каталогу' })).toHaveAttribute('href', '/universities')
  })

  it('aborts and ignores an obsolete detail request when the slug changes', async () => {
    let obsoleteSignal: AbortSignal | undefined
    fetchMock.mockImplementation((input, init) => {
      const url = new URL(String(input), 'http://localhost')
      if (url.pathname === '/api/universities/slow') {
        obsoleteSignal = init?.signal ?? undefined
        return new Promise(() => undefined)
      }
      if (url.pathname === '/api/universities/bseu') return Promise.resolve(response(bseu))
      return Promise.reject(new Error('Unexpected request'))
    })
    const user = userEvent.setup()
    renderRoute(['/universities/slow'])

    await waitFor(() => expect(obsoleteSignal).toBeDefined())
    await user.click(screen.getByRole('button', { name: 'Тест: открыть БГЭУ' }))
    await waitFor(() => expect(obsoleteSignal?.aborted).toBe(true))
    expect(await screen.findByRole('heading', { level: 1, name: bseu.full_name })).toBeInTheDocument()
  })
})

describe('frontend detail isolation', () => {
  it('uses only mocked read-only API requests', async () => {
    renderRoute(['/universities/bseu'])
    await screen.findByRole('heading', { level: 1, name: bseu.full_name })

    const urls = fetchMock.mock.calls.map(([input]) => String(input))
    expect(urls).toEqual(['/api/universities/bseu'])
    expect(urls.every((url) => !url.includes('/refresh') && !url.includes('telegram'))).toBe(true)
  })
})
