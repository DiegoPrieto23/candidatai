import { Link, NavLink, Outlet, useLocation, useSearchParams } from 'react-router'
import { DesktopIcon, MoonIcon, PlusIcon, SunIcon, TerminalWindowIcon } from '@phosphor-icons/react'
import type { Stage } from '@/api/client'
import { useStatus } from '@/api/queries'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { STAGE_LABEL, STAGES } from '@/lib/labels'
import { useTheme, type ThemeChoice } from '@/lib/theme'
import { cn } from '@/lib/utils'

const THEME_META: Record<ThemeChoice, { icon: typeof SunIcon; label: string }> = {
  system: { icon: DesktopIcon, label: 'Tema: el del sistema' },
  light: { icon: SunIcon, label: 'Tema: claro' },
  dark: { icon: MoonIcon, label: 'Tema: oscuro' },
}

function ThemeToggle() {
  const { choice, cycle } = useTheme()
  const { icon: Icon, label } = THEME_META[choice]
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button variant="ghost" size="icon" onClick={cycle} aria-label={label}>
          <Icon className="size-[18px]" />
        </Button>
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  )
}

function StageCounts() {
  const { data, isPending, isError } = useStatus()
  const [params] = useSearchParams()
  const { pathname } = useLocation()
  const active = pathname === '/' ? (params.get('stage') ?? 'all') : null

  if (isError) return null
  const items: { key: Stage | 'all'; label: string; count?: number }[] = [
    { key: 'all', label: 'Todas', count: data?.total },
    ...STAGES.map((stage) => ({ key: stage, label: STAGE_LABEL[stage], count: data?.by_stage[stage] })),
  ]
  return (
    <nav aria-label="Ofertas por etapa" className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
      <ul className="flex min-w-max gap-1">
        {items.map(({ key, label, count }) => {
          const selected = active === key
          return (
            <li key={key}>
              <Link
                to={key === 'all' ? '/' : `/?stage=${key}`}
                aria-current={selected ? 'page' : undefined}
                className={cn(
                  'group flex items-baseline gap-2 rounded-md px-3 py-2 text-sm transition-colors',
                  selected
                    ? 'bg-foreground/[0.06] text-foreground dark:bg-foreground/10'
                    : 'text-muted-foreground hover:bg-foreground/[0.04] hover:text-foreground',
                )}
              >
                <span>{label}</span>
                {isPending ? (
                  <Skeleton className="h-3.5 w-4" />
                ) : (
                  <span
                    className={cn(
                      'tabular text-xs font-medium',
                      count ? (selected ? 'text-primary' : 'text-foreground/70') : 'text-muted-foreground/60',
                    )}
                  >
                    {count ?? 0}
                  </span>
                )}
              </Link>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}

function ExtractionReminder() {
  const { data } = useStatus()
  const pending = data?.by_stage.pending_extraction ?? 0
  if (!pending) return null
  return (
    <div
      role="status"
      className="flex items-start gap-3 rounded-xl border border-primary/20 bg-accent/60 px-4 py-3 text-sm text-accent-foreground animate-in fade-in slide-in-from-top-1"
    >
      <TerminalWindowIcon className="mt-0.5 size-[18px] shrink-0" weight="duotone" />
      <p>
        <span className="font-medium">
          {pending === 1 ? 'Hay 1 oferta por extraer.' : `Hay ${pending} ofertas por extraer.`}
        </span>{' '}
        Ejecuta el skill{' '}
        <code className="rounded bg-background/70 px-1.5 py-0.5 font-mono text-[0.85em]">procesar-ofertas</code>{' '}
        en tu agente.
      </p>
    </div>
  )
}

function navClass({ isActive }: { isActive: boolean }) {
  return cn(
    'flex items-center gap-1.5 rounded-md px-3 py-1.5 transition-colors',
    isActive ? 'text-foreground' : 'text-muted-foreground hover:text-foreground',
  )
}

function NavCount({ stage, label, muted = false }: { stage: Stage; label: string; muted?: boolean }) {
  const { data } = useStatus()
  const count = data?.by_stage[stage] ?? 0
  if (!count) return null
  return (
    <span
      className={cn(
        'tabular grid h-[18px] min-w-[18px] place-items-center rounded-full px-1 text-[0.7rem] font-semibold',
        muted ? 'bg-foreground/10 text-foreground/80' : 'bg-primary text-primary-foreground',
      )}
    >
      <span className="sr-only">, </span>
      {count}
      <span className="sr-only"> {label}</span>
    </span>
  )
}

export function AppShell() {
  return (
    <div className="min-h-[100dvh]">
      <header className="sticky top-0 z-20 border-b bg-background/80 backdrop-blur-md supports-[backdrop-filter]:bg-background/65">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-6 px-4 sm:px-6">
          <Link to="/" className="flex items-center gap-2.5 font-semibold tracking-tight">
            <span className="grid size-7 place-items-center rounded-md bg-foreground font-mono text-[11px] font-bold text-background">
              JH
            </span>
            <span className="hidden sm:inline">Job Hunter</span>
          </Link>
          <nav className="flex items-center gap-1 text-sm">
            <NavLink to="/" end className={navClass}>
              Bandeja
            </NavLink>
            <NavLink to="/triaje" className={navClass}>
              Triaje
              <NavCount stage="pending_triage" label="por revisar" />
            </NavLink>
            <NavLink to="/alertas" className={navClass}>
              Alertas
              <NavCount stage="pending_detail" label="por completar" muted />
            </NavLink>
            <NavLink to="/empresas" className={navClass}>
              Empresas
            </NavLink>
            <NavLink to="/plataformas" className={navClass}>
              Plataformas
            </NavLink>
            <NavLink to="/plantillas" className={navClass}>
              Plantillas
            </NavLink>
          </nav>
          <div className="ml-auto flex items-center gap-1.5">
            <ThemeToggle />
            <Button asChild size="sm" className="active:translate-y-px">
              <Link to="/nueva">
                <PlusIcon weight="bold" />
                Nueva oferta
              </Link>
            </Button>
          </div>
        </div>
        <div className="mx-auto max-w-6xl px-4 pb-2 sm:px-6">
          <StageCounts />
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 pb-24 pt-6 sm:px-6 sm:pt-8">
        <div className="mb-6 empty:hidden">
          <ExtractionReminder />
        </div>
        <Outlet />
      </main>
    </div>
  )
}
