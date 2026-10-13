import { useEffect, useRef } from 'react'
import { Link, Outlet, useLocation, useSearchParams } from 'react-router'
import { useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { BellRingingIcon, CircleNotchIcon, FlaskIcon, PlusIcon, TerminalWindowIcon } from '@phosphor-icons/react'
import type { Stage } from '@/api/client'
import { keys, useAgentRuns, useFollowups, useStatus } from '@/api/queries'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { STAGE_LABEL, STAGES } from '@/lib/labels'
import { cn } from '@/lib/utils'
import { UserPrompts } from '@/components/UserPrompts'
import { AgentButton } from '@/components/AgentButton'
import { Brand, MobileNav, Sidebar } from '@/components/Sidebar'

function StageCounts() {
  const { t } = useTranslation('nav')
  const { data, isPending, isError } = useStatus()
  const [params] = useSearchParams()
  const { pathname } = useLocation()
  const active = pathname === '/bandeja' ? (params.get('stage') ?? 'all') : null

  if (isError) return null
  const items: { key: Stage | 'all'; label: string; count?: number }[] = [
    { key: 'all', label: t('header.all'), count: data?.total },
    ...STAGES.map((stage) => ({ key: stage, label: STAGE_LABEL[stage], count: data?.by_stage[stage] })),
  ]
  return (
    <nav aria-label={t('header.byStage')} className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
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
  const { t } = useTranslation('nav')
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
          <span className="font-medium">{t('reminders.toExtract', { count: pending })}</span>{' '}
          {t('reminders.extractHint')}{' '}
          <code className="rounded bg-background/70 px-1.5 py-0.5 font-mono text-[0.85em]">process-jobs</code>.
        </p>
        <AgentButton action="process-jobs">{t('reminders.processNow')}</AgentButton>
      </div>
    </div>
  )
}

function FollowupReminder() {
  const { t } = useTranslation('nav')
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
          {t('reminders.followups', { count: due, days: data?.days_without_reply })}
        </span>{' '}
        <Link to="/procesos" className="underline underline-offset-4">
          {t('reminders.followupsLink')}
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
  const { t } = useTranslation('nav')
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
        {current.status === 'running' ? t('reminders.running') : t('reminders.queued')}: «{current.label}».{' '}
        <Link to="/agente" className="underline underline-offset-4">
          {t('reminders.seeProgress')}
        </Link>
      </p>
    </div>
  )
}

// Modo demo (fase 12.1): la carpeta de datos la creó `cai demo seed`. Fijo en todas las páginas.
function DemoBanner() {
  const { t } = useTranslation('nav')
  const { data } = useStatus()
  if (!data?.demo_mode) return null
  return (
    <div
      role="note"
      aria-label={t('demo.label')}
      className="border-b border-warning-border bg-warning text-warning-foreground"
    >
      <p className="mx-auto flex max-w-6xl items-center gap-2 px-4 py-1.5 text-xs sm:px-6">
        <FlaskIcon className="size-4 shrink-0" weight="duotone" />
        <span>
          <span className="font-semibold">{t('demo.title')}</span> {t('demo.body')}
        </span>
      </p>
    </div>
  )
}

export function AppShell() {
  const { t } = useTranslation('nav')
  // En Inicio el recorrido ya enseña las etapas: sin la fila de recuentos.
  const { pathname } = useLocation()
  const home = pathname === '/'
  return (
    <div className="flex min-h-[100dvh]">
      <Sidebar />
      <div className="min-w-0 flex-1">
        <header className="sticky top-0 z-20 border-b bg-background/80 backdrop-blur-md supports-[backdrop-filter]:bg-background/65">
          <DemoBanner />
          {/* Una sola fila en escritorio; en móvil los recuentos bajan a una segunda línea. */}
          {/* En Inicio, «Nueva oferta» va con las acciones de la página: en escritorio, sin esta fila. */}
          <div
            className={cn(
              'mx-auto flex max-w-6xl flex-wrap items-center lg:flex-nowrap gap-x-3 gap-y-1 px-4 py-2 sm:px-6',
              home && 'lg:hidden',
            )}
          >
            <MobileNav />
            <div className="lg:hidden">
              <Brand />
            </div>
            {!home && (
              <div className="order-last min-w-0 basis-full lg:order-none lg:basis-auto lg:flex-1">
                <StageCounts />
              </div>
            )}
            {!home && (
              <Button asChild size="sm" className="ml-auto shrink-0 active:translate-y-px">
                <Link to="/nueva">
                  <PlusIcon weight="bold" />
                  <span className="sr-only sm:not-sr-only">{t('header.newJob')}</span>
                </Link>
              </Button>
            )}
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-4 pb-24 pt-6 sm:px-6 sm:pt-8">
          <div className="mb-6 space-y-3 empty:hidden">
            <BackgroundRunReminder />
            <ExtractionReminder />
            <FollowupReminder />
          </div>
          <Outlet />
        </main>
      </div>
      <UserPrompts />
    </div>
  )
}
