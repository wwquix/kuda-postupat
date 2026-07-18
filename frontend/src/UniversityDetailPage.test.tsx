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

const discoveryBseu: UniversityDetail = {
  ...bseu,
  program_count: 3,
  offering_count: 5,
  programs: [
    {
      ...bseu.programs[0],
      offering_count: 2,
      offerings: [
        bseu.programs[0].offerings[0],
        {
          ...bseu.programs[0].offerings[0],
          id: 2,
          funding_type: 'budget',
          places: 25,
          monitoring_supported: false,
          monitoring_status: 'reference_only',
          official_url: 'https://bseu.by/programs/economic-informatics/budget',
        },
      ],
    },
    {
      ...bseu.programs[0],
      id: 2,
      code: null,
      slug: 'management',
      name: 'Менеджмент',
      qualification: null,
      faculty_name: 'Факультет экономики и менеджмента',
      official_url: 'https://bseu.by/programs/management',
      offering_count: 2,
      offerings: [
        {
          ...bseu.programs[0].offerings[0],
          id: 3,
          study_form: 'part_time',
          monitoring_supported: false,
          monitoring_status: 'reference_only',
          official_url: 'https://bseu.by/programs/management/part-time',
        },
        {
          ...bseu.programs[0].offerings[0],
          id: 4,
          funding_type: 'budget',
          monitoring_supported: false,
          monitoring_status: 'reference_only',
          official_url: 'https://bseu.by/programs/management/budget',
        },
      ],
    },
    {
      ...bseu.programs[0],
      id: 3,
      code: '6-05-0412-02',
      slug: 'marketing',
      name: 'Маркетинг',
      qualification: null,
      faculty_name: 'Факультет маркетинга и логистики',
      official_url: 'https://bseu.by/programs/marketing',
      offering_count: 1,
      offerings: [{
        ...bseu.programs[0].offerings[0],
        id: 5,
        study_form: 'distance',
        monitoring_supported: false,
        monitoring_status: 'unsupported',
        official_url: 'https://bseu.by/programs/marketing/distance',
      }],
    },
  ],
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
let bseuDetail = bseu

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
    if (url.pathname === '/api/universities/bseu') return response(bseuDetail)
    if (url.pathname === '/api/universities/bseu/programs/economic-informatics') return response(bseuDetail.programs[0])
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
    <button onClick={() => navigate(-1)} type="button">Тест: назад</button>
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
  bseuDetail = bseu
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
    expect(screen.getByRole('link', { name: 'Сравнить вуз' })).toHaveAttribute('href', '/compare?universities=bseu')
    expect(screen.getByRole('heading', { name: 'О вузе' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Официальные ресурсы' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Мониторинг и покрытие источников' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Импортированные программы' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Экономическая информатика' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /2026 · Дневная форма · Платная/ })).toBeInTheDocument()
    expect(screen.getByText('60 мест')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Live-мониторинг БГЭУ' })).toHaveAttribute('href', '/monitor')
    expect(screen.getByRole('button', { name: `Сохранить — ${bseu.full_name}` })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: `Официальная страница программы «${bseu.programs[0].name}» (откроется в новой вкладке)` })).toHaveAttribute('href', bseu.programs[0].official_url)
    expect(screen.getByRole('link', { name: 'Официальная страница набора 2026 (откроется в новой вкладке)' })).toHaveAttribute('href', bseu.programs[0].offerings[0].official_url)
    expect(container.querySelectorAll('h1')).toHaveLength(1)
    expect(screen.getByRole('link', { name: 'Экономическая информатика' })).toHaveAttribute(
      'href',
      '/universities/bseu/programs/economic-informatics',
    )
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
    expect(screen.queryByRole('heading', { name: 'Найти программу' })).not.toBeInTheDocument()
  })
})

describe('program discovery URL filters', () => {
  it('parses filters on initial load and shows only matching Programs and Offerings', async () => {
    bseuDetail = discoveryBseu
    renderRoute(['/universities/bseu?program_query=%D0%9C%D0%95%D0%9D%D0%95%D0%94%D0%96&study_form=part_time'])

    expect(await screen.findByRole('heading', { name: 'Менеджмент' })).toBeInTheDocument()
    expect(screen.getByLabelText('Название или код')).toHaveValue('МЕНЕДЖ')
    expect(screen.getByLabelText('Форма обучения')).toHaveValue('part_time')
    expect(screen.queryByRole('heading', { name: 'Экономическая информатика' })).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /2026 · Заочная форма · Платная/ })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: /2026 · Дневная форма · Бюджет/ })).not.toBeInTheDocument()
    expect(screen.getByText('Показано: 1 программа из 3 · 1 вариант обучения из 5')).toBeInTheDocument()
  })

  it('updates compact URL parameters and derives only available filter options', async () => {
    bseuDetail = discoveryBseu
    const user = userEvent.setup()
    renderRoute(['/universities/bseu?from=catalog'])
    await screen.findByRole('heading', { name: 'Экономическая информатика' })

    expect(screen.getByRole('option', { name: 'Дистанционная форма' })).toBeInTheDocument()
    expect(screen.queryByRole('option', { name: 'Вечерняя форма' })).not.toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Финансирование'), 'budget')
    await waitFor(() => expect(screen.getByLabelText('Текущий маршрут')).toHaveTextContent(
      '/universities/bseu?from=catalog&funding_type=budget',
    ))
    expect(screen.getByRole('heading', { name: 'Экономическая информатика' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Менеджмент' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Маркетинг' })).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Тест: назад' }))
    await waitFor(() => expect(screen.getByLabelText('Текущий маршрут')).toHaveTextContent(
      '/universities/bseu?from=catalog',
    ))
    expect(screen.getByRole('heading', { name: 'Маркетинг' })).toBeInTheDocument()
  })

  it('shows a distinct filtered empty state with one reset action and restores the full list', async () => {
    bseuDetail = discoveryBseu
    const user = userEvent.setup()
    renderRoute(['/universities/bseu'])
    await screen.findByRole('heading', { name: 'Экономическая информатика' })

    await user.type(screen.getByLabelText('Название или код'), 'несуществующая программа')
    expect(await screen.findByText('По выбранным условиям импортированные программы не найдены')).toBeInTheDocument()
    expect(screen.queryByText('Каталог программ ещё не импортирован')).not.toBeInTheDocument()
    const reset = screen.getByRole('button', { name: 'Сбросить фильтры' })
    expect(screen.getAllByRole('button', { name: 'Сбросить фильтры' })).toHaveLength(1)
    await user.click(reset)

    expect(await screen.findByRole('heading', { name: 'Экономическая информатика' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Менеджмент' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Маркетинг' })).toBeInTheDocument()
    expect(screen.getByLabelText('Текущий маршрут')).toHaveTextContent('/universities/bseu')
    expect(screen.getByText('Показано: 3 программы из 3 · 5 вариантов обучения из 5')).toBeInTheDocument()
  })

  it('drops unknown URL values without crashing or hiding imported Programs', async () => {
    bseuDetail = discoveryBseu
    renderRoute(['/universities/bseu?study_form=telepathy&funding_type=unknown&monitoring_status=missing'])

    expect(await screen.findByRole('heading', { name: 'Экономическая информатика' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Менеджмент' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Маркетинг' })).toBeInTheDocument()
    await waitFor(() => expect(screen.getByLabelText('Текущий маршрут')).toHaveTextContent('/universities/bseu'))
  })
})

describe('catalog return navigation and obsolete requests', () => {
  it('carries the exact university URL through the program link and return action', async () => {
    const origin = '/universities/bseu?from=catalog'
    const user = userEvent.setup()
    renderRoute([origin])

    await screen.findByRole('heading', { level: 1, name: bseu.full_name })
    await user.click(screen.getByRole('link', { name: 'Экономическая информатика' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Экономическая информатика' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Назад к вузу' })).toHaveAttribute('href', origin)
  })

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
