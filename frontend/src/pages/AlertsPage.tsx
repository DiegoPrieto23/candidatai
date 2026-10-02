import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router'
import {
  ArrowSquareOutIcon,
  ArrowsClockwiseIcon,
  EnvelopeSimpleIcon,
  FunnelSimpleXIcon,
  ProhibitIcon,
  WarningIcon,
  XIcon,
} from '@phosphor-icons/react'
import type { AlertJob, EmailPollResult } from '@/api/client'
import { useAlerts, useJobEvent, usePollAlerts } from '@/api/queries'
import { DiscardDialog, type DiscardChoice } from '@/components/DiscardDialog'
import { Kbd } from '@/components/Kbd'
import { EmptyState, ErrorState, InlineCode } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { isActivatable, isTyping } from '@/lib/keyboard'
import { discardReasonLabel, formatRelative } from '@/lib/labels'
import { cn } from '@/lib/utils'

/** Abre la oferta en su portal, en una pestaña nueva y sin dar acceso a esta. */
function openOffer(job: AlertJob) {
  window.open(job.url, '_blank', 'noopener,noreferrer')
}

function AlertRow({
  job,
  selected,
  onSelect,
  onDiscard,
}: {
  job: AlertJob
  selected: boolean
  onSelect: () => void
  onDiscard: () => void
}) {
  const ref = useRef<HTMLLIElement>(null)
  useEffect(() => {
    if (selected) ref.current?.scrollIntoView({ block: 'nearest' })
  }, [selected])
  const where = [job.company, job.location].filter(Boolean).join(' · ')
  return (
    <li
      ref={ref}
      role="option"
      aria-selected={selected}
      onClick={onSelect}
      className={cn(
        'relative flex cursor-pointer flex-col gap-3 px-4 py-3 transition-colors sm:flex-row sm:items-center',
        selected ? 'bg-accent/70' : 'hover:bg-foreground/[0.03]',
      )}
    >
      {selected && <span aria-hidden className="absolute inset-y-2 left-0 w-0.5 rounded-full bg-primary" />}
      <div className={cn('min-w-0 flex-1', !job.prefilter_passed && !selected && 'opacity-60')}>
        <p className="flex items-center gap-1.5 text-sm font-medium">
          <Link
            to={`/jobs/${job.job_id}`}
            onClick={(e) => e.stopPropagation()}
            className="truncate underline-offset-4 hover:underline"
          >
            {job.title}
          </Link>
          {job.risk_flags.length > 0 && (
            <WarningIcon
              className="size-3.5 shrink-0 text-warning-foreground"
              weight="fill"
              aria-label="Posible contenido dirigido a una IA"
            />
          )}
        </p>
        <p className="truncate text-xs text-muted-foreground">{where}</p>
        {!job.prefilter_passed && job.prefilter_reason && (
          <p className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground">
            <FunnelSimpleXIcon className="size-3.5 shrink-0" />
            <span className="truncate">{job.prefilter_reason}</span>
          </p>
        )}
      </div>
      <div className="flex shrink-0 items-center gap-3 text-xs text-muted-foreground">
        {job.platform_label && (
          <span className="rounded-full border px-2 py-0.5 font-medium text-foreground/80">{job.platform_label}</span>
        )}
        <span className="tabular hidden w-24 text-right md:inline" title={`Caduca ${formatRelative(job.expires_at)}`}>
          {formatRelative(job.first_seen_at)}
        </span>
        <Button
          asChild
          variant="outline"
          size="sm"
          onClick={(e) => e.stopPropagation()}
          className="active:translate-y-px"
        >
          <a href={job.url} target="_blank" rel="noopener noreferrer">
            Abrir
            <ArrowSquareOutIcon />
          </a>
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={(e) => {
            e.stopPropagation()
            onSelect()
            onDiscard()
          }}
          className="active:translate-y-px"
        >
          <XIcon weight="bold" />
          Descartar
        </Button>
      </div>
    </li>
  )
}

function PollResult({ result, onClose }: { result: EmailPollResult; onClose: () => void }) {
  return (
    <div
      role="status"
      className="flex items-start gap-3 rounded-xl border bg-card px-4 py-2.5 text-sm animate-in fade-in slide-in-from-top-1"
    >
      <EnvelopeSimpleIcon className="mt-0.5 size-[18px] shrink-0 text-primary" weight="duotone" />
      <div className="min-w-0 flex-1">
        <p>{result.message}</p>
        {result.errors.length > 0 && (
          <ul className="mt-1 space-y-0.5 text-xs text-muted-foreground">
            {result.errors.slice(0, 5).map((issue, i) => (
              <li key={i}>{issue.message}</li>
            ))}
          </ul>
        )}
      </div>
      <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground" aria-label="Cerrar aviso">
        <XIcon className="size-4" />
      </button>
    </div>
  )
}

interface Done {
  jobId: number
  title: string
  reason: string
}

function ListSkeleton() {
  return (
    <div aria-busy="true" aria-label="Cargando alertas" className="space-y-2 rounded-xl border bg-card p-3">
      {Array.from({ length: 6 }, (_, i) => (
        <Skeleton key={i} className="h-12" />
      ))}
    </div>
  )
}

export function AlertsPage() {
  const { data, isPending, isError, error, refetch } = useAlerts()
  const event = useJobEvent()
  const poll = usePollAlerts()
  const [hidden, setHidden] = useState<Set<number>>(new Set())
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [discarding, setDiscarding] = useState(false)
  const [done, setDone] = useState<Done | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const jobs = useMemo(() => (data?.jobs ?? []).filter((j) => !hidden.has(j.job_id)), [data, hidden])
  const index = Math.max(0, jobs.findIndex((j) => j.job_id === selectedId))
  const current = jobs[index] as AlertJob | undefined
  const passing = jobs.filter((j) => j.prefilter_passed)
  const failing = jobs.filter((j) => !j.prefilter_passed)

  const select = useCallback(
    (i: number) => {
      const next = jobs[Math.min(Math.max(i, 0), jobs.length - 1)]
      if (next) setSelectedId(next.job_id)
    },
    [jobs],
  )

  /** Oculta la oferta ya y selecciona la siguiente; si la API falla, vuelve a aparecer. */
  const discard = useCallback(
    (job: AlertJob, choice: DiscardChoice) => {
      const position = jobs.indexOf(job)
      const after = jobs[position + 1] ?? jobs[position - 1]
      setHidden((prev) => new Set(prev).add(job.job_id))
      setSelectedId(after ? after.job_id : null)
      setActionError(null)
      event.mutate(
        { jobId: job.job_id, body: { type: 'discarded', reason: choice.reason, note: choice.note } },
        {
          onSuccess: () => setDone({ jobId: job.job_id, title: job.title, reason: choice.reason }),
          onError: (err) => {
            setHidden((prev) => {
              const next = new Set(prev)
              next.delete(job.job_id)
              return next
            })
            setSelectedId(job.job_id)
            setActionError(err.message)
          },
        },
      )
    },
    [event, jobs],
  )

  const undo = () => {
    if (!done) return
    const { jobId } = done
    setDone(null)
    event.mutate(
      { jobId, body: { type: 'reopened' } },
      {
        onSuccess: () => {
          setHidden((prev) => {
            const next = new Set(prev)
            next.delete(jobId)
            return next
          })
          setSelectedId(jobId)
        },
        onError: (err) => setActionError(err.message),
      },
    )
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (discarding || e.metaKey || e.ctrlKey || e.altKey || isTyping(e.target)) return
      if (!current) return
      const key = e.key.toLowerCase()
      if (key === 'j' || e.key === 'ArrowDown') select(index + 1)
      else if (key === 'k' || e.key === 'ArrowUp') select(index - 1)
      else if (key === 'd') setDiscarding(true)
      else if (key === 'o' || (e.key === 'Enter' && !isActivatable(e.target))) openOffer(current)
      else return
      e.preventDefault()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [current, discarding, index, select])

  const total = jobs.length
  const renderRow = (job: AlertJob) => (
    <AlertRow
      key={job.job_id}
      job={job}
      selected={job.job_id === current?.job_id}
      onSelect={() => setSelectedId(job.job_id)}
      onDiscard={() => setDiscarding(true)}
    />
  )

  return (
    <div className="animate-in fade-in duration-300">
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Alertas</h1>
          <p className="max-w-prose text-sm text-muted-foreground">
            {isPending
              ? 'Cargando…'
              : `${total === 1 ? '1 oferta resumen' : `${total} ofertas resumen`} de tus alertas por correo. ` +
                'Ábrelas en su portal y envíalas con el botón «Enviar a Job Hunter» para completarlas, o descártalas.'}
          </p>
        </div>
        <div className="flex shrink-0 flex-col items-start gap-2 sm:items-end">
          <Button
            variant="outline"
            size="sm"
            onClick={() => poll.mutate()}
            disabled={poll.isPending}
            className="active:translate-y-px"
          >
            <ArrowsClockwiseIcon className={cn(poll.isPending && 'animate-spin')} />
            {poll.isPending ? 'Leyendo el correo…' : 'Revisar correo ahora'}
          </Button>
          {total > 0 && (
            <p className="hidden items-center gap-3 text-xs text-muted-foreground md:flex" aria-label="Atajos de teclado">
              <span className="flex items-center gap-1"><Kbd>J</Kbd><Kbd>K</Kbd> mover</span>
              <span className="flex items-center gap-1"><Kbd>O</Kbd> abrir</span>
              <span className="flex items-center gap-1"><Kbd>D</Kbd> descartar</span>
            </p>
          )}
        </div>
      </div>

      <div className="mb-4 space-y-3 empty:hidden">
        {poll.data && <PollResult result={poll.data} onClose={() => poll.reset()} />}
        {poll.error && (
          <p role="alert" className="rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-2.5 text-sm">
            No se pudo leer el correo: {poll.error.message}
          </p>
        )}
        {done && (
          <div role="status" className="flex items-center gap-3 rounded-xl border bg-card px-4 py-2.5 text-sm animate-in fade-in slide-in-from-top-1">
            <ProhibitIcon className="size-[18px] shrink-0 text-muted-foreground" />
            <p className="min-w-0 flex-1 truncate">
              Descartada <span className="font-medium">{done.title}</span>
              <span className="text-muted-foreground"> · {discardReasonLabel(done.reason)}</span>
            </p>
            <Button variant="ghost" size="xs" onClick={undo}>
              Deshacer
            </Button>
            <button type="button" onClick={() => setDone(null)} className="text-muted-foreground hover:text-foreground" aria-label="Cerrar aviso">
              <XIcon className="size-4" />
            </button>
          </div>
        )}
        {actionError && (
          <p role="alert" className="rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-2.5 text-sm">
            No se pudo guardar: {actionError}
          </p>
        )}
      </div>

      {isPending ? (
        <ListSkeleton />
      ) : isError ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : total === 0 ? (
        <section className="rounded-xl border bg-card">
          <EmptyState icon={<EnvelopeSimpleIcon className="size-6" weight="duotone" />} title="Sin alertas pendientes">
            Las ofertas de tus alertas de LinkedIn y otros portales aparecen aquí. Configura IMAP en{' '}
            <InlineCode text=".env" /> o deja correos <InlineCode text=".eml" /> en <InlineCode text="data/inbox/" />.
          </EmptyState>
        </section>
      ) : (
        <div className="space-y-6">
          {passing.length > 0 && (
            <section className="overflow-hidden rounded-xl border bg-card">
              <ul role="listbox" aria-label="Encajan con tus preferencias" className="divide-y">
                {passing.map(renderRow)}
              </ul>
            </section>
          )}
          {failing.length > 0 && (
            <section>
              <h2 className="mb-2 px-1 text-sm font-medium text-muted-foreground">
                No pasan el prefiltro ({failing.length})
              </h2>
              <div className="overflow-hidden rounded-xl border bg-card">
                <ul role="listbox" aria-label="No pasan el prefiltro" className="divide-y">
                  {failing.map(renderRow)}
                </ul>
              </div>
            </section>
          )}
        </div>
      )}

      {current && (
        <DiscardDialog
          open={discarding}
          onOpenChange={setDiscarding}
          jobTitle={`${current.title} · ${current.company}`}
          onConfirm={(choice) => {
            setDiscarding(false)
            discard(current, choice)
          }}
        />
      )}
    </div>
  )
}
