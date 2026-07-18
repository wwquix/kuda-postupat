import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation, useNavigate } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import App from './App'
import type { ImportedProgram } from './types'

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
  official_url: 'https://bseu.by/russian/teaching/specialities.htm',
  active: true,
  source_checked_at: '2026-07-12T18:14:28Z',
  verified_at: null,
  updated_at: '2026-07-12T18:14:28Z',
  offering_count: 2,
  offerings: [
    {
      id: 2,
      admission_year: 2025,
      study_form: 'full_time',
      funding_type: 'budget',
      places: null,
      monitoring_supported: false,
      monitoring_status: 'reference_only',
      official_url: 'https://bseu.by/offering-2025',
      source_url: 'https://bseu.by/offering-2025',
      source_checked_at: '2026-07-12T18:14:28Z',
    },
    {
      id: 1,
      admission_year: 2026,
      study_form: 'full_time',
      funding_type: 'paid',
      places: 60,
      monitoring_supported: true,
      monitoring_status: 'online',
      official_url: 'https://bseu.by/offering-2026',
      source_url: 'https://bseu.by/offering-2026',
      source_checked_at: '2026-07-12T18:14:28Z',
    },
  ],
  coverage_state: 'available',
}

const multiFormProgram: ImportedProgram = {
  ...program,
  offering_count: 4,
  offerings: [
    {
      ...program.offerings[1],
      id: 4,
      study_form: 'weekend',
      funding_type: 'employer_grant',
      monitoring_supported: false,
      monitoring_status: 'experimental_mode',
      official_url: 'https://bseu.by/offering-weekend',
      source_url: 'https://bseu.by/offering-weekend',
    },
    {
      ...program.offerings[1],
      id: 3,
      study_form: 'part_time',
      monitoring_supported: false,
      monitoring_status: 'reference_only',
      official_url: 'https://bseu.by/offering-part-time',
      source_url: 'https://bseu.by/offering-part-time',
    },
    program.offerings[0],
    program.offerings[1],
  ],
}

const fetchMock = vi.fn<typeof fetch>()
let programDetail = program

function response(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status >= 400 ? 'Request failed' : 'OK',
    json: async () => body,
  } as Response
}

function installApiMock() {
  fetchMock.mockImplementation(async (input) => {
    const url = new URL(String(input), 'http://localhost')
    if (url.pathname === '/api/universities/bseu/programs/economic-informatics') return response(programDetail)
    if (url.pathname === '/api/universities/bseu/programs/empty-program') {
      return response({ ...program, slug: 'empty-program', name: 'Программа без наборов', offering_count: 0, offerings: [] })
    }
    if (url.pathname === '/api/universities/bseu/programs/missing') return response({ detail: 'raw not found' }, 404)
    throw new Error(`Unexpected mocked request: ${url.pathname}`)
  })
}

function LocationProbe() {
  const location = useLocation()
  return <output aria-label="Текущий маршрут">{location.pathname}{location.search}</output>
}

function ProgramControls() {
  const navigate = useNavigate()
  return <button onClick={() => navigate('/universities/bseu/programs/economic-informatics')} type="button">
    Тест: открыть программу
  </button>
}

function renderRoute(initialEntries: Parameters<typeof MemoryRouter>[0]['initialEntries']) {
  return render(<MemoryRouter initialEntries={initialEntries}>
    <App />
    <LocationProbe />
    <ProgramControls />
  </MemoryRouter>)
}

beforeEach(() => {
  programDetail = program
  fetchMock.mockReset()
  installApiMock()
  vi.stubGlobal('fetch', fetchMock)
  document.title = 'Тест'
})

describe('program detail states and honest rendering', () => {
  it('announces loading and renders only stored program and offering fields', async () => {
    let resolveDetail: ((value: Response) => void) | undefined
    fetchMock.mockImplementation((input) => {
      const url = new URL(String(input), 'http://localhost')
      if (url.pathname === '/api/universities/bseu/programs/economic-informatics') {
        return new Promise((resolve) => { resolveDetail = resolve })
      }
      return Promise.reject(new Error('Unexpected request'))
    })
    const { container } = renderRoute(['/universities/bseu/programs/economic-informatics'])

    expect(screen.getByRole('heading', { level: 1, name: 'Загружаем страницу программы…' })).toBeInTheDocument()
    await waitFor(() => expect(resolveDetail).toBeDefined())
    resolveDetail?.(response(program))

    expect(await screen.findByRole('heading', { level: 1, name: program.name })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'БГЭУ' })).toHaveAttribute('href', '/universities/bseu')
    expect(screen.getByText(program.qualification as string)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Дневная форма' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Дневная форма · 2025 год' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Дневная форма · 2026 год' })).toBeInTheDocument()
    expect(screen.getByText('60 мест')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Открыть live-мониторинг: Дневная форма, 2026, Платно' })).toHaveAttribute('href', '/monitor')
    expect(screen.getByText('Вариант доступен в каталоге, но пока не отслеживается автоматически.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: `Сохранить — ${program.name}` })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: `Официальная страница программы «${program.name}» (откроется в новой вкладке)` })).toHaveAttribute('href', program.official_url)
    expect(screen.getByRole('link', { name: 'Официальная страница набора 2025 (откроется в новой вкладке)' })).toHaveAttribute('href', program.offerings[0].official_url)
    expect(screen.getByRole('link', { name: 'Официальная страница набора 2026 (откроется в новой вкладке)' })).toHaveAttribute('href', program.offerings[1].official_url)
    expect(screen.queryByText(/язык обучения/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/история/i)).not.toBeInTheDocument()
    expect(container.querySelectorAll('h1')).toHaveLength(1)
    expect(container.querySelector('a[href^="/program-offerings/"]')).not.toBeInTheDocument()
    await waitFor(() => expect(document.title).toBe('Экономическая информатика · БГЭУ · Куда поступать'))
  })

  it('uses the exact coverage wording when offerings have not been imported', async () => {
    renderRoute(['/universities/bseu/programs/empty-program'])

    expect(await screen.findByRole('heading', { level: 1, name: 'Программа без наборов' })).toBeInTheDocument()
    expect(screen.getByText('Варианты обучения ещё не импортированы')).toBeInTheDocument()
    expect(screen.getByText(/не отсутствие реальных вариантов обучения/)).toBeInTheDocument()
    expect(screen.queryByText(/0 вариантов/)).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Кратко о вариантах' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /live-мониторинг/i })).not.toBeInTheDocument()
  })

  it('renders 404 separately from a retryable API failure', async () => {
    renderRoute(['/universities/bseu/programs/missing'])

    expect(await screen.findByRole('heading', { level: 1, name: 'Программа не найдена' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Повторить запрос' })).not.toBeInTheDocument()
    expect(screen.queryByText('raw not found')).not.toBeInTheDocument()
  })

  it('retries a safe error without exposing raw API details', async () => {
    let fail = true
    fetchMock.mockImplementation(async () => {
      if (fail) return response({ detail: 'raw database exception' }, 500)
      return response(program)
    })
    const user = userEvent.setup()
    renderRoute(['/universities/bseu/programs/economic-informatics'])

    expect(await screen.findByRole('heading', { name: 'Не удалось загрузить страницу программы' })).toBeInTheDocument()
    expect(screen.queryByText('raw database exception')).not.toBeInTheDocument()
    fail = false
    await user.click(screen.getByRole('button', { name: 'Повторить запрос' }))
    expect(await screen.findByRole('heading', { level: 1, name: program.name })).toBeInTheDocument()
  })
})

describe('program offering clarity', () => {
  it('keeps a one-Offering summary compact and omits zero-count categories', async () => {
    programDetail = {
      ...program,
      offering_count: 1,
      offerings: [program.offerings[1]],
    }
    renderRoute(['/universities/bseu/programs/economic-informatics'])

    await screen.findByRole('heading', { level: 1, name: program.name })
    const summary = screen.getByRole('region', { name: 'Кратко о вариантах' })
    expect(within(summary).getByText('1 вариант')).toBeInTheDocument()
    expect(within(summary).queryByText('Бюджет')).not.toBeInTheDocument()
    expect(within(summary).getByText('Платно').nextElementSibling).toHaveTextContent('1')
    expect(within(summary).getByText('1 форма').nextElementSibling).toHaveTextContent('Дневная форма')
    expect(screen.getByRole('region', { name: 'Дневная форма' })).toHaveTextContent('1 вариант')
  })

  it('groups multiple Offerings in deterministic study-form order and keeps records distinct', async () => {
    programDetail = multiFormProgram
    renderRoute(['/universities/bseu/programs/economic-informatics'])

    await screen.findByRole('heading', { level: 1, name: program.name })
    const fullTime = screen.getByRole('region', { name: 'Дневная форма' })
    const partTime = screen.getByRole('region', { name: 'Заочная форма' })
    const weekend = screen.getByRole('region', { name: 'Weekend' })
    expect(fullTime.compareDocumentPosition(partTime) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(partTime.compareDocumentPosition(weekend) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(within(fullTime).getAllByRole('article')).toHaveLength(2)
    expect(within(partTime).getAllByRole('article')).toHaveLength(1)
    expect(within(weekend).getAllByRole('article')).toHaveLength(1)

    const summary = screen.getByRole('region', { name: 'Кратко о вариантах' })
    expect(within(summary).getByText('4 варианта')).toBeInTheDocument()
    expect(within(summary).getByText('Бюджет').nextElementSibling).toHaveTextContent('1')
    expect(within(summary).getByText('Платно').nextElementSibling).toHaveTextContent('2')
    expect(within(summary).getByText('Live-мониторинг').nextElementSibling).toHaveTextContent('1')
    expect(within(summary).getByText('3 формы').nextElementSibling).toHaveTextContent('Дневная форма, Заочная форма, Weekend')
  })

  it('shows known plans only and scopes live monitoring to the matching Offering', async () => {
    renderRoute(['/universities/bseu/programs/economic-informatics'])
    await screen.findByRole('heading', { level: 1, name: program.name })

    const referenceCard = screen.getByRole('link', {
      name: 'Официальная страница набора 2025 (откроется в новой вкладке)',
    }).closest('article')
    const liveCard = screen.getByRole('link', {
      name: 'Официальная страница набора 2026 (откроется в новой вкладке)',
    }).closest('article')
    expect(referenceCard).not.toBeNull()
    expect(liveCard).not.toBeNull()
    expect(within(referenceCard as HTMLElement).queryByText('План приёма')).not.toBeInTheDocument()
    expect(within(referenceCard as HTMLElement).queryByText(/0 мест/)).not.toBeInTheDocument()
    expect(within(referenceCard as HTMLElement).getByText('Только справочные данные')).toBeInTheDocument()
    expect(within(referenceCard as HTMLElement).queryByRole('link', { name: /live-мониторинг/i })).not.toBeInTheDocument()
    expect(within(liveCard as HTMLElement).getByText('60 мест')).toBeInTheDocument()
    expect(within(liveCard as HTMLElement).getByRole('link', { name: /live-мониторинг/i })).toHaveAttribute('href', '/monitor')
  })

  it('uses existing labels for additional enum values and keeps their monitoring neutral', async () => {
    programDetail = multiFormProgram
    renderRoute(['/universities/bseu/programs/economic-informatics'])
    await screen.findByRole('heading', { level: 1, name: program.name })

    const weekendGroup = screen.getByRole('region', { name: 'Weekend' })
    expect(within(weekendGroup).getAllByText('Employer grant').length).toBeGreaterThan(0)
    expect(within(weekendGroup).getByText('Experimental mode')).toBeInTheDocument()
    expect(within(weekendGroup).queryByRole('link', { name: /live-мониторинг/i })).not.toBeInTheDocument()
  })
})

describe('program navigation and obsolete requests', () => {
  it('preserves the exact originating university URL and has a safe direct fallback', async () => {
    const origin = '/universities/bseu?from=catalog'
    renderRoute([{ pathname: '/universities/bseu/programs/economic-informatics', state: { universityReturnTo: origin } }])
    await screen.findByRole('heading', { level: 1, name: program.name })
    expect(screen.getByRole('link', { name: 'Назад к вузу' })).toHaveAttribute('href', origin)
  })

  it('falls back to the owning university on a direct opening', async () => {
    renderRoute(['/universities/bseu/programs/economic-informatics'])
    await screen.findByRole('heading', { level: 1, name: program.name })
    expect(screen.getByRole('link', { name: 'Назад к вузу' })).toHaveAttribute('href', '/universities/bseu')
  })

  it('aborts and ignores an obsolete request when the program key changes', async () => {
    let obsoleteSignal: AbortSignal | undefined
    fetchMock.mockImplementation((input, init) => {
      const url = new URL(String(input), 'http://localhost')
      if (url.pathname === '/api/universities/bseu/programs/slow') {
        obsoleteSignal = init?.signal ?? undefined
        return new Promise(() => undefined)
      }
      if (url.pathname === '/api/universities/bseu/programs/economic-informatics') return Promise.resolve(response(program))
      return Promise.reject(new Error('Unexpected request'))
    })
    const user = userEvent.setup()
    renderRoute(['/universities/bseu/programs/slow'])

    await waitFor(() => expect(obsoleteSignal).toBeDefined())
    await user.click(screen.getByRole('button', { name: 'Тест: открыть программу' }))
    await waitFor(() => expect(obsoleteSignal?.aborted).toBe(true))
    expect(await screen.findByRole('heading', { level: 1, name: program.name })).toBeInTheDocument()
  })
})

describe('frontend program detail isolation', () => {
  it('uses only the nested read-only API request', async () => {
    renderRoute(['/universities/bseu/programs/economic-informatics'])
    await screen.findByRole('heading', { level: 1, name: program.name })

    expect(fetchMock.mock.calls.map(([input]) => String(input))).toEqual([
      '/api/universities/bseu/programs/economic-informatics',
    ])
    expect(fetchMock.mock.calls.every(([, init]) => !init?.method || init.method === 'GET')).toBe(true)
  })
})
