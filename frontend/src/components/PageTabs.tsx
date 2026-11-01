import type { ComponentType } from 'react'
import { NavLink } from 'react-router'
import type { IconProps } from '@phosphor-icons/react'
import { cn } from '@/lib/utils'

export type PageTab = {
  to: string
  label: string
  icon: ComponentType<IconProps>
  /** Solo activa en su ruta exacta: la pestaña que abre la sección, no las que cuelgan de ella. */
  end?: boolean
  /** Lo que te espera ahí. A 0, no se enseña. */
  count?: number
  /** Cómo lo dice un lector de pantalla, porque la cifra sola no se entiende: «Por completar (3)». */
  countLabel?: string
}

/**
 * Las pestañas de una sección, cada una con su propia URL. En móvil, la fila se desplaza en vez de
 * partirse en dos.
 */
export function PageTabs({ label, tabs, className }: { label: string; tabs: readonly PageTab[]; className?: string }) {
  return (
    <nav aria-label={label} className={cn('w-full min-w-0', className)}>
      <ul className="scroll-row inline-flex max-w-full gap-1 rounded-lg border bg-card p-1">
        {tabs.map(({ to, label: name, icon: Icon, end, count, countLabel }) => (
          <li key={to} className="flex-none">
            <NavLink
              to={to}
              end={end}
              aria-label={count ? countLabel : undefined}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-2 rounded-md px-3 py-1.5 text-sm whitespace-nowrap transition-colors',
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
                  {name}
                  {!!count && (
                    <span className="tabular grid h-[18px] min-w-[18px] place-items-center rounded-full bg-foreground/10 px-1 text-[0.7rem] font-semibold text-foreground/80">
                      {count}
                    </span>
                  )}
                </>
              )}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  )
}
