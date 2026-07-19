import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Activity, AlertTriangle, ArrowUpRight, BookOpen, CheckCircle2, Clock3,
  GraduationCap, RefreshCw, ShieldAlert, Target, TrendingUp, Users,
} from 'lucide-react'
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { api, ApiError } from '../api'
import { useDocumentTitle } from '../useDocumentTitle'
import type { CollectorStatus, HealthStatus, PublicConfig, Snapshot, Specialty } from '../types'

type SnapshotState = 'unknown' | 'available' | 'empty'

const chartColors = {
  grid: 'var(--chart-grid)',
  observed: 'var(--chart-observed)',
  projected: 'var(--chart-projected)',
  projectedSoft: 'var(--chart-projected-soft)',
} as const

const dateTime = (value?: string | null) => value
  ? new Intl.DateTimeFormat('ru-BY', { dateStyle: 'short', timeStyle: 'short', timeZone: 'Europe/Minsk' }).format(new Date(value))
  : '—'
const shortTime = (value: string) => new Intl.DateTimeFormat('ru-BY', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Minsk' }).format(new Date(value))

function cutoffLabel(snapshot: Snapshot) {
  if (snapshot.no_competition) return 'Конкурса пока нет'
  if (snapshot.estimated_cutoff_min == null) return 'Недостаточно данных'
  return snapshot.estimated_cutoff_min === snapshot.estimated_cutoff_max
    ? String(snapshot.estimated_cutoff_min)
    : `${snapshot.estimated_cutoff_min}–${snapshot.estimated_cutoff_max}`
}

function statusStyle(status: string) {
  if (status.includes('не проходит')) return 'border-danger/30 bg-danger/10 text-danger'
  if (status.includes('Погранич')) return 'border-warning/30 bg-warning/10 text-warning'
  if (status.includes('Недостаточно')) return 'bg-slate-50 text-slate-600 border-slate-200'
  return 'border-success/30 bg-success/10 text-success'
}

function Metric({ label, value, hint, icon: Icon }: { label: string; value: string | number; hint?: string; icon: typeof Users }) {
  return <div className="metric">
    <div className="mb-3 flex items-center justify-between text-accent"><span className="eyebrow">{label}</span><Icon size={17} /></div>
    <div className="text-2xl font-semibold tracking-tight">{value}</div>
    {hint && <div className="mt-1 text-xs text-text-tertiary">{hint}</div>}
  </div>
}

export default function MonitorPage() {
  useDocumentTitle('Монитор поступления · Куда поступать')

  const [specialties, setSpecialties] = useState<Specialty[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [latest, setLatest] = useState<Snapshot | null>(null)
  const [history, setHistory] = useState<Snapshot[]>([])
  const [collector, setCollector] = useState<CollectorStatus | null>(null)
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [config, setConfig] = useState<PublicConfig | null>(null)
  const [snapshotState, setSnapshotState] = useState<SnapshotState>('unknown')
  const [score, setScore] = useState(276)
  const [loading, setLoading] = useState(true)
  const [reloading, setReloading] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(async (id?: number | null) => {
    setError('')
    try {
      const list = specialties.length ? specialties : await api.specialties()
      if (!specialties.length) setSpecialties(list)
      const target = id ?? selectedId ?? list[0]?.id
      if (!target) throw new Error('Специальность для мониторинга пока не настроена.')
      setSelectedId(target)
      const [currentResult, historyResult, statusResult, healthResult, configResult] = await Promise.allSettled([
        api.latest(target),
        api.history(target),
        api.status(),
        api.health(),
        api.config(),
      ])
      let partialFailure = false

      if (currentResult.status === 'fulfilled') {
        setLatest(currentResult.value)
        setSnapshotState('available')
        setScore((previous) => previous === 276 ? currentResult.value.user_score : previous)
      } else if (currentResult.reason instanceof ApiError && currentResult.reason.status === 404) {
        setSnapshotState((current) => current === 'available' ? current : 'empty')
      } else {
        partialFailure = true
      }
      if (historyResult.status === 'fulfilled') setHistory(historyResult.value)
      else partialFailure = true
      if (statusResult.status === 'fulfilled') setCollector(statusResult.value)
      else partialFailure = true
      if (healthResult.status === 'fulfilled') setHealth(healthResult.value)
      else partialFailure = true
      if (configResult.status === 'fulfilled') setConfig(configResult.value)
      else partialFailure = true

      if (partialFailure) {
        setError('Не удалось загрузить часть данных мониторинга. Уже полученный корректный снимок сохранён на экране.')
      }
    } catch {
      setError('Не удалось загрузить данные мониторинга. Проверьте соединение и повторите загрузку.')
    }
    finally { setLoading(false) }
  }, [selectedId, specialties])

  useEffect(() => {
    const initialLoad = window.setTimeout(() => { void load() }, 0)
    return () => window.clearTimeout(initialLoad)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const orderedHistory = useMemo(() => [...history].reverse(), [history])
  const previous = history[1]
  const applicationsDelta = latest && previous ? latest.applications_total - previous.applications_total : 0
  const scoreRanges = useMemo(() => latest ? Object.entries(latest.distribution)
    .map(([range, count]) => ({ range: range.replace('-', '–'), count, min: Number(range.split('-')[0]), max: Number(range.split('-')[1]) })) : [], [latest])
  const whatIf = useMemo(() => {
    if (!latest) return null
    const above = scoreRanges.filter((range) => range.min > score).reduce((sum, range) => sum + range.count, 0)
    const cutoffMin = latest.estimated_cutoff_min
    const cutoffMax = latest.estimated_cutoff_max
    let status = 'Недостаточно данных'
    if (latest.no_competition) status = 'Уверенно проходит'
    else if (cutoffMin != null && cutoffMax != null) {
      status = score > cutoffMax ? (score - cutoffMax >= 5 ? 'Уверенно проходит' : 'Пока проходит')
        : score >= cutoffMin ? 'Пограничная ситуация' : 'Пока не проходит'
    }
    return { position: above + 1, status }
  }, [latest, score, scoreRanges])

  const retryLoad = async () => {
    setReloading(true)
    try { await load(selectedId) }
    finally { setReloading(false) }
  }

  const collectorRefreshing = health?.refresh_in_progress === true || collector?.state === 'refreshing'
  const lastRunStatus = collector?.last_run?.status
    ?? (collector?.state !== 'refreshing' ? collector?.state : null)
  const collectorFailed = lastRunStatus === 'error' || Boolean(health?.last_error)
  const collectorLabel = collectorRefreshing
    ? 'Проверяем данные БГЭУ'
    : lastRunStatus === 'not_modified'
      ? 'Источник проверен, изменений нет'
      : lastRunStatus === 'success'
        ? 'Получены новые данные'
        : lastRunStatus === 'error'
          ? 'Последняя проверка источника завершилась ошибкой'
          : 'Ожидаем первую проверку источника'
  const staleAfterSeconds = (config?.stale_after_minutes ?? 30) * 60
  const sourceIsStale = latest?.source_age_seconds !== null
    && latest?.source_age_seconds !== undefined
    && latest.source_age_seconds > staleAfterSeconds

  return <div className="page-shell">
    <section aria-labelledby="monitor-title" className="border-b border-text-primary/10 bg-text-primary text-white">
      <div className="page-container flex flex-col gap-5 py-7 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4"><div aria-hidden="true" className="grid size-12 place-items-center rounded-2xl bg-white/10"><GraduationCap /></div><div><div className="text-xs font-bold uppercase tracking-[.2em] text-white/70">Вступительная кампания · БГЭУ</div><h1 id="monitor-title" className="mt-1 text-2xl font-semibold tracking-[-0.02em]">Монитор поступления</h1></div></div>
        <div className="flex flex-wrap gap-3">
          {specialties.length > 1 && <select value={selectedId ?? ''} onChange={(event) => void load(Number(event.target.value))} className="rounded-xl border border-white/20 bg-white/10 px-4 py-2 text-sm outline-none"><option className="text-text-primary" value="">Специальность</option>{specialties.map((item) => <option className="text-text-primary" key={item.id} value={item.id}>{item.display_name}</option>)}</select>}
        </div>
      </div>
    </section>

    <div className="page-container space-y-6 py-7 lg:py-10">
      {loading ? <div className="grid min-h-72 place-items-center" role="status"><div className="text-center"><RefreshCw aria-hidden="true" className="mx-auto mb-3 animate-spin text-accent"/><p>Загружаем конкурсную ситуацию…</p></div></div> : <>
      <section aria-labelledby="public-monitor-status-title" className="panel p-5 sm:p-6">
        <div className="eyebrow">Состояние мониторинга</div>
        <h2 className="mt-2 text-xl font-semibold" id="public-monitor-status-title">Автоматическая проверка источника</h2>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="surface-sunken p-4">
            <div className="text-xs font-bold uppercase tracking-wider text-text-tertiary">Автоматическое обновление</div>
            <p className="mt-2 font-semibold" role="status">
              {health === null
                ? 'Состояние автоматического обновления уточняется'
                : health.scheduler_running
                  ? 'Автоматическое обновление включено'
                  : 'Автоматическое обновление сейчас недоступно'}
            </p>
          </div>
          <div className="surface-sunken p-4">
            <div className="text-xs font-bold uppercase tracking-wider text-text-tertiary">Последний результат</div>
            <p className="mt-2 font-semibold" role="status">{collectorLabel}</p>
            <p className="mt-1 text-sm text-text-secondary">Последняя успешная проверка: {dateTime(health?.last_success_at ?? latest?.last_checked_at)}</p>
          </div>
          <div className="surface-sunken p-4">
            <div className="text-xs font-bold uppercase tracking-wider text-text-tertiary">Следующая проверка</div>
            <p className="mt-2 font-semibold">{dateTime(collector?.next_run_at)}</p>
          </div>
          <div className="surface-sunken p-4">
            <div className="text-xs font-bold uppercase tracking-wider text-text-tertiary">Текущая активность</div>
            <p className="mt-2 font-semibold" role="status">
              {collectorRefreshing ? 'Проверяем данные БГЭУ' : 'Фоновая проверка не выполняется'}
            </p>
          </div>
        </div>
      </section>
      {error && <div role="alert" className="state-crossfade flex flex-col gap-4 rounded-2xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger sm:flex-row sm:items-start sm:justify-between"><div className="flex min-w-0 gap-3"><ShieldAlert aria-hidden="true" className="shrink-0" size={20}/><div><b>Не удалось полностью обновить страницу.</b><div className="break-words">{error}</div>{latest && <div className="mt-1">Показан последний корректный снимок.</div>}</div></div><button className="min-h-11 shrink-0 rounded-xl border border-danger/40 bg-elevated px-4 py-2.5 font-bold text-danger focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus" disabled={reloading} onClick={() => void retryLoad()} type="button"><RefreshCw aria-hidden="true" className={reloading ? 'mr-2 inline animate-spin' : 'mr-2 inline'} size={16}/>{reloading ? 'Загружаем…' : 'Повторить загрузку'}</button></div>}
      {collectorFailed && <div role="alert" className="flex gap-3 rounded-2xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger"><ShieldAlert aria-hidden="true" className="shrink-0" size={20}/><div><b>Последняя проверка источника завершилась ошибкой.</b>{latest && <p className="mt-1">Ниже показан последний корректный снимок. Автоматическая проверка повторится, когда сборщик будет доступен.</p>}{!latest && <p className="mt-1">Первый корректный снимок пока не получен. Автоматическая проверка повторится, когда сборщик будет доступен.</p>}</div></div>}
      {sourceIsStale && <div role="status" className="flex gap-3 rounded-2xl border border-warning/30 bg-warning/10 p-4 text-sm text-warning"><AlertTriangle aria-hidden="true" className="shrink-0" size={20}/><div><b>БГЭУ давно не обновлял данные на своей стороне.</b> Платформа могла проверить источник недавно, но timestamp внутри опубликованных БГЭУ данных остаётся старым. Это не означает сбой сборщика.</div></div>}
      {snapshotState === 'empty' && !latest ? <div className="panel p-8 text-center"><BookOpen aria-hidden="true" className="mx-auto mb-3 text-accent"/><h2 className="text-xl font-bold">Первый корректный снимок конкурсной ситуации ещё не получен</h2><p className="mt-2 text-text-secondary">Автоматическая проверка повторится, когда источник будет доступен.</p><button className="mt-5 min-h-11 rounded-xl bg-accent px-4 py-2.5 font-bold text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2 disabled:cursor-wait disabled:opacity-60" disabled={reloading} onClick={() => void retryLoad()} type="button"><RefreshCw aria-hidden="true" className={reloading ? 'mr-2 inline animate-spin' : 'mr-2 inline'} size={16}/>{reloading ? 'Загружаем…' : 'Повторить загрузку'}</button></div> : latest ? <>
        <section className="panel overflow-hidden">
          <div className="grid lg:grid-cols-[1.2fr_.8fr]">
            <div className="p-6 sm:p-8">
              <div className="eyebrow">Основная специальность</div>
              <h2 className="mt-3 max-w-3xl text-3xl font-semibold leading-tight tracking-tight sm:text-4xl">{latest.specialty}</h2>
              <div className="mt-3 text-sm text-text-secondary">{latest.study_form[0].toUpperCase() + latest.study_form.slice(1)} форма · {latest.funding_type} основа</div>
              <div className="mt-6 flex flex-wrap items-center gap-3"><span className={`rounded-full border px-4 py-2 text-sm font-bold ${statusStyle(whatIf?.status ?? latest.user_status)}`}><CheckCircle2 className="mr-2 inline" size={16}/>{whatIf?.status ?? latest.user_status}</span><a href={latest.source_url} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-sm font-semibold text-accent hover:underline">Официальный источник <ArrowUpRight size={15}/></a></div>
            </div>
            <div className="bg-accent-soft/70 p-6 sm:p-8">
              <div className="eyebrow">Мой балл · сценарий</div>
              <div className="mt-3 flex items-center gap-4"><input aria-label="Мой балл" type="number" min="0" max="500" value={score} onChange={(event) => setScore(Number(event.target.value))} className="w-32 rounded-2xl border border-accent/20 bg-white px-4 py-3 text-3xl font-semibold outline-none focus:ring-2 focus:ring-focus/30"/><div className="text-sm text-text-secondary">Можно проверить другой балл.<br/>Серверное значение: {latest.user_score}</div></div>
              <div className="mt-5 text-sm"><span className="text-text-tertiary">Предполагаемое место:</span> <b>≈ {whatIf?.position ?? latest.estimated_user_position ?? '—'}</b></div>
            </div>
          </div>
          <div className="grid gap-3 border-t border-text-primary/10 p-4 sm:grid-cols-2 lg:grid-cols-4 sm:p-6">
            <Metric label="План приема" value={latest.admission_plan} hint="мест" icon={Target}/>
            <Metric label="Подано заявлений" value={latest.applications_total} hint={applicationsDelta ? `${applicationsDelta > 0 ? '+' : ''}${applicationsDelta} с прошлого снимка` : 'без изменений'} icon={Users}/>
            <Metric label="Текущий конкурс" value={`${latest.competition.toFixed(2)}×`} hint="заявления / места" icon={TrendingUp}/>
            <Metric label="Предполагаемый порог" value={cutoffLabel(latest)} hint="по текущему распределению" icon={Activity}/>
          </div>
        </section>

        <section className="grid gap-6 lg:grid-cols-2">
          <div className="panel min-w-0 p-5 sm:p-6"><div className="mb-6"><div className="eyebrow">Динамика</div><h3 className="mt-2 text-xl font-bold">Предполагаемый порог</h3></div><div className="h-72 min-w-0"><ResponsiveContainer height="100%" width="100%"><LineChart accessibilityLayer data={orderedHistory}><CartesianGrid stroke={chartColors.grid} strokeDasharray="3 3"/><XAxis dataKey="fetched_at" tick={{fontSize:11}} tickFormatter={shortTime}/><YAxis domain={['dataMin - 5','dataMax + 5']} tick={{fontSize:11}}/><Tooltip labelFormatter={(v) => dateTime(String(v))}/><Line connectNulls dataKey="estimated_cutoff_min" dot={false} isAnimationActive={false} name="Нижняя граница" stroke={chartColors.projected} strokeWidth={3} type="monotone"/><Line connectNulls dataKey="estimated_cutoff_max" dot={false} isAnimationActive={false} name="Верхняя граница" stroke={chartColors.projectedSoft} strokeWidth={2} type="monotone"/></LineChart></ResponsiveContainer></div></div>
          <div className="panel min-w-0 p-5 sm:p-6"><div className="mb-6"><div className="eyebrow">Динамика</div><h3 className="mt-2 text-xl font-bold">Количество заявлений</h3></div><div className="h-72 min-w-0"><ResponsiveContainer height="100%" width="100%"><AreaChart accessibilityLayer data={orderedHistory}><defs><linearGradient id="applications" x1="0" x2="0" y1="0" y2="1"><stop offset="5%" stopColor={chartColors.observed} stopOpacity={0.2}/><stop offset="95%" stopColor={chartColors.observed} stopOpacity={0}/></linearGradient></defs><CartesianGrid stroke={chartColors.grid} strokeDasharray="3 3"/><XAxis dataKey="fetched_at" tick={{fontSize:11}} tickFormatter={shortTime}/><YAxis allowDecimals={false} tick={{fontSize:11}}/><Tooltip labelFormatter={(v) => dateTime(String(v))}/><Area dataKey="applications_total" fill="url(#applications)" isAnimationActive={false} name="Заявления" stroke={chartColors.observed} strokeWidth={3} type="monotone"/></AreaChart></ResponsiveContainer></div></div>
        </section>

        <section className="panel min-w-0 p-5 sm:p-6"><div className="mb-6"><div className="eyebrow">Срез на {dateTime(latest.fetched_at)}</div><h3 className="mt-2 text-xl font-bold">Распределение абитуриентов по баллам</h3></div><div className="h-80 min-w-0"><ResponsiveContainer height="100%" width="100%"><BarChart accessibilityLayer data={scoreRanges}><CartesianGrid stroke={chartColors.grid} strokeDasharray="3 3"/><XAxis dataKey="range" interval="preserveStartEnd" tick={{fontSize:10}}/><YAxis allowDecimals={false} tick={{fontSize:11}}/><Tooltip/><Bar dataKey="count" fill={chartColors.observed} isAnimationActive={false} name="Абитуриенты" radius={[5,5,0,0]}/></BarChart></ResponsiveContainer></div></section>

        <section className="panel overflow-hidden"><div className="flex flex-col gap-2 border-b border-text-primary/10 p-5 sm:flex-row sm:items-end sm:justify-between sm:p-6"><div><div className="eyebrow">Журнал наблюдений</div><h3 className="mt-2 text-xl font-bold">История обновлений</h3></div><div className="text-xs text-text-tertiary">Показаны только изменения данных</div></div><div className="overflow-x-auto"><table className="w-full min-w-[760px] text-left text-sm"><thead className="bg-background/70 text-xs uppercase tracking-wider text-text-tertiary"><tr><th className="px-6 py-4">Получено</th><th className="px-4 py-4">Заявлений</th><th className="px-4 py-4">Конкурс</th><th className="px-4 py-4">Порог</th><th className="px-4 py-4">Место</th><th className="px-6 py-4">Статус</th></tr></thead><tbody>{history.map((item) => <tr key={item.id} className="border-t border-text-primary/5"><td className="px-6 py-4 font-medium">{dateTime(item.fetched_at)}</td><td className="px-4 py-4">{item.applications_total}</td><td className="px-4 py-4">{item.competition.toFixed(2)}×</td><td className="px-4 py-4">{cutoffLabel(item)}</td><td className="px-4 py-4">{item.estimated_user_position ? `≈ ${item.estimated_user_position}` : '—'}</td><td className="px-6 py-4"><span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${statusStyle(item.user_status)}`}>{item.user_status}</span></td></tr>)}</tbody></table></div></section>

        <section className="grid gap-4 lg:grid-cols-[1fr_auto]"><div className="rounded-2xl border border-warning/30 bg-warning/10 p-5 text-sm text-warning"><div className="flex gap-3"><AlertTriangle aria-hidden="true" className="shrink-0" size={21}/><div><b>Это автоматическая оценка на основании текущих заявлений, а не официальный итоговый проходной балл.</b><p className="mt-1 text-warning/80">Порог может измениться; диапазоны баллов не позволяют определить точное место внутри группы.</p></div></div></div><div className="rounded-2xl border border-border bg-elevated p-5 text-sm"><div className="flex items-center gap-2 font-semibold"><Clock3 aria-hidden="true" size={18} className="text-accent"/>Время данных</div><div className="mt-2 text-text-secondary">Источник проверен платформой: {dateTime(health?.last_success_at ?? latest.last_checked_at ?? latest.fetched_at)}</div><div className="text-text-secondary">Время данных БГЭУ: {dateTime(latest.source_updated_at)}</div></div></section>
      </> : null}
      </>}
    </div>
  </div>
}
