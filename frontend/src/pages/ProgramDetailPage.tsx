import {
  ArrowLeft,
  Building2,
  CalendarDays,
  ExternalLink,
  RadioTower,
  RefreshCw,
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'

import { api, ApiError } from '../api'
import { apiValueLabel, formatCatalogDate } from '../catalogPresentation'
import { SaveControl } from '../components/SaveControl'
import {
  formatOfferingCount,
  formatPlaceCount,
  formatStudyFormCount,
  fundingTypeLabel,
  groupOfferingsByStudyForm,
  offeringMonitoringPresentation,
  summarizeOfferings,
} from '../programOfferingPresentation'
import type { ImportedProgram, OfferingSummary } from '../types'
import { useDocumentTitle } from '../useDocumentTitle'

type DetailState = {
  key: string | null
  data: ImportedProgram | null
  status: 'loading' | 'success' | 'error' | 'not_found'
}

function universityReturnDestination(state: unknown, universitySlug: string) {
  const fallback = `/universities/${encodeURIComponent(universitySlug)}`
  if (!state || typeof state !== 'object' || !('universityReturnTo' in state)) return fallback
  const candidate = (state as { universityReturnTo?: unknown }).universityReturnTo
  return typeof candidate === 'string'
    && (candidate === fallback || candidate.startsWith(`${fallback}?`))
    ? candidate
    : fallback
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

function OfferingCard({
  offering,
  studyFormLabel,
}: {
  offering: OfferingSummary
  studyFormLabel: string
}) {
  const checkedAt = formatCatalogDate(offering.source_checked_at)
  const fundingLabel = fundingTypeLabel(offering.funding_type)
  const monitoring = offeringMonitoringPresentation(offering)
  const identity = `${studyFormLabel}, ${offering.admission_year}, ${fundingLabel}`
  return <article className="min-w-0 rounded-2xl border border-ink/10 bg-cream/65 p-4 sm:p-5" aria-labelledby={`program-offering-${offering.id}`}>
    <div className="flex min-w-0 flex-wrap items-start justify-between gap-3">
      <h4 aria-label={`${studyFormLabel} · ${offering.admission_year} год`} className="min-w-0 break-words text-lg font-extrabold" id={`program-offering-${offering.id}`}>
        {offering.admission_year} год
      </h4>
      <span className="max-w-full break-words rounded-full bg-moss px-3 py-1 text-sm font-extrabold text-white">{fundingLabel}</span>
    </div>
    <dl className="mt-4 grid min-w-0 gap-3 text-sm sm:grid-cols-2">
      <div><dt className="font-semibold text-ink/50">Год приёма</dt><dd className="mt-1">{offering.admission_year}</dd></div>
      <div><dt className="font-semibold text-ink/50">Финансирование</dt><dd className="mt-1 font-bold">{fundingLabel}</dd></div>
      {offering.places !== null && <div><dt className="font-semibold text-ink/50">План приёма</dt><dd className="mt-1">{formatPlaceCount(offering.places)}</dd></div>}
      {checkedAt && <div><dt className="font-semibold text-ink/50">Источник проверен</dt><dd className="mt-1">{checkedAt}</dd></div>}
    </dl>
    <section aria-label={`Мониторинг: ${identity}`} className={`mt-4 min-w-0 rounded-xl border p-4 ${monitoring.kind === 'live' ? 'border-moss/25 bg-moss/10' : 'border-ink/10 bg-white/70'}`}>
      <h5 className="break-words font-extrabold">{monitoring.title}</h5>
      <p className="mt-1 break-words text-sm leading-6 text-ink/65">{monitoring.description}</p>
      {monitoring.kind === 'live' && <Link
        aria-label={`Открыть live-мониторинг: ${identity}`}
        className="mt-3 inline-flex max-w-full items-center gap-2 rounded-xl bg-moss px-4 py-2.5 font-bold text-white"
        to="/monitor"
      ><RadioTower aria-hidden="true" className="shrink-0" size={17} /><span className="break-words">Открыть live-мониторинг</span></Link>}
    </section>
    <div className="mt-4 min-w-0">
      <ExternalResourceLink href={offering.official_url} label={`Официальная страница набора ${offering.admission_year}`} />
    </div>
  </article>
}

function OfferingSummary({ offerings }: { offerings: OfferingSummary[] }) {
  const summary = summarizeOfferings(offerings)
  return <section aria-labelledby="offering-summary-title" className="panel mt-5 min-w-0 p-5 sm:p-6">
    <h3 className="text-xl font-extrabold" id="offering-summary-title">Кратко о вариантах</h3>
    <dl className="mt-4 grid min-w-0 gap-3 sm:grid-cols-2 lg:grid-cols-5">
      <div className="min-w-0 rounded-xl bg-cream p-4"><dt className="text-sm font-semibold text-ink/55">Импортировано</dt><dd className="mt-1 break-words text-lg font-extrabold">{formatOfferingCount(summary.total)}</dd></div>
      {summary.budget > 0 && <div className="min-w-0 rounded-xl bg-cream p-4"><dt className="text-sm font-semibold text-ink/55">Бюджет</dt><dd className="mt-1 text-lg font-extrabold">{summary.budget}</dd></div>}
      {summary.paid > 0 && <div className="min-w-0 rounded-xl bg-cream p-4"><dt className="text-sm font-semibold text-ink/55">Платно</dt><dd className="mt-1 text-lg font-extrabold">{summary.paid}</dd></div>}
      <div className="min-w-0 rounded-xl bg-cream p-4">
        <dt className="text-sm font-semibold text-ink/55">{formatStudyFormCount(summary.studyForms.length)}</dt>
        <dd className="mt-1 break-words font-extrabold">{summary.studyForms.map(apiValueLabel).join(', ')}</dd>
      </div>
      {summary.live > 0 && <div className="min-w-0 rounded-xl bg-moss/10 p-4"><dt className="text-sm font-semibold text-ink/55">Live-мониторинг</dt><dd className="mt-1 text-lg font-extrabold">{summary.live}</dd></div>}
    </dl>
  </section>
}

function OfferingGroups({ offerings }: { offerings: OfferingSummary[] }) {
  const groups = groupOfferingsByStudyForm(offerings)
  return <div className="mt-5 grid min-w-0 gap-5">
    {groups.map((group, index) => {
      const groupId = `offering-group-${index}`
      return <section aria-labelledby={groupId} className="panel min-w-0 p-5 sm:p-6" key={group.studyForm}>
        <div className="flex min-w-0 flex-wrap items-baseline justify-between gap-2">
          <h3 className="min-w-0 break-words text-2xl font-extrabold" id={groupId}>{group.studyFormLabel}</h3>
          <p className="shrink-0 font-bold text-ink/55">{formatOfferingCount(group.offerings.length)}</p>
        </div>
        <div className="mt-4 grid min-w-0 gap-4 lg:grid-cols-2">
          {group.offerings.map((offering) => <OfferingCard key={offering.id} offering={offering} studyFormLabel={group.studyFormLabel} />)}
        </div>
      </section>
    })}
  </div>
}

function PageShell({ backTo, children }: { backTo: string; children: ReactNode }) {
  return <div className="mx-auto max-w-7xl px-5 py-10 lg:px-8 lg:py-14">
    <Link className="inline-flex items-center gap-2 rounded-xl font-bold text-moss" to={backTo}>
      <ArrowLeft aria-hidden="true" size={18} />Назад к вузу
    </Link>
    {children}
  </div>
}

export function ProgramDetailPage() {
  const { universitySlug = '', programKey = '' } = useParams()
  const location = useLocation()
  const backTo = useMemo(
    () => universityReturnDestination(location.state, universitySlug),
    [location.state, universitySlug],
  )
  const requestKey = `${universitySlug}\u0000${programKey}`
  const [retry, setRetry] = useState(0)
  const [request, setRequest] = useState<DetailState>({ key: null, data: null, status: 'loading' })
  const current = request.key === requestKey
    ? request
    : { key: requestKey, data: null, status: 'loading' as const }

  useDocumentTitle(
    current.data
      ? `${current.data.name} · ${current.data.university.short_name} · Куда поступать`
      : 'Программа · Куда поступать',
  )

  useEffect(() => {
    const controller = new AbortController()
    api.program(universitySlug, programKey, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setRequest({ key: requestKey, data, status: 'success' })
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        setRequest({
          key: requestKey,
          data: null,
          status: error instanceof ApiError && error.status === 404 ? 'not_found' : 'error',
        })
      })
    return () => controller.abort()
  }, [programKey, requestKey, retry, universitySlug])

  if (current.status === 'loading') return <PageShell backTo={backTo}>
    <section aria-labelledby="program-loading-title" aria-live="polite" className="panel mt-6 p-7" role="status">
      <h1 className="text-2xl font-extrabold" id="program-loading-title">Загружаем страницу программы…</h1>
      <p className="mt-2 text-ink/65">Получаем импортированные сведения и варианты обучения.</p>
    </section>
  </PageShell>

  if (current.status === 'not_found') return <PageShell backTo={backTo}>
    <section aria-labelledby="program-not-found-title" className="panel mt-6 p-7" role="status">
      <h1 className="text-3xl font-extrabold" id="program-not-found-title">Программа не найдена</h1>
      <p className="mt-3 text-ink/65">Проверьте адрес или вернитесь к импортированным программам вуза.</p>
    </section>
  </PageShell>

  if (current.status === 'error') return <PageShell backTo={backTo}>
    <section aria-labelledby="program-error-title" className="panel mt-6 border-red-200 p-7" role="alert">
      <h1 className="text-3xl font-extrabold" id="program-error-title">Не удалось загрузить страницу программы</h1>
      <p className="mt-3 text-ink/65">Сервис временно недоступен. Попробуйте повторить запрос.</p>
      <button className="mt-5 inline-flex items-center gap-2 rounded-xl bg-moss px-4 py-2.5 font-bold text-white" onClick={() => {
        setRequest({ key: requestKey, data: null, status: 'loading' })
        setRetry((value) => value + 1)
      }} type="button"><RefreshCw aria-hidden="true" size={17} />Повторить запрос</button>
    </section>
  </PageShell>

  const program = current.data
  if (!program) return null
  const checkedAt = formatCatalogDate(program.verified_at ?? program.source_checked_at)

  return <div className="min-w-0 bg-[linear-gradient(180deg,#f8f7f1_0%,#f2f0e7_100%)]">
    <PageShell backTo={backTo}>
      <header className="mt-7 max-w-4xl">
        {program.code && <div className="eyebrow">{program.code}</div>}
        <h1 className="mt-3 break-words text-4xl font-extrabold leading-tight tracking-tight sm:text-5xl">{program.name}</h1>
        <Link className="mt-5 inline-flex items-center gap-2 rounded-sm font-bold text-moss underline decoration-moss/30 underline-offset-4 hover:decoration-moss" to={`/universities/${encodeURIComponent(program.university.slug)}`}>
          <Building2 aria-hidden="true" size={18} />{program.university.short_name}
        </Link>
        <div className="mt-5">
          <SaveControl
            kind="program"
            label={program.name}
            programSlug={program.slug}
            universitySlug={program.university.slug}
          />
        </div>
      </header>

      <div className="mt-8 grid min-w-0 gap-5 lg:grid-cols-2">
        <section aria-labelledby="program-identity-title" className="panel min-w-0 p-5 sm:p-6">
          <h2 className="text-2xl font-extrabold" id="program-identity-title">О программе</h2>
          <dl className="mt-5 grid gap-4 text-sm sm:grid-cols-2">
            {program.qualification && <div><dt className="font-semibold text-ink/50">Квалификация</dt><dd className="mt-1 break-words">{program.qualification}</dd></div>}
            {program.faculty_name && <div><dt className="font-semibold text-ink/50">Подразделение</dt><dd className="mt-1 break-words">{program.faculty_name}</dd></div>}
            {program.education_level && <div><dt className="font-semibold text-ink/50">Уровень образования</dt><dd className="mt-1">{program.education_level}</dd></div>}
            {program.duration_years !== null && <div><dt className="font-semibold text-ink/50">Продолжительность</dt><dd className="mt-1">{program.duration_years} года</dd></div>}
            {checkedAt && <div><dt className="flex items-center gap-2 font-semibold text-ink/50"><CalendarDays aria-hidden="true" size={16} />Данные проверены</dt><dd className="mt-1">{checkedAt}</dd></div>}
          </dl>
        </section>

        <section aria-labelledby="program-resources-title" className="panel min-w-0 p-5 sm:p-6">
          <h2 className="text-2xl font-extrabold" id="program-resources-title">Официальные ресурсы</h2>
          <div className="mt-5">
            <ExternalResourceLink href={program.official_url} label={`Официальная страница программы «${program.name}»`} />
          </div>
        </section>
      </div>

      <section aria-labelledby="offerings-title" className="mt-10 min-w-0">
        <h2 className="text-3xl font-extrabold" id="offerings-title">Варианты обучения</h2>
        <p className="mt-3 max-w-3xl leading-7 text-ink/65">Показаны только варианты, уже импортированные платформой из сохранённых официальных источников.</p>
        {program.offerings.length > 0
          ? <><OfferingSummary offerings={program.offerings} /><OfferingGroups offerings={program.offerings} /></>
          : <div className="panel mt-5 p-6"><p className="font-bold">Варианты обучения ещё не импортированы</p><p className="mt-2 text-ink/65">Это описывает покрытие платформы, а не отсутствие реальных вариантов обучения.</p></div>}
      </section>
    </PageShell>
  </div>
}
