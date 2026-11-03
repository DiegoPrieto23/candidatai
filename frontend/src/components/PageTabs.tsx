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
export function PageTabs({
  label,
  tabs,
  className,
  level = 'main',
}: {
  label: string
  tabs: readonly PageTab[]
  className?: string
  /** `sub`: pestañas dentro de otra pestaña. Pesan menos para que se lea cuál manda. */
  level?: 'main' | 'sub'
}) {
  const main = level === 'main'
  return (
    <nav aria-label={label} className={cn('w-full min-w-0', main && 'border-b', className)}>
      <ul className={cn('scroll-row flex max-w-full', main ? '-mb-px gap-5' : 'gap-1')}>
        {tabs.map(({ to, label: name, icon: Icon, end, count, countLabel }) => (
          <li key={to} className="flex-none">
            <NavLink
              to={to}
              end={end}
              aria-label={count ? countLabel : undefined}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-2 text-sm whitespace-nowrap transition-colors',
                  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset',
                  main ? 'border-b-2 pt-0.5 pb-2.5' : 'rounded-md px-2.5 py-1',
                  main && (isActive ? 'border-primary' : 'border-transparent hover:border-foreground/20'),
                  !main && isActive && 'bg-foreground/[0.07] dark:bg-foreground/10',
                  isActive ? 'font-medium text-foreground' : 'text-muted-foreground hover:text-foreground',
                )
              }
            >
              {({ isActive }) => (
                <>
                  <Icon className={cn('size-4', isActive && main && 'text-primary')} weight={isActive ? 'fill' : 'regular'} aria-hidden />
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
