import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation, useNavigate } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import App from './App'
import type { UniversityDetail, UniversityListResponse } from './types'

function university(overrides: Partial<UniversityDetail>): UniversityDetail {
  return {
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
      note: 'Показаны только импортированные данные.',
    },
    description: null,
    source_url: 'https://edu.gov.by/registry',
    source_checked_at: '2026-07-12T18:14:28Z',
    data_verified_at: '2026-07-12T18:14:28Z',
    updated_at: '2026-07-12T18:14:28Z',
    sources: [],
    programs: [],
    ...overrides,
  }
}

const bseu = university({})
const bsu = university({
  id: 2,
  code: 'bsu',
  slug: 'bsu',
  short_name: 'БГУ',
  full_name: 'Белорусский государственный университет',
  official_site_url: 'https://bsu.by/',
  admissions_url: 'https://abiturient.bsu.by/',
  monitoring_status: 'reference_only',
  coverage: { programs: 'available', offerings: 'available', online_monitoring: 'not_implemented', note: 'Live-покрытие не реализовано.' },
})
const brsu = university({
  id: 3,
  code: 'brsu',
  slug: 'brsu',
  short_name: 'БрГУ',
  full_name: 'Брестский государственный университет имени А.С. Пушкина',
  city: null,
  region: null,
  ownership_type: 'unknown',
  official_site_url: '',
  admissions_url: null,
  monitoring_status: 'reference_only',
  categories: [],
  program_count: 0,
  offering_count: 0,
  data_verified_at: null,
  coverage: { programs: 'not_imported', offerings: 'not_imported', online_monitoring: 'not_implemented', note: 'Каталог не импортирован.' },
})
const fourth = university({
  id: 4,
  code: 'bntu',
  slug: 'bntu',
  short_name: 'БНТУ',
  full_name: 'Белорусский национальный технический университет',
  official_site_url: 'https://bntu.by/',
  admissions_url: 'https://abiturient.bntu.by/',
  monitoring_status: 'reference_only',
  coverage: { programs: 'available', offerings: 'available', online_monitoring: 'not_implemented', note: 'Live-покрытие не реализовано.' },
})
const retryUniversity = university({
  id: 5,
  code: 'retry-u',
  slug: 'retry-u',
  short_name: 'ТЕСТ',
  full_name: 'Тестовый университет после повтора',
  monitoring_status: 'reference_only',
  coverage: { programs: 'available', offerings: 'available', online_monitoring: 'not_implemented', note: 'Live-покрытие не реализовано.' },
})

const details = new Map([bseu, bsu, brsu, fourth, retryUniversity].map((item) => [item.slug, item]))
const fetchMock = vi.fn<typeof fetch>()
let retryDetailFails: boolean
let searchFails: boolean

function response(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status >= 400 ? 'Request failed' : 'OK',
    json: async () => body,
  } as Response
}

function listResponse(items: UniversityDetail[]): UniversityListResponse {
  return {
    items,
    pagination: {
      page: 1,
      page_size: 6,
      total_items: items.length,
      total_pages: items.length > 0 ? 1 : 0,
      has_next: false,
      has_previous: false,
    },
  }
}

function installApiMock() {
  fetchMock.mockImplementation(async (input, init) => {
    const url = new URL(String(input), 'http://localhost')
    if (url.pathname === '/api/universities') {
      if (searchFails) return response({ detail: 'raw search failure' }, 500)
      const query = url.searchParams.get('q')?.toLowerCase() ?? ''
      const matches = [bseu, bsu, brsu, fourth].filter((item) => (
        item.short_name.toLowerCase().includes(query)
        || item.full_name.toLowerCase().includes(query)
        || item.slug.includes(query)
      ))
      return response(listResponse(matches))
    }
    if (url.pathname.startsWith('/api/universities/')) {
      const slug = decodeURIComponent(url.pathname.split('/').at(-1) ?? '')
      if (slug === 'retry-u' && retryDetailFails) {
        retryDetailFails = false
        return response({ detail: 'raw detail failure' }, 500)
      }
      const detail = details.get(slug)
      return detail ? response(detail) : response({ detail: 'not found' }, 404)
    }
    throw new Error(`Unexpected mocked request: ${init?.method ?? 'GET'} ${url.pathname}`)
  })
}

function LocationProbe() {
  const location = useLocation()
  return <output aria-label="Текущий URL сравнения">{location.pathname}{location.search}</output>
}

function HistoryControls() {
  const navigate = useNavigate()
  return <div><button onClick={() => navigate(-1)} type="button">Назад в истории</button><button onClick={() => navigate(1)} type="button">Вперёд в истории</button></div>
}

function renderCompare(initialEntries = ['/compare'], initialIndex = initialEntries.length - 1) {
  return render(<MemoryRouter initialEntries={initialEntries} initialIndex={initialIndex}>
    <App />
    <LocationProbe />
    <HistoryControls />
  </MemoryRouter>)
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
}

beforeEach(() => {
  installStorage()
  retryDetailFails = false
  searchFails = false
  fetchMock.mockReset()
  installApiMock()
  vi.stubGlobal('fetch', fetchMock)
})

describe('public university comparison', () => {
  it('renders the empty route, active navigation, and no catalog request before server-side search', () => {
    renderCompare()

    expect(screen.getByRole('heading', { level: 1, name: 'Сравнение вузов' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Выберите вузы для сравнения' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Сравнение' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('searchbox', { name: 'Поиск вуза для сравнения' })).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('shows one selected university, honest missing values, and asks for another', async () => {
    renderCompare(['/compare?universities=brsu'])

    expect(screen.getByText('Загружаем данные для сравнения…')).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: brsu.full_name })).toBeInTheDocument()
    expect(screen.getByText('Добавьте ещё один вуз, чтобы перейти к сравнению.')).toBeInTheDocument()
    expect(screen.getByText('Каталог программ ещё не импортирован')).toBeInTheDocument()
    expect(screen.getAllByText('Данные пока не добавлены').length).toBeGreaterThanOrEqual(4)
    expect(screen.getAllByRole('link', { name: 'Монитор поступления' })).toHaveLength(1)
  })

  it('renders two and three universities in URL order, removes duplicates, and caps direct URLs at three', async () => {
    const { unmount } = renderCompare(['/compare?universities=bseu,bsu'])
    await screen.findByRole('heading', { name: bsu.full_name })
    expect(screen.getAllByRole('article').map((card) => within(card).getByRole('heading').textContent)).toEqual([
      bseu.full_name,
      bsu.full_name,
    ])
    const firstCards = screen.getAllByRole('article')
    expect(within(firstCards[0]).getByRole('link', { name: 'Монитор поступления' })).toHaveAttribute('href', '/monitor')
    expect(within(firstCards[1]).queryByRole('link', { name: 'Монитор поступления' })).not.toBeInTheDocument()
    unmount()

    renderCompare(['/compare?universities=bseu,bsu,bseu,brsu,bntu'])
    await screen.findByRole('heading', { name: brsu.full_name })
    await waitFor(() => expect(screen.getByLabelText('Текущий URL сравнения')).toHaveTextContent('/compare?universities=bseu,bsu,brsu'))
    expect(screen.getAllByRole('article').map((card) => within(card).getByRole('heading').textContent)).toEqual([
      bseu.full_name,
      bsu.full_name,
      brsu.full_name,
    ])
    expect(fetchMock.mock.calls.map(([input]) => String(input)).some((url) => url.endsWith('/api/universities/bntu'))).toBe(false)
  })

  it('searches on the server, adds a university, prevents duplicates, and never mutates a profile', async () => {
    const user = userEvent.setup()
    renderCompare(['/compare?universities=bseu'])
    await screen.findByRole('heading', { name: bseu.full_name })

    await user.type(screen.getByRole('searchbox', { name: 'Поиск вуза для сравнения' }), 'bsu')
    await user.click(screen.getByRole('button', { name: 'Найти' }))
    await user.click(await screen.findByRole('button', { name: 'Добавить БГУ' }))
    expect(await screen.findByRole('heading', { name: bsu.full_name })).toBeInTheDocument()
    expect(screen.getByLabelText('Текущий URL сравнения')).toHaveTextContent('/compare?universities=bseu,bsu')

    const searchCall = fetchMock.mock.calls.map(([input]) => new URL(String(input), 'http://localhost')).find((url) => url.pathname === '/api/universities')
    expect(searchCall?.searchParams.get('q')).toBe('bsu')
    expect(searchCall?.searchParams.get('page_size')).toBe('6')
    expect(fetchMock.mock.calls.every(([, init]) => !init?.method || init.method === 'GET')).toBe(true)
    expect(fetchMock.mock.calls.some(([input]) => new URL(String(input), 'http://localhost').pathname.startsWith('/api/profile'))).toBe(false)

    await user.clear(screen.getByRole('searchbox', { name: 'Поиск вуза для сравнения' }))
    await user.type(screen.getByRole('searchbox', { name: 'Поиск вуза для сравнения' }), 'bseu')
    await user.click(screen.getByRole('button', { name: 'Найти' }))
    expect(await screen.findByText('Уже выбрано')).toBeInTheDocument()
  })

  it('removes and replaces universities while preserving the remaining order', async () => {
    const user = userEvent.setup()
    renderCompare(['/compare?universities=bseu,bsu,brsu'])
    await screen.findByRole('heading', { name: brsu.full_name })

    await user.selectOptions(screen.getByLabelText('Кого заменить'), 'bsu')
    await user.type(screen.getByRole('searchbox', { name: 'Поиск вуза для сравнения' }), 'bntu')
    await user.click(screen.getByRole('button', { name: 'Найти' }))
    await user.click(await screen.findByRole('button', { name: 'Заменить на БНТУ' }))
    expect(await screen.findByRole('heading', { name: fourth.full_name })).toBeInTheDocument()
    expect(screen.getByLabelText('Текущий URL сравнения')).toHaveTextContent('/compare?universities=bseu,bntu,brsu')

    await user.click(screen.getByRole('button', { name: 'Убрать из сравнения — БНТУ' }))
    await waitFor(() => expect(screen.getByLabelText('Текущий URL сравнения')).toHaveTextContent('/compare?universities=bseu,brsu'))
  })

  it('restores selection through browser Back and Forward and works from a copied URL without a profile', async () => {
    const user = userEvent.setup()
    renderCompare(['/compare?universities=bseu', '/compare?universities=bseu,bsu'])
    await screen.findByRole('heading', { name: bsu.full_name })

    await user.click(screen.getByRole('button', { name: 'Назад в истории' }))
    await waitFor(() => expect(screen.getByLabelText('Текущий URL сравнения')).toHaveTextContent('/compare?universities=bseu'))
    expect(await screen.findByText('Добавьте ещё один вуз, чтобы перейти к сравнению.')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Вперёд в истории' }))
    expect(await screen.findByRole('heading', { name: bsu.full_name })).toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([input]) => String(input).includes('/api/profile'))).toBe(false)
  })

  it('shows unknown universities and retries a transient detail API error', async () => {
    const user = userEvent.setup()
    const { unmount } = renderCompare(['/compare?universities=unknown'])
    expect(await screen.findByRole('heading', { name: 'Университет не найден: unknown' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Убрать из сравнения' }))
    expect(screen.getByLabelText('Текущий URL сравнения')).toHaveTextContent('/compare')
    unmount()

    retryDetailFails = true
    renderCompare(['/compare?universities=retry-u'])
    expect(await screen.findByRole('heading', { name: 'Не удалось загрузить данные для сравнения' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Повторить запрос' }))
    expect(await screen.findByRole('heading', { name: retryUniversity.full_name })).toBeInTheDocument()
  })

  it('offers a retry when server-side catalog search fails', async () => {
    const user = userEvent.setup()
    searchFails = true
    renderCompare()
    await user.type(screen.getByRole('searchbox', { name: 'Поиск вуза для сравнения' }), 'БГУ')
    await user.click(screen.getByRole('button', { name: 'Найти' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Не удалось выполнить поиск вузов')

    searchFails = false
    await user.click(screen.getByRole('button', { name: 'Повторить поиск' }))
    expect(await screen.findByRole('button', { name: 'Добавить БГУ' })).toBeInTheDocument()
  })
})
