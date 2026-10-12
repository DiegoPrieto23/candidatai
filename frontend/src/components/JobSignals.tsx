import { useEffect, useRef, useState } from 'react'
import { ArrowsClockwiseIcon, CheckIcon, ClockCounterClockwiseIcon, LinkBreakIcon, XIcon } from '@phosphor-icons/react'
import type { JobSignals, JobView, Stage } from '@/api/client'
import { useCheckJobOpen, useConfirmJobOpen, useJobEvent } from '@/api/queries'
import { DiscardDialog } from '@/components/DiscardDialog'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { formatDate, formatDateTime } from '@/lib/labels'
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

function listDates(dates: string[]): string {
  const labels = dates.map((d) => formatDate(d))
  if (labels.length < 2) return labels.join('')
  return `${labels.slice(0, -1).join(', ')} y ${labels[labels.length - 1]}`
}

function repostText(reposted: NonNullable<JobSignals['reposted']>): string {
  const channel = CHANNEL_LABEL[reposted.channel] ?? reposted.channel
  return `Publicada de nuevo en ${channel} en ${reposted.count} días distintos: ${listDates(reposted.dates)}.`
}

/** Insignias «Republicada ×N» y «¿Cerrada?» para listas (bandeja, triaje). */
export function SignalBadges({ signals, className }: { signals?: JobSignals; className?: string }) {
  const reposted = signals?.reposted
  const closed = signals?.possibly_closed
  if (!reposted && !closed) return null
  return (
    <span className={cn('inline-flex shrink-0 items-center gap-1', className)}>
      {closed && (
        <Tooltip>
          <TooltipTrigger asChild>
            <span className="rounded-full border border-warning-border bg-warning px-1.5 py-px text-[0.7rem] leading-4 font-medium whitespace-nowrap text-warning-foreground">
              ¿Cerrada?
            </span>
          </TooltipTrigger>
          <TooltipContent>Puede que ya no esté publicada: {closed.detail}.</TooltipContent>
        </Tooltip>
      )}
      {reposted && (
        <Tooltip>
          <TooltipTrigger asChild>
            <span className="rounded-full border px-1.5 py-px text-[0.7rem] leading-4 font-medium whitespace-nowrap text-muted-foreground">
              Republicada ×{reposted.count}
            </span>
          </TooltipTrigger>
          <TooltipContent className="max-w-xs">
            {repostText(reposted)} Es una observación, no un veredicto.
          </TooltipContent>
        </Tooltip>
      )}
    </span>
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
      aria-label="Puede que esté cerrada"
      className="rounded-xl border border-warning-border bg-warning p-5 text-warning-foreground"
    >
      <div className="flex items-start gap-3">
        <LinkBreakIcon className="mt-0.5 size-6 shrink-0" weight="duotone" />
        <div className="min-w-0 flex-1 space-y-3">
          <div>
            <h2 className="font-semibold">Puede que ya no esté publicada</h2>
            <p className="mt-1 text-sm opacity-90">
              {closed.detail.charAt(0).toUpperCase() + closed.detail.slice(1)}. Comprobado el{' '}
              {formatDateTime(closed.checked_at)}
              {closed.since !== closed.checked_at && <> (lo dice desde el {formatDate(closed.since)})</>}. Job
              Hunter no la cierra: decide tú.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="outline" className="bg-background/70" onClick={() => setDiscarding(true)}>
              <XIcon weight="bold" />
              Descartar
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="bg-background/70"
              disabled={confirm.isPending}
              onClick={() => confirm.mutate(job.id)}
            >
              <CheckIcon weight="bold" />
              Sigue abierta
            </Button>
            <Button
              size="sm"
              variant="ghost"
              disabled={check.isPending}
              onClick={() => check.mutate({ jobId: job.id, force: true })}
            >
              <ArrowsClockwiseIcon className={cn(check.isPending && 'animate-spin')} />
              {check.isPending ? 'Comprobando…' : 'Comprobar otra vez'}
            </Button>
          </div>
          {check.data && !check.data.possibly_closed && (
            <p role="status" className="text-sm">{check.data.message}</p>
          )}
          {error && <p role="alert" className="text-sm text-destructive">{error.message}</p>}
        </div>
      </div>
      <DiscardDialog
        open={discarding}
        onOpenChange={setDiscarding}
        jobTitle={`${job.title} · ${job.company}`}
        initialReason="closed"
        pending={event.isPending}
        error={event.isError ? event.error.message : null}
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
  const reposted = job.signals?.reposted
  if (!reposted) return null
  return (
    <p className="flex items-start gap-2.5 rounded-xl border bg-card px-4 py-3 text-sm text-muted-foreground">
      <ClockCounterClockwiseIcon className="mt-0.5 size-[18px] shrink-0" weight="duotone" />
      <span>
        <span className="font-medium text-foreground">Republicada ×{reposted.count}.</span> {repostText(reposted)} Puede
        ser una oferta difícil de cubrir o una publicación que se renueva sola: es una observación, no un veredicto.
      </span>
    </p>
  )
}

/** Aviso junto a «Generar CV» si puede estar cerrada. */
export function ClosedHint({ signals }: { signals?: JobSignals }) {
  const closed = signals?.possibly_closed
  if (!closed) return null
  return (
    <p role="note" className="mt-2 flex items-start gap-1.5 text-xs text-warning-foreground">
      <LinkBreakIcon className="mt-px size-3.5 shrink-0" weight="bold" />
      Antes de gastar cuota: puede que esta oferta ya no esté publicada ({closed.detail}).
    </p>
  )
}
