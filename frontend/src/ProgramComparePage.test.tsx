import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import App from './App'
import type { ImportedProgram, OfferingSummary } from './types'

const offering = (
  id: number,
  studyForm: string,
  fundingType: string,
  year: number,
  places: number | null,
  monitoringStatus: string,
  monitoringSupported = false,
): OfferingSummary => ({
  id,
  admission_year: year,
  study_form: studyForm,
  funding_type: fundingType,
  places,
  monitoring_supported: monitoringSupported,
  monitoring_status: monitoringStatus,
  official_url: `https://example.test/offerings/${id}`,
  source_url: `https://example.test/offerings/${id}`,
  source_checked_at: '2026-07-17T12:00:00Z',
})

const makeProgram = (
  id: number,
  universitySlug: string,
  universityName: string,
  slug: string,
  name: string,
  offerings: OfferingSummary[],
): ImportedProgram => ({
  id,
  university_id: id,
  university: { id, code: universitySlug, slug: universitySlug, short_name: universityName },
  code: `6-05-000${id}-00`,
  slug,
  name,
  qualification: `Квалификация ${id}`,
  faculty_name: `Факультет ${id}`,
  education_level: 'Высшее образование',
  duration_years: 4,
  official_url: `https://example.test/programs/${id}`,
  active: true,
  source_checked_at: '2026-07-17T12:00:00Z',
  verified_at: null,
  updated_at: '2026-07-17T12:00:00Z',
  offering_count: offerings.length,
  offerings,
  coverage_state: 'available',
})

const economicInformatics = makeProgram(1, 'bseu', 'БГЭУ', 'economic-informatics', 'Экономическая информатика', [
  offering(2, 'full_time', 'budget', 2025, null, 'reference_only'),
  offering(3, 'part_time', 'paid', 2026, 25, 'reference_only'),
  offering(1, 'full_time', 'paid', 2026, 60, 'online', true),
])
const management = {
  ...makeProgram(2, 'bseu', 'БГЭУ', 'management', 'Менеджмент', [
    offering(4, 'full_time', 'budget', 2026, null, 'reference_only'),
  ]),
  code: null,
  qualification: null,
  faculty_name: null,
  education_level: null,
  duration_years: null,
}
const accounting = makeProgram(3, 'alpha', 'Альфа', 'accounting', 'Бухгалтерский учёт', [
  offering(5, 'distance', 'paid', 2026, null, 'unsupported'),
])
const retryProgram = makeProgram(4, 'alpha', 'Альфа', 'retry', 'Программа после повтора', [])

const programs = new Map([
  ['bseu:economic-informatics', economicInformatics],
  ['bseu:management', management],
  ['alpha:accounting', accounting],
  ['alpha:retry', retryProgram],
])
const fetchMock = vi.fn<typeof fetch>()
let retryFailures = 0
let failAll = false

function response(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status >= 400 ? 'Request failed' : 'OK',
    json: async () => body,
  } as Response
}

function installApiMock() {
  fetchMock.mockImplementation(async (input, init) => {
    const url = new URL(String(input), 'http://localhost')
    const match = url.pathname.match(/^\/api\/universities\/([^/]+)\/programs\/([^/]+)$/u)
    if (!match) throw new Error(`Unexpected request: ${url.pathname}`)
    expect(!init?.method || init.method === 'GET').toBe(true)
    const key = `${decodeURIComponent(match[1])}:${decodeURIComponent(match[2])}`
    if (failAll) return response({ detail: 'temporary failure' }, 500)
    if (key === 'alpha:retry' && retryFailures > 0) {
      retryFailures -= 1
      return response({ detail: 'temporary failure' }, 500)
    }
    const program = programs.get(key)
    return program ? response(program) : response({ detail: 'not found' }, 404)
  })
}

function LocationProbe() {
  const location = useLocation()
  return <output aria-label="Текущий URL сравнения программ">{location.pathname}{location.search}</output>
}

function renderCompare(route: string) {
  return render(<MemoryRouter initialEntries={[route]}>
    <App />
    <LocationProbe />
  </MemoryRouter>)
}

beforeEach(() => {
  retryFailures = 0
  failAll = false
  fetchMock.mockReset()
  installApiMock()
  vi.stubGlobal('fetch', fetchMock)
})

describe('public Program comparison states and URL contract', () => {
  it('shows empty guidance and links to MyList without issuing requests', () => {
    renderCompare('/compare/programs')

    expect(screen.getByRole('heading', { level: 1, name: 'Сравнение программ' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Выберите 2–3 программы' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Перейти в Мой список' })).toHaveAttribute('href', '/my-list')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('loads one Program but shows guidance instead of a false full comparison', async () => {
    renderCompare('/compare/programs?programs=bseu:economic-informatics')

    expect(screen.getByRole('status', { name: 'Загрузка программы bseu:economic-informatics' })).toBeInTheDocument()
    expect(await screen.findByRole('article', { name: economicInformatics.name })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Нужна ещё одна программа' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Выбранная программа' })).toBeInTheDocument()
  })

  it('canonicalizes duplicates, malformed identities, and excess values once', async () => {
    renderCompare('/compare/programs?programs=%20bseu%20%3A%20economic-informatics%20%2Cbseu%3Aeconomic-informatics%2Cbad%2Cbseu%3Amanagement%2Calpha%3Aaccounting%2Cu%3Ax&noise=1')

    await screen.findByRole('article', { name: accounting.name })
    await waitFor(() => expect(screen.getByLabelText('Текущий URL сравнения программ')).toHaveTextContent(
      '/compare/programs?programs=bseu%3Aeconomic-informatics%2Cbseu%3Amanagement%2Calpha%3Aaccounting',
    ))
    expect(fetchMock.mock.calls).toHaveLength(3)
  })

  it('renders two and three Programs in URL order', async () => {
    const { unmount } = renderCompare('/compare/programs?programs=bseu:economic-informatics,bseu:management')
    const first = await screen.findByRole('article', { name: economicInformatics.name })
    const second = await screen.findByRole('article', { name: management.name })
    expect(first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    unmount()

    renderCompare('/compare/programs?programs=alpha:accounting,bseu:management,bseu:economic-informatics')
    const accountingCard = await screen.findByRole('article', { name: accounting.name })
    const managementCard = await screen.findByRole('article', { name: management.name })
    const economicCard = await screen.findByRole('article', { name: economicInformatics.name })
    expect(accountingCard.compareDocumentPosition(managementCard) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(managementCard.compareDocumentPosition(economicCard) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('keeps successful Programs visible beside a not-found card', async () => {
    renderCompare('/compare/programs?programs=bseu:economic-informatics,missing:deleted')

    expect(await screen.findByRole('article', { name: economicInformatics.name })).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Программа не найдена: missing:deleted' })).toBeInTheDocument()
    expect(screen.getByText(/Остальные результаты сравнения сохранены/)).toBeInTheDocument()
  })

  it('retries only a failed Program and keeps successful content visible', async () => {
    retryFailures = 1
    const user = userEvent.setup()
    renderCompare('/compare/programs?programs=bseu:economic-informatics,alpha:retry')

    const successful = await screen.findByRole('article', { name: economicInformatics.name })
    const retry = await screen.findByRole('button', { name: 'Повторить загрузку — alpha:retry' })
    expect(successful).toBeInTheDocument()
    await user.click(retry)
    expect(await screen.findByRole('article', { name: retryProgram.name })).toBeInTheDocument()
    expect(successful).toBeInTheDocument()
    expect(fetchMock.mock.calls.filter(([input]) => String(input).endsWith('/alpha/programs/retry'))).toHaveLength(2)
  })

  it('shows an aggregate honest state when every request fails', async () => {
    failAll = true
    renderCompare('/compare/programs?programs=bseu:economic-informatics,bseu:management')

    expect(await screen.findByRole('heading', { name: 'Не удалось загрузить выбранные программы' })).toBeInTheDocument()
    expect(screen.getByLabelText('Текущий URL сравнения программ')).toHaveTextContent(
      'programs=bseu%3Aeconomic-informatics%2Cbseu%3Amanagement',
    )
  })

  it('removes Programs through URL navigation down to guidance and empty states', async () => {
    const user = userEvent.setup()
    renderCompare('/compare/programs?programs=bseu:economic-informatics,bseu:management')
    await screen.findByRole('article', { name: management.name })

    await user.click(screen.getByRole('button', { name: `Убрать из сравнения — ${economicInformatics.name}` }))
    await waitFor(() => expect(screen.getByLabelText('Текущий URL сравнения программ')).toHaveTextContent(
      '/compare/programs?programs=bseu%3Amanagement',
    ))
    expect(screen.getByRole('heading', { name: 'Нужна ещё одна программа' })).toBeInTheDocument()
    expect(screen.queryByRole('article', { name: economicInformatics.name })).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: `Убрать из сравнения — ${management.name}` }))
    expect(screen.getByRole('heading', { name: 'Выберите 2–3 программы' })).toBeInTheDocument()
    expect(screen.getByLabelText('Текущий URL сравнения программ')).toHaveTextContent('/compare/programs')
  })
})

describe('Program and Offering comparison content', () => {
  it('shows sourced Program summaries and omits unknown optional values', async () => {
    renderCompare('/compare/programs?programs=bseu:economic-informatics,bseu:management')
    const economicCard = await screen.findByRole('article', { name: economicInformatics.name })
    const managementCard = await screen.findByRole('article', { name: management.name })

    expect(within(economicCard).getByText('Квалификация 1')).toBeInTheDocument()
    expect(within(economicCard).getByText('Дневная форма, Заочная форма')).toBeInTheDocument()
    expect(within(economicCard).getByText('85 мест')).toBeInTheDocument()
    expect(within(economicCard).getByText('Бюджетные варианты').nextElementSibling).toHaveTextContent('1')
    expect(within(economicCard).getByText('Платные варианты').nextElementSibling).toHaveTextContent('2')
    expect(within(economicCard).getByText('Варианты с live-мониторингом').nextElementSibling).toHaveTextContent('1')
    expect(within(managementCard).queryByText('Квалификация')).not.toBeInTheDocument()
    expect(within(managementCard).queryByText('Подразделение')).not.toBeInTheDocument()
    expect(within(managementCard).queryByText('Продолжительность')).not.toBeInTheDocument()
    expect(within(managementCard).queryByText('Известные места, сумма')).not.toBeInTheDocument()
    expect(within(managementCard).queryByText(/0 мест/)).not.toBeInTheDocument()
  })

  it('keeps Offerings distinct, ordered, and honestly monitored with unchanged sources', async () => {
    renderCompare('/compare/programs?programs=bseu:economic-informatics,bseu:management')
    const card = await screen.findByRole('article', { name: economicInformatics.name })
    const fullTime = within(card).getByRole('region', { name: 'Дневная форма' })
    const partTime = within(card).getByRole('region', { name: 'Заочная форма' })
    expect(fullTime.compareDocumentPosition(partTime) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()

    const liveOffering = within(card).getByRole('region', { name: 'Вариант обучения: Дневная форма, 2026, Платно' })
    const referenceOffering = within(card).getByRole('region', { name: 'Вариант обучения: Дневная форма, 2025, Бюджет' })
    expect(within(liveOffering).getByText('Доступен live-мониторинг')).toBeInTheDocument()
    expect(within(liveOffering).getByRole('link', { name: /Открыть live-мониторинг/ })).toHaveAttribute('href', '/monitor')
    expect(within(referenceOffering).getByText('Только справочные данные')).toBeInTheDocument()
    expect(within(referenceOffering).getByText(/доступен в каталоге/)).toBeInTheDocument()
    expect(within(referenceOffering).queryByRole('link', { name: /live-мониторинг/i })).not.toBeInTheDocument()
    expect(within(referenceOffering).queryByText('План приёма')).not.toBeInTheDocument()

    expect(within(card).getByRole('link', { name: `Официальная страница программы «${economicInformatics.name}» (откроется в новой вкладке)` })).toHaveAttribute('href', economicInformatics.official_url)
    expect(within(liveOffering).getByRole('link', { name: 'Официальный источник варианта 2026 (откроется в новой вкладке)' })).toHaveAttribute('href', economicInformatics.offerings[2].official_url)
  })
})
