import { Link, NavLink, Outlet } from 'react-router-dom'

const navigationClass = ({ isActive }: { isActive: boolean }) => [
  'rounded-xl px-3 py-2 text-sm font-semibold transition',
  isActive ? 'bg-mint text-moss' : 'text-ink/70 hover:bg-ink/5 hover:text-ink',
].join(' ')

export function SiteLayout() {
  return <div className="flex min-h-screen min-w-0 flex-col bg-cream text-ink">
    <a className="skip-link" href="#main-content">Перейти к содержимому</a>
    <header className="border-b border-ink/10 bg-white/95">
      <div className="mx-auto flex max-w-7xl flex-col gap-4 px-5 py-4 sm:flex-row sm:items-center sm:justify-between lg:px-8">
        <Link aria-label="Куда поступать — главная" className="flex w-fit items-center rounded-xl" to="/">
          <span>
            <span className="block text-base font-extrabold tracking-tight">Куда поступать</span>
            <span className="block text-xs text-ink/55">Данные для абитуриентов Беларуси</span>
          </span>
        </Link>
        <nav aria-label="Основная навигация" className="flex flex-wrap items-center gap-1">
          <NavLink className={navigationClass} end to="/">Главная</NavLink>
          <NavLink className={navigationClass} to="/universities">Вузы</NavLink>
          <NavLink className={navigationClass} to="/compare">Сравнение</NavLink>
          <NavLink className={navigationClass} to="/recommendations">Подбор вариантов</NavLink>
          <NavLink className={navigationClass} to="/my-list">Мой список</NavLink>
          <NavLink className={navigationClass} to="/monitor">Монитор поступления</NavLink>
        </nav>
      </div>
    </header>
    <main className="min-w-0 flex-1" id="main-content" tabIndex={-1}>
      <Outlet />
    </main>
    <footer className="border-t border-ink/10 bg-white">
      <div className="mx-auto flex max-w-7xl flex-col gap-2 px-5 py-6 text-sm text-ink/60 sm:flex-row sm:items-center sm:justify-between lg:px-8">
        <span className="font-semibold text-ink/75">Куда поступать</span>
        <span>Проверяйте итоговые решения на официальных ресурсах вузов.</span>
      </div>
    </footer>
  </div>
}
