import { Menu, X } from 'lucide-react'
import { AnimatePresence, LazyMotion, domAnimation, m, useReducedMotion } from 'motion/react'
import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, Outlet } from 'react-router-dom'

const navigationItems = [
  { label: 'Главная', to: '/', end: true },
  { label: 'Вузы', to: '/universities', end: false },
  { label: 'Сравнение', to: '/compare', end: false },
  { label: 'Подбор вариантов', to: '/recommendations', end: false },
  { label: 'Мой список', to: '/my-list', end: false },
  { label: 'Монитор поступления', to: '/monitor', end: false },
] as const

const navigationClass = ({ isActive }: { isActive: boolean }) => [
  'site-nav-link',
  isActive ? 'site-nav-link--active' : '',
].join(' ')

export function SiteLayout() {
  const [mobileOpen, setMobileOpen] = useState(false)
  const menuButtonRef = useRef<HTMLButtonElement>(null)
  const reduceMotion = useReducedMotion()

  useEffect(() => {
    if (!mobileOpen) return
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      setMobileOpen(false)
      menuButtonRef.current?.focus()
    }
    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [mobileOpen])

  return <LazyMotion features={domAnimation}>
    <div className="flex min-h-screen min-w-0 flex-col text-text-primary">
    <a className="skip-link" href="#main-content">Перейти к содержимому</a>
    <header className="site-header sticky top-0 z-40 px-3 pt-3 sm:px-5 sm:pt-4">
      <div className="glass-surface--compact mx-auto max-w-7xl px-3 py-2.5 sm:px-4">
        <div className="flex min-w-0 items-center justify-between gap-3">
          <Link aria-label="Куда поступать — главная" className="pressable flex min-h-11 min-w-0 items-center gap-3 rounded-xl px-1.5" onClick={() => setMobileOpen(false)} to="/">
            <span aria-hidden="true" className="grid size-9 shrink-0 place-items-center rounded-xl bg-accent text-sm font-semibold text-white shadow-glass-compact">К</span>
            <span className="min-w-0">
              <span className="block truncate text-[15px] font-semibold tracking-[-0.015em]">Куда поступать</span>
              <span className="hidden text-xs leading-4 text-text-secondary sm:block">Данные для абитуриентов Беларуси</span>
            </span>
          </Link>

          <nav aria-label="Основная навигация" className="hidden items-center gap-0.5 lg:flex">
            {navigationItems.map((item) => <NavLink className={navigationClass} end={item.end} key={item.to} to={item.to}>{item.label}</NavLink>)}
          </nav>

          <button
            aria-controls="mobile-site-navigation"
            aria-expanded={mobileOpen}
            aria-label={mobileOpen ? 'Закрыть основную навигацию' : 'Открыть основную навигацию'}
            className="pressable grid size-11 shrink-0 place-items-center rounded-xl border border-border/70 bg-elevated/90 text-text-primary lg:hidden"
            onClick={() => setMobileOpen((open) => !open)}
            ref={menuButtonRef}
            type="button"
          >
            {mobileOpen ? <X aria-hidden="true" size={20} /> : <Menu aria-hidden="true" size={20} />}
          </button>
        </div>

        <AnimatePresence initial={false}>
          {mobileOpen && <m.nav
            animate={{ opacity: 1, transform: 'scale(1)' }}
            aria-label="Мобильная основная навигация"
            className="mobile-site-nav mt-2 grid gap-1 border-t border-border/60 pt-2 lg:hidden"
            exit={{ opacity: 0, transform: reduceMotion ? 'none' : 'scale(0.985)' }}
            id="mobile-site-navigation"
            initial={{ opacity: 0, transform: reduceMotion ? 'none' : 'scale(0.985)' }}
            transition={{
              duration: reduceMotion ? 0.16 : 0.24,
              ease: [0.32, 0.72, 0, 1],
            }}
          >
            {navigationItems.map((item) => <NavLink className={navigationClass} end={item.end} key={item.to} onClick={() => setMobileOpen(false)} to={item.to}>{item.label}</NavLink>)}
          </m.nav>}
        </AnimatePresence>
      </div>
    </header>
    <main className="min-w-0 flex-1" id="main-content" tabIndex={-1}>
      <Outlet />
    </main>
    <footer className="border-t border-divider bg-elevated/95">
      <div className="page-container flex flex-col gap-2 py-7 text-sm text-text-secondary sm:flex-row sm:items-center sm:justify-between">
        <span className="font-semibold text-text-primary">Куда поступать</span>
        <span className="max-w-2xl sm:text-right">Проверяйте итоговые решения на официальных ресурсах вузов.</span>
      </div>
    </footer>
    </div>
  </LazyMotion>
}
