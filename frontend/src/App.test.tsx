import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import App from './App'
import type { CollectorStatus, HealthStatus, PublicConfig, Snapshot } from './types'

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

const snapshot: Snapshot = {
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
  data_age_seconds: 60,
  source_age_seconds: 120,
  last_checked_at: '2026-07-13T18:05:00Z',
}

const collector: CollectorStatus = {
  state: 'ok',
  consecutive_errors: 0,
  next_run_at: '2026-07-13T18:15:00Z',
  last_run: { status: 'success', error_message: null, finished_at: '2026-07-13T18:05:00Z', rows_found: 1 },
}

const health: HealthStatus = {
  status: 'ok',
  database: 'ok',
  scheduler_running: true,
  refresh_in_progress: false,
  last_success_at: '2026-07-13T18:05:00Z',
  last_error: null,
}

const publicConfig: PublicConfig = {
  university: 'БГЭУ',
  target_specialties: ['Экономическая информатика'],
  study_form: 'дневная',
  funding_type: 'платная',
  user_score: 276,
  poll_interval_minutes: 10,
  timezone: 'Europe/Minsk',
  source_url: 'https://bseu.by/abiturient/',
  stale_after_minutes: 30,
  telegram_enabled: false,
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
let monitorSnapshot: Snapshot | null
let monitorHistory: Snapshot[]
let monitorCollector: CollectorStatus
let monitorHealth: HealthStatus
let monitorConfig: PublicConfig
let failOncePath: string | null
let failingPaths: Set<string>

function response(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status >= 400 ? 'Request failed' : 'OK',
    json: async () => body,
  } as Response
}

function installSuccessfulApiMock() {
  fetchMock.mockImplementation(async (input, init) => {
    const url = String(input)
    const path = new URL(url, 'http://localhost').pathname
    if (failOncePath === path) {
      failOncePath = null
      throw new Error('temporary API failure')
    }
    if (failingPaths.has(path)) throw new Error('API unavailable')
    if (url.endsWith('/api/catalog/meta')) return response(catalogMeta)
    if (url.endsWith('/api/specialties')) return response([specialty])
    if (url.includes('/api/specialties/1/latest')) {
      return monitorSnapshot === null
        ? response({ detail: 'Для специальности еще нет корректных данных' }, 404)
        : response(monitorSnapshot)
    }
    if (url.includes('/api/specialties/1/history')) return response(monitorHistory)
    if (url.endsWith('/api/status')) return response(monitorCollector)
    if (url.endsWith('/api/health')) return response(monitorHealth)
    if (url.endsWith('/api/config')) return response(monitorConfig)
    throw new Error(`Unexpected mocked request: ${init?.method ?? 'GET'} ${url}`)
  })
}

function renderRoute(route: string) {
  return render(<MemoryRouter initialEntries={[route]}><App /></MemoryRouter>)
}

beforeEach(() => {
  fetchMock.mockReset()
  monitorSnapshot = snapshot
  monitorHistory = [snapshot]
  monitorCollector = collector
  monitorHealth = health
  monitorConfig = publicConfig
  failOncePath = null
  failingPaths = new Set()
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
    expect(screen.getByText('Автоматическое обновление включено')).toBeInTheDocument()
    expect(screen.getByText('Получены новые данные')).toBeInTheDocument()
    expect(screen.getByText(/Последняя успешная проверка:/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Обновить' })).not.toBeInTheDocument()
    expect(screen.queryByText(/MANUAL_REFRESH_TOKEN/)).not.toBeInTheDocument()
    expect(container.querySelectorAll('h1')).toHaveLength(1)

    const requestedUrls = fetchMock.mock.calls.map(([input]) => String(input))
    expect(requestedUrls).toEqual(expect.arrayContaining([
      '/api/specialties',
      '/api/specialties/1/latest',
      '/api/specialties/1/history?limit=200',
      '/api/status',
      '/api/health',
      '/api/config',
    ]))
    expect(requestedUrls.every((url) => url.startsWith('/api/'))).toBe(true)
    expect(fetchMock.mock.calls.every(([, init]) => !init?.method || init.method === 'GET')).toBe(true)
    expect(requestedUrls).not.toContain('/api/refresh')
  })

  it('distinguishes unchanged, refreshing, collector-error, and old-source states', async () => {
    monitorCollector = {
      ...collector,
      state: 'not_modified',
      last_run: { ...collector.last_run!, status: 'not_modified' },
    }
    const { unmount } = renderRoute('/monitor')
    expect(await screen.findByText('Источник проверен, изменений нет')).toBeInTheDocument()
    unmount()

    monitorCollector = { ...collector, state: 'refreshing' }
    monitorHealth = { ...health, refresh_in_progress: true }
    const refreshing = renderRoute('/monitor')
    expect((await screen.findAllByText('Проверяем данные БГЭУ')).length).toBeGreaterThan(0)
    refreshing.unmount()

    monitorCollector = {
      ...collector,
      state: 'error',
      last_run: { ...collector.last_run!, status: 'error', error_message: 'source unavailable' },
    }
    monitorHealth = { ...health, last_error: 'source unavailable' }
    monitorSnapshot = { ...snapshot, source_age_seconds: 7_200, is_stale: true }
    renderRoute('/monitor')
    expect(await screen.findByText('Последняя проверка источника завершилась ошибкой.')).toBeInTheDocument()
    expect(screen.getByText('БГЭУ давно не обновлял данные на своей стороне.')).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 2, name: 'Экономическая информатика' })).toBeInTheDocument()
  })

  it('shows an honest no-snapshot state and retries with GET requests only', async () => {
    const user = userEvent.setup()
    monitorSnapshot = null
    monitorHistory = []
    renderRoute('/monitor')

    expect(await screen.findByRole('heading', {
      name: 'Первый корректный снимок конкурсной ситуации ещё не получен',
    })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Повторить загрузку' }))
    await waitFor(() => expect(fetchMock.mock.calls.filter(([input]) => (
      String(input) === '/api/specialties/1/latest'
    )).length).toBeGreaterThan(1))

    expect(fetchMock.mock.calls.every(([, init]) => !init?.method || init.method === 'GET')).toBe(true)
    expect(fetchMock.mock.calls.map(([input]) => String(input))).not.toContain('/api/refresh')
  })

  it('retains the last snapshot when a collector read fails and offers a safe retry', async () => {
    failingPaths.add('/api/status')
    renderRoute('/monitor')

    expect(await screen.findByText('Не удалось полностью обновить страницу.')).toBeInTheDocument()
    expect(screen.getByText('Показан последний корректный снимок.')).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 2, name: 'Экономическая информатика' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Повторить загрузку' })).toBeInTheDocument()
  })

  it('reports unavailable automatic updates without claiming a collector failure', async () => {
    monitorHealth = { ...health, scheduler_running: false }
    renderRoute('/monitor')

    expect(await screen.findByText('Автоматическое обновление сейчас недоступно')).toBeInTheDocument()
    expect(screen.queryByText('Последняя проверка источника завершилась ошибкой.')).not.toBeInTheDocument()
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
