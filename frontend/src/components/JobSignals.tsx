import { useEffect, useRef, useState } from 'react'
import {
  ArrowsClockwiseIcon,
  ArrowsHorizontalIcon,
  CalendarXIcon,
  CheckIcon,
  ClockCounterClockwiseIcon,
  EyeSlashIcon,
  FlagIcon,
  HourglassIcon,
  LinkBreakIcon,
  RobotIcon,
  XIcon,
  type Icon,
} from '@phosphor-icons/react'
import { useTranslation } from 'react-i18next'
import { SafeTrans } from '@/components/SafeTrans'
import type { JobSignals, JobView, Stage } from '@/api/client'
import { useCheckJobOpen, useConfirmJobOpen, useJobEvent } from '@/api/queries'
import { DiscardDialog } from '@/components/DiscardDialog'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { errorMessage } from '@/lib/errors'
import { formatList, i18n } from '@/lib/i18n'
import { formatDate, formatDateTime, formatMoney, formatNumber } from '@/lib/labels'
import { cn } from '@/lib/utils'

/** Etapas en las que se puede descartar (el aviso de cierre solo tiene sentido antes de enviar). */
const BEFORE_SENDING: ReadonlySet<Stage> = new Set([
  'pending_detail',
  'pending_extraction',
  'pending_triage',
  'approved',
  'cv_ready',
])
/** Las que comprueba el worker cada día; la ficha también, al abrirla, si la comprobación caducó. */
const CHECKED_STAGES: ReadonlySet<Stage> = new Set(['approved', 'cv_ready'])

const CHANNEL_LABEL: Record<string, string> = {
  linkedin: 'LinkedIn',
  infojobs: 'InfoJobs',
  indeed: 'Indeed',
  tecnoempleo: 'Tecnoempleo',
}

function repostText(reposted: NonNullable<JobSignals['reposted']>): string {
  const channel = CHANNEL_LABEL[reposted.channel] ?? reposted.channel
  const dates = formatList(reposted.dates.map((d) => formatDate(d)))
  return i18n.t('signals:reposted', { channel, count: reposted.count, dates })
}

type DoubtfulCode = 'salary_range_wide' | 'employer_hidden' | 'fixed_term' | 'stale_repost' | 'ai_screening'

const DOUBTFUL_ICON: Record<DoubtfulCode, Icon> = {
  salary_range_wide: ArrowsHorizontalIcon,
  employer_hidden: EyeSlashIcon,
  fixed_term: HourglassIcon,
  stale_repost: CalendarXIcon,
  ai_screening: RobotIcon,
}

function money(amount: number, currency: string | null | undefined): string {
  return currency ? formatMoney(amount, currency) : formatNumber(amount)
}

/** Señales de oferta dudosa activas (fase 25.3), en el orden del backend, con su texto. */
export function doubtfulSignals(signals?: JobSignals): { code: DoubtfulCode; detail: string }[] {
  if (!signals) return []
  type DetailKey =
    | Exclude<DoubtfulCode, 'employer_hidden'>
    | 'agency'
    | 'agency_for_client'
    | 'unnamed'
    | 'ai_screening_phrase'
  const t = (key: DetailKey, values?: Record<string, unknown>) =>
    i18n.t(`signals:doubtful.detail.${key}`, values ?? {})
  const out: { code: DoubtfulCode; detail: string }[] = []
  const salary = signals.salary_range_wide
  if (salary) {
    out.push({
      code: 'salary_range_wide',
      detail: t('salary_range_wide', {
        min: money(salary.min, salary.currency),
        max: money(salary.max, salary.currency),
        pct: salary.pct,
      }),
    })
  }
  const hidden = signals.employer_hidden
  if (hidden) out.push({ code: 'employer_hidden', detail: t(hidden.reason, { client: hidden.client }) })
  if (signals.fixed_term) out.push({ code: 'fixed_term', detail: t('fixed_term') })
  const stale = signals.stale_repost
  if (stale) {
    out.push({
      code: 'stale_repost',
      detail: t('stale_repost', {
        first: formatDate(stale.first_seen),
        last: formatDate(stale.last_seen),
        days: stale.span_days,
        count: stale.count,
        channel: CHANNEL_LABEL[stale.channel] ?? stale.channel,
      }),
    })
  }
  const ai = signals.ai_screening
  if (ai) {
    out.push({ code: 'ai_screening', detail: ai.matched ? t('ai_screening_phrase', { phrase: ai.matched }) : t('ai_screening') })
  }
  return out
}

/** Insignias «Republicada ×N», «¿Cerrada?» y de oferta dudosa para listas (bandeja, triaje). */
export function SignalBadges({ signals, className }: { signals?: JobSignals; className?: string }) {
  const { t } = useTranslation('signals')
  const reposted = signals?.reposted
  const closed = signals?.possibly_closed
  const doubtful = doubtfulSignals(signals)
  if (!reposted && !closed && doubtful.length === 0) return null
  return (
    <span className={cn('inline-flex shrink-0 items-center gap-1', className)}>
      {closed && (
        <Tooltip>
          <TooltipTrigger asChild>
            <span className="rounded-full border border-warning-border bg-warning px-1.5 py-px text-[0.7rem] leading-4 font-medium whitespace-nowrap text-warning-foreground">
              {t('closedBadge')}
            </span>
          </TooltipTrigger>
          <TooltipContent>{t('closedTooltip', { detail: closed.detail })}</TooltipContent>
        </Tooltip>
      )}
      {reposted && (
        <Tooltip>
          <TooltipTrigger asChild>
            <span className="rounded-full border px-1.5 py-px text-[0.7rem] leading-4 font-medium whitespace-nowrap text-muted-foreground">
              {t('repostedBadge', { count: reposted.count })}
            </span>
          </TooltipTrigger>
          <TooltipContent className="max-w-xs">
            {repostText(reposted)} {t('observation')}
          </TooltipContent>
        </Tooltip>
      )}
      {doubtful.map(({ code, detail }) => {
        const SignalIcon = DOUBTFUL_ICON[code]
        return (
          <Tooltip key={code}>
            <TooltipTrigger asChild>
              <span className="inline-flex items-center gap-1 rounded-full border px-1.5 py-px text-[0.7rem] leading-4 font-medium whitespace-nowrap text-muted-foreground">
                <SignalIcon className="size-3" weight="bold" aria-hidden />
                {t(`doubtful.badge.${code}`)}
              </span>
            </TooltipTrigger>
            <TooltipContent className="max-w-xs">
              {detail} {t('observation')}
            </TooltipContent>
          </Tooltip>
        )
      })}
    </span>
  )
}

/** Oferta dudosa (fase 25.3): una nota en la ficha con cada señal y su explicación. No es un aviso:
 *  no cambian el score ni descartan la oferta. */
export function DoubtfulNote({ job }: { job: JobView }) {
  const { t } = useTranslation('signals', { keyPrefix: 'doubtful' })
  const doubtful = doubtfulSignals(job.signals)
  if (doubtful.length === 0) return null
  return (
    <section aria-label={t('label')} className="rounded-xl border bg-card px-4 py-3 text-sm">
      <h2 className="flex items-center gap-2 font-medium">
        <FlagIcon className="size-[18px] shrink-0 text-muted-foreground" weight="duotone" aria-hidden />
        {t('title')}
      </h2>
      <ul className="mt-2 space-y-1.5">
        {doubtful.map(({ code, detail }) => {
          const SignalIcon = DOUBTFUL_ICON[code]
          return (
            <li key={code} className="flex items-start gap-2">
              <SignalIcon className="mt-0.5 size-4 shrink-0 text-muted-foreground" weight="bold" aria-hidden />
              <span>
                <span className="font-medium">{t(`badge.${code}`)}.</span>{' '}
                <span className="text-muted-foreground">{detail}</span>
              </span>
            </li>
          )
        })}
      </ul>
      <p className="mt-2 text-xs text-muted-foreground">
        <SafeTrans t={t} i18nKey="intro" components={{ code: <code className="font-mono text-[0.85em]" /> }} />
      </p>
    </section>
  )
}

/**
 * Al abrir una oferta aprobada o con CV listo, comprueba si sigue abierta (una vez por visita). El
 * backend devuelve la comprobación reciente sin repetirla si es de hace menos de `fresh_hours`.
 */
function useAutoCheck(job: JobView) {
  const check = useCheckJobOpen()
  const done = useRef<number | null>(null)
  const eligible = job.stage !== null && CHECKED_STAGES.has(job.stage) && Boolean(job.url)
  useEffect(() => {
    if (!eligible || done.current === job.id) return
    done.current = job.id
    check.mutate({ jobId: job.id })
  }, [eligible, job.id, check])
}

/** Aviso de posible cierre en la ficha: propone descartar, nunca cierra sola. */
export function ClosedNotice({ job }: { job: JobView }) {
  const { t } = useTranslation('signals', { keyPrefix: 'closedNotice' })
  useAutoCheck(job)
  const closed = job.signals?.possibly_closed
  const check = useCheckJobOpen()
  const confirm = useConfirmJobOpen()
  const event = useJobEvent()
  const [discarding, setDiscarding] = useState(false)
  if (!closed || job.stage === null || !BEFORE_SENDING.has(job.stage)) return null
  const error = check.error ?? confirm.error
  return (
    <section
      aria-label={t('label')}
      className="rounded-xl border border-warning-border bg-warning p-5 text-warning-foreground"
    >
      <div className="flex items-start gap-3">
        <LinkBreakIcon className="mt-0.5 size-6 shrink-0" weight="duotone" />
        <div className="min-w-0 flex-1 space-y-3">
          <div>
            <h2 className="font-semibold">{t('title')}</h2>
            <p className="mt-1 text-sm opacity-90">
              {t('checked', {
                detail: closed.detail.charAt(0).toUpperCase() + closed.detail.slice(1),
                checkedAt: formatDateTime(closed.checked_at),
              })}
              {closed.since !== closed.checked_at && t('since', { since: formatDate(closed.since) })}
              {t('decide')}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="outline" className="bg-background/70" onClick={() => setDiscarding(true)}>
              <XIcon weight="bold" />
              {t('discard')}
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="bg-background/70"
              disabled={confirm.isPending}
              onClick={() => confirm.mutate(job.id)}
            >
              <CheckIcon weight="bold" />
              {t('stillOpen')}
            </Button>
            <Button
              size="sm"
              variant="ghost"
              disabled={check.isPending}
              onClick={() => check.mutate({ jobId: job.id, force: true })}
            >
              <ArrowsClockwiseIcon className={cn(check.isPending && 'animate-spin')} />
              {check.isPending ? t('checking') : t('checkAgain')}
            </Button>
          </div>
          {check.data && !check.data.possibly_closed && (
            <p role="status" className="text-sm">{check.data.message}</p>
          )}
          {error && <p role="alert" className="text-sm text-destructive">{errorMessage(error)}</p>}
        </div>
      </div>
      <DiscardDialog
        open={discarding}
        onOpenChange={setDiscarding}
        jobTitle={`${job.title} · ${job.company}`}
        initialReason="closed"
        pending={event.isPending}
        error={event.isError ? errorMessage(event.error) : null}
        onConfirm={(choice) =>
          event.mutate(
            { jobId: job.id, body: { type: 'discarded', reason: choice.reason, note: choice.note } },
            { onSuccess: () => setDiscarding(false) },
          )
        }
      />
    </section>
  )
}

/** Republicada: una nota discreta en la ficha, no un aviso. */
export function RepostNote({ job }: { job: JobView }) {
  const { t } = useTranslation('signals')
  const reposted = job.signals?.reposted
  if (!reposted) return null
  return (
    <p className="flex items-start gap-2.5 rounded-xl border bg-card px-4 py-3 text-sm text-muted-foreground">
      <ClockCounterClockwiseIcon className="mt-0.5 size-[18px] shrink-0" weight="duotone" />
      <span>
        <SafeTrans
          t={t}
          i18nKey="repostNote"
          values={{ count: reposted.count, text: repostText(reposted) }}
          components={{ strong: <span className="font-medium text-foreground" /> }}
        />
      </span>
    </p>
  )
}

/** Aviso junto a «Generar CV» si puede estar cerrada. */
export function ClosedHint({ signals }: { signals?: JobSignals }) {
  const { t } = useTranslation('signals')
  const closed = signals?.possibly_closed
  if (!closed) return null
  return (
    <p role="note" className="mt-2 flex items-start gap-1.5 text-xs text-warning-foreground">
      <LinkBreakIcon className="mt-px size-3.5 shrink-0" weight="bold" />
      {t('closedHint', { detail: closed.detail })}
    </p>
  )
}
