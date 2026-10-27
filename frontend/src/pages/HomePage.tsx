import { useState, type ReactNode } from 'react'
import { Link } from 'react-router'
import { ArrowRightIcon } from '@phosphor-icons/react'
import { Trans, useTranslation } from 'react-i18next'
import type { JobRow, Stage, UpcomingItem } from '@/api/client'
import { useFollowups, useJobs, useReplies, useStatus, useUpcoming } from '@/api/queries'
import { AgentButton } from '@/components/AgentButton'
import { ScoreBadge } from '@/components/MatchDetails'
import { ErrorState } from '@/components/States'
import { Skeleton } from '@/components/ui/skeleton'
import { formatList, joinNodes } from '@/lib/i18n'
import { dateFormatter, STAGE_LABEL, UPCOMING_KIND_LABEL } from '@/lib/labels'
import { APP_TIME_ZONE, formatWhen } from '@/lib/time'
import { cn } from '@/lib/utils'

// --- Qué toca hoy ---------------------------------------------------------------------------

const TODAY = { timeZone: APP_TIME_ZONE, weekday: 'long', day: 'numeric', month: 'long' } as const

function Pending({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link
      to={to}
      className="rounded-sm text-primary underline decoration-primary/30 decoration-2 underline-offset-[6px] transition-colors hover:decoration-primary"
    >
      {children}
    </Link>
  )
}

function Today() {
  const { t } = useTranslation('home')
  const status = useStatus()
  const followups = useFollowups()
  const replies = useReplies()
  // La fecha del encabezado, la de cuando se abre la página.
  const [now] = useState(() => new Date())
  const s = status.data?.by_stage
  const due = followups.data?.followups.length ?? 0
  const proposed = replies.data?.counts.proposed ?? 0
  const unclassified = replies.data?.counts.new ?? 0

  const yours: ReactNode[] = []
  if (s?.pending_triage)
    yours.push(
      <Pending key="triage" to="/por-revisar">
        {t('today.toReview', { count: s.pending_triage })}
      </Pending>,
    )
  if (s?.cv_ready)
    yours.push(
      <Pending key="cv" to="/bandeja?stage=cv_ready">
        {t('today.cvReady', { count: s.cv_ready })}
      </Pending>,
    )
  if (proposed)
    yours.push(
      <Pending key="replies" to="/respuestas">
        {t('today.replies', { count: proposed })}
      </Pending>,
    )
  if (due)
    yours.push(
      <Pending key="followups" to="/procesos">
        {t('today.followups', { count: due })}
      </Pending>,
    )

  const agent: string[] = []
  if (s?.pending_extraction) agent.push(t('today.agentToExtract', { count: s.pending_extraction }))
  if (s?.approved) agent.push(t('today.agentApproved', { count: s.approved }))
  if (unclassified) agent.push(t('today.agentUnclassified', { count: unclassified }))

  // Solo una acción destacada: la que más desbloquea ahora. Las demás, con borde.
  const primary = s?.pending_extraction
    ? 'process-jobs'
    : unclassified
      ? 'review-replies'
      : s?.pending_triage
        ? 'assess-fit'
        : 'search-jobs'

  return (
    <section aria-labelledby="hoy" className="max-w-3xl">
      <p className="text-sm text-muted-foreground first-letter:uppercase">{dateFormatter(TODAY).format(now)}</p>
      <h1 id="hoy" className="mt-3 text-3xl leading-[1.2] font-semibold tracking-tight text-balance sm:text-[2.6rem]">
        {status.isPending ? (
          <Skeleton className="h-12 w-full max-w-xl" />
        ) : yours.length ? (
          <Trans t={t} i18nKey="today.youHave" components={{ list: <>{joinNodes(yours)}</> }} />
        ) : (
          t('today.nothing')
        )}
      </h1>
      {agent.length > 0 && (
        <p className="mt-4 text-base text-muted-foreground">{t('today.forAgent', { list: formatList(agent) })}</p>
      )}
      {/* Abren tu agente en una terminal con la orden escrita: lo que haga lo ves y lo apruebas tú. */}
      <div className="mt-6 flex flex-wrap items-start gap-2">
        <AgentButton action="search-jobs" size="default" primary={primary === 'search-jobs'}>
          {t('today.searchJobs')}
        </AgentButton>
        {!!s?.pending_extraction && (
          <AgentButton action="process-jobs" size="default" primary={primary === 'process-jobs'}>
            {t('today.processJobs')}
          </AgentButton>
        )}
        {!!s?.pending_triage && (
          <AgentButton action="assess-fit" size="default" primary={primary === 'assess-fit'}>
            {t('today.assessFit')}
          </AgentButton>
        )}
        {unclassified > 0 && (
          <AgentButton action="review-replies" size="default" primary={primary === 'review-replies'}>
            {t('today.reviewReplies')}
          </AgentButton>
        )}
      </div>
    </section>
  )
}

// --- Recorrido ------------------------------------------------------------------------------

type Actor = 'you' | 'agent' | 'company'

const TRACK: { stage: Stage; actor: Actor; to: string }[] = [
  { stage: 'pending_detail', actor: 'you', to: '/alertas' },
  { stage: 'pending_extraction', actor: 'agent', to: '/bandeja?stage=pending_extraction' },
  { stage: 'pending_triage', actor: 'you', to: '/por-revisar' },
  { stage: 'approved', actor: 'agent', to: '/bandeja?stage=approved' },
  { stage: 'cv_ready', actor: 'you', to: '/bandeja?stage=cv_ready' },
  { stage: 'applied', actor: 'company', to: '/procesos' },
  { stage: 'in_process', actor: 'you', to: '/procesos' },
]

function Track() {
  const { t } = useTranslation('home')
  const { data, isPending, isError, error, refetch } = useStatus()
  if (isError) return <ErrorState error={error} onRetry={() => void refetch()} />
  const counts = data?.by_stage
  const max = Math.max(1, ...TRACK.map((step) => counts?.[step.stage] ?? 0))

  return (
    <section aria-labelledby="recorrido">
      <div className="mb-3 flex items-baseline justify-between gap-4">
        <h2 id="recorrido" className="text-sm font-medium">
          {t('track.title')}
        </h2>
        {counts && (
          <Link to="/bandeja?stage=closed" className="text-xs text-muted-foreground hover:text-foreground">
            {t('track.closed', { count: counts.closed })}
          </Link>
        )}
      </div>
      <ol className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border bg-border sm:grid-cols-4 lg:grid-cols-7">
        {TRACK.map(({ stage, actor, to }, i) => {
          const count = counts?.[stage] ?? 0
          const yours = actor === 'you' && count > 0
          // 7 etapas: en 2 y 4 columnas la última ocupa dos celdas para no dejar un hueco.
          const last = i === TRACK.length - 1
          return (
            <li key={stage} className="contents">
              <Link
                to={to}
                className={cn(
                  'group relative flex flex-col gap-3 p-4 transition-colors outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset',
                  last && 'col-span-2 lg:col-span-1',
                  yours ? 'bg-accent/70 hover:bg-accent' : 'bg-background hover:bg-foreground/[0.03]',
                )}
              >
                <span
                  className={cn(
                    'text-[0.7rem] font-medium tracking-wide uppercase',
                    yours ? 'text-accent-foreground' : 'text-muted-foreground/80',
                  )}
                >
                  {t(`track.actor.${actor}`)}
                </span>
                {isPending ? (
                  <Skeleton className="h-8 w-10" />
                ) : (
                  <span
                    className={cn(
                      'tabular text-3xl leading-none font-semibold tracking-tight',
                      count ? 'text-foreground' : 'text-muted-foreground/50',
                    )}
                  >
                    {count}
                  </span>
                )}
                <span className="h-1 w-full overflow-hidden rounded-full bg-foreground/[0.07]" aria-hidden>
                  <span
                    className={cn(
                      'block h-full rounded-full transition-[width] duration-700 ease-out motion-reduce:transition-none',
                      yours ? 'bg-primary' : 'bg-foreground/25',
                    )}
                    style={{ width: `${(count / max) * 100}%` }}
                  />
                </span>
                <span className="text-sm text-muted-foreground group-hover:text-foreground">
                  {STAGE_LABEL[stage]}
                </span>
              </Link>
            </li>
          )
        })}
      </ol>
    </section>
  )
}

// --- Listas ---------------------------------------------------------------------------------

function Panel({
  title,
  more,
  children,
  className,
}: {
  title: string
  more?: { to: string; label: string }
  children: ReactNode
  className?: string
}) {
  return (
    <section className={cn('min-w-0 rounded-xl border bg-card', className)}>
      <div className="flex items-baseline justify-between gap-4 border-b px-4 py-3">
        <h2 className="text-sm font-medium">{title}</h2>
        {more && (
          <Link
            to={more.to}
            className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
          >
            {more.label}
            <ArrowRightIcon className="size-3" />
          </Link>
        )}
      </div>
      {children}
    </section>
  )
}

function Empty({ children }: { children: ReactNode }) {
  return <p className="px-4 py-6 text-sm text-muted-foreground">{children}</p>
}

function Loading({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-3 p-4">
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className="h-9" />
      ))}
    </div>
  )
}

function JobList({ stage, limit, empty }: { stage: Stage; limit: number; empty: ReactNode }) {
  const { data, isPending, isError, error, refetch } = useJobs({ stage, page: 1, sort: 'score', dir: 'desc' })
  if (isPending) return <Loading rows={Math.min(limit, 4)} />
  if (isError) return <ErrorState error={error} onRetry={() => void refetch()} className="py-8" />
  const jobs = data.items.slice(0, limit)
  if (!jobs.length) return <Empty>{empty}</Empty>
  return (
    <ul className="divide-y">
      {jobs.map((job) => (
        <JobItem key={job.id} job={job} />
      ))}
    </ul>
  )
}

function JobItem({ job }: { job: JobRow }) {
  return (
    <li>
      <Link
        to={`/jobs/${job.id}`}
        className="flex items-center justify-between gap-4 px-4 py-3 transition-colors hover:bg-foreground/[0.03] focus-visible:bg-foreground/[0.03] focus-visible:outline-none"
      >
        <span className="min-w-0">
          <span className="block truncate text-sm font-medium">{job.title}</span>
          <span className="block truncate text-xs text-muted-foreground">
            {[job.company, job.location].filter(Boolean).join(' · ')}
          </span>
        </span>
        <ScoreBadge score={job.score} />
      </Link>
    </li>
  )
}

function Upcoming() {
  const { t } = useTranslation('home')
  const { data, isPending, isError, error, refetch } = useUpcoming(7)
  if (isPending) return <Loading rows={2} />
  if (isError) return <ErrorState error={error} onRetry={() => void refetch()} className="py-8" />
  if (!data.items.length) return <Empty>{t('upcomingEmpty')}</Empty>
  return (
    <ul className="divide-y">
      {data.items.slice(0, 4).map((item: UpcomingItem) => (
        <li key={`${item.kind}-${item.milestone_id ?? item.job_id}-${item.starts_at}`}>
          <Link
            to={`/jobs/${item.job_id}`}
            className="block px-4 py-3 transition-colors hover:bg-foreground/[0.03] focus-visible:bg-foreground/[0.03] focus-visible:outline-none"
          >
            <span className="block text-xs text-primary">{formatWhen(item.starts_at, item.all_day)}</span>
            <span className="block truncate text-sm font-medium">{item.title || UPCOMING_KIND_LABEL[item.kind]}</span>
            <span className="block truncate text-xs text-muted-foreground">
              {item.job_title} · {item.company}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  )
}

function Followups() {
  const { t } = useTranslation('home')
  const { data, isPending } = useFollowups()
  if (isPending || !data?.followups.length) return null
  return (
    <Panel title={t('followups.title')} more={{ to: '/procesos', label: t('followups.more') }}>
      <ul className="divide-y">
        {data.followups.slice(0, 4).map((f) => (
          <li key={f.job_id}>
            <Link
              to={`/jobs/${f.job_id}`}
              className="flex items-center justify-between gap-4 px-4 py-3 transition-colors hover:bg-foreground/[0.03] focus-visible:bg-foreground/[0.03] focus-visible:outline-none"
            >
              <span className="min-w-0">
                <span className="block truncate text-sm font-medium">{f.title}</span>
                <span className="block truncate text-xs text-muted-foreground">{f.company}</span>
              </span>
              <span className="tabular shrink-0 text-xs text-muted-foreground">{t('followups.days', { count: f.days_waiting })}</span>
            </Link>
          </li>
        ))}
      </ul>
    </Panel>
  )
}

// --- Página ---------------------------------------------------------------------------------

export function HomePage() {
  const { t } = useTranslation('home')
  return (
    <div className="space-y-12 animate-in fade-in duration-300 sm:space-y-14">
      <Today />
      <Track />
      <div className="grid items-start gap-6 lg:grid-cols-5">
        <Panel
          title={t('panels.bestFit')}
          more={{ to: '/por-revisar', label: t('panels.review') }}
          className="lg:col-span-3"
        >
          <JobList
            stage="pending_triage"
            limit={6}
            empty={t('panels.bestFitEmpty')}
          />
        </Panel>
        <div className="grid min-w-0 gap-6 lg:col-span-2">
          <Panel title={t('panels.readyToSend')} more={{ to: '/bandeja?stage=cv_ready', label: t('panels.all') }}>
            <JobList stage="cv_ready" limit={4} empty={t('panels.readyEmpty')} />
          </Panel>
          <Panel title={t('panels.next7')} more={{ to: '/procesos', label: t('panels.calendar') }}>
            <Upcoming />
          </Panel>
          <Followups />
        </div>
      </div>
    </div>
  )
}
