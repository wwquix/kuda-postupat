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

  return <div className="page-shell page-shell--home">
    <div className="page-container section-space">
      <section aria-labelledby="home-title" className="grid gap-12 lg:grid-cols-[1.04fr_.96fr] lg:items-center lg:gap-16">
        <div className="min-w-0 py-2 lg:py-8">
          <div className="eyebrow">Платформа для абитуриентов Беларуси</div>
          <h1 className="display-heading mt-5 max-w-3xl" id="home-title">Куда поступать</h1>
          <p className="body-copy mt-6 max-w-2xl">Собираем проверенные сведения о вузах и сохраняем понятную картину вступительной кампании — без выдуманных значений и обещаний поступления.</p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:flex-wrap">
            <Link className="button-primary" to="/monitor">Открыть монитор БГЭУ <ArrowRight aria-hidden="true" size={18} /></Link>
            <Link className="button-secondary" to="/universities">Перейти к каталогу вузов</Link>
          </div>
        </div>

        <div className="grid min-w-0 gap-4">
          <section aria-labelledby="catalog-coverage-title" className="glass-surface--strong materialize p-6 sm:p-7">
            <div className="flex items-start justify-between gap-4">
              <div className="grid size-11 shrink-0 place-items-center rounded-2xl bg-accent-soft text-accent"><Database aria-hidden="true" size={21} /></div>
              <span className="status-pill">Официальные источники</span>
            </div>
            <h2 className="mt-5 text-xl font-semibold tracking-[-0.02em]" id="catalog-coverage-title">Каталог платформы</h2>
            <div aria-live="polite" className="mt-3 min-h-16">
              {catalogCount.status === 'loading' && <p className="text-sm leading-6 text-text-secondary" role="status">Уточняем актуальное покрытие каталога…</p>}
              {catalogCount.status === 'available' && <p className="text-lg font-medium leading-8">В каталоге платформы — <strong className="text-3xl font-semibold tracking-[-0.025em] text-text-primary">{catalogCount.universities}</strong> университетов Беларуси.</p>}
              {catalogCount.status === 'unavailable' && <p className="text-sm leading-6 text-text-secondary">Количество вузов временно не удалось подтвердить. Обновите страницу позже.</p>}
            </div>
            <Link className="text-button mt-2" to="/universities">Открыть каталог вузов <ArrowRight aria-hidden="true" size={17} /></Link>
          </section>

          <section aria-labelledby="monitor-coverage-title" className="glass-surface--strong materialize p-6 sm:p-7">
            <div className="flex items-start justify-between gap-4">
              <div className="grid size-11 shrink-0 place-items-center rounded-2xl bg-accent-soft text-accent"><RadioTower aria-hidden="true" size={21} /></div>
              <span className="status-pill">Только БГЭУ</span>
            </div>
            <h2 className="mt-5 text-xl font-semibold tracking-[-0.02em]" id="monitor-coverage-title">Live-мониторинг</h2>
            <p className="mt-3 leading-7 text-text-secondary">Сейчас автоматический live-мониторинг работает только для БГЭУ. Для остальных вузов такой статус не заявляется.</p>
          </section>
        </div>
      </section>

      <section aria-labelledby="data-notice-title" className="mt-12 rounded-3xl border border-warning/30 bg-warning/10 p-6 text-warning sm:mt-16 sm:p-8">
        <h2 className="text-lg font-semibold tracking-[-0.01em]" id="data-notice-title">Как читать данные</h2>
        <p className="mt-2 max-w-4xl leading-7 text-warning/85">Сведения сверяются с официальными источниками, но покрытие платформы пока неполное. Отсутствие импортированной программы или значения не означает, что их нет в реальности. Финальные условия поступления всегда проверяйте на сайте выбранного вуза.</p>
      </section>
    </div>
  </div>
}
