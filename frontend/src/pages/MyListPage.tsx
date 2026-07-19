import { ArrowRightLeft, BellRing, LoaderCircle, RefreshCw, Send } from 'lucide-react'
import { type FormEvent, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { apiValueLabel } from '../catalogPresentation'
import { SaveControl } from '../components/SaveControl'
import {
  MAX_COMPARED_PROGRAMS,
  programComparisonPath,
  programIdentityFor,
  programIdentityKey,
} from '../programComparison'
import type { ProgramIdentity } from '../programComparison'
import type { ProgramWatchEvent, SavedProgram, SavedUniversity } from '../types'
import { useProfile } from '../useProfile'
import { useDocumentTitle } from '../useDocumentTitle'

const MIN_SCORE = 0
const MAX_SCORE = 500
const eventTimeFormatter = new Intl.DateTimeFormat('ru-BY', {
  dateStyle: 'medium',
  timeStyle: 'short',
})

function TelegramNotifications() {
  const profile = useProfile()
  const { loadTelegramAvailability } = profile
  const [operation, setOperation] = useState<'challenge' | 'refresh' | 'unlink' | null>(null)
  const [confirmingUnlink, setConfirmingUnlink] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [clock, setClock] = useState(Date.now)
  const status = profile.telegramLinkStatus
  const challengeExpiry = status?.challenge_expires_at ?? null
  const challengeExpired = challengeExpiry !== null && Date.parse(challengeExpiry) <= clock
  const localChallengeActive = profile.telegramLinkChallenge !== null
    && Date.parse(profile.telegramLinkChallenge.expires_at) > clock

  useEffect(() => {
    void loadTelegramAvailability()
  }, [loadTelegramAvailability])

  useEffect(() => {
    const interval = window.setInterval(() => setClock(Date.now()), 30_000)
    return () => window.clearInterval(interval)
  }, [])

  const createChallenge = async (openAfterCreation = false) => {
    if (operation !== null) return
    setOperation('challenge')
    setError(null)
    try {
      const challenge = await profile.createTelegramLinkChallenge()
      if (openAfterCreation) {
        window.open(challenge.deep_link, '_blank', 'noopener,noreferrer')
      }
    } catch {
      setError('Не удалось подготовить подключение. Попробуйте ещё раз.')
    } finally {
      setOperation(null)
    }
  }

  const refreshStatus = async () => {
    if (operation !== null) return
    setOperation('refresh')
    setError(null)
    try {
      await profile.refreshTelegramLinkStatus()
    } catch {
      setError('Не удалось проверить подключение. Попробуйте ещё раз.')
    } finally {
      setOperation(null)
    }
  }

  const unlink = async () => {
    if (operation !== null) return
    setOperation('unlink')
    setError(null)
    try {
      await profile.unlinkTelegram()
      setConfirmingUnlink(false)
    } catch {
      setError('Не удалось отключить Telegram. Попробуйте ещё раз.')
    } finally {
      setOperation(null)
    }
  }

  return <section aria-labelledby="telegram-notifications-title" className="panel min-w-0 p-5 sm:p-6">
    <h2 className="text-2xl font-semibold" id="telegram-notifications-title">Уведомления в Telegram</h2>

    {profile.telegramStatusState === 'ready' && profile.telegramEnabled === false && <div
      aria-live="polite"
      className="mt-4 rounded-2xl border border-text-primary/10 bg-background/65 p-4"
      role="status"
    >
      <p className="font-semibold">Telegram-уведомления появятся позже</p>
      <p className="mt-2 leading-7 text-text-secondary">
        Сохранённые программы, наблюдения и история изменений продолжают работать без Telegram.
      </p>
    </div>}

    {profile.telegramStatusState === 'loading' && <p
      aria-live="polite"
      className="mt-4 flex items-center gap-2 text-text-secondary"
      role="status"
    >
      <LoaderCircle aria-hidden="true" className="animate-spin" size={18} />Проверяем подключение…
    </p>}

    {profile.telegramStatusState === 'error' && <div className="mt-4" role="alert">
      <p className="font-semibold text-danger">Не удалось загрузить статус Telegram.</p>
      <button
        className="mt-3 inline-flex min-h-11 items-center gap-2 rounded-xl border border-accent/25 bg-white px-4 py-2.5 font-bold text-accent disabled:cursor-wait disabled:opacity-60"
        disabled={operation !== null}
        onClick={() => void (profile.telegramEnabled === null
          ? profile.loadTelegramAvailability()
          : refreshStatus())}
        type="button"
      >
        <RefreshCw aria-hidden="true" size={17} />Повторить запрос
      </button>
    </div>}

    {profile.telegramEnabled === true && profile.telegramStatusState === 'ready' && status?.linked && <div className="mt-4">
      <p aria-live="polite" className="inline-flex items-center gap-2 font-semibold text-success" role="status">
        <Send aria-hidden="true" size={18} />Telegram подключён
      </p>
      {status.linked_at && <p className="mt-2 text-sm text-text-secondary">
        Подключено {eventTimeFormatter.format(new Date(status.linked_at))}.
      </p>}
      {!confirmingUnlink
        ? <button
          className="mt-4 min-h-11 rounded-xl border border-danger/30 bg-elevated px-4 py-2.5 font-bold text-danger"
          onClick={() => setConfirmingUnlink(true)}
          type="button"
        >Отключить Telegram</button>
        : <div aria-live="polite" className="mt-4 rounded-2xl border border-danger/30 bg-danger/10 p-4">
          <p className="font-semibold">Отключить уведомления для этого анонимного профиля?</p>
          <div className="mt-3 flex flex-wrap gap-3">
            <button
              className="min-h-11 rounded-xl bg-danger px-4 py-2.5 font-bold text-white disabled:cursor-wait disabled:opacity-60"
              disabled={operation !== null}
              onClick={() => void unlink()}
              type="button"
            >{operation === 'unlink' ? 'Отключаем…' : 'Подтвердить отключение'}</button>
            <button
              className="min-h-11 rounded-xl border border-text-primary/15 bg-white px-4 py-2.5 font-bold"
              disabled={operation !== null}
              onClick={() => setConfirmingUnlink(false)}
              type="button"
            >Отмена</button>
          </div>
        </div>}
    </div>}

    {profile.telegramEnabled === true && profile.telegramStatusState === 'ready' && status && !status.linked && <div className="mt-4">
      <p className="max-w-3xl leading-7 text-text-secondary">
        Telegram получает новые изменения из включённых наблюдений БГЭУ. Отключение Telegram не выключает наблюдения.
      </p>
      {challengeExpiry && !challengeExpired && <div className="mt-4 rounded-2xl bg-background/65 p-4">
        <p className="font-semibold">Запрос на подключение действует до{' '}
          <time dateTime={challengeExpiry}>{eventTimeFormatter.format(new Date(challengeExpiry))}</time>.
        </p>
        <div className="mt-3 flex flex-wrap gap-3">
          {localChallengeActive
            ? <a
              className="inline-flex min-h-11 items-center rounded-xl bg-accent px-4 py-2.5 font-bold text-white"
              href={profile.telegramLinkChallenge?.deep_link}
              rel="noopener noreferrer"
              target="_blank"
            >Открыть Telegram</a>
            : <button
              className="min-h-11 rounded-xl bg-accent px-4 py-2.5 font-bold text-white disabled:cursor-wait disabled:opacity-60"
              disabled={operation !== null}
              onClick={() => void createChallenge(true)}
              type="button"
            >{operation === 'challenge' ? 'Готовим ссылку…' : 'Открыть Telegram'}</button>}
          <button
            className="inline-flex min-h-11 items-center gap-2 rounded-xl border border-accent/25 bg-white px-4 py-2.5 font-bold text-accent disabled:cursor-wait disabled:opacity-60"
            disabled={operation !== null}
            onClick={() => void refreshStatus()}
            type="button"
          >
            {operation === 'refresh' && <LoaderCircle aria-hidden="true" className="animate-spin" size={17} />}
            Проверить подключение
          </button>
        </div>
      </div>}
      {challengeExpiry && challengeExpired && <div aria-live="polite" className="mt-4 rounded-2xl bg-background/65 p-4" role="status">
        <p className="font-semibold">Срок ссылки истёк. Создайте новую ссылку для подключения.</p>
        <button
          className="mt-3 min-h-11 rounded-xl bg-accent px-4 py-2.5 font-bold text-white disabled:cursor-wait disabled:opacity-60"
          disabled={operation !== null}
          onClick={() => void createChallenge()}
          type="button"
        >{operation === 'challenge' ? 'Создаём…' : 'Создать новую ссылку'}</button>
      </div>}
      {!challengeExpiry && <button
        className="mt-4 min-h-11 rounded-xl bg-accent px-4 py-2.5 font-bold text-white disabled:cursor-wait disabled:opacity-60"
        disabled={operation !== null}
        onClick={() => void createChallenge()}
        type="button"
      >{operation === 'challenge' ? 'Подключаем…' : 'Подключить Telegram'}</button>}
    </div>}

    {error && <p aria-live="assertive" className="mt-3 text-sm font-semibold text-danger" role="alert">{error}</p>}
  </section>
}

function ScoreEditor({ currentScore }: { currentScore: number | null }) {
  const { updateScore } = useProfile()
  const [value, setValue] = useState(currentScore === null ? '' : String(currentScore))
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  const save = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    setMessage(null)
    const score = Number(value)
    if (value.trim() === '' || !Number.isInteger(score) || score < MIN_SCORE || score > MAX_SCORE) {
      setError('Введите целое число от 0 до 500.')
      return
    }
    setPending(true)
    try {
      await updateScore(score)
      setMessage('Личный балл сохранён.')
    } catch {
      setError('Не удалось сохранить балл. Попробуйте ещё раз.')
    } finally {
      setPending(false)
    }
  }

  const clear = async () => {
    setPending(true)
    setError(null)
    setMessage(null)
    try {
      await updateScore(null)
      setValue('')
      setMessage('Личный балл удалён.')
    } catch {
      setError('Не удалось удалить балл. Попробуйте ещё раз.')
    } finally {
      setPending(false)
    }
  }

  return <section aria-labelledby="personal-score-title" className="panel min-w-0 p-5 sm:p-6">
    <h2 className="text-2xl font-semibold" id="personal-score-title">Личный балл</h2>
    <p className="mt-2 text-text-secondary">
      {currentScore === null ? 'Баллы пока не добавлены.' : `Текущий балл: ${currentScore}`}
    </p>
    <form className="mt-5 flex min-w-0 flex-col gap-3 sm:flex-row sm:items-end" noValidate onSubmit={save}>
      <label className="grid min-w-0 flex-1 gap-2 text-sm font-bold" htmlFor="personal-admission-score">
        Балл для поступления
        <input
          className="field-control text-base"
          disabled={pending}
          id="personal-admission-score"
          inputMode="numeric"
          max={MAX_SCORE}
          min={MIN_SCORE}
          onChange={(event) => setValue(event.target.value)}
          step={1}
          type="number"
          value={value}
        />
      </label>
      <button className="min-h-12 rounded-xl bg-accent px-5 py-3 font-bold text-white disabled:cursor-wait disabled:opacity-60" disabled={pending} type="submit">
        {pending ? 'Сохраняем…' : 'Сохранить балл'}
      </button>
      {currentScore !== null && <button
        className="min-h-12 rounded-xl border border-text-primary/15 bg-white px-5 py-3 font-bold text-text-secondary disabled:cursor-wait disabled:opacity-60"
        disabled={pending}
        onClick={clear}
        type="button"
      >Удалить балл</button>}
    </form>
    {error && <p aria-live="assertive" className="mt-3 text-sm font-semibold text-danger" role="alert">{error}</p>}
    {message && <p aria-live="polite" className="mt-3 text-sm font-semibold text-accent" role="status">{message}</p>}
  </section>
}

function SavedUniversityCard({ item }: { item: SavedUniversity }) {
  const university = item.university
  const monitoringAvailable = university.coverage.online_monitoring === 'available'
  return <article className="panel min-w-0 p-5 sm:p-6">
    <h3 className="break-words text-xl font-semibold">
      <Link className="rounded-sm underline decoration-accent/35 decoration-2 underline-offset-4" to={`/universities/${encodeURIComponent(university.slug)}`}>
        {university.full_name}
      </Link>
    </h3>
    <p className="mt-2 break-words text-sm text-text-secondary">
      {[university.city, university.region].filter(Boolean).join(' · ') || 'Местоположение уточняется'}
    </p>
    <div className="mt-4 rounded-2xl bg-background/65 p-4 text-sm">
      <span className="font-bold">Покрытие платформы: </span>
      {monitoringAvailable
        ? <><span>Мониторинг доступен</span> · <Link className="font-bold text-accent underline" to="/monitor">Открыть монитор</Link></>
        : <span>Мониторинг пока недоступен</span>}
    </div>
    <div className="mt-5 border-t border-text-primary/10 pt-4">
      <SaveControl kind="university" label={university.full_name} universitySlug={university.slug} />
    </div>
  </article>
}

function MonitoringResult({ item }: { item: SavedProgram }) {
  if (item.monitoring_state === 'score_required') {
    return <p className="mt-4 rounded-2xl bg-background/65 p-4 font-semibold">Добавьте личный балл, чтобы увидеть текущий статус.</p>
  }
  if (item.monitoring_state === 'temporarily_unavailable') {
    return <p className="mt-4 rounded-2xl bg-background/65 p-4 font-semibold">Статус временно недоступен</p>
  }
  if (item.monitoring_state === 'unsupported' || !item.monitoring) {
    return <p className="mt-4 rounded-2xl bg-background/65 p-4 font-semibold">Мониторинг пока недоступен</p>
  }
  const status = item.monitoring
  const cutoff = status.estimated_cutoff_min === null || status.estimated_cutoff_max === null
    ? null
    : status.estimated_cutoff_min === status.estimated_cutoff_max
      ? String(status.estimated_cutoff_min)
      : `${status.estimated_cutoff_min}–${status.estimated_cutoff_max}`
  return <div className="mt-4 rounded-2xl border border-accent/15 bg-accent-soft/70 p-4">
    <h4 className="font-semibold">Статус для вашего балла</h4>
    <p className="mt-2 text-lg font-semibold text-accent">{status.status}</p>
    <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-3">
      <div><dt className="font-semibold text-text-tertiary">Конкурс</dt><dd>{status.competition}</dd></div>
      {cutoff && <div><dt className="font-semibold text-text-tertiary">Предполагаемый диапазон</dt><dd>{cutoff}</dd></div>}
      {status.estimated_user_position !== null && <div><dt className="font-semibold text-text-tertiary">Примерное место</dt><dd>{status.estimated_user_position}</dd></div>}
    </dl>
    <Link className="mt-4 inline-flex rounded-sm font-bold text-accent underline" to="/monitor">Подробнее в мониторе</Link>
  </div>
}

function WatchControl({
  item,
  enabled,
  personalScore,
}: {
  item: SavedProgram
  enabled: boolean
  personalScore: number | null
}) {
  const profile = useProfile()
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const program = item.program

  if (!item.watch_supported) {
    return <p className="mt-4 rounded-2xl bg-background/65 p-4 font-semibold">
      Мониторинг пока недоступен
    </p>
  }

  const toggle = async () => {
    setPending(true)
    setError(null)
    try {
      if (enabled) {
        await profile.disableWatch(program.university.slug, program.slug)
      } else {
        await profile.enableWatch(program.university.slug, program.slug)
      }
    } catch {
      setError('Не удалось изменить наблюдение. Попробуйте ещё раз.')
    } finally {
      setPending(false)
    }
  }

  return <div className="mt-4 rounded-2xl border border-accent/15 bg-white p-4" aria-busy={pending}>
    {enabled && <p aria-live="polite" className="inline-flex items-center gap-2 font-semibold text-accent" role="status">
      <BellRing aria-hidden="true" size={18} />Наблюдение включено
    </p>}
    <button
      className="mt-3 flex min-h-11 w-full items-center justify-center gap-2 rounded-xl border border-accent/25 bg-accent-soft px-4 py-2.5 font-bold text-accent disabled:cursor-wait disabled:opacity-60 sm:w-auto"
      disabled={pending}
      onClick={() => void toggle()}
      type="button"
    >
      {pending && <LoaderCircle aria-hidden="true" className="animate-spin" size={17} />}
      {pending
        ? enabled ? 'Отключаем…' : 'Включаем…'
        : enabled ? 'Отключить наблюдение' : 'Включить наблюдение'}
    </button>
    {personalScore === null && <p className="mt-3 text-sm leading-6 text-text-secondary">
      Изменения позиции и статуса требуют личный балл. Добавьте его выше, чтобы получать такие события.
    </p>}
    {error && <p aria-live="assertive" className="mt-3 text-sm font-semibold text-danger" role="alert">{error}</p>}
  </div>
}

function SavedProgramCard({
  comparisonDisabled,
  comparisonSelected,
  item,
  onComparisonChange,
  watchEnabled,
  personalScore,
}: {
  comparisonDisabled: boolean
  comparisonSelected: boolean
  item: SavedProgram
  onComparisonChange: () => void
  watchEnabled: boolean
  personalScore: number | null
}) {
  const program = item.program
  return <article className="panel min-w-0 p-5 sm:p-6">
    <label className={`mb-4 flex min-w-0 items-start gap-3 rounded-xl border p-3 font-bold ${comparisonSelected ? 'border-accent/35 bg-accent-soft' : 'border-text-primary/10 bg-white'} ${comparisonDisabled ? 'cursor-not-allowed opacity-55' : 'cursor-pointer'}`}>
      <input
        aria-label={`Выбрать для сравнения — ${program.name} (${program.university.short_name})`}
        checked={comparisonSelected}
        className="mt-1 size-4 shrink-0 accent-accent"
        disabled={comparisonDisabled}
        onChange={onComparisonChange}
        type="checkbox"
      />
      <span className="min-w-0 break-words">
        {comparisonSelected ? 'Выбрано для сравнения' : 'Выбрать для сравнения'}
        {comparisonDisabled && <span className="mt-1 block text-xs font-semibold text-text-secondary">Сначала снимите один из трёх выбранных вариантов.</span>}
      </span>
    </label>
    <h3 className="break-words text-xl font-semibold">
      <Link className="rounded-sm underline decoration-accent/35 decoration-2 underline-offset-4" to={`/universities/${encodeURIComponent(program.university.slug)}/programs/${encodeURIComponent(program.slug)}`}>
        {program.name}
      </Link>
    </h3>
    <p className="mt-2 text-sm text-text-secondary">
      <Link className="font-bold text-accent underline" to={`/universities/${encodeURIComponent(program.university.slug)}`}>
        {program.university.short_name}
      </Link>
    </p>
    {program.offerings.length > 0 && <div className="mt-4 grid gap-3">
      {program.offerings.map((offering) => <div className="min-w-0 rounded-2xl border border-text-primary/10 bg-background/65 p-4 text-sm" key={offering.id}>
        <p className="break-words font-bold">{offering.admission_year} · {apiValueLabel(offering.study_form)} · {apiValueLabel(offering.funding_type)}</p>
        <p className="mt-1 text-text-secondary">{offering.monitoring_supported ? apiValueLabel(offering.monitoring_status) : 'Мониторинг пока недоступен'}</p>
      </div>)}
    </div>}
    <MonitoringResult item={item} />
    <WatchControl enabled={watchEnabled} item={item} personalScore={personalScore} />
    <div className="mt-5 border-t border-text-primary/10 pt-4">
      <SaveControl
        kind="program"
        label={program.name}
        programSlug={program.slug}
        universitySlug={program.university.slug}
      />
    </div>
  </article>
}

function ChangeHistory({
  events,
  personalScore,
}: {
  events: ProgramWatchEvent[]
  personalScore: number | null
}) {
  return <section aria-labelledby="watch-history-title" className="min-w-0">
    <h2 className="text-3xl font-semibold" id="watch-history-title">История изменений</h2>
    {personalScore === null && <p className="mt-3 max-w-3xl text-sm leading-6 text-text-secondary">
      Изменения позиции и статуса появятся после того, как вы укажете личный балл. Общие изменения заявлений и диапазона доступны без него.
    </p>}
    {events.length === 0
      ? <p className="panel mt-5 p-5 text-text-secondary">Изменений пока нет</p>
      : <ol className="mt-5 grid min-w-0 gap-4">
        {events.map((event, index) => {
          const programPath = `/universities/${encodeURIComponent(event.university.slug)}/programs/${encodeURIComponent(event.program.slug)}`
          return <li className="panel min-w-0 p-5 sm:p-6" key={`${event.created_at}:${event.event_kind}:${event.program.slug}:${index}`}>
            <article className="min-w-0">
              <div className="flex min-w-0 flex-wrap items-baseline justify-between gap-2">
                <h3 className="min-w-0 break-words text-lg font-semibold">
                  <Link className="underline decoration-accent/35 decoration-2 underline-offset-4" to={programPath}>{event.program.name}</Link>
                </h3>
                <time className="text-sm text-text-tertiary" dateTime={event.created_at}>
                  {eventTimeFormatter.format(new Date(event.created_at))}
                </time>
              </div>
              <p className="mt-2 break-words text-sm text-text-secondary">
                <Link className="font-bold text-accent underline" to={`/universities/${encodeURIComponent(event.university.slug)}`}>
                  {event.university.full_name}
                </Link>
              </p>
              <p className="mt-4 break-words leading-7">{event.description}</p>
              {event.telegram_delivery_status === 'confirmed' && <p className="mt-3 inline-flex items-center gap-2 text-sm font-bold text-accent">
                <Send aria-hidden="true" size={16} />Отправлено в Telegram
              </p>}
              <div className="mt-4 flex flex-wrap gap-4 text-sm font-bold">
                <Link className="text-accent underline" to={programPath}>Открыть программу</Link>
                <Link className="text-accent underline" to="/monitor">Открыть монитор</Link>
              </div>
            </article>
          </li>
        })}
      </ol>}
  </section>
}

export function MyListPage() {
  const profile = useProfile()
  const navigate = useNavigate()
  const [comparisonSelectionState, setComparisonSelection] = useState<ProgramIdentity[]>([])
  useDocumentTitle('Мой список поступления · Куда поступать')

  const universities = profile.data?.universities ?? []
  const programs = profile.data?.programs ?? []
  const score = profile.data?.profile.personal_score ?? null
  const empty = universities.length === 0 && programs.length === 0
  const watchedPrograms = new Set(profile.watches.map((watch) => (
    `${watch.university.slug}:${watch.program.slug}`
  )))
  const availableProgramKey = programs.map((item) => programIdentityKey(programIdentityFor(item.program))).join(',')
  const availablePrograms = new Set(availableProgramKey.split(',').filter(Boolean))
  const comparisonSelection = comparisonSelectionState.filter((identity) => (
    availablePrograms.has(programIdentityKey(identity))
  ))

  const toggleComparison = (identity: ProgramIdentity) => {
    const key = programIdentityKey(identity)
    if (comparisonSelection.some((item) => programIdentityKey(item) === key)) {
      setComparisonSelection(comparisonSelection.filter((item) => programIdentityKey(item) !== key))
      return
    }
    if (comparisonSelection.length < MAX_COMPARED_PROGRAMS) {
      setComparisonSelection([...comparisonSelection, identity])
    }
  }

  return <div className="page-shell">
    <div className="page-container py-10 lg:py-14">
      <header className="max-w-3xl">
        <div className="eyebrow">Личный выбор</div>
        <h1 className="page-heading">Мой список поступления</h1>
        <p className="body-copy mt-4">Сохраняйте вузы и программы в анонимном профиле этого браузера и проверяйте доступные данные мониторинга.</p>
      </header>

      {profile.invalidTokenRecovered && <div aria-live="polite" className="panel mt-6 border-warning/30 p-5" role="status">
        Сохранённый доступ устарел. Новый анонимный список будет создан после следующего действия.
      </div>}

      {profile.status === 'loading' && <div aria-live="polite" className="panel mt-6 flex items-center gap-3 p-6" role="status">
        <LoaderCircle aria-hidden="true" className="animate-spin text-accent" size={20} />Загружаем сохранённый список…
      </div>}

      {profile.status === 'error' && <section aria-labelledby="my-list-error-title" className="panel mt-6 border-danger/30 p-6" role="alert">
        <h2 className="text-2xl font-semibold" id="my-list-error-title">Не удалось загрузить сохранённый список</h2>
        <p className="mt-2 text-text-secondary">Сервис временно недоступен. Сохранённые элементы не удалены.</p>
        <button className="mt-4 inline-flex items-center gap-2 rounded-xl bg-accent px-4 py-2.5 font-bold text-white" onClick={() => void profile.retry()} type="button">
          <RefreshCw aria-hidden="true" size={17} />Повторить запрос
        </button>
      </section>}

      {profile.status !== 'loading' && profile.status !== 'error' && <div className="mt-8 grid gap-8">
        <div className="grid gap-5 lg:grid-cols-2">
          <ScoreEditor currentScore={score} />
          <TelegramNotifications />
        </div>

        {empty && <section aria-labelledby="empty-list-title" className="panel p-6 sm:p-8">
          <h2 className="text-2xl font-semibold" id="empty-list-title">Список пока пуст</h2>
          <p className="mt-3 text-text-secondary">Выберите вуз или программу, чтобы собрать личный список поступления.</p>
          <div className="mt-5 flex flex-wrap gap-3">
            <Link className="button-primary" to="/universities">Перейти к вузам</Link>
            <Link className="button-secondary text-accent" to="/monitor">Открыть монитор</Link>
          </div>
        </section>}

        <section aria-labelledby="saved-universities-title" className="min-w-0">
          <h2 className="text-3xl font-semibold" id="saved-universities-title">Сохранённые вузы</h2>
          {universities.length > 0
            ? <div className="mt-5 grid min-w-0 gap-5 lg:grid-cols-2">{universities.map((item) => <SavedUniversityCard item={item} key={item.university.slug} />)}</div>
            : <p className="panel mt-5 p-5 text-text-secondary">Сохранённых вузов пока нет.</p>}
        </section>

        <section aria-labelledby="saved-programs-title" className="min-w-0">
          <h2 className="text-3xl font-semibold" id="saved-programs-title">Сохранённые программы</h2>
          {programs.length > 0
            ? <>
              <section aria-labelledby="program-comparison-selection-title" className="panel mt-5 min-w-0 p-5 sm:p-6">
                <div className="flex min-w-0 flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-w-0">
                    <h3 className="text-xl font-semibold" id="program-comparison-selection-title">Сравнить сохранённые программы</h3>
                    <p aria-live="polite" className="mt-2 font-bold text-text-secondary">Выбрано {comparisonSelection.length} из {MAX_COMPARED_PROGRAMS}</p>
                  </div>
                  <button
                    className="inline-flex min-h-11 shrink-0 items-center justify-center gap-2 rounded-xl bg-accent px-4 py-2.5 font-bold text-white disabled:cursor-not-allowed disabled:opacity-45"
                    disabled={comparisonSelection.length < 2}
                    onClick={() => navigate(programComparisonPath(comparisonSelection))}
                    type="button"
                  ><ArrowRightLeft aria-hidden="true" size={18} />Сравнить выбранные программы</button>
                </div>
                <p className="mt-3 text-sm leading-6 text-text-secondary">Выбор хранится только на этой странице до перехода; сравнение откроется по ссылке без сохранения нового состояния.</p>
              </section>
              <div className="mt-5 grid min-w-0 gap-5">{programs.map((item) => {
                const identity = programIdentityFor(item.program)
                const key = programIdentityKey(identity)
                const selected = comparisonSelection.some((current) => programIdentityKey(current) === key)
                return <SavedProgramCard
                  comparisonDisabled={!selected && comparisonSelection.length >= MAX_COMPARED_PROGRAMS}
                  comparisonSelected={selected}
                  item={item}
                  key={key}
                  onComparisonChange={() => toggleComparison(identity)}
                  personalScore={score}
                  watchEnabled={watchedPrograms.has(key)}
                />
              })}</div>
            </>
            : <p className="panel mt-5 p-5 text-text-secondary">Сохранённых программ пока нет.</p>}
        </section>

        <ChangeHistory events={profile.watchEvents} personalScore={score} />
      </div>}
    </div>
  </div>
}
