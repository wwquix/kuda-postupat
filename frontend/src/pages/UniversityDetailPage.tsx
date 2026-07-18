import {
  ArrowLeft,
  Building2,
  CalendarDays,
  ExternalLink,
  MapPin,
  RadioTower,
  RefreshCw,
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link, useLocation, useParams, useSearchParams } from 'react-router-dom'

import { api, ApiError } from '../api'
import { apiValueLabel, formatCatalogDate, sourceTypeLabel } from '../catalogPresentation'
import { SaveControl } from '../components/SaveControl'
import {
  DEFAULT_PROGRAM_DISCOVERY_QUERY,
  deriveProgramDiscoveryOptions,
  filterProgramsForDiscovery,
  formatProgramDiscoverySummary,
  hasProgramDiscoveryFilters,
  parseProgramDiscoveryQuery,
  serializeProgramDiscoveryQuery,
} from '../programDiscoveryQuery'
import type { ProgramDiscoveryOptions, ProgramDiscoveryQuery } from '../programDiscoveryQuery'
import type { ImportedProgram, OfferingSummary, UniversityDetail } from '../types'
import { useDocumentTitle } from '../useDocumentTitle'

type DetailState = {
  slug: string | null
  data: UniversityDetail | null
  status: 'loading' | 'success' | 'error' | 'not_found'
}

const EMPTY_PROGRAMS: ImportedProgram[] = []

function catalogReturnDestination(state: unknown) {
  if (!state || typeof state !== 'object' || !('catalogReturnTo' in state)) return '/universities'
  const candidate = (state as { catalogReturnTo?: unknown }).catalogReturnTo
  return typeof candidate === 'string'
    && (candidate === '/universities' || candidate.startsWith('/universities?'))
    ? candidate
    : '/universities'
}

function ExternalResourceLink({ href, label }: { href: string; label: string }) {
  return <a
    aria-label={`${label} (откроется в новой вкладке)`}
    className="inline-flex items-center gap-1.5 rounded-sm font-bold text-moss underline decoration-moss/30 underline-offset-4 hover:decoration-moss"
    href={href}
    rel="noreferrer"
    target="_blank"
  >{label}<ExternalLink aria-hidden="true" size={16} /></a>
}

function OfferingCard({ offering }: { offering: OfferingSummary }) {
  const checkedAt = formatCatalogDate(offering.source_checked_at)
  return <section className="min-w-0 rounded-2xl border border-ink/10 bg-cream/65 p-4" aria-labelledby={`offering-${offering.id}`}>
    <h4 className="break-words font-extrabold" id={`offering-${offering.id}`}>
      {offering.admission_year} · {apiValueLabel(offering.study_form)} · {apiValueLabel(offering.funding_type)}
    </h4>
    <dl className="mt-3 grid gap-2 text-sm text-ink/70 sm:grid-cols-2">
      {offering.places !== null && <div><dt className="font-semibold text-ink/50">План приёма</dt><dd>{offering.places} мест</dd></div>}
      <div><dt className="font-semibold text-ink/50">Статус платформы</dt><dd>{apiValueLabel(offering.monitoring_status)}</dd></div>
      {checkedAt && <div><dt className="font-semibold text-ink/50">Источник проверен</dt><dd>{checkedAt}</dd></div>}
    </dl>
    <div className="mt-4">
      <ExternalResourceLink href={offering.official_url} label={`Официальная страница набора ${offering.admission_year}`} />
    </div>
  </section>
}

function ProgramCard({
  program,
  offerings,
  universitySlug,
  universityReturnTo,
}: {
  program: ImportedProgram
  offerings: OfferingSummary[]
  universitySlug: string
  universityReturnTo: string
}) {
  const checkedAt = formatCatalogDate(program.verified_at ?? program.source_checked_at)
  const programSlug = program.slug.trim()
  return <article className="panel min-w-0 p-5 sm:p-6" aria-labelledby={`program-${program.id}`}>
    <div className="flex min-w-0 flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
      <div className="min-w-0">
        {program.code && <div className="eyebrow">{program.code}</div>}
        <h3 className="mt-2 break-words text-xl font-extrabold" id={`program-${program.id}`}>
          {programSlug
            ? <Link
              className="rounded-sm text-moss underline decoration-moss/25 underline-offset-4 hover:decoration-moss"
              state={{ universityReturnTo }}
              to={`/universities/${encodeURIComponent(universitySlug)}/programs/${encodeURIComponent(programSlug)}`}
            >{program.name}</Link>
            : program.name}
        </h3>
      </div>
      <ExternalResourceLink href={program.official_url} label={`Официальная страница программы «${program.name}»`} />
    </div>
    <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-3">
      {program.qualification && <div><dt className="font-semibold text-ink/50">Квалификация</dt><dd className="mt-1 break-words">{program.qualification}</dd></div>}
      {program.faculty_name && <div><dt className="font-semibold text-ink/50">Подразделение</dt><dd className="mt-1 break-words">{program.faculty_name}</dd></div>}
      {program.education_level && <div><dt className="font-semibold text-ink/50">Уровень образования</dt><dd className="mt-1">{program.education_level}</dd></div>}
      {program.duration_years !== null && <div><dt className="font-semibold text-ink/50">Продолжительность</dt><dd className="mt-1">{program.duration_years} года</dd></div>}
      {checkedAt && <div><dt className="font-semibold text-ink/50">Данные проверены</dt><dd className="mt-1">{checkedAt}</dd></div>}
    </dl>
    {offerings.length > 0
      ? <div className="mt-5 grid gap-3"><h4 className="text-lg font-extrabold">Импортированные наборы</h4>{offerings.map((offering) => <OfferingCard key={offering.id} offering={offering} />)}</div>
      : <p className="mt-5 rounded-2xl bg-cream p-4 font-semibold text-ink/70">Наборы для этой программы ещё не импортированы платформой.</p>}
  </article>
}

function ProgramDiscoveryPanel({
  options,
  query,
  resultSummary,
  hasResults,
  onChange,
  onReset,
}: {
  options: ProgramDiscoveryOptions
  query: ProgramDiscoveryQuery
  resultSummary: string
  hasResults: boolean
  onChange: (patch: Partial<ProgramDiscoveryQuery>, replace?: boolean) => void
  onReset: () => void
}) {
  const active = hasProgramDiscoveryFilters(query)
  const selectClassName = 'mt-2 min-h-11 w-full min-w-0 rounded-xl border border-ink/15 bg-white px-3 py-2.5 text-ink'
  return <section aria-labelledby="program-discovery-title" className="panel mt-5 min-w-0 p-5 sm:p-6">
    <div className="flex min-w-0 flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
      <div className="min-w-0">
        <h3 className="text-xl font-extrabold" id="program-discovery-title">Найти программу</h3>
        <p className="mt-1 text-sm leading-6 text-ink/65">Поиск работает по названию и коду специальности; фильтры применяются к вариантам обучения.</p>
      </div>
      {hasResults && <button
        className="min-h-11 shrink-0 rounded-xl border border-moss/25 bg-white px-4 py-2.5 font-bold text-moss disabled:cursor-not-allowed disabled:opacity-45"
        disabled={!active}
        onClick={onReset}
        type="button"
      >Сбросить фильтры</button>}
    </div>
    <div className="mt-5 grid min-w-0 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <label className="min-w-0 text-sm font-bold" htmlFor="program-query">
        Название или код
        <input
          aria-controls="program-results"
          className={selectClassName}
          id="program-query"
          onChange={(event) => onChange({ program_query: event.target.value }, true)}
          placeholder="Например, экономика"
          type="search"
          value={query.program_query}
        />
      </label>
      <label className="min-w-0 text-sm font-bold" htmlFor="program-study-form">
        Форма обучения
        <select aria-controls="program-results" className={selectClassName} id="program-study-form" onChange={(event) => onChange({ study_form: event.target.value || undefined })} value={query.study_form ?? ''}>
          <option value="">Все</option>
          {options.studyForms.map((value) => <option key={value} value={value}>{apiValueLabel(value)}</option>)}
        </select>
      </label>
      <label className="min-w-0 text-sm font-bold" htmlFor="program-funding-type">
        Финансирование
        <select aria-controls="program-results" className={selectClassName} id="program-funding-type" onChange={(event) => onChange({ funding_type: event.target.value || undefined })} value={query.funding_type ?? ''}>
          <option value="">Все</option>
          {options.fundingTypes.map((value) => <option key={value} value={value}>{apiValueLabel(value)}</option>)}
        </select>
      </label>
      <label className="min-w-0 text-sm font-bold" htmlFor="program-monitoring-status">
        Статус мониторинга
        <select aria-controls="program-results" className={selectClassName} id="program-monitoring-status" onChange={(event) => onChange({ monitoring_status: event.target.value || undefined })} value={query.monitoring_status ?? ''}>
          <option value="">Все</option>
          {options.monitoringStatuses.map((value) => <option key={value} value={value}>{apiValueLabel(value)}</option>)}
        </select>
      </label>
    </div>
    <p aria-live="polite" className="mt-5 break-words font-bold text-ink/70">{resultSummary}</p>
  </section>
}

function LoadingState({ returnTo }: { returnTo: string }) {
  return <div className="mx-auto max-w-7xl px-5 py-10 lg:px-8 lg:py-14">
    <Link className="inline-flex items-center gap-2 rounded-xl font-bold text-moss" to={returnTo}><ArrowLeft aria-hidden="true" size={18} />Назад к каталогу</Link>
    <div aria-labelledby="detail-loading-title" aria-live="polite" className="panel mt-6 p-7" role="status">
      <h1 className="text-2xl font-extrabold" id="detail-loading-title">Загружаем страницу вуза…</h1>
      <p className="mt-2 text-ink/65">Получаем сохранённые сведения и покрытие платформы.</p>
    </div>
  </div>
}

export function UniversityDetailPage() {
  const { slug = '' } = useParams()
  const location = useLocation()
  const [searchParams, setSearchParams] = useSearchParams()
  const searchKey = searchParams.toString()
  const returnTo = useMemo(() => catalogReturnDestination(location.state), [location.state])
  const [retry, setRetry] = useState(0)
  const [request, setRequest] = useState<DetailState>({ slug: null, data: null, status: 'loading' })
  const current = request.slug === slug ? request : { slug, data: null, status: 'loading' as const }
  const programs = current.data?.programs ?? EMPTY_PROGRAMS
  const discoveryOptions = useMemo(() => deriveProgramDiscoveryOptions(programs), [programs])
  const discoveryQuery = useMemo(
    () => parseProgramDiscoveryQuery(new URLSearchParams(searchKey), discoveryOptions),
    [discoveryOptions, searchKey],
  )
  const discoveryResult = useMemo(
    () => filterProgramsForDiscovery(programs, discoveryQuery),
    [discoveryQuery, programs],
  )

  useDocumentTitle(current.data ? `${current.data.short_name} · Куда поступать` : 'Вуз · Куда поступать')

  useEffect(() => {
    const controller = new AbortController()
    api.university(slug, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setRequest({ slug, data, status: 'success' })
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        setRequest({
          slug,
          data: null,
          status: error instanceof ApiError && error.status === 404 ? 'not_found' : 'error',
        })
      })
    return () => controller.abort()
  }, [retry, slug])

  useEffect(() => {
    if (current.status !== 'success' || !current.data) return
    const canonical = serializeProgramDiscoveryQuery(
      discoveryQuery,
      new URLSearchParams(searchKey),
    ).toString()
    if (canonical !== searchKey) setSearchParams(canonical, { replace: true })
  }, [current.data, current.status, discoveryQuery, searchKey, setSearchParams])

  if (current.status === 'loading') return <LoadingState returnTo={returnTo} />

  if (current.status === 'not_found') return <div className="mx-auto max-w-4xl px-5 py-10 lg:px-8 lg:py-14">
    <Link className="inline-flex items-center gap-2 rounded-xl font-bold text-moss" to={returnTo}><ArrowLeft aria-hidden="true" size={18} />Назад к каталогу</Link>
    <section aria-labelledby="university-not-found-title" className="panel mt-6 p-7" role="status">
      <h1 className="text-3xl font-extrabold" id="university-not-found-title">Университет не найден</h1>
      <p className="mt-3 text-ink/65">Проверьте адрес или вернитесь к подтверждённому каталогу вузов.</p>
    </section>
  </div>

  if (current.status === 'error') return <div className="mx-auto max-w-4xl px-5 py-10 lg:px-8 lg:py-14">
    <Link className="inline-flex items-center gap-2 rounded-xl font-bold text-moss" to={returnTo}><ArrowLeft aria-hidden="true" size={18} />Назад к каталогу</Link>
    <section aria-labelledby="university-error-title" className="panel mt-6 border-red-200 p-7" role="alert">
      <h1 className="text-3xl font-extrabold" id="university-error-title">Не удалось загрузить страницу вуза</h1>
      <p className="mt-3 text-ink/65">Сервис временно недоступен. Попробуйте повторить запрос.</p>
      <button className="mt-5 inline-flex items-center gap-2 rounded-xl bg-moss px-4 py-2.5 font-bold text-white" onClick={() => {
        setRequest({ slug, data: null, status: 'loading' })
        setRetry((value) => value + 1)
      }} type="button"><RefreshCw aria-hidden="true" size={17} />Повторить запрос</button>
    </section>
  </div>

  const university = current.data
  if (!university) return <LoadingState returnTo={returnTo} />
  const verifiedAt = formatCatalogDate(university.data_verified_at)
  const sourceCheckedAt = formatCatalogDate(university.source_checked_at)
  const universityReturnTo = `${location.pathname}${location.search}`
  const hasLiveMonitoring = university.slug === 'bseu'
    && university.coverage.online_monitoring === 'available'
  const updateDiscoveryQuery = (patch: Partial<ProgramDiscoveryQuery>, replace = false) => {
    setSearchParams(
      serializeProgramDiscoveryQuery(
        { ...discoveryQuery, ...patch },
        new URLSearchParams(searchKey),
      ),
      { replace },
    )
  }
  const resetDiscoveryQuery = () => {
    setSearchParams(
      serializeProgramDiscoveryQuery(
        DEFAULT_PROGRAM_DISCOVERY_QUERY,
        new URLSearchParams(searchKey),
      ),
    )
  }

  return <div className="min-w-0 bg-[linear-gradient(180deg,#f8f7f1_0%,#f2f0e7_100%)]">
    <div className="mx-auto max-w-7xl px-5 py-10 lg:px-8 lg:py-14">
      <Link className="inline-flex items-center gap-2 rounded-xl font-bold text-moss" to={returnTo}><ArrowLeft aria-hidden="true" size={18} />Назад к каталогу</Link>

      <header className="mt-7 max-w-4xl">
        <div className="eyebrow">{university.short_name}</div>
        <h1 className="mt-3 break-words text-4xl font-extrabold leading-tight tracking-tight sm:text-5xl">{university.full_name}</h1>
        {university.description && <p className="mt-5 break-words text-lg leading-8 text-ink/70">{university.description}</p>}
        <div className="mt-5">
          <div className="flex flex-wrap items-center gap-4">
            <Link className="inline-flex min-h-11 items-center rounded-xl border border-moss/25 bg-white px-4 py-2.5 font-bold text-moss" to={`/compare?universities=${encodeURIComponent(university.slug)}`}>Сравнить вуз</Link>
            <SaveControl kind="university" label={university.full_name} universitySlug={university.slug} />
          </div>
        </div>
      </header>

      <div className="mt-8 grid min-w-0 gap-5 lg:grid-cols-2">
        <section aria-labelledby="identity-title" className="panel min-w-0 p-5 sm:p-6">
          <h2 className="text-2xl font-extrabold" id="identity-title">О вузе</h2>
          <dl className="mt-5 grid gap-4 text-sm sm:grid-cols-2">
            {(university.city || university.region) && <div><dt className="flex items-center gap-2 font-semibold text-ink/50"><MapPin aria-hidden="true" size={16} />Местоположение</dt><dd className="mt-1 break-words">{[university.city, university.region].filter(Boolean).join(' · ')}</dd></div>}
            <div><dt className="flex items-center gap-2 font-semibold text-ink/50"><Building2 aria-hidden="true" size={16} />Тип учреждения</dt><dd className="mt-1">{apiValueLabel(university.institution_kind)}</dd></div>
            <div><dt className="font-semibold text-ink/50">Форма собственности</dt><dd className="mt-1">{apiValueLabel(university.ownership_type)}</dd></div>
          </dl>
          {university.categories.length > 0 && <div className="mt-5 flex flex-wrap gap-2">{university.categories.map((category) => <span className="rounded-full border border-moss/15 bg-mint px-3 py-1.5 text-sm font-semibold text-moss" key={category.code}>{category.label_ru}</span>)}</div>}
        </section>

        <section aria-labelledby="resources-title" className="panel min-w-0 p-5 sm:p-6">
          <h2 className="text-2xl font-extrabold" id="resources-title">Официальные ресурсы</h2>
          <div className="mt-5 grid gap-4">
            <ExternalResourceLink href={university.official_site_url} label={`Официальный сайт — ${university.short_name}`} />
            {university.admissions_url
              ? <ExternalResourceLink href={university.admissions_url} label={`Страница для абитуриентов — ${university.short_name}`} />
              : <p className="font-semibold text-ink/70">Ссылка для абитуриентов пока не добавлена</p>}
          </div>
        </section>
      </div>

      <section aria-labelledby="coverage-title" className="panel mt-5 min-w-0 p-5 sm:p-6">
        <h2 className="text-2xl font-extrabold" id="coverage-title">Мониторинг и покрытие источников</h2>
        <dl className="mt-5 grid gap-4 text-sm sm:grid-cols-2 lg:grid-cols-4">
          <div><dt className="font-semibold text-ink/50">Статус мониторинга</dt><dd className="mt-1">{apiValueLabel(university.monitoring_status)}</dd></div>
          <div><dt className="font-semibold text-ink/50">Live-покрытие платформы</dt><dd className="mt-1">{hasLiveMonitoring ? 'Доступно' : 'Пока не реализовано'}</dd></div>
          {verifiedAt && <div><dt className="font-semibold text-ink/50">Данные вуза проверены</dt><dd className="mt-1">{verifiedAt}</dd></div>}
          {sourceCheckedAt && <div><dt className="font-semibold text-ink/50">Основной источник проверен</dt><dd className="mt-1">{sourceCheckedAt}</dd></div>}
          <div><dt className="font-semibold text-ink/50">Покрытие программ</dt><dd className="mt-1">{university.programs.length > 0 ? `Импортировано программ: ${university.programs.length}` : 'Каталог программ ещё не импортирован'}</dd></div>
        </dl>
        {hasLiveMonitoring && <Link className="mt-5 inline-flex items-center gap-2 rounded-xl bg-moss px-4 py-2.5 font-bold text-white" to="/monitor"><RadioTower aria-hidden="true" size={18} />Live-мониторинг БГЭУ</Link>}
        {university.sources.length > 0 && <div className="mt-6 border-t border-ink/10 pt-5">
          <h3 className="text-lg font-extrabold">Сохранённые источники</h3>
          <ul className="mt-3 grid gap-3 sm:grid-cols-2">
            {university.sources.map((source) => <li className="min-w-0 rounded-2xl bg-cream/65 p-4" key={`${source.source_type}:${source.source_url}`}>
              <ExternalResourceLink href={source.source_url} label={sourceTypeLabel(source.source_type)} />
              {formatCatalogDate(source.checked_at) && <p className="mt-2 flex items-center gap-2 text-sm text-ink/60"><CalendarDays aria-hidden="true" size={15} />Проверено: {formatCatalogDate(source.checked_at)}</p>}
            </li>)}
          </ul>
        </div>}
      </section>

      <section aria-labelledby="programs-title" className="mt-10 min-w-0">
        <h2 className="text-3xl font-extrabold" id="programs-title">Импортированные программы</h2>
        <p className="mt-3 max-w-3xl leading-7 text-ink/65">Здесь показаны только программы и наборы, уже импортированные этой платформой из сохранённых официальных источников.</p>
        {university.programs.length > 0
          ? <>
            <ProgramDiscoveryPanel
              hasResults={discoveryResult.shownPrograms > 0}
              onChange={updateDiscoveryQuery}
              onReset={resetDiscoveryQuery}
              options={discoveryOptions}
              query={discoveryQuery}
              resultSummary={formatProgramDiscoverySummary(discoveryResult)}
            />
            {discoveryResult.shownPrograms > 0
              ? <div className="mt-5 grid min-w-0 gap-5" id="program-results">{discoveryResult.items.map(({ program, offerings }) => <ProgramCard key={program.id} offerings={offerings} program={program} universitySlug={university.slug} universityReturnTo={universityReturnTo} />)}</div>
              : <div className="panel mt-5 p-6" id="program-results" role="status">
                <p className="font-bold">По выбранным условиям импортированные программы не найдены</p>
                <p className="mt-2 text-ink/65">В каталоге вуза есть программы, но ни одна из них не соответствует текущему поиску и фильтрам.</p>
                <button className="mt-5 min-h-11 rounded-xl bg-moss px-4 py-2.5 font-bold text-white" onClick={resetDiscoveryQuery} type="button">Сбросить фильтры</button>
              </div>}
          </>
          : <div className="panel mt-5 p-6"><p className="font-bold">Каталог программ ещё не импортирован</p><p className="mt-2 text-ink/65">Это не означает, что у университета нет реальных программ.</p></div>}
      </section>
    </div>
  </div>
}
