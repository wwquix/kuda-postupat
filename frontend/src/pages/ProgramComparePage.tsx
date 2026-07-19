import { ExternalLink, RadioTower, RefreshCw, X } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'

import { api, ApiError } from '../api'
import { apiValueLabel, formatCatalogDate } from '../catalogPresentation'
import {
  parseProgramComparisonSelection,
  programComparisonPath,
  programComparisonSearch,
  programIdentityKey,
  summarizeProgramForComparison,
} from '../programComparison'
import type { ProgramIdentity } from '../programComparison'
import {
  formatOfferingCount,
  formatPlaceCount,
  fundingTypeLabel,
  groupOfferingsByStudyForm,
  offeringMonitoringPresentation,
} from '../programOfferingPresentation'
import type { ImportedProgram, OfferingSummary } from '../types'
import { useDocumentTitle } from '../useDocumentTitle'

type LoadStatus = 'loading' | 'success' | 'not_found' | 'error'

type ProgramRequest = {
  key: string
  status: LoadStatus
  data: ImportedProgram | null
}

function ExternalResourceLink({ href, label }: { href: string; label: string }) {
  return <a
    aria-label={`${label} (откроется в новой вкладке)`}
    className="inline-flex max-w-full items-start gap-1.5 break-words rounded-sm font-bold text-accent underline decoration-accent/30 underline-offset-4 hover:decoration-accent"
    href={href}
    rel="noreferrer"
    target="_blank"
  ><span>{label}</span><ExternalLink aria-hidden="true" className="mt-1 shrink-0" size={15} /></a>
}

function CompactOffering({
  offering,
  studyFormLabel,
}: {
  offering: OfferingSummary
  studyFormLabel: string
}) {
  const funding = fundingTypeLabel(offering.funding_type)
  const monitoring = offeringMonitoringPresentation(offering)
  const identity = `${studyFormLabel}, ${offering.admission_year}, ${funding}`
  return <section aria-label={`Вариант обучения: ${identity}`} className="min-w-0 rounded-2xl border border-text-primary/10 bg-background/65 p-4">
    <div className="flex min-w-0 flex-wrap items-start justify-between gap-2">
      <h5 className="break-words font-semibold">{offering.admission_year} год</h5>
      <span className="max-w-full break-words rounded-full bg-accent px-3 py-1 text-sm font-semibold text-white">{funding}</span>
    </div>
    <dl className="mt-3 grid min-w-0 gap-2 text-sm">
      <div><dt className="font-semibold text-text-tertiary">Финансирование</dt><dd className="mt-0.5 font-bold">{funding}</dd></div>
      {offering.places !== null && <div><dt className="font-semibold text-text-tertiary">План приёма</dt><dd className="mt-0.5">{formatPlaceCount(offering.places)}</dd></div>}
      <div><dt className="font-semibold text-text-tertiary">Мониторинг</dt><dd className="mt-0.5 font-bold">{monitoring.title}</dd></div>
    </dl>
    <p className="mt-2 break-words text-sm leading-6 text-text-secondary">{monitoring.description}</p>
    {monitoring.kind === 'live' && <Link
      aria-label={`Открыть live-мониторинг: ${identity}`}
      className="mt-3 inline-flex max-w-full items-center gap-2 rounded-xl bg-accent px-3 py-2 text-sm font-bold text-white"
      to="/monitor"
    ><RadioTower aria-hidden="true" className="shrink-0" size={16} /><span className="break-words">Открыть live-мониторинг</span></Link>}
    <div className="mt-3 min-w-0">
      <ExternalResourceLink href={offering.official_url} label={`Официальный источник варианта ${offering.admission_year}`} />
    </div>
  </section>
}

function ComparedOfferingGroups({ program }: { program: ImportedProgram }) {
  const groups = groupOfferingsByStudyForm(program.offerings)
  if (groups.length === 0) {
    return <p className="mt-4 rounded-2xl bg-background p-4 text-sm text-text-secondary">Варианты обучения ещё не импортированы платформой.</p>
  }
  return <div className="mt-4 grid min-w-0 gap-4">
    {groups.map((group, index) => <section aria-labelledby={`compare-offering-group-${program.id}-${index}`} className="min-w-0" key={group.studyForm}>
      <div className="flex min-w-0 flex-wrap items-baseline justify-between gap-2">
        <h4 className="break-words text-lg font-semibold" id={`compare-offering-group-${program.id}-${index}`}>{group.studyFormLabel}</h4>
        <p className="shrink-0 text-sm font-bold text-text-tertiary">{formatOfferingCount(group.offerings.length)}</p>
      </div>
      <div className="mt-3 grid min-w-0 gap-3">
        {group.offerings.map((offering) => <CompactOffering key={offering.id} offering={offering} studyFormLabel={group.studyFormLabel} />)}
      </div>
    </section>)}
  </div>
}

function ProgramComparisonCard({
  identity,
  onRemove,
  program,
}: {
  identity: ProgramIdentity
  onRemove: () => void
  program: ImportedProgram
}) {
  const summary = summarizeProgramForComparison(program)
  const checkedAt = formatCatalogDate(program.verified_at ?? program.source_checked_at)
  const detailPath = `/universities/${encodeURIComponent(program.university.slug)}/programs/${encodeURIComponent(program.slug)}`
  const titleId = `compared-program-${program.id}`
  return <article aria-labelledby={titleId} className="panel flex min-w-0 flex-col p-5 sm:p-6">
    <div className="flex min-w-0 items-start justify-between gap-3">
      <div className="min-w-0">
        {program.code && <div className="eyebrow break-words">{program.code}</div>}
        <h2 className="mt-2 break-words text-2xl font-semibold leading-snug" id={titleId}>{program.name}</h2>
        <Link className="mt-2 inline-flex max-w-full break-words font-bold text-accent underline" to={`/universities/${encodeURIComponent(program.university.slug)}`}>{program.university.short_name}</Link>
      </div>
      <button
        aria-label={`Убрать из сравнения — ${program.name}`}
        className="icon-button"
        onClick={onRemove}
        type="button"
      ><X aria-hidden="true" size={18} /></button>
    </div>

    <dl className="mt-5 grid min-w-0 gap-3 text-sm">
      {program.qualification && <div><dt className="font-semibold text-text-tertiary">Квалификация</dt><dd className="mt-1 break-words">{program.qualification}</dd></div>}
      {program.faculty_name && <div><dt className="font-semibold text-text-tertiary">Подразделение</dt><dd className="mt-1 break-words">{program.faculty_name}</dd></div>}
      {program.education_level && <div><dt className="font-semibold text-text-tertiary">Уровень образования</dt><dd className="mt-1 break-words">{program.education_level}</dd></div>}
      {program.duration_years !== null && <div><dt className="font-semibold text-text-tertiary">Продолжительность</dt><dd className="mt-1">{program.duration_years} года</dd></div>}
      <div><dt className="font-semibold text-text-tertiary">Импортированные варианты</dt><dd className="mt-1 font-semibold">{summary.totalOfferings}</dd></div>
      <div><dt className="font-semibold text-text-tertiary">Формы обучения</dt><dd className="mt-1 break-words">{summary.studyForms.length > 0 ? summary.studyForms.map(apiValueLabel).join(', ') : 'Варианты ещё не импортированы'}</dd></div>
      <div><dt className="font-semibold text-text-tertiary">Бюджетные варианты</dt><dd className="mt-1 font-semibold">{summary.budgetOfferings}</dd></div>
      <div><dt className="font-semibold text-text-tertiary">Платные варианты</dt><dd className="mt-1 font-semibold">{summary.paidOfferings}</dd></div>
      {summary.knownPlaces !== null && <div><dt className="font-semibold text-text-tertiary">Известные места, сумма</dt><dd className="mt-1 font-semibold">{formatPlaceCount(summary.knownPlaces)}</dd></div>}
      <div><dt className="font-semibold text-text-tertiary">Варианты с live-мониторингом</dt><dd className="mt-1 font-semibold">{summary.liveOfferings}</dd></div>
      {checkedAt && <div><dt className="font-semibold text-text-tertiary">Данные проверены</dt><dd className="mt-1">{checkedAt}</dd></div>}
    </dl>

    <div className="mt-5 grid min-w-0 gap-3 border-t border-text-primary/10 pt-4 text-sm">
      <Link className="w-fit max-w-full break-words font-bold text-accent underline" to={detailPath}>Открыть страницу программы</Link>
      <ExternalResourceLink href={program.official_url} label={`Официальная страница программы «${program.name}»`} />
    </div>

    <section aria-labelledby={`compared-offerings-${program.id}`} className="mt-6 min-w-0 border-t border-text-primary/10 pt-5">
      <h3 className="text-xl font-semibold" id={`compared-offerings-${program.id}`}>Варианты обучения</h3>
      <ComparedOfferingGroups program={program} />
    </section>
    <span className="sr-only">Идентификатор сравнения: {programIdentityKey(identity)}</span>
  </article>
}

function ProgramComparisonSlot({
  identity,
  onRemove,
  onStatus,
}: {
  identity: ProgramIdentity
  onRemove: () => void
  onStatus: (key: string, status: LoadStatus) => void
}) {
  const identityKey = programIdentityKey(identity)
  const [retry, setRetry] = useState(0)
  const requestKey = `${identityKey}:${retry}`
  const [request, setRequest] = useState<ProgramRequest>({ key: requestKey, status: 'loading', data: null })

  useEffect(() => {
    const controller = new AbortController()
    api.program(identity.universitySlug, identity.programSlug, controller.signal)
      .then((program) => {
        if (controller.signal.aborted) return
        setRequest({ key: requestKey, status: 'success', data: program })
        onStatus(identityKey, 'success')
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        const status = error instanceof ApiError && error.status === 404 ? 'not_found' : 'error'
        setRequest({ key: requestKey, status, data: null })
        onStatus(identityKey, status)
      })
    return () => controller.abort()
  }, [identity.programSlug, identity.universitySlug, identityKey, onStatus, requestKey])

  const current = request.key === requestKey
    ? request
    : { key: requestKey, status: 'loading' as const, data: null }
  const retryFailedRequest = () => {
    const nextRetry = retry + 1
    setRequest({ key: `${identityKey}:${nextRetry}`, status: 'loading', data: null })
    onStatus(identityKey, 'loading')
    setRetry(nextRetry)
  }

  if (current.status === 'loading') return <section aria-label={`Загрузка программы ${identityKey}`} className="panel min-w-0 p-5" role="status">
    <div className="flex min-w-0 items-start justify-between gap-3">
      <p className="flex min-w-0 items-center gap-2 break-words font-bold"><RefreshCw aria-hidden="true" className="shrink-0 animate-spin text-accent" size={18} />Загружаем {identityKey}…</p>
      <button aria-label={`Убрать из сравнения — ${identityKey}`} className="icon-button" onClick={onRemove} type="button"><X aria-hidden="true" size={18} /></button>
    </div>
  </section>

  if (current.status === 'not_found') return <section aria-labelledby={`missing-program-${identityKey}`} className="panel min-w-0 border-warning/30 p-5" role="status">
    <h2 className="break-words text-xl font-semibold" id={`missing-program-${identityKey}`}>Программа не найдена: {identityKey}</h2>
    <p className="mt-2 break-words text-text-secondary">Программа могла быть удалена или её адрес изменился. Остальные результаты сравнения сохранены.</p>
    <button aria-label={`Убрать из сравнения — ${identityKey}`} className="mt-4 inline-flex items-center gap-2 font-bold text-accent underline" onClick={onRemove} type="button"><X aria-hidden="true" size={16} />Убрать из сравнения</button>
  </section>

  if (current.status === 'error') return <section aria-labelledby={`failed-program-${identityKey}`} className="panel min-w-0 border-danger/30 p-5" role="alert">
    <h2 className="break-words text-xl font-semibold" id={`failed-program-${identityKey}`}>Не удалось загрузить программу: {identityKey}</h2>
    <p className="mt-2 break-words text-text-secondary">Идентификатор остаётся в URL. Повторите только этот безопасный GET-запрос.</p>
    <div className="mt-4 flex flex-wrap gap-3">
      <button aria-label={`Повторить загрузку — ${identityKey}`} className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-accent px-4 py-2.5 font-bold text-white" onClick={retryFailedRequest} type="button"><RefreshCw aria-hidden="true" size={17} />Повторить</button>
      <button aria-label={`Убрать из сравнения — ${identityKey}`} className="min-h-11 rounded-xl border border-text-primary/15 bg-white px-4 py-2.5 font-bold" onClick={onRemove} type="button">Убрать</button>
    </div>
  </section>

  return current.data
    ? <ProgramComparisonCard identity={identity} onRemove={onRemove} program={current.data} />
    : null
}

export function ProgramComparePage() {
  useDocumentTitle('Сравнение программ · Куда поступать')
  const location = useLocation()
  const navigate = useNavigate()
  const selection = useMemo(() => parseProgramComparisonSelection(
    new URLSearchParams(location.search).get('programs'),
  ), [location.search])
  const canonicalSearch = programComparisonSearch(selection)
  const [statuses, setStatuses] = useState<Record<string, LoadStatus>>({})

  useEffect(() => {
    if (location.search !== canonicalSearch) {
      navigate({ pathname: '/compare/programs', search: canonicalSearch }, { replace: true })
    }
  }, [canonicalSearch, location.search, navigate])

  const reportStatus = useCallback((key: string, status: LoadStatus) => {
    setStatuses((current) => current[key] === status ? current : { ...current, [key]: status })
  }, [])
  const remove = (identity: ProgramIdentity) => {
    const removedKey = programIdentityKey(identity)
    navigate(programComparisonPath(selection.filter((item) => programIdentityKey(item) !== removedKey)))
  }
  const allFailed = selection.length > 0 && selection.every((identity) => (
    statuses[programIdentityKey(identity)] === 'error'
  ))

  return <div className="page-shell">
    <div className="page-container py-10 lg:py-14">
      <header className="max-w-4xl">
        <div className="eyebrow">Сохранённые данные каталога</div>
        <h1 className="page-heading">Сравнение программ</h1>
        <p className="body-copy mt-4">Сопоставьте 2–3 импортированные программы и их отдельные варианты обучения. Страница не ранжирует программы и не оценивает шансы поступления.</p>
      </header>

      {selection.length === 0 && <section aria-labelledby="program-compare-empty-title" className="panel mt-8 p-6">
        <h2 className="text-2xl font-semibold" id="program-compare-empty-title">Выберите 2–3 программы</h2>
        <p className="mt-3 max-w-3xl leading-7 text-text-secondary">Добавьте программы из анонимного списка поступления. Выбор хранится только в URL сравнения.</p>
        <Link className="mt-5 inline-flex min-h-11 items-center rounded-xl bg-accent px-4 py-2.5 font-bold text-white" to="/my-list">Перейти в Мой список</Link>
      </section>}

      {selection.length === 1 && <section aria-labelledby="program-compare-guidance-title" className="panel mt-8 border-warning/30 p-5">
        <h2 className="text-xl font-semibold" id="program-compare-guidance-title">Нужна ещё одна программа</h2>
        <p className="mt-2 text-text-secondary">Выбранная программа показана ниже, но полное сравнение начинается с двух программ.</p>
        <Link className="mt-4 inline-flex font-bold text-accent underline" to="/my-list">Добавить программу из Моего списка</Link>
      </section>}

      {allFailed && <section aria-labelledby="program-compare-all-failed-title" className="panel mt-8 border-danger/30 p-6" role="alert">
        <h2 className="text-xl font-semibold" id="program-compare-all-failed-title">Не удалось загрузить выбранные программы</h2>
        <p className="mt-2 text-text-secondary">Каноническая ссылка сохранена. Повторите загрузку нужной программы в её карточке.</p>
      </section>}

      {selection.length > 0 && <section aria-labelledby="program-comparison-results-title" className="mt-8 min-w-0">
        <div className="flex min-w-0 flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div className="min-w-0">
            <h2 className="break-words text-3xl font-semibold" id="program-comparison-results-title">{selection.length === 1 ? 'Выбранная программа' : 'Сравниваемые программы'}</h2>
            <p className="mt-2 text-text-secondary">Порядок карточек соответствует порядку идентификаторов в URL.</p>
          </div>
          <p className="shrink-0 font-bold text-text-secondary">Выбрано {selection.length} из 3</p>
        </div>
        <div className="mt-5 grid min-w-0 gap-5 md:grid-cols-2 xl:grid-cols-3">
          {selection.map((identity) => {
            const key = programIdentityKey(identity)
            return <ProgramComparisonSlot identity={identity} key={key} onRemove={() => remove(identity)} onStatus={reportStatus} />
          })}
        </div>
      </section>}
    </div>
  </div>
}
