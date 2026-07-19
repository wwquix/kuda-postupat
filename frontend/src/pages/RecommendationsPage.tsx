import {
  ArrowLeft,
  ArrowRight,
  BookmarkCheck,
  LoaderCircle,
  RadioTower,
  RefreshCw,
  SearchCheck,
} from 'lucide-react'
import { type FormEvent, type ReactNode, useEffect, useMemo, useState } from 'react'
import { Link, useLocation, useSearchParams } from 'react-router-dom'

import { api } from '../api'
import { apiValueLabel } from '../catalogPresentation'
import { SaveControl } from '../components/SaveControl'
import {
  buildRecommendationApiParams,
  DEFAULT_RECOMMENDATION_QUERY,
  parseRecommendationQuery,
  recommendationQueriesEqual,
  serializeRecommendationQuery,
  type RecommendationQuery,
  validateRecommendationQuery,
} from '../recommendationQuery'
import type {
  CatalogMeta,
  ProgramRecommendation,
  RecommendationReason,
  RecommendationResponse,
  RecommendationResultClass,
  UniversityRecommendation,
} from '../types'
import { useDocumentTitle } from '../useDocumentTitle'
import { useProfile } from '../useProfile'

interface RecommendationFormState {
  score: string
  city: string
  region: string
  ownership_type: string
  institution_kind: string
  category: string
  study_form: string
  funding_type: string
  online_monitoring: string
}

const reasonLabels: Record<string, string> = {
  catalog: 'Каталог',
  score: 'Введённый балл',
  city: 'Город',
  region: 'Регион',
  ownership_type: 'Форма собственности',
  institution_kind: 'Тип учреждения',
  category: 'Категория',
  study_form: 'Форма обучения',
  funding_type: 'Финансирование',
  online_monitoring: 'Live-мониторинг',
}

const classStyles: Record<RecommendationResultClass, string> = {
  MONITORED_STATUS: 'border-success/30 bg-success/10 text-success',
  PARAMETER_MATCH: 'border-warning/30 bg-warning/10 text-warning',
  INSUFFICIENT_COVERAGE: 'border-text-primary/15 bg-background text-text-secondary',
}

const formFromQuery = (
  query: RecommendationQuery,
  profileScore: number | null | undefined,
): RecommendationFormState => ({
  score: query.score !== undefined
    ? String(query.score)
    : !query.applied && profileScore !== null && profileScore !== undefined
      ? String(profileScore)
      : '',
  city: query.city ?? '',
  region: query.region ?? '',
  ownership_type: query.ownership_type ?? '',
  institution_kind: query.institution_kind ?? '',
  category: query.category ?? '',
  study_form: query.study_form ?? '',
  funding_type: query.funding_type ?? '',
  online_monitoring: query.online_monitoring === undefined ? '' : String(query.online_monitoring),
})

const queryFromForm = (form: RecommendationFormState): RecommendationQuery => ({
  applied: true,
  score: form.score === '' ? undefined : Number(form.score),
  city: form.city || undefined,
  region: form.region || undefined,
  ownership_type: form.ownership_type || undefined,
  institution_kind: form.institution_kind || undefined,
  category: form.category || undefined,
  study_form: form.study_form || undefined,
  funding_type: form.funding_type || undefined,
  online_monitoring: form.online_monitoring === '' ? undefined : form.online_monitoring === 'true',
  page: 1,
})

function SelectControl({
  id,
  label,
  value,
  onChange,
  children,
}: {
  id: string
  label: string
  value: string
  onChange: (value: string) => void
  children: ReactNode
}) {
  return <label className="grid min-w-0 gap-2 text-sm font-bold text-text-secondary" htmlFor={id}>
    {label}
    <select
      className="field-control font-normal"
      id={id}
      onChange={(event) => onChange(event.target.value)}
      value={value}
    >{children}</select>
  </label>
}

function MatchReasons({ reasons }: { reasons: RecommendationReason[] }) {
  return <dl className="flex flex-wrap gap-2 text-xs">
    {reasons.map((reason) => <div
      className="rounded-full border border-text-primary/10 bg-white px-3 py-1.5"
      key={`${reason.parameter}-${reason.value}`}
    >
      <dt className="inline font-bold text-text-tertiary">{reasonLabels[reason.parameter] ?? reason.parameter}: </dt>
      <dd className="inline font-semibold">
        {reason.parameter === 'online_monitoring'
          ? reason.value === 'true' ? 'доступен' : 'не реализован на платформе'
          : ['ownership_type', 'institution_kind', 'study_form', 'funding_type'].includes(reason.parameter)
            ? apiValueLabel(reason.value)
            : reason.value}
      </dd>
    </div>)}
  </dl>
}

function ResultClass({ item }: { item: ProgramRecommendation | UniversityRecommendation }) {
  return <div>
    <span className={`inline-flex rounded-full border px-3 py-1.5 text-xs font-semibold ${classStyles[item.result_class]}`}>
      {item.result_label}
    </span>
    <p className="mt-3 font-bold leading-6">{item.admission_evaluation}</p>
  </div>
}

function ProgramCard({ item, returnTo }: { item: ProgramRecommendation; returnTo: string }) {
  const { program } = item
  const monitorSupported = program.offerings.some(
    (offering) => offering.monitoring_supported && offering.monitoring_status === 'online',
  )
  return <article className="panel flex min-w-0 flex-col gap-5 p-5 sm:p-6">
    <header className="min-w-0">
      <div className="eyebrow">{program.university.short_name}</div>
      <h3 className="mt-2 break-words text-xl font-semibold leading-snug">
        <Link
          className="underline decoration-accent/35 decoration-2 underline-offset-4 hover:decoration-accent"
          state={{ universityReturnTo: returnTo }}
          to={`/universities/${encodeURIComponent(program.university.slug)}/programs/${encodeURIComponent(program.slug)}`}
        >{program.name}</Link>
      </h3>
      <Link
        className="mt-2 inline-block break-words font-semibold text-accent hover:underline"
        to={`/universities/${encodeURIComponent(program.university.slug)}`}
      >{program.university.short_name} — страница вуза</Link>
    </header>
    <ResultClass item={item} />
    <MatchReasons reasons={item.match_reasons} />
    {item.coverage_notes.length > 0 && <ul className="grid gap-2 text-sm leading-6 text-text-secondary">
      {item.coverage_notes.map((note) => <li key={note}>{note}</li>)}
    </ul>}
    <section aria-label={`Варианты обучения — ${program.name}`}>
      <h4 className="text-sm font-semibold">Импортированные варианты обучения</h4>
      {program.offerings.length > 0
        ? <ul className="mt-2 grid gap-2 text-sm">
          {program.offerings.map((offering) => <li className="rounded-xl bg-background/75 px-3 py-2" key={offering.id}>
            {offering.admission_year} · {apiValueLabel(offering.study_form)} · {apiValueLabel(offering.funding_type)}
            {offering.places !== null ? ` · ${offering.places} мест` : ''}
          </li>)}
        </ul>
        : <p className="mt-2 text-sm text-text-secondary">Варианты ещё не импортированы платформой.</p>}
    </section>
    <div className="mt-auto flex flex-wrap items-center gap-4 border-t border-text-primary/10 pt-4">
      {monitorSupported && <Link className="inline-flex items-center gap-2 font-bold text-accent" to="/monitor">
        <RadioTower aria-hidden="true" size={17} />Монитор
      </Link>}
      <SaveControl
        kind="program"
        label={program.name}
        programSlug={program.slug}
        universitySlug={program.university.slug}
      />
    </div>
  </article>
}

function UniversityCard({ item }: { item: UniversityRecommendation }) {
  const { university } = item
  return <article className="panel flex min-w-0 flex-col gap-5 p-5 sm:p-6">
    <header className="min-w-0">
      <div className="eyebrow">{university.short_name}</div>
      <h3 className="mt-2 break-words text-xl font-semibold leading-snug">
        <Link
          className="underline decoration-accent/35 decoration-2 underline-offset-4 hover:decoration-accent"
          to={`/universities/${encodeURIComponent(university.slug)}`}
        >{university.full_name}</Link>
      </h3>
      <p className="mt-2 text-sm text-text-secondary">
        {[university.city, university.region].filter(Boolean).join(' · ') || 'Местоположение уточняется'}
      </p>
    </header>
    <ResultClass item={item} />
    <MatchReasons reasons={item.match_reasons} />
    <div className="flex flex-wrap gap-2 text-xs font-semibold">
      <span className="rounded-full bg-accent-soft px-3 py-1.5">{apiValueLabel(university.ownership_type)}</span>
      {university.categories.map((category) => <span
        className="rounded-full border border-accent/15 px-3 py-1.5"
        key={category.code}
      >{category.label_ru}</span>)}
    </div>
    <div className="rounded-2xl bg-background/70 p-4 text-sm leading-6">
      {university.program_count > 0
        ? `Импортировано программ: ${university.program_count}; вариантов обучения: ${university.offering_count}.`
        : 'Программы этого вуза ещё не импортированы платформой.'}
    </div>
    {item.coverage_notes.length > 0 && <ul className="grid gap-2 text-sm leading-6 text-text-secondary">
      {item.coverage_notes.map((note) => <li key={note}>{note}</li>)}
    </ul>}
    <div className="mt-auto border-t border-text-primary/10 pt-4">
      <SaveControl kind="university" label={university.full_name} universitySlug={university.slug} />
    </div>
  </article>
}

function PaginationControl({
  page,
  totalPages,
  onPage,
}: {
  page: number
  totalPages: number
  onPage: (page: number) => void
}) {
  if (totalPages <= 1) return null
  return <nav aria-label="Страницы рекомендаций" className="mt-8 flex items-center justify-center gap-3">
    <button
      className="inline-flex items-center gap-1 rounded-xl border border-text-primary/15 bg-white px-4 py-2 font-bold disabled:opacity-45"
      disabled={page <= 1}
      onClick={() => onPage(page - 1)}
      type="button"
    ><ArrowLeft aria-hidden="true" size={17} />Назад</button>
    <span className="text-sm font-semibold">Страница {page} из {totalPages}</span>
    <button
      className="inline-flex items-center gap-1 rounded-xl border border-text-primary/15 bg-white px-4 py-2 font-bold disabled:opacity-45"
      disabled={page >= totalPages}
      onClick={() => onPage(page + 1)}
      type="button"
    >Вперёд<ArrowRight aria-hidden="true" size={17} /></button>
  </nav>
}

export function RecommendationsPage() {
  useDocumentTitle('Подбор вариантов · Куда поступать')
  const location = useLocation()
  const profile = useProfile()
  const [searchParams, setSearchParams] = useSearchParams()
  const searchKey = searchParams.toString()
  const parsedQuery = useMemo(
    () => parseRecommendationQuery(new URLSearchParams(searchKey)),
    [searchKey],
  )
  const [metaRequest, setMetaRequest] = useState<{
    data: CatalogMeta | null
    status: 'loading' | 'success' | 'error'
  }>({ data: null, status: 'loading' })
  const [metaRetry, setMetaRetry] = useState(0)
  const [resultsRetry, setResultsRetry] = useState(0)
  const [results, setResults] = useState<{
    key: string | null
    data: RecommendationResponse | null
    status: 'idle' | 'success' | 'error'
  }>({ key: null, data: null, status: 'idle' })
  const [draftState, setDraftState] = useState<{
    sourceKey: string
    value: RecommendationFormState
  } | null>(null)
  const [formError, setFormError] = useState('')
  const [scoreSaveState, setScoreSaveState] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')

  const query = useMemo(
    () => metaRequest.data
      ? validateRecommendationQuery(parsedQuery, metaRequest.data)
      : parsedQuery,
    [metaRequest.data, parsedQuery],
  )
  const canonicalKey = serializeRecommendationQuery(query).toString()
  const draft = draftState?.sourceKey === searchKey
    ? draftState.value
    : formFromQuery(query, profile.data?.profile.personal_score)
  const requestKey = query.applied ? buildRecommendationApiParams(query).toString() : null
  const currentResults = requestKey && results.key === requestKey ? results : null
  const backgroundLoading = Boolean(
    requestKey && results.data && results.key !== requestKey && results.status === 'success',
  )
  const initialLoading = Boolean(requestKey && !currentResults && !backgroundLoading)

  useEffect(() => {
    const controller = new AbortController()
    api.catalogMeta(controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return
        setMetaRequest({ data, status: 'success' })
      })
      .catch(() => {
        if (!controller.signal.aborted) setMetaRequest({ data: null, status: 'error' })
      })
    return () => controller.abort()
  }, [metaRetry])

  useEffect(() => {
    if (!metaRequest.data) return
    const validated = validateRecommendationQuery(parsedQuery, metaRequest.data)
    if (!recommendationQueriesEqual(parsedQuery, validated)) {
      setSearchParams(serializeRecommendationQuery(validated), { replace: true })
    }
  }, [metaRequest.data, parsedQuery, setSearchParams])

  useEffect(() => {
    if (!metaRequest.data || !query.applied || canonicalKey !== searchKey) return undefined
    const controller = new AbortController()
    const key = buildRecommendationApiParams(query).toString()
    api.recommendations(buildRecommendationApiParams(query), controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setResults({ key, data, status: 'success' })
      })
      .catch(() => {
        if (!controller.signal.aborted) setResults({ key, data: null, status: 'error' })
      })
    return () => controller.abort()
  }, [canonicalKey, metaRequest.data, query, resultsRetry, searchKey])

  const changeDraft = (patch: Partial<RecommendationFormState>) => {
    setDraftState({ sourceKey: searchKey, value: { ...draft, ...patch } })
    setFormError('')
    setScoreSaveState('idle')
  }

  const apply = (event: FormEvent) => {
    event.preventDefault()
    const next = queryFromForm(draft)
    if (next.score !== undefined && (!Number.isInteger(next.score) || next.score < 0 || next.score > 500)) {
      setFormError('Введите целый балл от 0 до 500.')
      return
    }
    setDraftState(null)
    setSearchParams(serializeRecommendationQuery(next))
  }

  const saveScore = async () => {
    const score = draft.score === '' ? undefined : Number(draft.score)
    if (score === undefined || !Number.isInteger(score) || score < 0 || score > 500) {
      setFormError('Чтобы сохранить балл, введите целое число от 0 до 500.')
      return
    }
    setScoreSaveState('saving')
    try {
      await profile.updateScore(score)
      setScoreSaveState('saved')
    } catch {
      setScoreSaveState('error')
    }
  }

  const setPage = (page: number) => {
    setDraftState(null)
    setSearchParams(serializeRecommendationQuery({ ...query, page }))
  }
  const meta = metaRequest.data
  const data = currentResults?.status === 'success' ? currentResults.data : null
  const noMatches = data
    && data.programs.pagination.total_items === 0
    && data.universities.pagination.total_items === 0
  const totalPages = data
    ? Math.max(data.programs.pagination.total_pages, data.universities.pagination.total_pages)
    : 0

  return <div className="page-shell">
    <div className="page-container py-10 lg:py-14">
      <header className="max-w-4xl">
        <div className="eyebrow">Честный подбор по импортированным данным</div>
        <h1 className="page-heading">
          Подбор вариантов поступления
        </h1>
        <p className="mt-5 max-w-3xl text-lg leading-8 text-text-secondary">
          Статус поступления показывается только там, где у платформы есть свежие реальные данные
          мониторинга. Совпадение с параметрами не гарантирует поступление.
        </p>
      </header>

      {metaRequest.status === 'loading' && <div aria-live="polite" className="panel mt-8 p-6" role="status">
        <span className="inline-flex items-center gap-2 font-bold">
          <LoaderCircle aria-hidden="true" className="animate-spin" size={19} />Загружаем параметры…
        </span>
      </div>}
      {metaRequest.status === 'error' && <div className="panel mt-8 border-danger/30 p-6" role="alert">
        <p className="font-bold">Не удалось загрузить параметры каталога.</p>
        <button
          className="mt-4 inline-flex items-center gap-2 rounded-xl bg-accent px-4 py-2.5 font-bold text-white"
          onClick={() => {
            setMetaRequest({ data: null, status: 'loading' })
            setMetaRetry((value) => value + 1)
          }}
          type="button"
        ><RefreshCw aria-hidden="true" size={17} />Повторить</button>
      </div>}

      {meta && <form aria-label="Параметры подбора" className="panel mt-8 p-5 sm:p-7" onSubmit={apply}>
        <div>
          <h2 className="text-2xl font-semibold tracking-[-0.02em]">Ваши параметры</h2>
          <p className="mt-1 text-sm leading-6 text-text-secondary">Ввод пользователя отделён от результатов; расчёт не является гарантией поступления.</p>
        </div>
        <div className="mt-5 grid min-w-0 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <label className="grid gap-2 text-sm font-bold text-text-secondary" htmlFor="recommendation-score">
            Балл
            <input
              className="field-control font-normal"
              id="recommendation-score"
              inputMode="numeric"
              max={500}
              min={0}
              onChange={(event) => changeDraft({ score: event.target.value })}
              placeholder="Например, 276"
              type="number"
              value={draft.score}
            />
          </label>
          <SelectControl id="recommendation-city" label="Город" onChange={(city) => changeDraft({ city })} value={draft.city}>
            <option value="">Любой</option>
            {meta.cities.map((city) => <option key={city}>{city}</option>)}
          </SelectControl>
          <SelectControl id="recommendation-region" label="Регион" onChange={(region) => changeDraft({ region })} value={draft.region}>
            <option value="">Любой</option>
            {meta.regions.map((region) => <option key={region}>{region}</option>)}
          </SelectControl>
          <SelectControl id="recommendation-ownership" label="Форма собственности" onChange={(ownership_type) => changeDraft({ ownership_type })} value={draft.ownership_type}>
            <option value="">Любая</option>
            {meta.ownership_types.map((value) => <option key={value} value={value}>{apiValueLabel(value)}</option>)}
          </SelectControl>
          <SelectControl id="recommendation-kind" label="Тип учреждения" onChange={(institution_kind) => changeDraft({ institution_kind })} value={draft.institution_kind}>
            <option value="">Любой</option>
            {meta.institution_kinds.map((value) => <option key={value} value={value}>{apiValueLabel(value)}</option>)}
          </SelectControl>
          <SelectControl id="recommendation-category" label="Категория" onChange={(category) => changeDraft({ category })} value={draft.category}>
            <option value="">Любая</option>
            {meta.categories.map((category) => <option key={category.code} value={category.code}>{category.label_ru}</option>)}
          </SelectControl>
          <SelectControl id="recommendation-study-form" label="Форма обучения" onChange={(study_form) => changeDraft({ study_form })} value={draft.study_form}>
            <option value="">Любая</option>
            {meta.study_forms.map((value) => <option key={value} value={value}>{apiValueLabel(value)}</option>)}
          </SelectControl>
          <SelectControl id="recommendation-funding" label="Финансирование" onChange={(funding_type) => changeDraft({ funding_type })} value={draft.funding_type}>
            <option value="">Любое</option>
            {meta.funding_types.map((value) => <option key={value} value={value}>{apiValueLabel(value)}</option>)}
          </SelectControl>
          <SelectControl id="recommendation-online" label="Live-мониторинг платформы" onChange={(online_monitoring) => changeDraft({ online_monitoring })} value={draft.online_monitoring}>
            <option value="">Не важно</option>
            <option value="true">Доступен</option>
            <option value="false">Не реализован на платформе</option>
          </SelectControl>
        </div>
        {formError && <p className="mt-4 font-semibold text-danger" role="alert">{formError}</p>}
        <div className="mt-6 flex flex-wrap items-center gap-3">
          <button className="button-primary" type="submit">
            <SearchCheck aria-hidden="true" size={18} />Подобрать варианты
          </button>
          <button
            className="button-secondary"
            onClick={() => {
              setDraftState(null)
              setSearchParams(serializeRecommendationQuery(DEFAULT_RECOMMENDATION_QUERY))
            }}
            type="button"
          >Очистить</button>
          <button
            className="button-secondary text-accent disabled:opacity-50"
            disabled={scoreSaveState === 'saving' || draft.score === ''}
            onClick={saveScore}
            type="button"
          >{scoreSaveState === 'saving'
              ? <LoaderCircle aria-hidden="true" className="animate-spin" size={18} />
              : <BookmarkCheck aria-hidden="true" size={18} />}
            Сохранить балл в профиле
          </button>
          <span aria-live="polite" className="text-sm font-semibold">
            {scoreSaveState === 'saved' && 'Балл сохранён в профиле.'}
            {scoreSaveState === 'error' && 'Не удалось сохранить балл. Попробуйте ещё раз.'}
          </span>
        </div>
      </form>}

      {!query.applied && metaRequest.status === 'success' && <section
        aria-labelledby="recommendation-start-title"
        className="panel mt-8 p-7"
      >
        <h2 className="text-2xl font-semibold" id="recommendation-start-title">Укажите важные параметры</h2>
        <p className="mt-3 max-w-3xl leading-7 text-text-secondary">
          Можно начать без балла: тогда подбор покажет совпадения каталога, но не будет рассчитывать
          статус поступления.
        </p>
      </section>}

      {initialLoading && <div aria-live="polite" className="panel mt-8 p-7" role="status">
        <span className="inline-flex items-center gap-2 font-bold">
          <LoaderCircle aria-hidden="true" className="animate-spin" size={20} />Подбираем варианты…
        </span>
      </div>}
      {backgroundLoading && <div aria-live="polite" className="mt-6 font-semibold text-accent" role="status">
        Обновляем результаты по новым параметрам…
      </div>}
      {currentResults?.status === 'error' && <div className="panel mt-8 border-danger/30 p-7" role="alert">
        <p className="text-xl font-semibold">Не удалось загрузить рекомендации</p>
        <p className="mt-2 text-text-secondary">Это ошибка запроса, а не отсутствие подходящих вариантов.</p>
        <button
          className="mt-5 inline-flex items-center gap-2 rounded-xl bg-accent px-4 py-2.5 font-bold text-white"
          onClick={() => setResultsRetry((value) => value + 1)}
          type="button"
        ><RefreshCw aria-hidden="true" size={17} />Повторить запрос</button>
      </div>}

      {noMatches && <section aria-labelledby="recommendation-empty-title" className="panel mt-8 p-7">
        <h2 className="text-2xl font-semibold" id="recommendation-empty-title">Совпадений не найдено</h2>
        <p className="mt-3 text-text-secondary">Попробуйте изменить один или несколько параметров.</p>
      </section>}

      {data && !noMatches && <div className={backgroundLoading ? 'opacity-60' : ''} aria-busy={backgroundLoading}>
        <aside className="surface-sunken mt-8 p-5 text-sm leading-6 text-text-secondary">
          {data.coverage.note} Результаты описывают только импортированное покрытие платформы.
        </aside>
        <section aria-labelledby="recommended-programs-title" className="mt-10 min-w-0">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 className="text-3xl font-semibold" id="recommended-programs-title">Программы</h2>
              <p className="mt-2 text-text-secondary">Найдено: {data.programs.pagination.total_items}</p>
            </div>
          </div>
          {data.programs.items.length > 0
            ? <div className="mt-5 grid min-w-0 gap-5 lg:grid-cols-2">
              {data.programs.items.map((item) => <ProgramCard
                item={item}
                key={item.program.id}
                returnTo={`${location.pathname}${location.search}`}
              />)}
            </div>
            : <p className="panel mt-5 p-6 font-semibold">На этой странице программ нет.</p>}
        </section>
        <section aria-labelledby="recommended-universities-title" className="mt-12 min-w-0">
          <h2 className="text-3xl font-semibold" id="recommended-universities-title">Университеты</h2>
          <p className="mt-2 text-text-secondary">Найдено: {data.universities.pagination.total_items}</p>
          {data.universities.items.length > 0
            ? <div className="mt-5 grid min-w-0 gap-5 lg:grid-cols-2">
              {data.universities.items.map((item) => <UniversityCard item={item} key={item.university.id} />)}
            </div>
            : <p className="panel mt-5 p-6 font-semibold">На этой странице университетов нет.</p>}
        </section>
        <PaginationControl page={query.page} totalPages={totalPages} onPage={setPage} />
      </div>}
    </div>
  </div>
}
