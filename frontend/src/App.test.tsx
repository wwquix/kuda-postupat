import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import App from './App'

vi.mock('recharts', () => {
  const ChartStub = ({ children }: { children?: ReactNode }) => <div>{children}</div>
  return {
    Area: ChartStub,
    AreaChart: ChartStub,
    Bar: ChartStub,
    BarChart: ChartStub,
    CartesianGrid: ChartStub,
    Line: ChartStub,
    LineChart: ChartStub,
    ResponsiveContainer: ChartStub,
    Tooltip: ChartStub,
    XAxis: ChartStub,
    YAxis: ChartStub,
  }
})

const specialty = {
  id: 1,
  display_name: 'Экономическая информатика · дневная · платная',
  study_form: 'дневная',
  funding_type: 'платная',
  source_url: 'https://bseu.by/abiturient/',
}

const snapshot = {
  id: 5,
  specialty_id: 1,
  specialty: 'Экономическая информатика',
  study_form: 'дневная',
  funding_type: 'платная',
  source_url: 'https://bseu.by/abiturient/',
  fetched_at: '2026-07-13T18:00:00Z',
  source_updated_at: '2026-07-13T17:30:00Z',
  admission_plan: 60,
  applications_total: 25,
  competition: 0.42,
  estimated_cutoff_min: null,
  estimated_cutoff_max: null,
  estimated_cutoff: null,
  no_competition: true,
  user_score: 276,
  estimated_user_position: 11,
  user_status: 'Уверенно проходит',
  distribution: { '271-275': 2, '276-280': 3 },
  is_stale: false,
  last_checked_at: '2026-07-13T18:05:00Z',
}

const collector = {
  state: 'ok',
  consecutive_errors: 0,
  next_run_at: '2026-07-13T18:15:00Z',
  last_run: { status: 'success', error_message: null, finished_at: '2026-07-13T18:05:00Z', rows_found: 1 },
}

const catalogMeta = {
  counts: {
    universities: 47,
    programs: 1,
    offerings: 1,
    universities_with_programs: 1,
    universities_with_admissions_url: 33,
  },
  coverage: { state: 'partial', note: 'Покрытие платформы неполное.' },
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

function installSuccessfulApiMock() {
  fetchMock.mockImplementation(async (input) => {
    const url = String(input)
    if (url.endsWith('/api/catalog/meta')) return response(catalogMeta)
    if (url.endsWith('/api/specialties')) return response([specialty])
    if (url.includes('/api/specialties/1/latest')) return response(snapshot)
    if (url.includes('/api/specialties/1/history')) return response([snapshot])
    if (url.endsWith('/api/status')) return response(collector)
    throw new Error(`Unexpected mocked request: ${url}`)
  })
}

function renderRoute(route: string) {
  return render(<MemoryRouter initialEntries={[route]}><App /></MemoryRouter>)
}

beforeEach(() => {
  fetchMock.mockReset()
  installSuccessfulApiMock()
  vi.stubGlobal('fetch', fetchMock)
})

describe('frontend shell routing', () => {
  it('renders the homepage with catalog statistics from the mocked API', async () => {
    const { container } = renderRoute('/')

    expect(screen.getByRole('heading', { level: 1, name: 'Куда поступать' })).toBeInTheDocument()
    expect(await screen.findByText(/В каталоге платформы —/)).toHaveTextContent('47 университетов Беларуси')
    expect(screen.getByText(/live-мониторинг работает только для БГЭУ/i)).toBeInTheDocument()
    expect(container.querySelectorAll('h1')).toHaveLength(1)
    expect(fetchMock).toHaveBeenCalledWith('/api/catalog/meta', undefined)
  })

  it('renders the existing monitor dashboard at /monitor using only mocked API calls', async () => {
    const { container } = renderRoute('/monitor')

    expect(screen.getByRole('heading', { level: 1, name: 'Монитор поступления' })).toBeInTheDocument()
    expect(await screen.findByRole('heading', { level: 2, name: 'Экономическая информатика' })).toBeInTheDocument()
    expect(screen.getByRole('spinbutton', { name: 'Мой балл' })).toHaveValue(276)
    expect(screen.getByRole('heading', { name: 'История обновлений' })).toBeInTheDocument()
    expect(container.querySelectorAll('h1')).toHaveLength(1)

    const requestedUrls = fetchMock.mock.calls.map(([input]) => String(input))
    expect(requestedUrls).toEqual(expect.arrayContaining([
      '/api/specialties',
      '/api/specialties/1/latest',
      '/api/specialties/1/history?limit=200',
      '/api/status',
    ]))
    expect(requestedUrls.every((url) => url.startsWith('/api/'))).toBe(true)
  })

  it('changes routes through navigation and exposes the active route', async () => {
    const user = userEvent.setup()
    renderRoute('/')
    await screen.findByText('47')

    const homeLink = screen.getByRole('link', { name: 'Главная' })
    const monitorLink = screen.getByRole('link', { name: 'Монитор поступления' })
    expect(homeLink).toHaveAttribute('aria-current', 'page')
    expect(monitorLink).not.toHaveAttribute('aria-current')

    await user.click(monitorLink)
    await screen.findByRole('heading', { level: 2, name: 'Экономическая информатика' })
    expect(monitorLink).toHaveAttribute('aria-current', 'page')
    expect(homeLink).not.toHaveAttribute('aria-current')
  })

  it('renders a safe 404 page with accessible navigation for an unknown route', () => {
    const { container } = renderRoute('/unknown-route')

    expect(screen.getByRole('heading', { level: 1, name: 'Страница не найдена' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'На главную' })).toHaveAttribute('href', '/')
    expect(within(screen.getByRole('main')).getByRole('link', { name: 'Монитор поступления' })).toHaveAttribute('href', '/monitor')
    expect(container.querySelectorAll('h1')).toHaveLength(1)
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('shows an honest safe state when homepage metadata cannot be loaded', async () => {
    fetchMock.mockRejectedValueOnce(new Error('backend unavailable'))
    renderRoute('/')

    expect(await screen.findByText(/Количество вузов временно не удалось подтвердить/)).toBeInTheDocument()
    expect(screen.queryByText(/0 университетов/)).not.toBeInTheDocument()
  })

  it('keeps the skip link first in keyboard order and sets meaningful page titles', async () => {
    const user = userEvent.setup()
    renderRoute('/')

    await waitFor(() => expect(document.title).toBe('Куда поступать · Данные для абитуриентов Беларуси'))
    await user.tab()
    expect(screen.getByRole('link', { name: 'Перейти к содержимому' })).toHaveFocus()
  })

  it('keeps routes and links inside a configured deployment base path', async () => {
    render(<MemoryRouter basename="/bseu" initialEntries={['/bseu/monitor']}><App /></MemoryRouter>)

    await screen.findByRole('heading', { level: 2, name: 'Экономическая информатика' })
    expect(screen.getByRole('link', { name: 'Главная' })).toHaveAttribute('href', '/bseu')
    expect(screen.getByRole('link', { name: 'Монитор поступления' })).toHaveAttribute('href', '/bseu/monitor')
  })
})
