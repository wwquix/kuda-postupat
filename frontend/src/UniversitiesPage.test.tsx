import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useLocation, useNavigate, MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import App from './App'
import type { CatalogMeta, UniversityListItem, UniversityListResponse } from './types'

const meta: CatalogMeta = {
  cities: ['Брест', 'Минск'],
  regions: ['Брестская область', 'Минск'],
  ownership_types: ['private', 'state'],
  institution_kinds: ['institute', 'university'],
  categories: [
    { code: 'economic', label_ru: 'Экономический' },
    { code: 'technical', label_ru: 'Технический' },
  ],
  monitoring_statuses: ['needs_review', 'online', 'reference_only'],
  admission_years: [2026],
  study_forms: ['full_time'],
  funding_types: ['paid'],
  counts: {
    universities: 47,
    programs: 1,
    offerings: 1,
    universities_with_programs: 1,
    universities_with_admissions_url: 33,
  },
  pagination: { default_page_size: 20, maximum_page_size: 100 },
  coverage: {
    universities_total: 47,
    universities_with_imported_programs: 1,
    programs_total: 1,
    offerings_total: 1,
    state: 'partial',
    note: 'Счётчики описывают только импортированное покрытие платформы.',
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
    note: 'Показаны только программы, импортированные платформой.',
  },
}

const privateUniversity: UniversityListItem = {
  id: 2,
  code: 'private-test',
  slug: 'private-test',
  short_name: 'ЧИУ',
  full_name: 'Частный институт с очень длинным официальным названием для проверки карточки',
  institution_kind: 'institute',
  ownership_type: 'private',
  city: 'Минск',
  region: null,
  official_site_url: 'https://example.edu.by/',
  admissions_url: null,
  monitoring_status: 'reference_only',
  active: true,
  categories: [{ code: 'technical', label_ru: 'Технический' }],
  program_count: 0,
  offering_count: 0,
  coverage: {
    programs: 'not_imported',
    offerings: 'not_imported',
    online_monitoring: 'not_implemented',
    note: 'Каталог программ ещё не импортирован.',
  },
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

function listResponse(url: URL): UniversityListResponse {
  const page = Number(url.searchParams.get('page') ?? 1)
  const q = url.searchParams.get('q')
  if (q === 'ничего') {
    return { items: [], pagination: { page, page_size: 20, total_items: 0, total_pages: 0, has_next: false, has_previous: false } }
  }
  if (page > 3) {
    return { items: [], pagination: { page, page_size: 20, total_items: 47, total_pages: 3, has_next: false, has_previous: true } }
  }
  const items = q ? [bseu] : [bseu, privateUniversity]
  const totalItems = q ? 1 : 47
  const totalPages = q ? 1 : 3
  return {
    items,
    pagination: {
      page,
      page_size: 20,
      total_items: totalItems,
      total_pages: totalPages,
      has_next: page < totalPages,
      has_previous: page > 1,
    },
  }
}

function installApiMock() {
  fetchMock.mockImplementation(async (input) => {
    const url = new URL(String(input), 'http://localhost')
    if (url.pathname === '/api/catalog/meta') return response(meta)
    if (url.pathname === '/api/universities') return response(listResponse(url))
    throw new Error(`Unexpected mocked request: ${url.pathname}`)
  })
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

function renderCatalog(initialEntries = ['/universities'], initialIndex = initialEntries.length - 1) {
  return render(<MemoryRouter initialEntries={initialEntries} initialIndex={initialIndex}>
    <App />
    <LocationProbe />
    <HistoryControls />
  </MemoryRouter>)
}

const universityCalls = () => fetchMock.mock.calls.filter(([input]) => (
  new URL(String(input), 'http://localhost').pathname === '/api/universities'
))

const lastUniversityUrl = () => new URL(
  String(universityCalls().at(-1)?.[0]),
  'http://localhost',
)

beforeEach(() => {
  fetchMock.mockReset()
  installApiMock()
  vi.stubGlobal('fetch', fetchMock)
})

describe('university catalog route and cards', () => {
  it('renders the route, active navigation and accessible university detail links', async () => {
    const { container } = renderCatalog()

    expect(screen.getByRole('heading', { level: 1, name: 'Вузы Беларуси' })).toBeInTheDocument()
    expect(await screen.findByText(/Найдено в каталоге платформы/)).toHaveTextContent('47')
    expect(screen.getByRole('link', { name: 'Вузы' })).toHaveAttribute('aria-current', 'page')
    expect(container.querySelectorAll('h1')).toHaveLength(1)
    expect(screen.getByRole('link', { name: bseu.full_name })).toHaveAttribute('href', '/universities/bseu')
    expect(screen.getByRole('link', { name: privateUniversity.full_name })).toHaveAttribute('href', '/universities/private-test')

    const request = lastUniversityUrl()
    expect(request.searchParams.get('page')).toBe('1')
    expect(request.searchParams.get('page_size')).toBe('20')
    expect(request.searchParams.get('sort')).toBe('name')
    expect(request.searchParams.get('order')).toBe('asc')
  })

  it('uses honest program and admissions wording and links only BSEU to the monitor', async () => {
    renderCatalog()
    await screen.findByRole('heading', { name: privateUniversity.full_name })

    expect(screen.getByText('Каталог программ ещё не импортирован')).toBeInTheDocument()
    expect(screen.queryByText('Специальностей нет')).not.toBeInTheDocument()
    expect(screen.getByText('Ссылка для абитуриентов пока не добавлена')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Live-мониторинг БГЭУ' })).toHaveAttribute('href', '/monitor')
    expect(screen.getAllByText(/Live-мониторинг БГЭУ/)).toHaveLength(1)

    const admissions = screen.getByRole('link', { name: /Официальная страница для абитуриентов — БГЭУ/ })
    expect(admissions).toHaveAttribute('target', '_blank')
    expect(admissions).toHaveAttribute('rel', 'noreferrer')
  })

  it('builds filter options from catalog metadata', async () => {
    renderCatalog()
    await screen.findByText(/Найдено в каталоге платформы/)

    expect(within(screen.getByLabelText('Город')).getByRole('option', { name: 'Минск' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Частный' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Технический' })).toBeInTheDocument()
  })
})

describe('loading, error and empty states', () => {
  it('announces initial loading before results resolve', async () => {
    let resolveList: ((value: Response) => void) | undefined
    fetchMock.mockImplementation((input) => {
      const url = new URL(String(input), 'http://localhost')
      if (url.pathname === '/api/catalog/meta') return Promise.resolve(response(meta))
      if (url.pathname === '/api/universities') return new Promise((resolve) => { resolveList = resolve })
      return Promise.reject(new Error('Unexpected request'))
    })
    renderCatalog()

    expect(screen.getByText('Загружаем параметры каталога…')).toBeInTheDocument()
    await waitFor(() => expect(resolveList).toBeDefined())
    expect(screen.getByText('Загружаем каталог вузов…')).toBeInTheDocument()
    resolveList?.(response(listResponse(new URL('http://localhost/api/universities'))))
    expect(await screen.findByText(/Найдено в каталоге платформы/)).toBeInTheDocument()
  })

  it('shows a safe API error and retries without presenting an empty catalog', async () => {
    let fail = true
    fetchMock.mockImplementation(async (input) => {
      const url = new URL(String(input), 'http://localhost')
      if (url.pathname === '/api/catalog/meta') return response(meta)
      if (url.pathname === '/api/universities' && fail) return response({ detail: 'raw internal error' }, 500)
      if (url.pathname === '/api/universities') return response(listResponse(url))
      throw new Error('Unexpected request')
    })
    const user = userEvent.setup()
    renderCatalog()

    expect(await screen.findByRole('heading', { name: 'Не удалось получить результаты' })).toBeInTheDocument()
    expect(screen.queryByText('raw internal error')).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: /ничего не найдено/i })).not.toBeInTheDocument()
    fail = false
    await user.click(screen.getByRole('button', { name: 'Повторить запрос' }))
    expect(await screen.findByText(/Найдено в каталоге платформы/)).toHaveTextContent('47')
  })

  it('shows a distinct empty state and clears search and filters from it', async () => {
    const user = userEvent.setup()
    renderCatalog(['/universities?q=ничего&city=Минск'])

    expect(await screen.findByRole('heading', { name: 'По заданным условиям ничего не найдено' })).toBeInTheDocument()
    await user.click(within(screen.getByRole('heading', { name: 'По заданным условиям ничего не найдено' }).parentElement!).getByRole('button', { name: 'Очистить поиск и фильтры' }))
    await waitFor(() => expect(screen.getByLabelText('Текущие параметры URL')).toHaveTextContent(''))
    expect(await screen.findByText(/Найдено в каталоге платформы/)).toHaveTextContent('47')
  })
})

describe('search and URL state', () => {
  it('debounces search, writes it to the URL and does not duplicate the request on Enter', async () => {
    renderCatalog()
    await screen.findByText(/Найдено в каталоге платформы/)
    const initialRequestCount = universityCalls().length
    const input = screen.getByRole('searchbox', { name: 'Поиск по названию, городу или категории' })

    fireEvent.change(input, { target: { value: 'БГЭУ' } })
    expect(universityCalls()).toHaveLength(initialRequestCount)
    await waitFor(() => expect(screen.getByLabelText('Текущие параметры URL')).toHaveTextContent('q=%D0%91%D0%93%D0%AD%D0%A3'))
    await waitFor(() => expect(universityCalls()).toHaveLength(initialRequestCount + 1))

    const countAfterDebounce = universityCalls().length
    fireEvent.submit(screen.getByRole('search'))
    await new Promise((resolve) => window.setTimeout(resolve, 350))
    expect(universityCalls()).toHaveLength(countAfterDebounce)

    fireEvent.click(screen.getByRole('button', { name: 'Очистить поиск' }))
    await waitFor(() => expect(screen.getByLabelText('Текущие параметры URL')).not.toHaveTextContent('q='))
    expect(lastUniversityUrl().searchParams.has('q')).toBe(false)
  })

  it('aborts an obsolete search request when a newer query is committed', async () => {
    renderCatalog()
    await screen.findByText(/Найдено в каталоге платформы/)
    let obsoleteSignal: AbortSignal | undefined

    fetchMock.mockImplementation((input, init) => {
      const url = new URL(String(input), 'http://localhost')
      if (url.pathname === '/api/catalog/meta') return Promise.resolve(response(meta))
      if (url.pathname === '/api/universities' && url.searchParams.get('q') === 'Бел') {
        obsoleteSignal = init?.signal ?? undefined
        return new Promise(() => undefined)
      }
      if (url.pathname === '/api/universities') return Promise.resolve(response(listResponse(url)))
      return Promise.reject(new Error('Unexpected request'))
    })

    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'Бел' } })
    await waitFor(() => expect(obsoleteSignal).toBeDefined())
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'БГЭУ' } })
    await waitFor(() => expect(obsoleteSignal?.aborted).toBe(true))
    expect(await screen.findByRole('heading', { name: bseu.full_name })).toBeInTheDocument()
  })

  it('restores combined state from a direct URL refresh', async () => {
    renderCatalog(['/universities?q=БГЭУ&city=Минск&sort=program_count&order=desc&page=2'])

    await waitFor(() => expect(lastUniversityUrl().searchParams.get('q')).toBe('БГЭУ'))
    expect(screen.getByRole('searchbox')).toHaveValue('БГЭУ')
    expect(screen.getByLabelText('Город')).toHaveValue('Минск')
    expect(screen.getByLabelText('Сортировка')).toHaveValue('program_count')
    expect(screen.getByLabelText('Направление сортировки')).toHaveValue('desc')
    expect(lastUniversityUrl().searchParams.get('page')).toBe('2')
  })

  it('restores filters through browser Back and Forward navigation', async () => {
    const user = userEvent.setup()
    renderCatalog(['/universities?city=Минск', '/universities?ownership_type=private'], 1)
    await waitFor(() => expect(screen.getByLabelText('Форма собственности')).toHaveValue('private'))

    await user.click(screen.getByRole('button', { name: 'Тест: назад' }))
    await waitFor(() => expect(screen.getByLabelText('Город')).toHaveValue('Минск'))
    expect(screen.getByLabelText('Форма собственности')).toHaveValue('')

    await user.click(screen.getByRole('button', { name: 'Тест: вперёд' }))
    await waitFor(() => expect(screen.getByLabelText('Форма собственности')).toHaveValue('private'))
  })
})

describe('backend filters, sorting and pagination', () => {
  it.each([
    ['city', 'Минск'],
    ['region', 'Минск'],
    ['ownership_type', 'private'],
    ['institution_kind', 'institute'],
    ['category', 'technical'],
    ['monitoring_status', 'reference_only'],
    ['has_admissions_url', 'false'],
    ['has_programs', 'false'],
    ['online_monitoring', 'true'],
  ])('forwards the %s filter to the production endpoint', async (key, value) => {
    renderCatalog([`/universities?${key}=${encodeURIComponent(value)}`])

    await waitFor(() => expect(lastUniversityUrl().searchParams.get(key)).toBe(value))
    expect(universityCalls()).toHaveLength(1)
  })

  it('shows combined active filters and clears all of them with one action', async () => {
    const user = userEvent.setup()
    renderCatalog(['/universities?q=БГЭУ&city=Минск&ownership_type=private'])

    expect(await screen.findByRole('button', { name: 'Убрать: Поиск: БГЭУ' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Убрать: Город: Минск' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Убрать: Собственность: Частный' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Очистить поиск и фильтры' }))
    await waitFor(() => expect(screen.getByLabelText('Текущие параметры URL')).toHaveTextContent(''))
    expect(lastUniversityUrl().searchParams.has('q')).toBe(false)
    expect(lastUniversityUrl().searchParams.has('city')).toBe(false)
  })

  it('synchronizes sorting and resets pagination to page one', async () => {
    const user = userEvent.setup()
    renderCatalog(['/universities?page=2'])
    await waitFor(() => expect(lastUniversityUrl().searchParams.get('page')).toBe('2'))

    await user.selectOptions(screen.getByLabelText('Сортировка'), 'program_count')
    await user.selectOptions(screen.getByLabelText('Направление сортировки'), 'desc')
    await waitFor(() => expect(lastUniversityUrl().searchParams.get('order')).toBe('desc'))
    expect(screen.getByLabelText('Текущие параметры URL')).toHaveTextContent('sort=program_count')
    expect(screen.getByLabelText('Текущие параметры URL')).not.toHaveTextContent('page=2')
    expect(lastUniversityUrl().searchParams.get('page')).toBe('1')
  })

  it('uses server pagination controls and stores non-default pages in the URL', async () => {
    const user = userEvent.setup()
    renderCatalog()
    await screen.findByText('Страница 1 из 3')

    await user.click(screen.getByRole('button', { name: 'Вперёд' }))
    await waitFor(() => expect(screen.getByLabelText('Текущие параметры URL')).toHaveTextContent('page=2'))
    expect(lastUniversityUrl().searchParams.get('page')).toBe('2')
    expect(await screen.findByText('Страница 2 из 3')).toBeInTheDocument()
  })

  it('recovers safely from invalid and unavailable pages', async () => {
    renderCatalog(['/universities?page=99'])

    await waitFor(() => expect(screen.getByLabelText('Текущие параметры URL')).toHaveTextContent('page=3'))
    expect(lastUniversityUrl().searchParams.get('page')).toBe('3')
    expect(await screen.findByText('Страница 3 из 3')).toBeInTheDocument()
  })

  it('normalizes invalid URL values before issuing a catalog request', async () => {
    renderCatalog(['/universities?page=zero&sort=DROP&order=sideways&ownership_type=bogus'])

    await waitFor(() => expect(universityCalls()).toHaveLength(1))
    expect(screen.getByLabelText('Текущие параметры URL')).toHaveTextContent('')
    expect(lastUniversityUrl().searchParams.get('page')).toBe('1')
    expect(lastUniversityUrl().searchParams.get('sort')).toBe('name')
    expect(lastUniversityUrl().searchParams.get('order')).toBe('asc')
    expect(lastUniversityUrl().searchParams.has('ownership_type')).toBe(false)
  })
})

describe('frontend test isolation', () => {
  it('uses only mocked catalog GET requests and never calls live, refresh or notification surfaces', async () => {
    renderCatalog(['/universities?online_monitoring=true'])
    await screen.findByText(/Найдено в каталоге платформы/)

    const urls = fetchMock.mock.calls.map(([input]) => String(input))
    expect(urls.every((url) => url.startsWith('/api/'))).toBe(true)
    expect(urls.every((url) => !url.includes('bseu.by'))).toBe(true)
    expect(urls.every((url) => !url.includes('/refresh'))).toBe(true)
    expect(urls.every((url) => !url.includes('telegram'))).toBe(true)
  })
})
