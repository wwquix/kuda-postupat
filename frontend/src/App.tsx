import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Activity, AlertTriangle, ArrowUpRight, BookOpen, CheckCircle2, Clock3,
  GraduationCap, RefreshCw, ShieldAlert, Target, TrendingUp, Users,
} from 'lucide-react'
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { api } from './api'
import type { CollectorStatus, Snapshot, Specialty } from './types'

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
  if (status.includes('не проходит')) return 'bg-red-50 text-red-700 border-red-200'
  if (status.includes('Погранич')) return 'bg-amber-50 text-amber-800 border-amber-200'
  if (status.includes('Недостаточно')) return 'bg-slate-50 text-slate-600 border-slate-200'
  return 'bg-emerald-50 text-emerald-800 border-emerald-200'
}

function Metric({ label, value, hint, icon: Icon }: { label: string; value: string | number; hint?: string; icon: typeof Users }) {
  return <div className="metric">
    <div className="mb-3 flex items-center justify-between text-moss"><span className="eyebrow">{label}</span><Icon size={17} /></div>
    <div className="text-2xl font-extrabold tracking-tight">{value}</div>
    {hint && <div className="mt-1 text-xs text-ink/55">{hint}</div>}
  </div>
}

export default function App() {
  const [specialties, setSpecialties] = useState<Specialty[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [latest, setLatest] = useState<Snapshot | null>(null)
  const [history, setHistory] = useState<Snapshot[]>([])
  const [collector, setCollector] = useState<CollectorStatus | null>(null)
  const [score, setScore] = useState(276)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(async (id?: number | null) => {
    setError('')
    try {
      const list = specialties.length ? specialties : await api.specialties()
      if (!specialties.length) setSpecialties(list)
      const target = id ?? selectedId ?? list[0]?.id
      if (!target) throw new Error('Данные еще не собраны. Подождите первое обновление сборщика.')
      setSelectedId(target)
      const [current, items, status] = await Promise.all([api.latest(target), api.history(target), api.status()])
      setLatest(current); setHistory(items); setCollector(status)
      setScore((previous) => previous === 276 ? current.user_score : previous)
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Не удалось загрузить данные') }
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

  async function refresh() {
    const token = window.prompt('Введите MANUAL_REFRESH_TOKEN')
    if (!token) return
    setRefreshing(true); setError('')
    try { await api.refresh(token); await load(selectedId) }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Ошибка обновления') }
    finally { setRefreshing(false) }
  }

  if (loading) return <div className="grid min-h-screen place-items-center bg-cream"><div className="text-center"><RefreshCw className="mx-auto mb-3 animate-spin text-moss"/><p>Загружаем конкурсную ситуацию…</p></div></div>

  return <div className="min-h-screen bg-[radial-gradient(circle_at_top_right,_rgba(109,190,148,0.18),_transparent_32%),linear-gradient(180deg,#f8f7f1_0%,#f2f0e7_100%)]">
    <header className="border-b border-ink/10 bg-ink text-white">
      <div className="mx-auto flex max-w-7xl flex-col gap-5 px-5 py-7 sm:flex-row sm:items-center sm:justify-between lg:px-8">
        <div className="flex items-center gap-4"><div className="grid size-12 place-items-center rounded-2xl bg-white/10"><GraduationCap /></div><div><div className="text-xs font-bold uppercase tracking-[.2em] text-emerald-200">Вступительная кампания · БГЭУ</div><h1 className="mt-1 text-2xl font-bold">Монитор поступления</h1></div></div>
        <div className="flex flex-wrap gap-3">
          {specialties.length > 1 && <select value={selectedId ?? ''} onChange={(event) => void load(Number(event.target.value))} className="rounded-xl border border-white/20 bg-white/10 px-4 py-2 text-sm outline-none"><option className="text-ink" value="">Специальность</option>{specialties.map((item) => <option className="text-ink" key={item.id} value={item.id}>{item.display_name}</option>)}</select>}
          <button onClick={() => void refresh()} disabled={refreshing} className="flex items-center gap-2 rounded-xl bg-white px-4 py-2 text-sm font-semibold text-ink transition hover:bg-emerald-50 disabled:opacity-60"><RefreshCw size={16} className={refreshing ? 'animate-spin' : ''}/>Обновить</button>
        </div>
      </div>
    </header>

    <main className="mx-auto max-w-7xl space-y-6 px-5 py-7 lg:px-8 lg:py-10">
      {error && <div className="flex gap-3 rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800"><ShieldAlert className="shrink-0" size={20}/><div><b>Не удалось получить свежие данные.</b><div>{error}</div>{latest && <div className="mt-1">Показан последний корректный снимок.</div>}</div></div>}
      {latest?.is_stale && <div className="flex gap-3 rounded-2xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900"><AlertTriangle className="shrink-0" size={20}/><div><b>Источник не обновлял данные более 30 минут.</b> Последняя проверка могла пройти успешно, но время данных на стороне БГЭУ устарело.</div></div>}
      {!latest ? <div className="panel p-8 text-center"><BookOpen className="mx-auto mb-3 text-moss"/><h2 className="text-xl font-bold">Корректных снимков пока нет</h2><p className="mt-2 text-ink/60">Запустите ручное обновление или дождитесь плановой проверки.</p></div> : <>
        <section className="panel overflow-hidden">
          <div className="grid lg:grid-cols-[1.2fr_.8fr]">
            <div className="p-6 sm:p-8">
              <div className="eyebrow">Основная специальность</div>
              <h2 className="mt-3 max-w-3xl text-3xl font-extrabold leading-tight tracking-tight sm:text-4xl">{latest.specialty}</h2>
              <div className="mt-3 text-sm text-ink/60">{latest.study_form[0].toUpperCase() + latest.study_form.slice(1)} форма · {latest.funding_type} основа</div>
              <div className="mt-6 flex flex-wrap items-center gap-3"><span className={`rounded-full border px-4 py-2 text-sm font-bold ${statusStyle(whatIf?.status ?? latest.user_status)}`}><CheckCircle2 className="mr-2 inline" size={16}/>{whatIf?.status ?? latest.user_status}</span><a href={latest.source_url} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-sm font-semibold text-moss hover:underline">Официальный источник <ArrowUpRight size={15}/></a></div>
            </div>
            <div className="bg-mint/70 p-6 sm:p-8">
              <div className="eyebrow">Мой балл · сценарий</div>
              <div className="mt-3 flex items-center gap-4"><input aria-label="Мой балл" type="number" min="0" max="500" value={score} onChange={(event) => setScore(Number(event.target.value))} className="w-32 rounded-2xl border border-moss/20 bg-white px-4 py-3 text-3xl font-extrabold outline-none focus:ring-2 focus:ring-moss/30"/><div className="text-sm text-ink/60">Можно проверить другой балл.<br/>Серверное значение: {latest.user_score}</div></div>
              <div className="mt-5 text-sm"><span className="text-ink/55">Предполагаемое место:</span> <b>≈ {whatIf?.position ?? latest.estimated_user_position ?? '—'}</b></div>
            </div>
          </div>
          <div className="grid gap-3 border-t border-ink/10 p-4 sm:grid-cols-2 lg:grid-cols-4 sm:p-6">
            <Metric label="План приема" value={latest.admission_plan} hint="мест" icon={Target}/>
            <Metric label="Подано заявлений" value={latest.applications_total} hint={applicationsDelta ? `${applicationsDelta > 0 ? '+' : ''}${applicationsDelta} с прошлого снимка` : 'без изменений'} icon={Users}/>
            <Metric label="Текущий конкурс" value={`${latest.competition.toFixed(2)}×`} hint="заявления / места" icon={TrendingUp}/>
            <Metric label="Предполагаемый порог" value={cutoffLabel(latest)} hint="по текущему распределению" icon={Activity}/>
          </div>
        </section>

        <section className="grid gap-6 lg:grid-cols-2">
          <div className="panel p-5 sm:p-6"><div className="mb-6"><div className="eyebrow">Динамика</div><h3 className="mt-2 text-xl font-bold">Предполагаемый порог</h3></div><div className="h-72"><ResponsiveContainer width="100%" height="100%"><LineChart data={orderedHistory}><CartesianGrid strokeDasharray="3 3" stroke="#dfe7df"/><XAxis dataKey="fetched_at" tickFormatter={shortTime} tick={{fontSize:11}}/><YAxis domain={['dataMin - 5','dataMax + 5']} tick={{fontSize:11}}/><Tooltip labelFormatter={(v) => dateTime(String(v))}/><Line type="monotone" dataKey="estimated_cutoff_min" name="Нижняя граница" stroke="#19664a" strokeWidth={3} dot={false} connectNulls/><Line type="monotone" dataKey="estimated_cutoff_max" name="Верхняя граница" stroke="#d99b35" strokeWidth={2} dot={false} connectNulls/></LineChart></ResponsiveContainer></div></div>
          <div className="panel p-5 sm:p-6"><div className="mb-6"><div className="eyebrow">Динамика</div><h3 className="mt-2 text-xl font-bold">Количество заявлений</h3></div><div className="h-72"><ResponsiveContainer width="100%" height="100%"><AreaChart data={orderedHistory}><defs><linearGradient id="applications" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#19664a" stopOpacity={.35}/><stop offset="95%" stopColor="#19664a" stopOpacity={0}/></linearGradient></defs><CartesianGrid strokeDasharray="3 3" stroke="#dfe7df"/><XAxis dataKey="fetched_at" tickFormatter={shortTime} tick={{fontSize:11}}/><YAxis tick={{fontSize:11}} allowDecimals={false}/><Tooltip labelFormatter={(v) => dateTime(String(v))}/><Area type="monotone" dataKey="applications_total" name="Заявления" stroke="#19664a" fill="url(#applications)" strokeWidth={3}/></AreaChart></ResponsiveContainer></div></div>
        </section>

        <section className="panel p-5 sm:p-6"><div className="mb-6"><div className="eyebrow">Срез на {dateTime(latest.fetched_at)}</div><h3 className="mt-2 text-xl font-bold">Распределение абитуриентов по баллам</h3></div><div className="h-80"><ResponsiveContainer width="100%" height="100%"><BarChart data={scoreRanges}><CartesianGrid strokeDasharray="3 3" stroke="#dfe7df"/><XAxis dataKey="range" interval="preserveStartEnd" tick={{fontSize:10}}/><YAxis allowDecimals={false} tick={{fontSize:11}}/><Tooltip/><Bar dataKey="count" name="Абитуриенты" fill="#19664a" radius={[5,5,0,0]}/></BarChart></ResponsiveContainer></div></section>

        <section className="panel overflow-hidden"><div className="flex flex-col gap-2 border-b border-ink/10 p-5 sm:flex-row sm:items-end sm:justify-between sm:p-6"><div><div className="eyebrow">Журнал наблюдений</div><h3 className="mt-2 text-xl font-bold">История обновлений</h3></div><div className="text-xs text-ink/50">Показаны только изменения данных</div></div><div className="overflow-x-auto"><table className="w-full min-w-[760px] text-left text-sm"><thead className="bg-cream/70 text-xs uppercase tracking-wider text-ink/55"><tr><th className="px-6 py-4">Получено</th><th className="px-4 py-4">Заявлений</th><th className="px-4 py-4">Конкурс</th><th className="px-4 py-4">Порог</th><th className="px-4 py-4">Место</th><th className="px-6 py-4">Статус</th></tr></thead><tbody>{history.map((item) => <tr key={item.id} className="border-t border-ink/5"><td className="px-6 py-4 font-medium">{dateTime(item.fetched_at)}</td><td className="px-4 py-4">{item.applications_total}</td><td className="px-4 py-4">{item.competition.toFixed(2)}×</td><td className="px-4 py-4">{cutoffLabel(item)}</td><td className="px-4 py-4">{item.estimated_user_position ? `≈ ${item.estimated_user_position}` : '—'}</td><td className="px-6 py-4"><span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${statusStyle(item.user_status)}`}>{item.user_status}</span></td></tr>)}</tbody></table></div></section>

        <section className="grid gap-4 lg:grid-cols-[1fr_auto]"><div className="rounded-2xl border border-amber-300 bg-amber-50 p-5 text-sm text-amber-950"><div className="flex gap-3"><AlertTriangle className="shrink-0" size={21}/><div><b>Это автоматическая оценка на основании текущих заявлений, а не официальный итоговый проходной балл.</b><p className="mt-1 text-amber-900/75">Порог может измениться; диапазоны баллов не позволяют определить точное место внутри группы.</p></div></div></div><div className="rounded-2xl border border-ink/10 bg-white p-5 text-sm"><div className="flex items-center gap-2 font-semibold"><Clock3 size={18} className="text-moss"/>Состояние сборщика</div><div className="mt-2 text-ink/60">Последняя проверка: {dateTime(latest.last_checked_at ?? latest.fetched_at)}</div><div className="text-ink/60">Источник обновлен: {dateTime(latest.source_updated_at)}</div><div className="mt-2"><span className={`inline-block size-2 rounded-full ${collector?.state === 'error' ? 'bg-red-500' : 'bg-emerald-500'}`}/> <span className="ml-1">{collector?.state === 'error' ? 'ошибка источника' : 'работает'}</span></div></div></section>
      </>}
    </main>
  </div>
}
