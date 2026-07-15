import { BellRing, LoaderCircle, RefreshCw, Send } from 'lucide-react'
import { type FormEvent, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { apiValueLabel } from '../catalogPresentation'
import { SaveControl } from '../components/SaveControl'
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
    <h2 className="text-2xl font-extrabold" id="telegram-notifications-title">Уведомления в Telegram</h2>

    {profile.telegramStatusState === 'loading' && <p
      aria-live="polite"
      className="mt-4 flex items-center gap-2 text-ink/65"
      role="status"
    >
      <LoaderCircle aria-hidden="true" className="animate-spin" size={18} />Проверяем подключение…
    </p>}

    {profile.telegramStatusState === 'error' && <div className="mt-4" role="alert">
      <p className="font-semibold text-red-700">Не удалось загрузить статус Telegram.</p>
      <button
        className="mt-3 inline-flex min-h-11 items-center gap-2 rounded-xl border border-moss/25 bg-white px-4 py-2.5 font-bold text-moss disabled:cursor-wait disabled:opacity-60"
        disabled={operation !== null}
        onClick={() => void refreshStatus()}
        type="button"
      >
        <RefreshCw aria-hidden="true" size={17} />Повторить запрос
      </button>
    </div>}

    {profile.telegramStatusState === 'ready' && status?.linked && <div className="mt-4">
      <p aria-live="polite" className="inline-flex items-center gap-2 font-extrabold text-moss" role="status">
        <Send aria-hidden="true" size={18} />Telegram подключён
      </p>
      {status.linked_at && <p className="mt-2 text-sm text-ink/60">
        Подключено {eventTimeFormatter.format(new Date(status.linked_at))}.
      </p>}
      {!confirmingUnlink
        ? <button
          className="mt-4 min-h-11 rounded-xl border border-red-200 bg-white px-4 py-2.5 font-bold text-red-700"
          onClick={() => setConfirmingUnlink(true)}
          type="button"
        >Отключить Telegram</button>
        : <div aria-live="polite" className="mt-4 rounded-2xl border border-red-200 bg-red-50 p-4">
          <p className="font-semibold">Отключить уведомления для этого анонимного профиля?</p>
          <div className="mt-3 flex flex-wrap gap-3">
            <button
              className="min-h-11 rounded-xl bg-red-700 px-4 py-2.5 font-bold text-white disabled:cursor-wait disabled:opacity-60"
              disabled={operation !== null}
              onClick={() => void unlink()}
              type="button"
            >{operation === 'unlink' ? 'Отключаем…' : 'Подтвердить отключение'}</button>
            <button
              className="min-h-11 rounded-xl border border-ink/15 bg-white px-4 py-2.5 font-bold"
              disabled={operation !== null}
              onClick={() => setConfirmingUnlink(false)}
              type="button"
            >Отмена</button>
          </div>
        </div>}
    </div>}

    {profile.telegramStatusState === 'ready' && status && !status.linked && <div className="mt-4">
      <p className="max-w-3xl leading-7 text-ink/65">
        Telegram получает новые изменения из включённых наблюдений БГЭУ. Отключение Telegram не выключает наблюдения.
      </p>
      {challengeExpiry && !challengeExpired && <div className="mt-4 rounded-2xl bg-cream/65 p-4">
        <p className="font-semibold">Запрос на подключение действует до{' '}
          <time dateTime={challengeExpiry}>{eventTimeFormatter.format(new Date(challengeExpiry))}</time>.
        </p>
        <div className="mt-3 flex flex-wrap gap-3">
          {localChallengeActive
            ? <a
              className="inline-flex min-h-11 items-center rounded-xl bg-moss px-4 py-2.5 font-bold text-white"
              href={profile.telegramLinkChallenge?.deep_link}
              rel="noopener noreferrer"
              target="_blank"
            >Открыть Telegram</a>
            : <button
              className="min-h-11 rounded-xl bg-moss px-4 py-2.5 font-bold text-white disabled:cursor-wait disabled:opacity-60"
              disabled={operation !== null}
              onClick={() => void createChallenge(true)}
              type="button"
            >{operation === 'challenge' ? 'Готовим ссылку…' : 'Открыть Telegram'}</button>}
          <button
            className="inline-flex min-h-11 items-center gap-2 rounded-xl border border-moss/25 bg-white px-4 py-2.5 font-bold text-moss disabled:cursor-wait disabled:opacity-60"
            disabled={operation !== null}
            onClick={() => void refreshStatus()}
            type="button"
          >
            {operation === 'refresh' && <LoaderCircle aria-hidden="true" className="animate-spin" size={17} />}
            Проверить подключение
          </button>
        </div>
      </div>}
      {challengeExpiry && challengeExpired && <div aria-live="polite" className="mt-4 rounded-2xl bg-cream/65 p-4" role="status">
        <p className="font-semibold">Срок ссылки истёк. Создайте новую ссылку для подключения.</p>
        <button
          className="mt-3 min-h-11 rounded-xl bg-moss px-4 py-2.5 font-bold text-white disabled:cursor-wait disabled:opacity-60"
          disabled={operation !== null}
          onClick={() => void createChallenge()}
          type="button"
        >{operation === 'challenge' ? 'Создаём…' : 'Создать новую ссылку'}</button>
      </div>}
      {!challengeExpiry && <button
        className="mt-4 min-h-11 rounded-xl bg-moss px-4 py-2.5 font-bold text-white disabled:cursor-wait disabled:opacity-60"
        disabled={operation !== null}
        onClick={() => void createChallenge()}
        type="button"
      >{operation === 'challenge' ? 'Подключаем…' : 'Подключить Telegram'}</button>}
    </div>}

    {error && <p aria-live="assertive" className="mt-3 text-sm font-semibold text-red-700" role="alert">{error}</p>}
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
    <h2 className="text-2xl font-extrabold" id="personal-score-title">Личный балл</h2>
    <p className="mt-2 text-ink/65">
      {currentScore === null ? 'Баллы пока не добавлены.' : `Текущий балл: ${currentScore}`}
    </p>
    <form className="mt-5 flex min-w-0 flex-col gap-3 sm:flex-row sm:items-end" noValidate onSubmit={save}>
      <label className="grid min-w-0 flex-1 gap-2 text-sm font-bold" htmlFor="personal-admission-score">
        Балл для поступления
        <input
          className="min-w-0 rounded-xl border border-ink/15 bg-white px-4 py-3 text-base"
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
      <button className="min-h-12 rounded-xl bg-moss px-5 py-3 font-bold text-white disabled:cursor-wait disabled:opacity-60" disabled={pending} type="submit">
        {pending ? 'Сохраняем…' : 'Сохранить балл'}
      </button>
      {currentScore !== null && <button
        className="min-h-12 rounded-xl border border-ink/15 bg-white px-5 py-3 font-bold text-ink/75 disabled:cursor-wait disabled:opacity-60"
        disabled={pending}
        onClick={clear}
        type="button"
      >Удалить балл</button>}
    </form>
    {error && <p aria-live="assertive" className="mt-3 text-sm font-semibold text-red-700" role="alert">{error}</p>}
    {message && <p aria-live="polite" className="mt-3 text-sm font-semibold text-moss" role="status">{message}</p>}
  </section>
}

function SavedUniversityCard({ item }: { item: SavedUniversity }) {
  const university = item.university
  const monitoringAvailable = university.coverage.online_monitoring === 'available'
  return <article className="panel min-w-0 p-5 sm:p-6">
    <h3 className="break-words text-xl font-extrabold">
      <Link className="rounded-sm underline decoration-moss/35 decoration-2 underline-offset-4" to={`/universities/${encodeURIComponent(university.slug)}`}>
        {university.full_name}
      </Link>
    </h3>
    <p className="mt-2 break-words text-sm text-ink/60">
      {[university.city, university.region].filter(Boolean).join(' · ') || 'Местоположение уточняется'}
    </p>
    <div className="mt-4 rounded-2xl bg-cream/65 p-4 text-sm">
      <span className="font-bold">Покрытие платформы: </span>
      {monitoringAvailable
        ? <><span>Мониторинг доступен</span> · <Link className="font-bold text-moss underline" to="/monitor">Открыть монитор</Link></>
        : <span>Мониторинг пока недоступен</span>}
    </div>
    <div className="mt-5 border-t border-ink/10 pt-4">
      <SaveControl kind="university" label={university.full_name} universitySlug={university.slug} />
    </div>
  </article>
}

function MonitoringResult({ item }: { item: SavedProgram }) {
  if (item.monitoring_state === 'score_required') {
    return <p className="mt-4 rounded-2xl bg-cream/65 p-4 font-semibold">Добавьте личный балл, чтобы увидеть текущий статус.</p>
  }
  if (item.monitoring_state === 'temporarily_unavailable') {
    return <p className="mt-4 rounded-2xl bg-cream/65 p-4 font-semibold">Статус временно недоступен</p>
  }
  if (item.monitoring_state === 'unsupported' || !item.monitoring) {
    return <p className="mt-4 rounded-2xl bg-cream/65 p-4 font-semibold">Мониторинг пока недоступен</p>
  }
  const status = item.monitoring
  const cutoff = status.estimated_cutoff_min === null || status.estimated_cutoff_max === null
    ? null
    : status.estimated_cutoff_min === status.estimated_cutoff_max
      ? String(status.estimated_cutoff_min)
      : `${status.estimated_cutoff_min}–${status.estimated_cutoff_max}`
  return <div className="mt-4 rounded-2xl border border-moss/15 bg-mint/70 p-4">
    <h4 className="font-extrabold">Статус для вашего балла</h4>
    <p className="mt-2 text-lg font-extrabold text-moss">{status.status}</p>
    <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-3">
      <div><dt className="font-semibold text-ink/50">Конкурс</dt><dd>{status.competition}</dd></div>
      {cutoff && <div><dt className="font-semibold text-ink/50">Предполагаемый диапазон</dt><dd>{cutoff}</dd></div>}
      {status.estimated_user_position !== null && <div><dt className="font-semibold text-ink/50">Примерное место</dt><dd>{status.estimated_user_position}</dd></div>}
    </dl>
    <Link className="mt-4 inline-flex rounded-sm font-bold text-moss underline" to="/monitor">Подробнее в мониторе</Link>
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
    return <p className="mt-4 rounded-2xl bg-cream/65 p-4 font-semibold">
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

  return <div className="mt-4 rounded-2xl border border-moss/15 bg-white p-4" aria-busy={pending}>
    {enabled && <p aria-live="polite" className="inline-flex items-center gap-2 font-extrabold text-moss" role="status">
      <BellRing aria-hidden="true" size={18} />Наблюдение включено
    </p>}
    <button
      className="mt-3 flex min-h-11 w-full items-center justify-center gap-2 rounded-xl border border-moss/25 bg-mint px-4 py-2.5 font-bold text-moss disabled:cursor-wait disabled:opacity-60 sm:w-auto"
      disabled={pending}
      onClick={() => void toggle()}
      type="button"
    >
      {pending && <LoaderCircle aria-hidden="true" className="animate-spin" size={17} />}
      {pending
        ? enabled ? 'Отключаем…' : 'Включаем…'
        : enabled ? 'Отключить наблюдение' : 'Включить наблюдение'}
    </button>
    {personalScore === null && <p className="mt-3 text-sm leading-6 text-ink/65">
      Изменения позиции и статуса требуют личный балл. Добавьте его выше, чтобы получать такие события.
    </p>}
    {error && <p aria-live="assertive" className="mt-3 text-sm font-semibold text-red-700" role="alert">{error}</p>}
  </div>
}

function SavedProgramCard({
  item,
  watchEnabled,
  personalScore,
}: {
  item: SavedProgram
  watchEnabled: boolean
  personalScore: number | null
}) {
  const program = item.program
  return <article className="panel min-w-0 p-5 sm:p-6">
    <h3 className="break-words text-xl font-extrabold">
      <Link className="rounded-sm underline decoration-moss/35 decoration-2 underline-offset-4" to={`/universities/${encodeURIComponent(program.university.slug)}/programs/${encodeURIComponent(program.slug)}`}>
        {program.name}
      </Link>
    </h3>
    <p className="mt-2 text-sm text-ink/65">
      <Link className="font-bold text-moss underline" to={`/universities/${encodeURIComponent(program.university.slug)}`}>
        {program.university.short_name}
      </Link>
    </p>
    {program.offerings.length > 0 && <div className="mt-4 grid gap-3">
      {program.offerings.map((offering) => <div className="min-w-0 rounded-2xl border border-ink/10 bg-cream/65 p-4 text-sm" key={offering.id}>
        <p className="break-words font-bold">{offering.admission_year} · {apiValueLabel(offering.study_form)} · {apiValueLabel(offering.funding_type)}</p>
        <p className="mt-1 text-ink/60">{offering.monitoring_supported ? apiValueLabel(offering.monitoring_status) : 'Мониторинг пока недоступен'}</p>
      </div>)}
    </div>}
    <MonitoringResult item={item} />
    <WatchControl enabled={watchEnabled} item={item} personalScore={personalScore} />
    <div className="mt-5 border-t border-ink/10 pt-4">
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
    <h2 className="text-3xl font-extrabold" id="watch-history-title">История изменений</h2>
    {personalScore === null && <p className="mt-3 max-w-3xl text-sm leading-6 text-ink/65">
      Изменения позиции и статуса появятся после того, как вы укажете личный балл. Общие изменения заявлений и диапазона доступны без него.
    </p>}
    {events.length === 0
      ? <p className="panel mt-5 p-5 text-ink/65">Изменений пока нет</p>
      : <ol className="mt-5 grid min-w-0 gap-4">
        {events.map((event, index) => {
          const programPath = `/universities/${encodeURIComponent(event.university.slug)}/programs/${encodeURIComponent(event.program.slug)}`
          return <li className="panel min-w-0 p-5 sm:p-6" key={`${event.created_at}:${event.event_kind}:${event.program.slug}:${index}`}>
            <article className="min-w-0">
              <div className="flex min-w-0 flex-wrap items-baseline justify-between gap-2">
                <h3 className="min-w-0 break-words text-lg font-extrabold">
                  <Link className="underline decoration-moss/35 decoration-2 underline-offset-4" to={programPath}>{event.program.name}</Link>
                </h3>
                <time className="text-sm text-ink/55" dateTime={event.created_at}>
                  {eventTimeFormatter.format(new Date(event.created_at))}
                </time>
              </div>
              <p className="mt-2 break-words text-sm text-ink/65">
                <Link className="font-bold text-moss underline" to={`/universities/${encodeURIComponent(event.university.slug)}`}>
                  {event.university.full_name}
                </Link>
              </p>
              <p className="mt-4 break-words leading-7">{event.description}</p>
              {event.telegram_delivery_status === 'confirmed' && <p className="mt-3 inline-flex items-center gap-2 text-sm font-bold text-moss">
                <Send aria-hidden="true" size={16} />Отправлено в Telegram
              </p>}
              <div className="mt-4 flex flex-wrap gap-4 text-sm font-bold">
                <Link className="text-moss underline" to={programPath}>Открыть программу</Link>
                <Link className="text-moss underline" to="/monitor">Открыть монитор</Link>
              </div>
            </article>
          </li>
        })}
      </ol>}
  </section>
}

export function MyListPage() {
  const profile = useProfile()
  useDocumentTitle('Мой список поступления · Куда поступать')

  const universities = profile.data?.universities ?? []
  const programs = profile.data?.programs ?? []
  const score = profile.data?.profile.personal_score ?? null
  const empty = universities.length === 0 && programs.length === 0
  const watchedPrograms = new Set(profile.watches.map((watch) => (
    `${watch.university.slug}:${watch.program.slug}`
  )))

  return <div className="min-w-0 bg-[linear-gradient(180deg,#f8f7f1_0%,#f2f0e7_100%)]">
    <div className="mx-auto max-w-7xl px-5 py-10 lg:px-8 lg:py-14">
      <header className="max-w-3xl">
        <div className="eyebrow">Личный выбор</div>
        <h1 className="mt-3 break-words text-4xl font-extrabold leading-tight tracking-tight sm:text-5xl">Мой список поступления</h1>
        <p className="mt-4 text-lg leading-8 text-ink/70">Сохраняйте вузы и программы на этом устройстве и проверяйте доступные данные мониторинга.</p>
      </header>

      {profile.invalidTokenRecovered && <div aria-live="polite" className="panel mt-6 border-amber-200 p-5" role="status">
        Сохранённый доступ устарел. Новый анонимный список будет создан после следующего действия.
      </div>}

      {profile.status === 'loading' && <div aria-live="polite" className="panel mt-6 flex items-center gap-3 p-6" role="status">
        <LoaderCircle aria-hidden="true" className="animate-spin text-moss" size={20} />Загружаем сохранённый список…
      </div>}

      {profile.status === 'error' && <section aria-labelledby="my-list-error-title" className="panel mt-6 border-red-200 p-6" role="alert">
        <h2 className="text-2xl font-extrabold" id="my-list-error-title">Не удалось загрузить сохранённый список</h2>
        <p className="mt-2 text-ink/65">Сервис временно недоступен. Сохранённые элементы не удалены.</p>
        <button className="mt-4 inline-flex items-center gap-2 rounded-xl bg-moss px-4 py-2.5 font-bold text-white" onClick={() => void profile.retry()} type="button">
          <RefreshCw aria-hidden="true" size={17} />Повторить запрос
        </button>
      </section>}

      {profile.status !== 'loading' && profile.status !== 'error' && <div className="mt-8 grid gap-8">
        <ScoreEditor currentScore={score} />
        <TelegramNotifications />

        {empty && <section aria-labelledby="empty-list-title" className="panel p-6 sm:p-8">
          <h2 className="text-2xl font-extrabold" id="empty-list-title">Список пока пуст</h2>
          <p className="mt-3 text-ink/65">Выберите вуз или программу, чтобы собрать личный список поступления.</p>
          <div className="mt-5 flex flex-wrap gap-3">
            <Link className="rounded-xl bg-moss px-4 py-2.5 font-bold text-white" to="/universities">Перейти к вузам</Link>
            <Link className="rounded-xl border border-moss/25 bg-white px-4 py-2.5 font-bold text-moss" to="/monitor">Открыть монитор</Link>
          </div>
        </section>}

        <section aria-labelledby="saved-universities-title" className="min-w-0">
          <h2 className="text-3xl font-extrabold" id="saved-universities-title">Сохранённые вузы</h2>
          {universities.length > 0
            ? <div className="mt-5 grid min-w-0 gap-5 lg:grid-cols-2">{universities.map((item) => <SavedUniversityCard item={item} key={item.university.slug} />)}</div>
            : <p className="panel mt-5 p-5 text-ink/65">Сохранённых вузов пока нет.</p>}
        </section>

        <section aria-labelledby="saved-programs-title" className="min-w-0">
          <h2 className="text-3xl font-extrabold" id="saved-programs-title">Сохранённые программы</h2>
          {programs.length > 0
            ? <div className="mt-5 grid min-w-0 gap-5">{programs.map((item) => {
              const key = `${item.program.university.slug}:${item.program.slug}`
              return <SavedProgramCard
                item={item}
                key={key}
                personalScore={score}
                watchEnabled={watchedPrograms.has(key)}
              />
            })}</div>
            : <p className="panel mt-5 p-5 text-ink/65">Сохранённых программ пока нет.</p>}
        </section>

        <ChangeHistory events={profile.watchEvents} personalScore={score} />
      </div>}
    </div>
  </div>
}
