import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import {
  ArrowSquareOutIcon,
  CheckIcon,
  ProhibitIcon,
  SealCheckIcon,
  UserCircleDashedIcon,
  WarningIcon,
  XIcon,
} from '@phosphor-icons/react'
import { Trans, useTranslation } from 'react-i18next'
import type { TriageItem } from '@/api/client'
import { useJobEvent, useTriage } from '@/api/queries'
import { DiscardDialog, type DiscardChoice } from '@/components/DiscardDialog'
import { SignalBadges } from '@/components/JobSignals'
import { KnownBadge, KnownPeople } from '@/components/NetworkPanel'
import { Kbd } from '@/components/Kbd'
import { MatchDetails, ScoreBadge } from '@/components/MatchDetails'
import { EmptyState, ErrorState } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { errorMessage } from '@/lib/errors'
import { discardReasonLabel, formatSalary, REMOTE_LABEL, SENIORITY_LABEL } from '@/lib/labels'
import { isActivatable, isTyping } from '@/lib/keyboard'
import { cn } from '@/lib/utils'

function QueueRow({
  item,
  selected,
  threshold,
  onSelect,
}: {
  item: TriageItem
  selected: boolean
  threshold: number
  onSelect: () => void
}) {
  const { t } = useTranslation('triage')
  const ref = useRef<HTMLLIElement>(null)
  useEffect(() => {
    if (selected) ref.current?.scrollIntoView({ block: 'nearest' })
  }, [selected])
  const low = item.match?.below_threshold ?? false
  const failed = item.match ? !item.match.hard_filters.passed : false
  return (
    <li
      ref={ref}
      role="option"
      aria-selected={selected}
      onClick={onSelect}
      className={cn(
        'relative flex cursor-pointer items-center gap-3 px-4 py-3 transition-colors',
        selected ? 'bg-accent/70' : 'hover:bg-foreground/[0.03]',
      )}
    >
      {selected && <span aria-hidden className="absolute inset-y-2 left-0 w-0.5 rounded-full bg-primary" />}
      <div className={cn('min-w-0 flex-1', low && !selected && 'opacity-60')}>
        <p className="flex items-center gap-1.5 text-sm font-medium">
          <span className="truncate">{item.job.title}</span>
          {item.job.risk_flags.length > 0 && (
            <WarningIcon className="size-3.5 shrink-0 text-warning-foreground" weight="fill" aria-label={t('risk')} />
          )}
          {failed && <ProhibitIcon className="size-3.5 shrink-0 text-muted-foreground" aria-label={t('failsFilters')} />}
          <SignalBadges signals={item.job.signals} />
          <KnownBadge count={item.job.known_contacts} />
        </p>
        <p className="truncate text-xs text-muted-foreground">{item.job.company}</p>
      </div>
      <ScoreBadge score={item.match?.score} threshold={threshold} />
    </li>
  )
}

function Facts({ item }: { item: TriageItem }) {
  const { t } = useTranslation('triage')
  const ext = item.extraction
  if (!ext) return null
  const salary = formatSalary(ext.salary)
  const facts = [
    REMOTE_LABEL[ext.remote_mode],
    ext.seniority !== 'unknown' ? SENIORITY_LABEL[ext.seniority] : null,
    ext.years_experience_min != null ? t('yearsPlus', { count: ext.years_experience_min }) : null,
    ext.locations.join(', ') || null,
    salary,
  ].filter(Boolean)
  return (
    <p className="mt-3 flex flex-wrap gap-x-3 gap-y-1 text-sm text-muted-foreground">
      {facts.map((fact, i) => (
        <span key={i} className="flex items-center gap-3">
          {i > 0 && <span aria-hidden className="size-1 rounded-full bg-muted-foreground/40" />}
          {fact}
        </span>
      ))}
    </p>
  )
}

function Detail({
  item,
  threshold,
  assessMinScore,
  onApprove,
  onDiscard,
}: {
  item: TriageItem
  threshold: number
  assessMinScore: number
  onApprove: () => void
  onDiscard: () => void
}) {
  const { t } = useTranslation('triage')
  return (
    <article aria-label={t('selected')} className="rounded-xl border bg-card p-5 sm:p-6 animate-in fade-in duration-200" key={item.job.id}>
      <header className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h2 className="text-xl leading-tight font-semibold tracking-tight text-balance">
            <Link to={`/jobs/${item.job.id}`} className="underline-offset-4 hover:underline">
              {item.job.title}
            </Link>
          </h2>
          <p className="mt-1 text-muted-foreground">
            <span className="text-foreground/90">{item.job.company}</span>
            {item.job.location && <>, {item.job.location}</>}
          </p>
          <Facts item={item} />
          <KnownPeople jobId={item.job.id} count={item.job.known_contacts} />
        </div>
        <ScoreBadge score={item.match?.score} threshold={threshold} size="lg" className="shrink-0" />
      </header>

      <div className="mt-5 flex flex-wrap items-center gap-2 border-y py-4">
        <Button onClick={onApprove} className="active:translate-y-px">
          <CheckIcon weight="bold" />
          {t('approve')}
          <Kbd>A</Kbd>
        </Button>
        <Button variant="outline" onClick={onDiscard} className="active:translate-y-px">
          <XIcon weight="bold" />
          {t('discard')}
          <Kbd>D</Kbd>
        </Button>
        <Button asChild variant="ghost" size="sm" className="ml-auto text-muted-foreground">
          <Link to={`/jobs/${item.job.id}`}>
            {t('detail')}
            <ArrowSquareOutIcon />
          </Link>
        </Button>
      </div>

      <div className="mt-6">
        {item.match ? (
          <MatchDetails match={item.match} assessMinScore={assessMinScore} />
        ) : (
          <p className="text-sm text-muted-foreground">
            <Trans
              t={t}
              i18nKey="noScore"
              components={{ code: <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em] text-foreground" /> }}
            />
          </p>
        )}
      </div>
    </article>
  )
}

interface Done {
  jobId: number
  title: string
  action: 'approved' | 'discarded'
  reason?: string
}

function DoneNotice({ done, onUndo, onClose }: { done: Done; onUndo: () => void; onClose: () => void }) {
  const { t } = useTranslation('triage')
  return (
    <div role="status" className="flex items-center gap-3 rounded-xl border bg-card px-4 py-2.5 text-sm animate-in fade-in slide-in-from-top-1">
      {done.action === 'approved' ? (
        <SealCheckIcon className="size-[18px] shrink-0 text-primary" weight="duotone" />
      ) : (
        <ProhibitIcon className="size-[18px] shrink-0 text-muted-foreground" />
      )}
      <p className="min-w-0 flex-1 truncate">
        {t(`done.${done.action}`)}{' '}
        <Link to={`/jobs/${done.jobId}`} className="font-medium underline-offset-4 hover:underline">
          {done.title}
        </Link>
        {done.reason && <span className="text-muted-foreground"> · {discardReasonLabel(done.reason)}</span>}
      </p>
      {done.action === 'discarded' && (
        <Button variant="ghost" size="xs" onClick={onUndo}>
          {t('done.undo')}
        </Button>
      )}
      <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground" aria-label={t('done.close')}>
        <XIcon className="size-4" />
      </button>
    </div>
  )
}

function QueueSkeleton() {
  const { t } = useTranslation('triage')
  return (
    <div aria-busy="true" aria-label={t('loadingQueue')} className="grid gap-6 lg:grid-cols-[20rem_minmax(0,1fr)]">
      <div className="space-y-2 rounded-xl border bg-card p-3">
        {Array.from({ length: 5 }, (_, i) => (
          <Skeleton key={i} className="h-11" />
        ))}
      </div>
      <Skeleton className="h-96 rounded-xl" />
    </div>
  )
}

export function TriagePage() {
  const { t } = useTranslation('triage')
  const navigate = useNavigate()
  const { data, isPending, isError, error, refetch } = useTriage()
  const event = useJobEvent()
  const [hidden, setHidden] = useState<Set<number>>(new Set())
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [discarding, setDiscarding] = useState(false)
  const [done, setDone] = useState<Done | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const items = useMemo(() => (data?.items ?? []).filter((i) => !hidden.has(i.job.id)), [data, hidden])
  const index = Math.max(0, items.findIndex((i) => i.job.id === selectedId))
  const current = items[index] as TriageItem | undefined
  const threshold = data?.triage_threshold ?? 0

  const select = useCallback(
    (i: number) => {
      const next = items[Math.min(Math.max(i, 0), items.length - 1)]
      if (next) setSelectedId(next.job.id)
    },
    [items],
  )

  /** Oculta la oferta ya y selecciona la siguiente; si la API falla, vuelve a aparecer. */
  const act = useCallback(
    (item: TriageItem, choice?: DiscardChoice) => {
      const position = items.indexOf(item)
      const after = items[position + 1] ?? items[position - 1]
      setHidden((prev) => new Set(prev).add(item.job.id))
      setSelectedId(after ? after.job.id : null)
      setActionError(null)
      const body = choice ? { type: 'discarded' as const, reason: choice.reason, note: choice.note } : { type: 'approved' as const }
      event.mutate(
        { jobId: item.job.id, body },
        {
          onSuccess: () =>
            setDone({ jobId: item.job.id, title: item.job.title, action: body.type, reason: choice?.reason }),
          onError: (err) => {
            setHidden((prev) => {
              const next = new Set(prev)
              next.delete(item.job.id)
              return next
            })
            setSelectedId(item.job.id)
            setActionError(errorMessage(err))
          },
        },
      )
    },
    [event, items],
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
      if (discarding || e.metaKey || e.ctrlKey || e.altKey || isTyping(e.target)) return
      if (!current) return
      const key = e.key.toLowerCase()
      if (key === 'j' || e.key === 'ArrowDown') select(index + 1)
      else if (key === 'k' || e.key === 'ArrowUp') select(index - 1)
      else if (key === 'a') act(current)
      else if (key === 'd') setDiscarding(true)
      else if (key === 'o' || (e.key === 'Enter' && !isActivatable(e.target)))
        navigate(`/jobs/${current.job.id}`)
      else return
      e.preventDefault()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [act, current, discarding, index, navigate, select])

  const remaining = items.length
  return (
    <div className="animate-in fade-in duration-300">
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{t('title')}</h1>
          <p className="text-sm text-muted-foreground">
            {isPending ? t('loading', { ns: 'common' }) : t('count', { count: remaining })}
            {remaining > 0 && t('byFit')}
          </p>
        </div>
        {remaining > 0 && (
          <p className="hidden items-center gap-3 text-xs text-muted-foreground md:flex" aria-label={t('shortcuts.label')}>
            <span className="flex items-center gap-1"><Kbd>J</Kbd><Kbd>K</Kbd> {t('shortcuts.move')}</span>
            <span className="flex items-center gap-1"><Kbd>A</Kbd> {t('shortcuts.approve')}</span>
            <span className="flex items-center gap-1"><Kbd>D</Kbd> {t('shortcuts.discard')}</span>
            <span className="flex items-center gap-1"><Kbd>O</Kbd> {t('shortcuts.detail')}</span>
          </p>
        )}
      </div>

      <div className="mb-4 space-y-3 empty:hidden">
        {data?.profile_missing && (
          <div role="status" className="flex items-start gap-3 rounded-xl border border-primary/20 bg-accent/60 px-4 py-3 text-sm text-accent-foreground">
            <UserCircleDashedIcon className="mt-0.5 size-[18px] shrink-0" weight="duotone" />
            <p>
              <Trans
                t={t}
                i18nKey="profileMissing"
                components={{
                  strong: <span className="font-medium" />,
                  code: <code className="rounded bg-background/70 px-1.5 py-0.5 font-mono text-[0.85em]" />,
                }}
              />
            </p>
          </div>
        )}
        {done && <DoneNotice done={done} onUndo={undo} onClose={() => setDone(null)} />}
        {actionError && (
          <p role="alert" className="rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-2.5 text-sm">
            {t('saveFailed', { error: actionError })}
          </p>
        )}
      </div>

      {isPending ? (
        <QueueSkeleton />
      ) : isError ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : !current ? (
        <section className="rounded-xl border bg-card">
          <EmptyState icon={<SealCheckIcon className="size-6" weight="duotone" />} title={t('empty.title')}>
            <Trans t={t} i18nKey="empty.body" components={{ code: <code className="font-mono text-foreground" /> }} />
          </EmptyState>
        </section>
      ) : (
        <div className="grid items-start gap-6 lg:grid-cols-[20rem_minmax(0,1fr)]">
          <section className="order-2 overflow-hidden rounded-xl border bg-card lg:order-1 lg:sticky lg:top-32">
            <ul role="listbox" aria-label={t('queue')} className="max-h-[calc(100dvh-12rem)] divide-y overflow-y-auto">
              {items.map((item, i) => (
                <QueueRow
                  key={item.job.id}
                  item={item}
                  selected={i === index}
                  threshold={threshold}
                  onSelect={() => setSelectedId(item.job.id)}
                />
              ))}
            </ul>
          </section>
          <div className="order-1 lg:order-2">
            <Detail
              item={current}
              threshold={threshold}
              assessMinScore={data?.assess_min_score ?? 0}
              onApprove={() => act(current)}
              onDiscard={() => setDiscarding(true)}
            />
          </div>
        </div>
      )}

      {current && (
        <DiscardDialog
          open={discarding}
          onOpenChange={setDiscarding}
          jobTitle={`${current.job.title} · ${current.job.company}`}
          onConfirm={(choice) => {
            setDiscarding(false)
            act(current, choice)
          }}
        />
      )}
    </div>
  )
}
