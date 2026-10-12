import { useEffect, useRef } from 'react'
import { Link, NavLink, Outlet, useLocation, useSearchParams } from 'react-router'
import { useQueryClient } from '@tanstack/react-query'
import {
  BellRingingIcon,
  CircleNotchIcon,
  DesktopIcon,
  FlaskIcon,
  MoonIcon,
  PlusIcon,
  SunIcon,
  TerminalWindowIcon,
} from '@phosphor-icons/react'
import type { Stage } from '@/api/client'
import { keys, useAgentRuns, useFollowups, useReplies, useStatus } from '@/api/queries'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { STAGE_LABEL, STAGES } from '@/lib/labels'
import { useTheme, type ThemeChoice } from '@/lib/theme'
import { cn } from '@/lib/utils'
import { UserPrompts } from '@/components/UserPrompts'
import { AgentButton } from '@/components/AgentButton'

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
  const active = pathname === '/bandeja' ? (params.get('stage') ?? 'all') : null

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
                to={key === 'all' ? '/bandeja' : `/bandeja?stage=${key}`}
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
      <div className="flex flex-1 flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <p>
          <span className="font-medium">
            {pending === 1 ? 'Hay 1 oferta por extraer.' : `Hay ${pending} ofertas por extraer.`}
          </span>{' '}
          Las extrae tu agente con el skill{' '}
          <code className="rounded bg-background/70 px-1.5 py-0.5 font-mono text-[0.85em]">procesar-ofertas</code>.
        </p>
        <AgentButton action="procesar-ofertas">Procesar ahora</AgentButton>
      </div>
    </div>
  )
}

function FollowupReminder() {
  const { data } = useFollowups()
  const { pathname } = useLocation()
  const due = data?.followups.length ?? 0
  if (!due || pathname === '/procesos') return null
  return (
    <div
      role="status"
      className="flex items-start gap-3 rounded-xl border border-primary/20 bg-accent/60 px-4 py-3 text-sm text-accent-foreground animate-in fade-in slide-in-from-top-1"
    >
      <BellRingingIcon className="mt-0.5 size-[18px] shrink-0" weight="duotone" />
      <p>
        <span className="font-medium">
          {due === 1
            ? `1 candidatura lleva ${data?.days_without_reply} días o más sin respuesta.`
            : `${due} candidaturas llevan ${data?.days_without_reply} días o más sin respuesta.`}
        </span>{' '}
        <Link to="/procesos" className="underline underline-offset-4">
          Revisa los seguimientos en Procesos
        </Link>
        .
      </p>
    </div>
  )
}

/**
 * En segundo plano (fase 19): aviso mientras tu agente trabaja sin ventana. Cuando termina una
 * ejecución, refresca todo: el agente ha podido extraer ofertas, valorarlas o generar un CV.
 */
function BackgroundRunReminder() {
  const { data } = useAgentRuns()
  const { pathname } = useLocation()
  const client = useQueryClient()
  // La última que terminó (no un recuento: la lista solo trae las 20 más recientes).
  const lastFinished = (data?.runs ?? []).reduce(
    (last, r) => (r.finished_at && r.finished_at > last ? r.finished_at : last),
    '',
  )
  const previous = useRef<string | null>(null)
  useEffect(() => {
    if (previous.current !== null && lastFinished > previous.current) {
      void client.invalidateQueries({
        predicate: (q) => q.queryKey[0] !== keys.agent[0],
      })
    }
    previous.current = lastFinished
  }, [lastFinished, client])

  const current = data?.runs.find((r) => r.status === 'running') ?? data?.runs.find((r) => r.status === 'queued')
  if (!current || pathname === '/agente') return null
  return (
    <div
      role="status"
      className="flex items-center gap-3 rounded-xl border px-4 py-2.5 text-sm text-muted-foreground animate-in fade-in"
    >
      <CircleNotchIcon
        className={cn('size-4 shrink-0', current.status === 'running' && 'animate-spin')}
        weight="bold"
      />
      <p>
        {current.status === 'running' ? 'Tu agente trabaja en segundo plano' : 'En cola en segundo plano'}: «
        {current.label}».{' '}
        <Link to="/agente" className="underline underline-offset-4">
          Ver el progreso
        </Link>
      </p>
    </div>
  )
}

/** Ejecuciones en curso (fase 19) y encargos pendientes. */
function AgentNavCount() {
  const runs = useAgentRuns()
  const { data } = useStatus()
  const active = runs.data?.active ?? 0
  const waiting = runs.data?.runs.filter((r) => r.status === 'needs_user').length ?? 0
  const requests = data?.agent_requests ?? 0
  const count = active + waiting + requests
  if (!count) return null
  return (
    <span
      className={cn(
        'tabular grid h-[18px] min-w-[18px] place-items-center rounded-full px-1 text-[0.7rem] font-semibold',
        active + waiting ? 'bg-primary text-primary-foreground' : 'bg-foreground/10 text-foreground/80',
      )}
    >
      <span className="sr-only">, </span>
      {count}
      <span className="sr-only"> en curso o pendientes</span>
    </span>
  )
}

// Modo demo (fase 12.1): la carpeta de datos la creó `jh demo seed`. Fijo en todas las páginas.
function DemoBanner() {
  const { data } = useStatus()
  if (!data?.demo_mode) return null
  return (
    <div
      role="note"
      aria-label="Modo demo"
      className="border-b border-warning-border bg-warning text-warning-foreground"
    >
      <p className="mx-auto flex max-w-6xl items-center gap-2 px-4 py-1.5 text-xs sm:px-6">
        <FlaskIcon className="size-4 shrink-0" weight="duotone" />
        <span>
          <span className="font-semibold">Modo demo: datos ficticios.</span> Personas, empresas y ofertas son
          inventadas; tus datos reales no se tocan.
        </span>
      </p>
    </div>
  )
}

function navClass({ isActive }: { isActive: boolean }) {
  return cn(
    'flex shrink-0 items-center gap-1.5 rounded-md px-2.5 py-1.5 whitespace-nowrap transition-colors',
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

/** Respuestas de las empresas que esperan tu decisión (fase 15). */
function RepliesNavCount() {
  const { data } = useReplies()
  const count = data?.counts.proposed ?? 0
  if (!count) return null
  return (
    <span className="tabular grid h-[18px] min-w-[18px] place-items-center rounded-full bg-primary px-1 text-[0.7rem] font-semibold text-primary-foreground">
      <span className="sr-only">, </span>
      {count}
      <span className="sr-only"> por revisar</span>
    </span>
  )
}

export function AppShell() {
  // En Inicio el recorrido ya enseña las etapas: sin la fila de recuentos.
  const { pathname } = useLocation()
  return (
    <div className="min-h-[100dvh]">
      <header className="sticky top-0 z-20 border-b bg-background/80 backdrop-blur-md supports-[backdrop-filter]:bg-background/65">
        <DemoBanner />
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-4 px-4 sm:px-6 lg:gap-6">
          <Link to="/" className="flex shrink-0 items-center gap-2.5 font-semibold tracking-tight whitespace-nowrap">
            <span className="grid size-7 place-items-center rounded-md bg-foreground font-mono text-[11px] font-bold text-background">
              JH
            </span>
            <span className="hidden sm:inline">Job Hunter</span>
          </Link>
          {/* En pantallas estrechas el menú se desplaza en horizontal en vez de ensanchar la página. */}
          <nav className="relative -my-2 flex min-w-0 items-center gap-0.5 overflow-x-auto py-2 text-sm [scrollbar-width:none]">
            <NavLink to="/" end className={navClass}>
              Inicio
            </NavLink>
            <NavLink to="/bandeja" className={navClass}>
              Bandeja
            </NavLink>
            <NavLink to="/por-revisar" className={navClass}>
              Por revisar
              <NavCount stage="pending_triage" label="por revisar" />
            </NavLink>
            <NavLink to="/procesos" className={navClass}>
              Procesos
            </NavLink>
            <NavLink to="/respuestas" className={navClass}>
              Respuestas
              <RepliesNavCount />
            </NavLink>
            <NavLink to="/embudo" className={navClass}>
              Embudo
            </NavLink>
            <NavLink to="/skills" className={navClass}>
              Skills
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
            <NavLink to="/perfil" className={navClass}>
              Mi perfil
            </NavLink>
            <NavLink to="/agente" className={navClass}>
              Agente
              <AgentNavCount />
            </NavLink>
          </nav>
          <div className="ml-auto flex shrink-0 items-center gap-1.5">
            <ThemeToggle />
            <Button asChild size="sm" className="active:translate-y-px">
              <Link to="/nueva">
                <PlusIcon weight="bold" />
                <span className="sr-only sm:not-sr-only">Nueva oferta</span>
              </Link>
            </Button>
          </div>
        </div>
        {pathname !== '/' && (
          <div className="mx-auto max-w-6xl px-4 pb-2 sm:px-6">
            <StageCounts />
          </div>
        )}
      </header>
      <main className="mx-auto max-w-6xl px-4 pb-24 pt-6 sm:px-6 sm:pt-8">
        <div className="mb-6 space-y-3 empty:hidden">
          <BackgroundRunReminder />
          <ExtractionReminder />
          <FollowupReminder />
        </div>
        <Outlet />
      </main>
      <UserPrompts />
    </div>
  )
}
