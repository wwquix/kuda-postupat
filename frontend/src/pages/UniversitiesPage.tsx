import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  ChevronDown,
  ExternalLink,
  Filter,
  RadioTower,
  RefreshCw,
  Search,
  SlidersHorizontal,
  X,
} from 'lucide-react'
import { type FormEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useLocation, useSearchParams } from 'react-router-dom'

import { api } from '../api'
import { apiValueLabel } from '../catalogPresentation'
import type { CatalogMeta, UniversityListItem, UniversityListResponse } from '../types'
import {
  buildUniversityApiParams,
  clearUniversityCatalogFilters,
  compactPageNumbers,
  hasUniversityCatalogFilters,
  parseUniversityCatalogQuery,
  serializeUniversityCatalogQuery,
  type SortOrder,
  type UniversityCatalogQuery,
  type UniversitySort,
  universityCatalogQueriesEqual,
  validateUniversityCatalogQuery,
} from '../universityCatalogQuery'
import { useDocumentTitle } from '../useDocumentTitle'

const SEARCH_DELAY_MS = 300

const booleanValue = (value: string) => {
  if (value === 'true') return true
  if (value === 'false') return false
  return undefined
}

function SearchControl({ value, onCommit }: { value: string; onCommit: (value: string) => void }) {
  const [draft, setDraft] = useState(value)
  const timer = useRef<number | null>(null)

  const cancelTimer = () => {
    if (timer.current !== null) window.clearTimeout(timer.current)
    timer.current = null
  }

  useEffect(() => () => cancelTimer(), [])

  const commit = (nextValue: string) => {
    cancelTimer()
    onCommit(nextValue.trim())
  }

  return <form
    aria-label="Поиск вузов"
    className="flex min-w-0 flex-1 items-center gap-2 rounded-2xl border border-ink/15 bg-white p-2 shadow-sm focus-within:border-moss/40"
    onSubmit={(event: FormEvent) => {
      event.preventDefault()
      commit(draft)
    }}
    role="search"
  >
    <Search aria-hidden="true" className="ml-2 shrink-0 text-moss" size={20} />
    <label className="sr-only" htmlFor="university-search">Поиск по названию, городу или категории</label>
    <input
      autoComplete="off"
      className="min-w-0 flex-1 bg-transparent px-1 py-2 text-base outline-none placeholder:text-ink/45"
      id="university-search"
      maxLength={200}
      onChange={(event) => {
        const nextValue = event.target.value
        setDraft(nextValue)
        cancelTimer()
        timer.current = window.setTimeout(() => commit(nextValue), SEARCH_DELAY_MS)
      }}
      placeholder="Название, город, категория…"
      type="search"
      value={draft}
    />
    {draft && <button
      aria-label="Очистить поиск"
      className="rounded-xl p-2 text-ink/55 transition hover:bg-ink/5 hover:text-ink"
      onClick={() => {
        setDraft('')
        commit('')
      }}
      type="button"
    ><X aria-hidden="true" size={18} /></button>}
  </form>
}

interface FilterSelectProps {
  id: string
  label: string
  value: string
  onChange: (value: string) => void
  children: React.ReactNode
}

function FilterSelect({ id, label, value, onChange, children }: FilterSelectProps) {
  return <label className="grid gap-2 text-sm font-semibold text-ink/75" htmlFor={id}>
    {label}
    <span className="relative">
      <select
        className="w-full appearance-none rounded-xl border border-ink/15 bg-white px-3 py-2.5 pr-9 font-normal text-ink"
        id={id}
        onChange={(event) => onChange(event.target.value)}
        value={value}
      >{children}</select>
      <ChevronDown aria-hidden="true" className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-ink/45" size={16} />
    </span>
  </label>
}

function UniversityFilters({
  meta,
  query,
  onChange,
}: {
  meta: CatalogMeta
  query: UniversityCatalogQuery
  onChange: (patch: Partial<UniversityCatalogQuery>) => void
}) {
  const [open, setOpen] = useState(() => (
    typeof window.matchMedia !== 'function' || window.matchMedia('(min-width: 1024px)').matches
  ))

  useEffect(() => {
    if (typeof window.matchMedia !== 'function') return undefined
    const media = window.matchMedia('(min-width: 1024px)')
    const handleChange = (event: MediaQueryListEvent) => setOpen(event.matches)
    media.addEventListener('change', handleChange)
    return () => media.removeEventListener('change', handleChange)
  }, [])

  const booleanSelect = (
    id: string,
    label: string,
    value: boolean | undefined,
    key: 'has_admissions_url' | 'has_programs' | 'online_monitoring',
    positive: string,
    negative: string,
  ) => <FilterSelect id={id} label={label} onChange={(next) => onChange({ [key]: booleanValue(next) })} value={value === undefined ? '' : String(value)}>
    <option value="">Не важно</option>
    <option value="true">{positive}</option>
    <option value="false">{negative}</option>
  </FilterSelect>

  return <details
    className="group panel p-4 sm:p-5"
    onToggle={(event) => setOpen(event.currentTarget.open)}
    open={open}
  >
    <summary className="flex cursor-pointer list-none items-center justify-between gap-3 rounded-xl font-bold lg:hidden">
      <span className="flex items-center gap-2"><Filter aria-hidden="true" size={18} />Фильтры</span>
      <ChevronDown aria-hidden="true" className="transition group-open:rotate-180" size={18} />
    </summary>
    <div className="mt-5 hidden gap-4 group-open:grid sm:grid-cols-2 lg:!mt-0 lg:!grid lg:grid-cols-3 xl:grid-cols-4">
      <FilterSelect id="filter-city" label="Город" onChange={(city) => onChange({ city: city || undefined })} value={query.city ?? ''}>
        <option value="">Все города</option>
        {meta.cities.map((city) => <option key={city} value={city}>{city}</option>)}
      </FilterSelect>
      <FilterSelect id="filter-region" label="Регион" onChange={(region) => onChange({ region: region || undefined })} value={query.region ?? ''}>
        <option value="">Все регионы</option>
        {meta.regions.map((region) => <option key={region} value={region}>{region}</option>)}
      </FilterSelect>
      <FilterSelect id="filter-ownership" label="Форма собственности" onChange={(ownership_type) => onChange({ ownership_type: ownership_type || undefined })} value={query.ownership_type ?? ''}>
        <option value="">Любая</option>
        {meta.ownership_types.map((value) => <option key={value} value={value}>{apiValueLabel(value)}</option>)}
      </FilterSelect>
      <FilterSelect id="filter-kind" label="Тип учреждения" onChange={(institution_kind) => onChange({ institution_kind: institution_kind || undefined })} value={query.institution_kind ?? ''}>
        <option value="">Любой</option>
        {meta.institution_kinds.map((value) => <option key={value} value={value}>{apiValueLabel(value)}</option>)}
      </FilterSelect>
      <FilterSelect id="filter-category" label="Категория" onChange={(category) => onChange({ category: category || undefined })} value={query.category ?? ''}>
        <option value="">Все категории</option>
        {meta.categories.map((category) => <option key={category.code} value={category.code}>{category.label_ru}</option>)}
      </FilterSelect>
      <FilterSelect id="filter-monitoring" label="Статус мониторинга платформы" onChange={(monitoring_status) => onChange({ monitoring_status: monitoring_status || undefined })} value={query.monitoring_status ?? ''}>
        <option value="">Любой статус</option>
        {meta.monitoring_statuses.map((value) => <option key={value} value={value}>{apiValueLabel(value)}</option>)}
      </FilterSelect>
      {booleanSelect('filter-admissions', 'Ссылка для абитуриентов', query.has_admissions_url, 'has_admissions_url', 'Добавлена', 'Пока не добавлена')}
      {booleanSelect('filter-programs', 'Покрытие программ', query.has_programs, 'has_programs', 'Программы импортированы', 'Ещё не импортированы')}
      {booleanSelect('filter-online', 'Live-мониторинг', query.online_monitoring, 'online_monitoring', 'Доступен на платформе', 'Не реализован на платформе')}
    </div>
  </details>
}

function UniversityCard({ university, returnTo }: { university: UniversityListItem; returnTo: string }) {
  const hasLiveMonitoring = university.slug === 'bseu'
    && university.coverage.online_monitoring === 'available'

  const monitoringLabel = university.monitoring_status === 'online' && !hasLiveMonitoring
    ? 'Статус требует проверки'
    : apiValueLabel(university.monitoring_status)

  return <article className="panel flex min-w-0 flex-col gap-5 p-5 sm:p-6">
    <div className="flex min-w-0 flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
      <div className="min-w-0">
        <div className="eyebrow">{university.short_name}</div>
        <h2 className="mt-2 break-words text-xl font-extrabold leading-snug">
          <Link
            className="inline-block rounded-sm text-ink underline decoration-moss/35 decoration-2 underline-offset-4 hover:decoration-moss"
            state={{ catalogReturnTo: returnTo }}
            to={`/universities/${encodeURIComponent(university.slug)}`}
          >{university.full_name}</Link>
        </h2>
        <p className="mt-2 text-sm text-ink/60">
          {[university.city, university.region].filter(Boolean).join(' · ') || 'Местоположение уточняется'}
        </p>
      </div>
      <span className="w-fit shrink-0 rounded-full border border-ink/10 bg-cream px-3 py-1.5 text-xs font-bold text-ink/70">
        {monitoringLabel}
      </span>
    </div>

    <div className="flex flex-wrap gap-2 text-xs font-semibold text-ink/70">
      <span className="rounded-full bg-mint px-3 py-1.5">{apiValueLabel(university.ownership_type)}</span>
      <span className="rounded-full bg-mint px-3 py-1.5">{apiValueLabel(university.institution_kind)}</span>
      {university.categories.map((category) => <span className="rounded-full border border-moss/15 px-3 py-1.5" key={category.code}>{category.label_ru}</span>)}
    </div>

    <div className="grid gap-3 sm:grid-cols-2">
      <div className="rounded-2xl border border-ink/10 bg-cream/60 p-4">
        <div className="text-xs font-bold uppercase tracking-wider text-ink/45">Покрытие платформы</div>
        {university.program_count > 0
          ? <p className="mt-2 font-semibold">Импортировано программ: {university.program_count}</p>
          : <p className="mt-2 font-semibold">Каталог программ ещё не импортирован</p>}
      </div>
      <div className="rounded-2xl border border-ink/10 bg-cream/60 p-4">
        <div className="text-xs font-bold uppercase tracking-wider text-ink/45">Для абитуриентов</div>
        {university.admissions_url
          ? <a
            aria-label={`Официальная страница для абитуриентов — ${university.short_name} (откроется в новой вкладке)`}
            className="mt-2 inline-flex items-center gap-1.5 font-semibold text-moss hover:underline"
            href={university.admissions_url}
            rel="noreferrer"
            target="_blank"
          >Официальная страница <ExternalLink aria-hidden="true" size={15} /></a>
          : <p className="mt-2 font-semibold">Ссылка для абитуриентов пока не добавлена</p>}
      </div>
    </div>

    <div className="mt-auto flex flex-wrap items-center gap-4 border-t border-ink/10 pt-4 text-sm">
      <a
        aria-label={`Официальный сайт — ${university.short_name} (откроется в новой вкладке)`}
        className="inline-flex items-center gap-1.5 font-semibold text-moss hover:underline"
        href={university.official_site_url}
        rel="noreferrer"
        target="_blank"
      >Официальный сайт <ExternalLink aria-hidden="true" size={15} /></a>
      {hasLiveMonitoring && <Link className="inline-flex items-center gap-1.5 font-semibold text-moss hover:underline" to="/monitor">
        <RadioTower aria-hidden="true" size={16} />Live-мониторинг БГЭУ
      </Link>}
    </div>
  </article>
}

function CatalogPagination({
  response,
  onPage,
}: {
  response: UniversityListResponse
  onPage: (page: number) => void
}) {
  const { pagination } = response
  if (pagination.total_pages <= 1) return null

  return <nav aria-label="Страницы каталога" className="mt-8 flex flex-wrap items-center justify-center gap-2">
    <button
      className="inline-flex items-center gap-1 rounded-xl border border-ink/15 bg-white px-3 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-45"
      disabled={!pagination.has_previous}
      onClick={() => onPage(pagination.page - 1)}
      type="button"
    ><ArrowLeft aria-hidden="true" size={16} />Назад</button>
    {compactPageNumbers(pagination.page, pagination.total_pages).map((page) => typeof page === 'number'
      ? <button
        aria-current={page === pagination.page ? 'page' : undefined}
        aria-label={`Страница ${page}`}
        className={`min-w-10 rounded-xl border px-3 py-2 text-sm font-bold ${page === pagination.page ? 'border-moss bg-moss text-white' : 'border-ink/15 bg-white text-ink'}`}
        key={page}
        onClick={() => onPage(page)}
        type="button"
      >{page}</button>
      : <span aria-hidden="true" className="px-1 text-ink/45" key={page}>…</span>)}
    <button
      className="inline-flex items-center gap-1 rounded-xl border border-ink/15 bg-white px-3 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-45"
      disabled={!pagination.has_next}
      onClick={() => onPage(pagination.page + 1)}
      type="button"
    >Вперёд<ArrowRight aria-hidden="true" size={16} /></button>
  </nav>
}

function LoadingCards() {
  return <div aria-live="polite" className="grid gap-5 lg:grid-cols-2" role="status">
    <span className="sr-only">Загружаем каталог вузов…</span>
    {[1, 2, 3, 4].map((item) => <div aria-hidden="true" className="panel min-h-72 animate-pulse bg-white/70 p-6" key={item}>
      <div className="h-3 w-20 rounded bg-ink/10" />
      <div className="mt-4 h-7 w-4/5 rounded bg-ink/10" />
      <div className="mt-3 h-4 w-2/5 rounded bg-ink/10" />
      <div className="mt-8 h-24 rounded-2xl bg-ink/5" />
    </div>)}
  </div>
}

export function UniversitiesPage() {
  const location = useLocation()
  const [searchParams, setSearchParams] = useSearchParams()
  const searchKey = searchParams.toString()
  const query = useMemo(() => parseUniversityCatalogQuery(new URLSearchParams(searchKey)), [searchKey])
  const [meta, setMeta] = useState<CatalogMeta | null>(null)
  const [metaLoading, setMetaLoading] = useState(true)
  const [metaError, setMetaError] = useState(false)
  const [metaRetry, setMetaRetry] = useState(0)
  const [results, setResults] = useState<{
    data: UniversityListResponse | null
    loading: boolean
    error: boolean
  }>({ data: null, loading: true, error: false })
  const [resultsRetry, setResultsRetry] = useState(0)

  useDocumentTitle('Вузы Беларуси · Куда поступать')

  useEffect(() => {
    const controller = new AbortController()
    api.catalogMeta(controller.signal)
      .then((response) => {
        if (controller.signal.aborted) return
        setMeta(response)
        setMetaError(false)
        setMetaLoading(false)
      })
      .catch(() => {
        if (controller.signal.aborted) return
        setMeta(null)
        setMetaError(true)
        setMetaLoading(false)
      })
    return () => controller.abort()
  }, [metaRetry])

  const validatedQuery = useMemo(
    () => meta ? validateUniversityCatalogQuery(query, meta) : query,
    [meta, query],
  )
  const canonicalSearch = useMemo(
    () => serializeUniversityCatalogQuery(validatedQuery).toString(),
    [validatedQuery],
  )
  const queryIsReady = Boolean(
    meta
    && universityCatalogQueriesEqual(query, validatedQuery)
    && searchKey === canonicalSearch
  )

  useEffect(() => {
    if (!meta || searchKey === canonicalSearch) return
    setSearchParams(new URLSearchParams(canonicalSearch), { replace: true })
  }, [canonicalSearch, meta, searchKey, setSearchParams])

  useEffect(() => {
    if (!meta || !queryIsReady) return undefined
    const controller = new AbortController()
    const pageSize = Math.max(1, Math.min(meta.pagination.default_page_size, meta.pagination.maximum_page_size))

    const load = async () => {
      await Promise.resolve()
      if (controller.signal.aborted) return
      setResults((current) => ({ ...current, loading: true, error: false }))
      try {
        const response = await api.universities(buildUniversityApiParams(query, pageSize), controller.signal)
        if (controller.signal.aborted) return
        if (response.pagination.total_items > 0 && query.page > response.pagination.total_pages) {
          setSearchParams(serializeUniversityCatalogQuery({
            ...query,
            page: Math.max(1, response.pagination.total_pages),
          }), { replace: true })
          return
        }
        setResults({ data: response, loading: false, error: false })
      } catch {
        if (controller.signal.aborted) return
        setResults((current) => ({ ...current, loading: false, error: true }))
      }
    }

    void load()
    return () => controller.abort()
  }, [meta, query, queryIsReady, resultsRetry, setSearchParams])

  const beginParameterChange = useCallback(() => {
    setResults((current) => ({ ...current, loading: true, error: false }))
  }, [])

  const updateQuery = useCallback((
    patch: Partial<UniversityCatalogQuery>,
    options: { resetPage?: boolean; replace?: boolean } = {},
  ) => {
    const next = {
      ...query,
      ...patch,
      page: options.resetPage === false ? (patch.page ?? query.page) : 1,
    }
    if (universityCatalogQueriesEqual(query, next)) return
    beginParameterChange()
    setSearchParams(serializeUniversityCatalogQuery(next), { replace: options.replace })
  }, [beginParameterChange, query, setSearchParams])

  const clearFilters = useCallback(() => {
    const next = clearUniversityCatalogFilters(query)
    if (universityCatalogQueriesEqual(query, next)) return
    beginParameterChange()
    setSearchParams(serializeUniversityCatalogQuery(next))
  }, [beginParameterChange, query, setSearchParams])

  const activeFilters = useMemo(() => {
    if (!meta) return []
    const items: Array<{ key: string; text: string; patch: Partial<UniversityCatalogQuery> }> = []
    if (query.q) items.push({ key: 'q', text: `Поиск: ${query.q}`, patch: { q: '' } })
    if (query.city) items.push({ key: 'city', text: `Город: ${query.city}`, patch: { city: undefined } })
    if (query.region) items.push({ key: 'region', text: `Регион: ${query.region}`, patch: { region: undefined } })
    if (query.ownership_type) items.push({ key: 'ownership', text: `Собственность: ${apiValueLabel(query.ownership_type)}`, patch: { ownership_type: undefined } })
    if (query.institution_kind) items.push({ key: 'kind', text: `Тип: ${apiValueLabel(query.institution_kind)}`, patch: { institution_kind: undefined } })
    if (query.category) items.push({
      key: 'category',
      text: `Категория: ${meta.categories.find((item) => item.code === query.category)?.label_ru ?? query.category}`,
      patch: { category: undefined },
    })
    if (query.monitoring_status) items.push({ key: 'monitoring', text: `Мониторинг: ${apiValueLabel(query.monitoring_status)}`, patch: { monitoring_status: undefined } })
    if (query.has_admissions_url !== undefined) items.push({ key: 'admissions', text: query.has_admissions_url ? 'Есть ссылка для абитуриентов' : 'Ссылка пока не добавлена', patch: { has_admissions_url: undefined } })
    if (query.has_programs !== undefined) items.push({ key: 'programs', text: query.has_programs ? 'Программы импортированы' : 'Программы ещё не импортированы', patch: { has_programs: undefined } })
    if (query.online_monitoring !== undefined) items.push({ key: 'online', text: query.online_monitoring ? 'Live-мониторинг доступен' : 'Live-мониторинг не реализован', patch: { online_monitoring: undefined } })
    return items
  }, [meta, query])

  return <div className="min-w-0 bg-[linear-gradient(180deg,#f8f7f1_0%,#f2f0e7_100%)]">
    <div className="mx-auto max-w-7xl px-5 py-10 lg:px-8 lg:py-14">
      <header className="max-w-3xl">
        <div className="eyebrow">Каталог платформы</div>
        <h1 className="mt-3 text-4xl font-extrabold leading-tight tracking-tight sm:text-5xl">Вузы Беларуси</h1>
        <p className="mt-4 text-lg leading-8 text-ink/70">Ищите по импортированному каталогу и уточняйте сведения на официальных сайтах вузов. Покрытие программ и мониторинга пока неполное.</p>
      </header>

      <div className="mt-8 flex flex-col gap-3 lg:flex-row lg:items-center">
        <SearchControl key={query.q} onCommit={(q) => updateQuery({ q })} value={query.q} />
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          <label className="sr-only" htmlFor="catalog-sort">Сортировка</label>
          <span className="relative min-w-48 flex-1 lg:flex-none">
            <SlidersHorizontal aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-moss" size={17} />
            <select
              className="w-full appearance-none rounded-xl border border-ink/15 bg-white py-3 pl-10 pr-9 text-sm font-semibold"
              id="catalog-sort"
              onChange={(event) => updateQuery({ sort: event.target.value as UniversitySort })}
              value={query.sort}
            >
              <option value="name">По названию</option>
              <option value="city">По городу</option>
              <option value="monitoring_status">По статусу мониторинга</option>
              <option value="program_count">По числу импортированных программ</option>
              <option value="updated_at">По времени обновления</option>
            </select>
            <ChevronDown aria-hidden="true" className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-ink/45" size={16} />
          </span>
          <label className="sr-only" htmlFor="catalog-order">Направление сортировки</label>
          <select
            className="rounded-xl border border-ink/15 bg-white px-3 py-3 text-sm font-semibold"
            id="catalog-order"
            onChange={(event) => updateQuery({ order: event.target.value as SortOrder })}
            value={query.order}
          >
            <option value="asc">По возрастанию</option>
            <option value="desc">По убыванию</option>
          </select>
        </div>
      </div>

      <div className="mt-5">
        {metaLoading && <div aria-live="polite" className="panel p-5 text-sm text-ink/65" role="status">Загружаем параметры каталога…</div>}
        {metaError && <div aria-live="assertive" className="panel border-red-200 p-6" role="alert">
          <h2 className="text-xl font-bold">Не удалось загрузить каталог</h2>
          <p className="mt-2 text-ink/65">Сервис временно недоступен. Данные не заменены пустым списком.</p>
          <button className="mt-4 inline-flex items-center gap-2 rounded-xl bg-moss px-4 py-2.5 font-bold text-white" onClick={() => {
            setMetaLoading(true)
            setMetaError(false)
            setMetaRetry((value) => value + 1)
          }} type="button"><RefreshCw aria-hidden="true" size={17} />Повторить</button>
        </div>}
        {meta && <UniversityFilters meta={meta} onChange={(patch) => updateQuery(patch)} query={query} />}
      </div>

      {activeFilters.length > 0 && <section aria-label="Активные фильтры" className="mt-5 flex flex-wrap items-center gap-2">
        {activeFilters.map((filterItem) => <button
          aria-label={`Убрать: ${filterItem.text}`}
          className="inline-flex items-center gap-1.5 rounded-full border border-moss/20 bg-mint px-3 py-1.5 text-sm font-semibold text-moss"
          key={filterItem.key}
          onClick={() => updateQuery(filterItem.patch)}
          type="button"
        >{filterItem.text}<X aria-hidden="true" size={14} /></button>)}
        <button className="rounded-xl px-3 py-1.5 text-sm font-bold text-moss hover:bg-moss/5" onClick={clearFilters} type="button">Очистить поиск и фильтры</button>
      </section>}

      <section aria-busy={results.loading} aria-labelledby="catalog-results-title" className="mt-8 min-w-0">
        <div className="mb-5 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="text-2xl font-extrabold" id="catalog-results-title">Результаты</h2>
            {results.data && !results.error && <p className="mt-1 text-sm text-ink/60">Найдено в каталоге платформы: <strong>{results.data.pagination.total_items}</strong></p>}
          </div>
          {results.data && !results.error && <p className="text-sm font-semibold text-ink/60">Страница {results.data.pagination.page} из {Math.max(1, results.data.pagination.total_pages)}</p>}
        </div>

        {meta && results.loading && !results.data && !results.error && <LoadingCards />}
        {meta && results.loading && results.data && !results.error && <div aria-live="polite" className="mb-4 inline-flex items-center gap-2 rounded-full bg-mint px-3 py-1.5 text-sm font-semibold text-moss" role="status"><RefreshCw aria-hidden="true" className="animate-spin" size={15} />Обновляем результаты…</div>}
        {meta && results.error && <div aria-live="assertive" className="panel border-red-200 p-6" role="alert">
          <h2 className="text-xl font-bold">Не удалось получить результаты</h2>
          <p className="mt-2 text-ink/65">Попробуйте повторить запрос. Ошибка не означает, что подходящих вузов нет.</p>
          <button className="mt-4 inline-flex items-center gap-2 rounded-xl bg-moss px-4 py-2.5 font-bold text-white" onClick={() => {
            setResults((current) => ({ ...current, loading: true, error: false }))
            setResultsRetry((value) => value + 1)
          }} type="button"><RefreshCw aria-hidden="true" size={17} />Повторить запрос</button>
        </div>}
        {meta && results.data && !results.error && results.data.items.length === 0 && !results.loading && <div className="panel p-7 text-center">
          <h2 className="text-2xl font-bold">По заданным условиям ничего не найдено</h2>
          <p className="mx-auto mt-3 max-w-xl text-ink/65">Попробуйте изменить запрос или снять фильтры. Это состояние относится только к импортированному каталогу платформы.</p>
          {hasUniversityCatalogFilters(query) && <button className="mt-5 rounded-xl bg-moss px-5 py-3 font-bold text-white" onClick={clearFilters} type="button">Очистить поиск и фильтры</button>}
        </div>}
        {meta && results.data && !results.error && results.data.items.length > 0 && <div className={`grid min-w-0 gap-5 lg:grid-cols-2 ${results.loading ? 'opacity-60' : ''}`}>
          {results.data.items.map((university) => <UniversityCard
            key={university.id}
            returnTo={`${location.pathname}${location.search}`}
            university={university}
          />)}
        </div>}
        {meta && results.data && !results.error && !results.loading && <CatalogPagination response={results.data} onPage={(page) => updateQuery({ page }, { resetPage: false })} />}
      </section>

      <aside className="mt-10 rounded-3xl border border-amber-300 bg-amber-50 p-6 text-amber-950/80">
        <div className="flex items-start gap-3">
          <CheckCircle2 aria-hidden="true" className="mt-0.5 shrink-0 text-amber-700" size={20} />
          <p className="leading-7">Количество программ и статусы описывают только покрытие этой платформы. Нулевой imported count не означает, что у вуза нет реальных программ.</p>
        </div>
      </aside>
    </div>
  </div>
}
