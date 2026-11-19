import { ArrowCounterClockwiseIcon, ArrowSquareOutIcon, RepeatIcon, XIcon } from '@phosphor-icons/react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import type { JobView, Schemas } from '@/api/client'
import { useDismissRepublished, useJobEvent, useRepublishedJobs } from '@/api/queries'
import { SafeTrans } from '@/components/SafeTrans'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { errorMessage } from '@/lib/errors'
import { formatDate } from '@/lib/labels'

type ReopeningOf = NonNullable<JobView['reopening']>

/** Cómo acabó la oferta anterior, en pocas palabras («te rechazaron durante el proceso»). */
type How = 'rejected' | 'rejected_in_process' | 'expired' | 'closed' | 'other'
type ClosedBy = 'withdrawn' | 'accepted' | 'discarded' | 'other'

function howItEnded(previous: ReopeningOf): How {
  if (previous.closed_by === 'rejected') {
    return previous.stage_before_close === 'in_process' ? 'rejected_in_process' : 'rejected'
  }
  if (previous.closed_by === 'expired') return 'expired'
  if (previous.closed_by === 'discarded' && previous.discard_reason === 'closed') return 'closed'
  return 'other'
}

/** «Reabierta» en las listas: la vacante vuelve tras cerrarla la empresa o caducar (fase 45). */
export function ReopenedBadge({ reopeningOf }: { reopeningOf?: number | null }) {
  const { t } = useTranslation('signals', { keyPrefix: 'reopening' })
  if (!reopeningOf) return null
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="inline-flex shrink-0 items-center gap-1 rounded-full border px-1.5 py-px text-[0.7rem] leading-4 font-medium whitespace-nowrap text-muted-foreground">
          <RepeatIcon className="size-3" weight="bold" aria-hidden />
          {t('badge')}
        </span>
      </TooltipTrigger>
      <TooltipContent className="max-w-xs">{t('badgeTooltip')}</TooltipContent>
    </Tooltip>
  )
}

/** En la ficha de una reapertura: de qué oferta viene y cómo acabó. Una nota, no un aviso. */
export function ReopeningNote({ job }: { job: JobView }) {
  const { t } = useTranslation('signals', { keyPrefix: 'reopening' })
  const previous = job.reopening
  if (!previous) return null
  return (
    <p className="flex items-start gap-2.5 rounded-xl border bg-card px-4 py-3 text-sm text-muted-foreground">
      <RepeatIcon className="mt-0.5 size-[18px] shrink-0" weight="duotone" />
      <span>
        <SafeTrans
          t={t}
          i18nKey="note"
          values={{ date: formatDate(previous.first_seen_at), how: t(`how.${howItEnded(previous)}`) }}
          components={{
            strong: <span className="font-medium text-foreground" />,
            job: <Link to={`/jobs/${previous.job_id}`} className="underline underline-offset-4 hover:text-foreground" />,
          }}
        />
      </span>
    </p>
  )
}

function ReopenButtons({ jobId, compact = false }: { jobId: number; compact?: boolean }) {
  const { t } = useTranslation('signals', { keyPrefix: 'republished' })
  const event = useJobEvent()
  const dismiss = useDismissRepublished()
  const error = event.error ?? dismiss.error
  return (
    <>
      <div className="flex flex-wrap gap-2">
        <Button
          size={compact ? 'xs' : 'sm'}
          variant="outline"
          className="bg-background/70"
          disabled={event.isPending}
          onClick={() => event.mutate({ jobId, body: { type: 'reopened' } })}
        >
          <ArrowCounterClockwiseIcon weight="bold" />
          {t('reopen')}
        </Button>
        <Button size={compact ? 'xs' : 'sm'} variant="ghost" disabled={dismiss.isPending} onClick={() => dismiss.mutate(jobId)}>
          <XIcon weight="bold" />
          {t('dismiss')}
        </Button>
      </div>
      {error && <p role="alert" className="text-sm text-destructive">{errorMessage(error)}</p>}
    </>
  )
}

function PostingLink({ url }: { url?: string | null }) {
  const { t } = useTranslation('signals', { keyPrefix: 'republished' })
  if (!url) return null
  return (
    <a href={url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 underline underline-offset-4">
      {t('view')}
      <ArrowSquareOutIcon className="size-3.5" aria-hidden />
    </a>
  )
}

/** En la ficha de una oferta que cerraste: ha vuelto a publicarse. Reabrir o ignorar. */
export function RepublishedNotice({ job }: { job: JobView }) {
  const { t } = useTranslation('signals', { keyPrefix: 'republished' })
  const signal = job.signals?.republished_after_close
  if (!signal || signal.dismissed_at || job.stage !== 'closed') return null
  return (
    <section aria-label={t('title')} className="rounded-xl border border-warning-border bg-warning p-5 text-warning-foreground">
      <div className="flex items-start gap-3">
        <RepeatIcon className="mt-0.5 size-6 shrink-0" weight="duotone" />
        <div className="min-w-0 flex-1 space-y-3">
          <div>
            <h2 className="font-semibold">{t('title')}</h2>
            <p className="mt-1 text-sm opacity-90">
              {t('jobText', { date: formatDate(signal.seen_at) })} <PostingLink url={signal.url} />
            </p>
          </div>
          <ReopenButtons jobId={job.id} />
        </div>
      </div>
    </section>
  )
}

function closedBy(item: Schemas['RepublishedNotice']): ClosedBy {
  const known: ClosedBy[] = ['withdrawn', 'accepted', 'discarded']
  return known.find((value) => value === item.closed_by) ?? 'other'
}

/** En la Bandeja: las ofertas que cerraste tú y han vuelto a publicarse. */
export function RepublishedBanner() {
  const { t } = useTranslation('signals', { keyPrefix: 'republished' })
  const { data } = useRepublishedJobs()
  const items = data?.items ?? []
  if (items.length === 0) return null
  return (
    <section aria-label={t('title')} className="rounded-xl border border-warning-border bg-warning px-4 py-3 text-sm text-warning-foreground">
      <h2 className="flex items-center gap-2 font-semibold">
        <RepeatIcon className="size-[18px] shrink-0" weight="duotone" />
        {t('bannerTitle', { count: items.length })}
      </h2>
      <ul className="mt-2 divide-y divide-warning-border/60">
        {items.map((item) => (
          <li key={item.job_id} className="flex flex-wrap items-center gap-x-4 gap-y-2 py-2">
            <div className="min-w-0 flex-1">
              <Link to={`/jobs/${item.job_id}`} className="font-medium underline-offset-4 hover:underline">
                {item.title}
              </Link>
              <span className="opacity-80"> · {item.company}</span>
              <p className="text-xs opacity-80">
                {t('bannerLine', { closedBy: t(`closedBy.${closedBy(item)}`), date: formatDate(item.seen_at) })}{' '}
                <PostingLink url={item.url} />
              </p>
            </div>
            <ReopenButtons jobId={item.job_id} compact />
          </li>
        ))}
      </ul>
    </section>
  )
}
