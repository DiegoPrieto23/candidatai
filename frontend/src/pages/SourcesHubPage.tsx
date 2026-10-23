import { NavLink, Outlet } from 'react-router'
import { useTranslation } from 'react-i18next'
import { BuildingsIcon, CompassIcon } from '@phosphor-icons/react'
import { cn } from '@/lib/utils'

const TABS = [
  { to: '/fuentes/plataformas', label: 'platforms', icon: CompassIcon },
  { to: '/fuentes/empresas', label: 'companies', icon: BuildingsIcon },
] as const

/**
 * «Fuentes» (fase 23.3): de dónde salen tus ofertas. Une las plataformas que recorre tu agente y
 * las empresas objetivo (APIs de ATS y portales), cada una en su pestaña con su propia URL.
 */
export function SourcesHubPage() {
  const { t } = useTranslation('platforms', { keyPrefix: 'hub' })
  return (
    <div className="grid gap-6">
      <nav aria-label={t('label')} className="mx-auto w-full max-w-3xl">
        <ul className="inline-flex gap-1 rounded-lg border bg-card p-1">
          {TABS.map(({ to, label, icon: Icon }) => (
            <li key={to}>
              <NavLink
                to={to}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-2 rounded-md px-3 py-1.5 text-sm transition-colors',
                    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                    isActive
                      ? 'bg-foreground/[0.07] font-medium text-foreground dark:bg-foreground/10'
                      : 'text-muted-foreground hover:text-foreground',
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    <Icon className="size-4" weight={isActive ? 'fill' : 'regular'} aria-hidden />
                    {t(label)}
                  </>
                )}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
      <Outlet />
    </div>
  )
}
