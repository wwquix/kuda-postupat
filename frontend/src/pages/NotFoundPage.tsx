import { ArrowLeft, Activity } from 'lucide-react'
import { Link } from 'react-router-dom'

import { useDocumentTitle } from '../useDocumentTitle'

export function NotFoundPage() {
  useDocumentTitle('Страница не найдена · Куда поступать')

  return <div className="page-shell grid min-h-[65vh] place-items-center px-5 py-14">
    <section aria-labelledby="not-found-title" className="panel w-full max-w-2xl p-7 text-center sm:p-10">
      <div className="eyebrow">Ошибка 404</div>
      <h1 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl" id="not-found-title">Страница не найдена</h1>
      <p className="mx-auto mt-4 max-w-lg leading-7 text-text-secondary">Такого раздела нет или адрес был введён с ошибкой. Можно безопасно вернуться на главную либо открыть работающий монитор БГЭУ.</p>
      <div className="mt-7 flex flex-col justify-center gap-3 sm:flex-row">
        <Link className="button-primary" to="/"><ArrowLeft aria-hidden="true" size={18} />На главную</Link>
        <Link className="button-secondary" to="/monitor"><Activity aria-hidden="true" size={18} />Монитор поступления</Link>
      </div>
    </section>
  </div>
}
