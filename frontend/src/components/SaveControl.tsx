import { Bookmark, LoaderCircle, Trash2 } from 'lucide-react'
import { useState } from 'react'

import { useProfile } from '../useProfile'

type SaveControlProps =
  | { kind: 'university'; universitySlug: string; label: string }
  | { kind: 'program'; universitySlug: string; programSlug: string; label: string }

export function SaveControl(props: SaveControlProps) {
  const profile = useProfile()
  const [pending, setPending] = useState(false)
  const [error, setError] = useState(false)
  const saved = props.kind === 'university'
    ? profile.data?.universities.some((item) => item.university.slug === props.universitySlug) ?? false
    : profile.data?.programs.some((item) => (
      item.program.university.slug === props.universitySlug
      && item.program.slug === props.programSlug
    )) ?? false

  const change = async () => {
    setPending(true)
    setError(false)
    try {
      if (props.kind === 'university') {
        await (saved
          ? profile.removeUniversity(props.universitySlug)
          : profile.saveUniversity(props.universitySlug))
      } else {
        await (saved
          ? profile.removeProgram(props.universitySlug, props.programSlug)
          : profile.saveProgram(props.universitySlug, props.programSlug))
      }
    } catch {
      setError(true)
    } finally {
      setPending(false)
    }
  }

  return <div className="min-w-0">
    <div className="flex flex-wrap items-center gap-3">
      {saved && <span aria-live="polite" className="inline-flex items-center gap-1.5 text-sm font-bold text-moss">
        <Bookmark aria-hidden="true" fill="currentColor" size={16} />Сохранено
      </span>}
      <button
        aria-label={`${saved ? 'Удалить из списка' : 'Сохранить'} — ${props.label}`}
        className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-moss/25 bg-white px-4 py-2 text-sm font-bold text-moss transition hover:bg-mint disabled:cursor-wait disabled:opacity-60"
        disabled={pending}
        onClick={change}
        type="button"
      >
        {pending
          ? <LoaderCircle aria-hidden="true" className="animate-spin" size={17} />
          : saved
            ? <Trash2 aria-hidden="true" size={17} />
            : <Bookmark aria-hidden="true" size={17} />}
        {pending ? 'Сохраняем…' : saved ? 'Удалить из списка' : 'Сохранить'}
      </button>
    </div>
    {error && <p aria-live="assertive" className="mt-2 text-sm font-semibold text-red-700" role="alert">
      Не удалось изменить список. Попробуйте ещё раз.
    </p>}
  </div>
}
