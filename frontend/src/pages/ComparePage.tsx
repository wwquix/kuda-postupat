import {
  ArrowRightLeft,
  ExternalLink,
  Plus,
  RadioTower,
  RefreshCw,
  Search,
  X,
} from 'lucide-react'
import { type FormEvent, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'

import { api, ApiError } from '../api'
import { apiValueLabel, formatCatalogDate } from '../catalogPresentation'
import type { UniversityDetail, UniversityListItem } from '../types'
import { useDocumentTitle } from '../useDocumentTitle'

const MAX_UNIVERSITIES = 3
const MISSING_VALUE = 'Данные пока не добавлены'

type ComparedUniversity = {
  slug: string
  status: 'success' | 'not_found' | 'error'
  data: UniversityDetail | null
}

type CompareState = {
  key: string
  loading: boolean
  items: ComparedUniversity[]
}

type SearchState = {
  status: 'idle' | 'loading' | 'success' | 'error'
  items: UniversityListItem[]
}

function normalizeCompareSelection(raw: string | null) {
  const unique: string[] = []
  for (const candidate of (raw ?? '').split(',')) {
    const slug = candidate.trim()
    if (!slug || unique.includes(slug)) continue
    unique.push(slug)
    if (unique.length === MAX_UNIVERSITIES) break
  }
  return unique
}

function compareSearch(selection: string[]) {
  return selection.length > 0
    ? `?universities=${selection.map(encodeURIComponent).join(',')}`
    : ''
}

function hasOnlineMonitoring(university: UniversityDetail) {
  return university.coverage.online_monitoring === 'available'
}

function catalogValueOrMissing(value: string | null | undefined) {
  return !value || value === 'unknown' ? MISSING_VALUE : apiValueLabel(value)
}

function ComparisonCard({
  university,
  onRemove,
}: {
  university: UniversityDetail
  onRemove: () => void
}) {
  const liveMonitoring = hasOnlineMonitoring(university)
  const hasMonitorRoute = university.slug === 'bseu' && liveMonitoring
  const verifiedAt = formatCatalogDate(university.data_verified_at)
  const monitoringLabel = university.monitoring_status === 'online' && !liveMonitoring
    ? 'Статус требует проверки'
    : apiValueLabel(university.monitoring_status)

  return <article className="panel flex min-w-0 flex-col p-5 sm:p-6" aria-labelledby={`compare-${university.slug}`}>
    <div className="flex min-w-0 items-start justify-between gap-3">
      <div className="min-w-0">
        <div className="eyebrow">{university.short_name}</div>
        <h2 className="mt-2 break-words text-xl font-extrabold leading-snug" id={`compare-${university.slug}`}>
          {university.full_name}
        </h2>
      </div>
      <button
        aria-label={`Убрать из сравнения — ${university.short_name}`}
        className="shrink-0 rounded-xl border border-ink/10 p-2 text-ink/55 hover:bg-ink/5 hover:text-ink"
        onClick={onRemove}
        type="button"
      ><X aria-hidden="true" size={18} /></button>
    </div>

    <dl className="mt-5 grid gap-4 text-sm">
      <div><dt className="font-semibold text-ink/50">Город и регион</dt><dd className="mt-1 break-words">{[university.city, university.region].filter(Boolean).join(' · ') || MISSING_VALUE}</dd></div>
      <div><dt className="font-semibold text-ink/50">Форма собственности</dt><dd className="mt-1">{catalogValueOrMissing(university.ownership_type)}</dd></div>
      <div><dt className="font-semibold text-ink/50">Тип учреждения</dt><dd className="mt-1">{catalogValueOrMissing(university.institution_kind)}</dd></div>
      <div><dt className="font-semibold text-ink/50">Категории</dt><dd className="mt-1">{university.categories.length > 0 ? university.categories.map((item) => item.label_ru).join(', ') : MISSING_VALUE}</dd></div>
      <div><dt className="font-semibold text-ink/50">Покрытие программ</dt><dd className="mt-1 font-semibold">{university.program_count > 0 ? `Импортировано программ: ${university.program_count}` : 'Каталог программ ещё не импортирован'}</dd></div>
      <div><dt className="font-semibold text-ink/50">Статус мониторинга</dt><dd className="mt-1">{monitoringLabel}</dd></div>
      <div><dt className="font-semibold text-ink/50">Онлайн-мониторинг платформы</dt><dd className="mt-1">{liveMonitoring ? 'Доступен' : 'Пока не реализован'}</dd></div>
      <div><dt className="font-semibold text-ink/50">Данные вуза проверены</dt><dd className="mt-1">{verifiedAt ?? MISSING_VALUE}</dd></div>
    </dl>

    <div className="mt-6 grid gap-3 border-t border-ink/10 pt-5 text-sm">
      {university.official_site_url
        ? <a className="inline-flex w-fit items-center gap-1.5 font-semibold text-moss hover:underline" href={university.official_site_url} rel="noreferrer" target="_blank">Официальный сайт <ExternalLink aria-hidden="true" size={15} /></a>
        : <p><span className="font-semibold">Официальный сайт:</span> {MISSING_VALUE}</p>}
      {university.admissions_url
        ? <a className="inline-flex w-fit items-center gap-1.5 font-semibold text-moss hover:underline" href={university.admissions_url} rel="noreferrer" target="_blank">Страница для абитуриентов <ExternalLink aria-hidden="true" size={15} /></a>
        : <p><span className="font-semibold">Страница для абитуриентов:</span> {MISSING_VALUE}</p>}
      <Link className="inline-flex w-fit items-center gap-1.5 font-semibold text-moss hover:underline" to={`/universities/${encodeURIComponent(university.slug)}`}>Подробнее о вузе</Link>
      {hasMonitorRoute && <Link className="inline-flex w-fit items-center gap-1.5 font-semibold text-moss hover:underline" to="/monitor"><RadioTower aria-hidden="true" size={16} />Монитор поступления</Link>}
    </div>
  </article>
}

function UniversitySearch({
  selection,
  onAdd,
  onReplace,
}: {
  selection: string[]
  onAdd: (slug: string) => void
  onReplace: (oldSlug: string, newSlug: string) => void
}) {
  const [query, setQuery] = useState('')
  const [replaceSlug, setReplaceSlug] = useState(selection[0] ?? '')
  const [search, setSearch] = useState<SearchState>({ status: 'idle', items: [] })
  const controllerRef = useRef<AbortController | null>(null)
  const effectiveReplaceSlug = selection.includes(replaceSlug) ? replaceSlug : selection[0] ?? ''

  useEffect(() => () => controllerRef.current?.abort(), [])

  const submit = async (event?: FormEvent) => {
    event?.preventDefault()
    const normalizedQuery = query.trim()
    if (!normalizedQuery) {
      setSearch({ status: 'idle', items: [] })
      return
    }
    controllerRef.current?.abort()
    const controller = new AbortController()
    controllerRef.current = controller
    setSearch((current) => ({ ...current, status: 'loading' }))
    const params = new URLSearchParams({
      q: normalizedQuery,
      page: '1',
      page_size: '6',
      sort: 'name',
      order: 'asc',
    })
    try {
      const response = await api.universities(params, controller.signal)
      if (!controller.signal.aborted) setSearch({ status: 'success', items: response.items })
    } catch {
      if (!controller.signal.aborted) setSearch({ status: 'error', items: [] })
    }
  }

  return <section aria-labelledby="compare-search-title" className="panel mt-7 p-5 sm:p-6">
    <h2 className="text-2xl font-extrabold" id="compare-search-title">Добавить вуз</h2>
    <p className="mt-2 text-ink/65">Поиск выполняется по серверному каталогу платформы.</p>
    <form className="mt-5 flex min-w-0 flex-col gap-3 sm:flex-row" onSubmit={(event) => void submit(event)} role="search">
      <label className="min-w-0 flex-1">
        <span className="sr-only">Поиск вуза для сравнения</span>
        <span className="flex min-w-0 items-center gap-2 rounded-xl border border-ink/15 bg-white px-3 focus-within:border-moss/40">
          <Search aria-hidden="true" className="shrink-0 text-moss" size={18} />
          <input className="min-w-0 flex-1 bg-transparent py-3 outline-none" maxLength={200} onChange={(event) => setQuery(event.target.value)} placeholder="Название, город или категория…" type="search" value={query} />
        </span>
      </label>
      <button className="min-h-11 rounded-xl bg-moss px-5 py-3 font-bold text-white disabled:cursor-wait disabled:opacity-60" disabled={search.status === 'loading'} type="submit">
        {search.status === 'loading' ? 'Ищем…' : 'Найти'}
      </button>
    </form>

    {selection.length === MAX_UNIVERSITIES && <label className="mt-5 grid max-w-md gap-2 text-sm font-semibold" htmlFor="compare-replace">
      Кого заменить
      <select className="rounded-xl border border-ink/15 bg-white px-3 py-2.5 font-normal" id="compare-replace" onChange={(event) => setReplaceSlug(event.target.value)} value={effectiveReplaceSlug}>
        {selection.map((slug) => <option key={slug} value={slug}>{slug}</option>)}
      </select>
    </label>}

    {search.status === 'error' && <div className="mt-5 rounded-2xl border border-red-200 bg-red-50 p-4 text-red-800" role="alert">
      <p className="font-bold">Не удалось выполнить поиск вузов</p>
      <button className="mt-3 inline-flex items-center gap-2 font-bold underline" onClick={() => void submit()} type="button"><RefreshCw aria-hidden="true" size={16} />Повторить поиск</button>
    </div>}
    {search.status === 'success' && search.items.length === 0 && <p className="mt-5 rounded-2xl bg-cream p-4 font-semibold">По запросу ничего не найдено в каталоге платформы.</p>}
    {search.status === 'success' && search.items.length > 0 && <ul className="mt-5 grid gap-3">
      {search.items.map((university) => {
        const selected = selection.includes(university.slug)
        return <li className="flex min-w-0 flex-col gap-3 rounded-2xl border border-ink/10 bg-cream/60 p-4 sm:flex-row sm:items-center sm:justify-between" key={university.slug}>
          <div className="min-w-0"><div className="font-extrabold">{university.short_name}</div><div className="break-words text-sm text-ink/65">{university.full_name}</div></div>
          {selected
            ? <span className="shrink-0 text-sm font-bold text-ink/55">Уже выбрано</span>
            : selection.length < MAX_UNIVERSITIES
              ? <button className="inline-flex min-h-11 shrink-0 items-center justify-center gap-2 rounded-xl border border-moss/25 bg-white px-4 py-2.5 font-bold text-moss" onClick={() => onAdd(university.slug)} type="button"><Plus aria-hidden="true" size={17} />Добавить {university.short_name}</button>
              : <button className="inline-flex min-h-11 shrink-0 items-center justify-center gap-2 rounded-xl border border-moss/25 bg-white px-4 py-2.5 font-bold text-moss" onClick={() => onReplace(effectiveReplaceSlug, university.slug)} type="button"><ArrowRightLeft aria-hidden="true" size={17} />Заменить на {university.short_name}</button>}
        </li>
      })}
    </ul>}
  </section>
}

export function ComparePage() {
  useDocumentTitle('Сравнение вузов · Куда поступать')
  const location = useLocation()
  const navigate = useNavigate()
  const selection = useMemo(() => normalizeCompareSelection(new URLSearchParams(location.search).get('universities')), [location.search])
  const selectionKey = selection.join(',')
  const canonicalSearch = compareSearch(selection)
  const [retry, setRetry] = useState(0)
  const [request, setRequest] = useState<CompareState>({ key: '', loading: false, items: [] })
  const requestKey = `${selectionKey}:${retry}`

  useEffect(() => {
    if (location.search !== canonicalSearch) navigate(`/compare${canonicalSearch}`, { replace: true })
  }, [canonicalSearch, location.search, navigate])

  useEffect(() => {
    if (!selectionKey) return undefined
    const controller = new AbortController()
    const requestedSlugs = selectionKey.split(',')
    Promise.all(requestedSlugs.map(async (slug): Promise<ComparedUniversity> => {
      try {
        return { slug, status: 'success', data: await api.university(slug, controller.signal) }
      } catch (error) {
        if (controller.signal.aborted) throw error
        return {
          slug,
          status: error instanceof ApiError && error.status === 404 ? 'not_found' : 'error',
          data: null,
        }
      }
    })).then((items) => {
      if (!controller.signal.aborted) setRequest({ key: requestKey, loading: false, items })
    }).catch(() => undefined)
    return () => controller.abort()
  }, [requestKey, selectionKey])

  const current = request.key === requestKey
    ? request
    : { key: requestKey, loading: selection.length > 0, items: [] }
  const updateSelection = (next: string[]) => navigate(`/compare${compareSearch(next)}`)
  const remove = (slug: string) => updateSelection(selection.filter((item) => item !== slug))
  const add = (slug: string) => {
    if (selection.includes(slug) || selection.length >= MAX_UNIVERSITIES) return
    updateSelection([...selection, slug])
  }
  const replace = (oldSlug: string, newSlug: string) => {
    if (selection.includes(newSlug)) return
    updateSelection(selection.map((slug) => slug === oldSlug ? newSlug : slug))
  }

  const successful = current.items.filter((item): item is ComparedUniversity & { data: UniversityDetail } => item.status === 'success' && item.data !== null)
  const failed = current.items.filter((item) => item.status === 'error')
  const unknown = current.items.filter((item) => item.status === 'not_found')

  return <div className="min-w-0 bg-[linear-gradient(180deg,#f8f7f1_0%,#f2f0e7_100%)]">
    <div className="mx-auto max-w-7xl px-5 py-10 lg:px-8 lg:py-14">
      <header className="max-w-4xl">
        <div className="eyebrow">Каталог платформы</div>
        <h1 className="mt-3 text-4xl font-extrabold leading-tight tracking-tight sm:text-5xl">Сравнение вузов</h1>
        <p className="mt-4 text-lg leading-8 text-ink/70">Сопоставьте 2–3 вуза по уже сохранённым данным платформы. Сравнение не ранжирует вузы и не оценивает шансы поступления.</p>
      </header>

      {selection.length === 0 && <section className="panel mt-8 p-6" aria-labelledby="compare-empty-title">
        <h2 className="text-2xl font-extrabold" id="compare-empty-title">Выберите вузы для сравнения</h2>
        <p className="mt-3 max-w-3xl leading-7 text-ink/65">Начните с поиска по каталогу. Выбор хранится только в URL, поэтому ссылку можно скопировать и открыть без профиля.</p>
      </section>}

      {current.loading && <div className="panel mt-8 flex items-center gap-3 p-6" role="status"><RefreshCw aria-hidden="true" className="animate-spin text-moss" size={20} /><span className="font-bold">Загружаем данные для сравнения…</span></div>}

      {!current.loading && failed.length > 0 && <section className="panel mt-8 border-red-200 p-6" role="alert">
        <h2 className="text-xl font-extrabold">Не удалось загрузить данные для сравнения</h2>
        <p className="mt-2 text-ink/65">Ранее выбранные вузы остаются в URL. Повторите безопасный GET-запрос.</p>
        <button className="mt-4 inline-flex min-h-11 items-center gap-2 rounded-xl bg-moss px-4 py-2.5 font-bold text-white" onClick={() => setRetry((value) => value + 1)} type="button"><RefreshCw aria-hidden="true" size={17} />Повторить запрос</button>
      </section>}

      {!current.loading && unknown.length > 0 && <section className="mt-8 grid gap-3" aria-label="Неизвестные вузы">
        {unknown.map((item) => <div className="panel border-amber-300 p-5" key={item.slug} role="status">
          <h2 className="text-xl font-extrabold">Университет не найден: {item.slug}</h2>
          <p className="mt-2 text-ink/65">Этот slug отсутствует в публичном каталоге платформы.</p>
          <button className="mt-3 inline-flex items-center gap-2 font-bold text-moss underline" onClick={() => remove(item.slug)} type="button"><X aria-hidden="true" size={16} />Убрать из сравнения</button>
        </div>)}
      </section>}

      {!current.loading && successful.length > 0 && <section aria-labelledby="comparison-results-title" className="mt-8">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div><h2 className="text-3xl font-extrabold" id="comparison-results-title">Выбранные вузы</h2><p className="mt-2 text-ink/65">Порядок соответствует ссылке сравнения.</p></div>
          <p className="font-bold text-ink/60">Выбрано: {selection.length} из {MAX_UNIVERSITIES}</p>
        </div>
        {selection.length === 1 && <p className="mt-5 rounded-2xl border border-amber-300 bg-amber-50 p-4 font-semibold text-amber-950">Добавьте ещё один вуз, чтобы перейти к сравнению.</p>}
        <div className="mt-5 grid min-w-0 gap-5 md:grid-cols-2 xl:grid-cols-3">
          {successful.map((item) => <ComparisonCard key={item.slug} onRemove={() => remove(item.slug)} university={item.data} />)}
        </div>
      </section>}

      <UniversitySearch onAdd={add} onReplace={replace} selection={selection} />
    </div>
  </div>
}
