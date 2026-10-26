import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import {
  ArrowSquareOutIcon,
  ArrowsClockwiseIcon,
  CaretDownIcon,
  PlusIcon,
  EnvelopeSimpleIcon,
  FunnelSimpleXIcon,
  ProhibitIcon,
  WarningIcon,
  XIcon,
} from '@phosphor-icons/react'
import type { AlertJob, EmailPollResult } from '@/api/client'
import { useAlerts, useJobEvent, usePollAlerts } from '@/api/queries'
import { DiscardDialog, type DiscardChoice } from '@/components/DiscardDialog'
import { MailboxDialog, MailboxesPanel, type MailboxDialogState } from '@/components/Mailboxes'
import { Kbd } from '@/components/Kbd'
import { Pager } from '@/components/Pager'
import { EmptyState, ErrorState, InlineCode } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { isActivatable, isTyping } from '@/lib/keyboard'
import { discardReasonLabel, formatRelative } from '@/lib/labels'
import { LIST_PAGE_SIZE, pageOf } from '@/lib/paging'
import { errorMessage } from '@/lib/errors'
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
  const { t } = useTranslation('alerts')
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
              aria-label={t('risk')}
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
        <span className="tabular hidden w-24 text-right md:inline" title={t('expires', { when: formatRelative(job.expires_at) })}>
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
            {t('open')}
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
          {t('discard')}
        </Button>
      </div>
    </li>
  )
}

function PollResult({ result, onClose }: { result: EmailPollResult; onClose: () => void }) {
  const { t } = useTranslation('alerts')
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
      <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground" aria-label={t('closeNotice')}>
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
  const { t } = useTranslation('alerts')
  return (
    <div aria-busy="true" aria-label={t('loading')} className="space-y-2 rounded-xl border bg-card p-3">
      {Array.from({ length: 6 }, (_, i) => (
        <Skeleton key={i} className="h-12" />
      ))}
    </div>
  )
}

export function AlertsPage() {
  const { t } = useTranslation('alerts')
  const { data, isPending, isError, error, refetch } = useAlerts()
  const event = useJobEvent()
  const poll = usePollAlerts()
  const [hidden, setHidden] = useState<Set<number>>(new Set())
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [discarding, setDiscarding] = useState(false)
  const [done, setDone] = useState<Done | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [mailDialog, setMailDialog] = useState<MailboxDialogState>(null)

  // Las que no pasan tus filtros van plegadas: las teclas solo recorren lo que se ve.
  const [showFailing, setShowFailing] = useState(false)
  const all = useMemo(() => (data?.jobs ?? []).filter((j) => !hidden.has(j.job_id)), [data, hidden])
  const passing = useMemo(() => all.filter((j) => j.prefilter_passed), [all])
  const failing = useMemo(() => all.filter((j) => !j.prefilter_passed), [all])
  // De 25 en 25. Al descartar la última de una página, se queda en la anterior.
  const [passingPage, setPassingPage] = useState(1)
  const [failingPage, setFailingPage] = useState(1)
  const passingAt = Math.min(passingPage, Math.max(1, Math.ceil(passing.length / LIST_PAGE_SIZE)))
  const failingAt = Math.min(failingPage, Math.max(1, Math.ceil(failing.length / LIST_PAGE_SIZE)))
  const passingShown = useMemo(() => pageOf(passing, passingAt), [passing, passingAt])
  const failingShown = useMemo(() => pageOf(failing, failingAt), [failing, failingAt])
  const jobs = useMemo(
    () => (showFailing ? [...passingShown, ...failingShown] : passingShown),
    [showFailing, passingShown, failingShown],
  )
  const index = Math.max(0, jobs.findIndex((j) => j.job_id === selectedId))
  const current = jobs[index] as AlertJob | undefined

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
            setActionError(errorMessage(err))
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
        onError: (err) => setActionError(errorMessage(err)),
      },
    )
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // Con el diálogo de buzones abierto, las teclas son suyas.
      if (discarding || mailDialog || e.metaKey || e.ctrlKey || e.altKey || isTyping(e.target)) return
      // Ni con el foco en el panel de buzones: «Quitar» y sus botones no son de la lista.
      if (e.target instanceof Element && e.target.closest('[data-mailboxes]')) return
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
  }, [current, discarding, mailDialog, index, select])

  const total = all.length
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
          <h1 className="text-2xl font-semibold tracking-tight">{t('title')}</h1>
          <p className="max-w-prose text-sm text-muted-foreground">
            {isPending ? t('loading', { ns: 'common' }) : t('summary', { count: total })}
          </p>
        </div>
        <div className="flex shrink-0 flex-col items-start gap-2 sm:items-end">
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" onClick={() => setMailDialog({ mode: 'add' })} className="active:translate-y-px">
              <PlusIcon />
              {t('addMailbox')}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => poll.mutate()}
              disabled={poll.isPending}
              className="active:translate-y-px"
            >
              <ArrowsClockwiseIcon className={cn(poll.isPending && 'animate-spin')} />
              {poll.isPending ? t('reading') : t('poll')}
            </Button>
          </div>
          {total > 0 && (
            <p className="hidden items-center gap-3 text-xs text-muted-foreground md:flex" aria-label={t('shortcuts.label')}>
              <span className="flex items-center gap-1"><Kbd>J</Kbd><Kbd>K</Kbd> {t('shortcuts.move')}</span>
              <span className="flex items-center gap-1"><Kbd>O</Kbd> {t('shortcuts.open')}</span>
              <span className="flex items-center gap-1"><Kbd>D</Kbd> {t('shortcuts.discard')}</span>
            </p>
          )}
        </div>
      </div>

      <div className="mb-4 space-y-3 empty:hidden">
        <MailboxesPanel onEdit={(source) => setMailDialog({ mode: 'edit', source })} />
        {poll.data && <PollResult result={poll.data} onClose={() => poll.reset()} />}
        {poll.error && (
          <p role="alert" className="rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-2.5 text-sm">
            {t('pollFailed', { error: errorMessage(poll.error) })}
          </p>
        )}
        {done && (
          <div role="status" className="flex items-center gap-3 rounded-xl border bg-card px-4 py-2.5 text-sm animate-in fade-in slide-in-from-top-1">
            <ProhibitIcon className="size-[18px] shrink-0 text-muted-foreground" />
            <p className="min-w-0 flex-1 truncate">
              {t('discarded')} <span className="font-medium">{done.title}</span>
              <span className="text-muted-foreground"> · {discardReasonLabel(done.reason)}</span>
            </p>
            <Button variant="ghost" size="xs" onClick={undo}>
              {t('undo')}
            </Button>
            <button type="button" onClick={() => setDone(null)} className="text-muted-foreground hover:text-foreground" aria-label={t('closeNotice')}>
              <XIcon className="size-4" />
            </button>
          </div>
        )}
        {actionError && (
          <p role="alert" className="rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-2.5 text-sm">
            {t('saveFailed', { error: actionError })}
          </p>
        )}
      </div>

      {isPending ? (
        <ListSkeleton />
      ) : isError ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : total === 0 ? (
        <section className="rounded-xl border bg-card">
          <EmptyState icon={<EnvelopeSimpleIcon className="size-6" weight="duotone" />} title={t('empty.title')}>
            <InlineCode text={t('empty.body')} />
            <Button size="sm" className="mt-3" onClick={() => setMailDialog({ mode: 'add' })}>
              <PlusIcon />
              {t('addMailbox')}
            </Button>
          </EmptyState>
        </section>
      ) : (
        <div className="space-y-6">
          {passing.length > 0 && (
            <section className="overflow-hidden rounded-xl border bg-card">
              <ul role="listbox" aria-label={t('passing')} className="divide-y">
                {passingShown.map(renderRow)}
              </ul>
              <Pager page={passingAt} total={passing.length} onPage={setPassingPage} className="border-t px-4 py-2.5" />
            </section>
          )}
          {failing.length > 0 && (
            <section>
              <h2 className="mb-2 px-1">
                <button
                  type="button"
                  aria-expanded={showFailing}
                  onClick={() => setShowFailing(!showFailing)}
                  className="inline-flex items-center gap-1.5 rounded-sm text-sm font-medium text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
                >
                  {t('failingCount', { count: failing.length })}
                  <CaretDownIcon className={cn('size-3.5 transition-transform', showFailing && 'rotate-180')} />
                </button>
              </h2>
              {showFailing && (
                <div className="overflow-hidden rounded-xl border bg-card">
                  <ul role="listbox" aria-label={t('failing')} className="divide-y">
                    {failingShown.map(renderRow)}
                  </ul>
                  <Pager page={failingAt} total={failing.length} onPage={setFailingPage} className="border-t px-4 py-2.5" />
                </div>
              )}
            </section>
          )}
        </div>
      )}

      <MailboxDialog state={mailDialog} onClose={() => setMailDialog(null)} />
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
