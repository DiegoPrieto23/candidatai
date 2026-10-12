import { NavLink, Outlet } from 'react-router'
import { BuildingsIcon, CompassIcon } from '@phosphor-icons/react'
import { cn } from '@/lib/utils'

const TABS = [
  { to: '/fuentes/empresas', label: 'Empresas objetivo', icon: BuildingsIcon },
  { to: '/fuentes/plataformas', label: 'Plataformas', icon: CompassIcon },
]

/**
 * «Fuentes» (fase 23.3): de dónde salen tus ofertas. Une las empresas objetivo (APIs de ATS y
 * portales) y las plataformas que recorre tu agente, cada una en su pestaña con su propia URL.
 */
export function SourcesHubPage() {
  return (
    <div className="grid gap-6">
      <nav aria-label="Fuentes de ofertas" className="mx-auto w-full max-w-3xl">
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
                    {label}
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
