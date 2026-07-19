import { Bookmark, LoaderCircle, Trash2 } from 'lucide-react'
import { AnimatePresence, LazyMotion, domAnimation, m } from 'motion/react'
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

  return <LazyMotion features={domAnimation}>
    <div className="min-w-0">
    <div className="flex flex-wrap items-center gap-3">
      <AnimatePresence initial={false}>
        {saved && <m.span
          animate={{ opacity: 1 }}
          aria-live="polite"
          className="inline-flex items-center gap-1.5 text-sm font-bold text-success"
          exit={{ opacity: 0 }}
          initial={{ opacity: 0 }}
          key="saved-status"
          transition={{ duration: 0.18, ease: [0.23, 1, 0.32, 1] }}
        >
          <Bookmark aria-hidden="true" fill="currentColor" size={16} />Сохранено
        </m.span>}
      </AnimatePresence>
      <button
        aria-label={`${saved ? 'Удалить из списка' : 'Сохранить'} — ${props.label}`}
        className="button-secondary min-h-11 text-accent disabled:cursor-wait disabled:opacity-60"
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
    <AnimatePresence initial={false}>
      {error && <m.p
        animate={{ opacity: 1 }}
        aria-live="assertive"
        className="mt-2 text-sm font-semibold text-danger"
        exit={{ opacity: 0 }}
        initial={{ opacity: 0 }}
        key="save-error"
        role="alert"
        transition={{ duration: 0.18, ease: [0.23, 1, 0.32, 1] }}
      >Не удалось изменить список. Попробуйте ещё раз.</m.p>}
    </AnimatePresence>
    </div>
  </LazyMotion>
}
