import { ArrowRight, Database, RadioTower } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { api } from '../api'
import { useDocumentTitle } from '../useDocumentTitle'

type CatalogCountState =
  | { status: 'loading' }
  | { status: 'available'; universities: number }
  | { status: 'unavailable' }

export function HomePage() {
  const [catalogCount, setCatalogCount] = useState<CatalogCountState>({ status: 'loading' })
  useDocumentTitle('Куда поступать · Данные для абитуриентов Беларуси')

  useEffect(() => {
    let active = true
    api.catalogMeta()
      .then((meta) => {
        if (!active) return
        const universities = meta.counts.universities
        setCatalogCount(Number.isInteger(universities) && universities > 0
          ? { status: 'available', universities }
          : { status: 'unavailable' })
      })
      .catch(() => {
        if (active) setCatalogCount({ status: 'unavailable' })
      })
    return () => { active = false }
  }, [])

  return <div className="bg-[radial-gradient(circle_at_top_right,_rgba(109,190,148,0.2),_transparent_34%),linear-gradient(180deg,#f8f7f1_0%,#f2f0e7_100%)]">
    <div className="mx-auto max-w-7xl px-5 py-10 sm:py-16 lg:px-8 lg:py-20">
      <section aria-labelledby="home-title" className="grid gap-10 lg:grid-cols-[1.12fr_.88fr] lg:items-center">
        <div>
          <div className="eyebrow">Платформа для абитуриентов Беларуси</div>
          <h1 className="mt-4 max-w-3xl text-4xl font-extrabold leading-tight tracking-tight sm:text-5xl lg:text-6xl" id="home-title">Куда поступать</h1>
          <p className="mt-5 max-w-2xl text-lg leading-8 text-ink/70">Собираем проверенные сведения о вузах и сохраняем понятную картину вступительной кампании — без выдуманных значений и обещаний поступления.</p>
          <div className="mt-8">
            <Link className="inline-flex items-center gap-2 rounded-xl bg-moss px-5 py-3 font-bold text-white shadow-card transition hover:bg-ink" to="/monitor">Открыть монитор БГЭУ <ArrowRight aria-hidden="true" size={18} /></Link>
          </div>
        </div>

        <div className="panel grid gap-4 p-5 sm:p-7">
          <div className="rounded-2xl border border-ink/10 bg-cream/70 p-5">
            <div className="flex items-center gap-3 text-moss"><Database aria-hidden="true" size={20} /><h2 className="text-base font-bold">Каталог платформы</h2></div>
            <div aria-live="polite" className="mt-3 min-h-14">
              {catalogCount.status === 'loading' && <p className="text-sm text-ink/60">Уточняем актуальное покрытие каталога…</p>}
              {catalogCount.status === 'available' && <p className="text-lg font-semibold">В каталоге платформы — <strong className="text-3xl font-extrabold text-ink">{catalogCount.universities}</strong> университетов Беларуси.</p>}
              {catalogCount.status === 'unavailable' && <p className="text-sm leading-6 text-ink/65">Количество вузов временно не удалось подтвердить. Обновите страницу позже.</p>}
            </div>
          </div>
          <div className="rounded-2xl border border-moss/15 bg-mint/70 p-5">
            <div className="flex items-center gap-3 text-moss"><RadioTower aria-hidden="true" size={20} /><h2 className="text-base font-bold">Live-мониторинг</h2></div>
            <p className="mt-3 leading-7 text-ink/75">Сейчас автоматический live-мониторинг работает только для БГЭУ. Для остальных вузов такой статус не заявляется.</p>
          </div>
        </div>
      </section>

      <section aria-labelledby="data-notice-title" className="mt-10 rounded-3xl border border-amber-300 bg-amber-50 p-6 sm:mt-14 sm:p-8">
        <h2 className="text-lg font-bold" id="data-notice-title">Как читать данные</h2>
        <p className="mt-2 max-w-4xl leading-7 text-amber-950/80">Сведения сверяются с официальными источниками, но покрытие платформы пока неполное. Отсутствие импортированной программы или значения не означает, что их нет в реальности. Финальные условия поступления всегда проверяйте на сайте выбранного вуза.</p>
      </section>
    </div>
  </div>
}
