import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { CheckIcon, PencilSimpleIcon, ShieldWarningIcon, WarningIcon, XIcon } from '@phosphor-icons/react'
import type { ReplyInboxItem } from '@/api/client'
import { useAcceptReply, useIgnoreReply, type ReplyDecision } from '@/api/queries'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { STAGE_LABEL } from '@/lib/labels'
import {
  CONFIDENCE_LABEL,
  MILESTONE_EVENTS,
  proposalSentence,
  REPLY_EVENT_LABEL,
  REPLY_EVENTS,
  type ProposalEvent,
} from '@/lib/replies'
import { fromLocalInput, toLocalDateInput, toLocalInput } from '@/lib/time'
import { errorMessage } from '@/lib/errors'
import { cn } from '@/lib/utils'

const CONFIDENCE_TONE = {
  high: 'border-emerald-600/30 text-emerald-700 dark:text-emerald-400',
  medium: 'border-warning-border text-warning-foreground',
  low: 'border-destructive/30 text-destructive',
} as const

/** Lo que propuso el agente, tal cual, como decisión para la API. */
function asIs(item: ReplyInboxItem): ReplyDecision | null {
  const p = item.proposal
  if (!p) return null
  return { job_id: p.job_id, event_type: p.event_type, occurred_at: p.occurred_at, milestone: p.milestone }
}

/**
 * La propuesta del agente para un correo, con Aceptar / Cambiar / Ignorar. Nada se registra hasta
 * que el usuario pulsa uno de ellos (fase 15). Sin propuesta, el usuario puede decidir él.
 */
export function ReplyProposalCard({ item, showJob = false }: { item: ReplyInboxItem; showJob?: boolean }) {
  const { t } = useTranslation('replies', { keyPrefix: 'card' })
  const accept = useAcceptReply()
  const ignore = useIgnoreReply()
  const [editing, setEditing] = useState(false)
  const proposal = item.proposal
  const pending = accept.isPending || ignore.isPending
  const error = accept.error ?? ignore.error
  const job = item.candidates.find((c) => c.job_id === (proposal?.job_id ?? item.job_id))
  const decision = asIs(item)

  if (item.status === 'accepted' || item.status === 'ignored') {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        {item.status === 'accepted' ? <CheckIcon className="size-4 text-primary" /> : <XIcon className="size-4" />}
        {item.status === 'accepted' ? t('accepted') : t('ignored')}
      </p>
    )
  }

  return (
    <div className="space-y-3">
      {proposal ? (
        <div className="space-y-1.5">
          <p className="font-medium text-balance">{proposalSentence(proposal)}.</p>
          <p className="text-sm text-muted-foreground">{proposal.summary}</p>
          <p className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span className={cn('rounded-full border px-2 py-0.5 font-medium', CONFIDENCE_TONE[proposal.confidence])}>
              {CONFIDENCE_LABEL[proposal.confidence]}
            </span>
            {proposal.milestone?.location && <span className="truncate">{proposal.milestone.location}</span>}
            {item.proposed_by && <span>{t('proposedBy', { agent: item.proposed_by })}</span>}
          </p>
          {showJob && job && (
            <p className="text-sm">
              {t('for')}{' '}
              <Link to={`/jobs/${job.job_id}`} className="font-medium underline-offset-4 hover:underline">
                {job.title} · {job.company}
              </Link>{' '}
              <span className="text-muted-foreground">({STAGE_LABEL[job.stage]})</span>
            </p>
          )}
          {proposal.injection_suspected && (
            <p className="flex items-start gap-1.5 text-sm text-destructive">
              <ShieldWarningIcon className="mt-0.5 size-4 shrink-0" weight="fill" />
              {t('injection')}
            </p>
          )}
          {item.valid_now === false && (
            <p className="flex items-start gap-1.5 text-sm text-warning-foreground">
              <WarningIcon className="mt-0.5 size-4 shrink-0" weight="fill" />
              {t('invalidNow')}
            </p>
          )}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">
          {t('unclassified')}
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        {decision && (
          <Button
            type="button"
            size="sm"
            disabled={pending}
            onClick={() => accept.mutate({ replyId: item.reply_id, body: decision })}
            className="active:translate-y-px"
          >
            <CheckIcon weight="bold" />
            {t('accept')}
          </Button>
        )}
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={pending}
          onClick={() => setEditing(true)}
          className="active:translate-y-px"
        >
          <PencilSimpleIcon />
          {decision ? t('change') : t('decide')}
        </Button>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          disabled={pending}
          onClick={() => ignore.mutate(item.reply_id)}
          className="active:translate-y-px"
        >
          <XIcon weight="bold" />
          {t('ignore')}
        </Button>
      </div>
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {t('saveFailed', { error: errorMessage(error) })}
        </p>
      )}
      <ReplyDecisionDialog item={item} open={editing} onOpenChange={setEditing} />
    </div>
  )
}

/** «Cambiar»: el usuario corrige la oferta, el tipo, la fecha del hito o añade una nota. */
export function ReplyDecisionDialog({
  item,
  open,
  onOpenChange,
}: {
  item: ReplyInboxItem
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto">
        {open && <DecisionForm item={item} onDone={() => onOpenChange(false)} />}
      </DialogContent>
    </Dialog>
  )
}

function DecisionForm({ item, onDone }: { item: ReplyInboxItem; onDone: () => void }) {
  const { t } = useTranslation('replies', { keyPrefix: 'decision' })
  const proposal = item.proposal
  const milestone = proposal?.milestone
  const [jobId, setJobId] = useState(proposal?.job_id ?? item.candidates[0]?.job_id ?? 0)
  const [eventType, setEventType] = useState<ProposalEvent>(proposal?.event_type ?? 'reply_received')
  const [allDay, setAllDay] = useState(milestone?.all_day ?? false)
  const [startsAt, setStartsAt] = useState(() =>
    milestone ? (milestone.all_day ? toLocalDateInput(milestone.starts_at) : toLocalInput(milestone.starts_at)) : '',
  )
  const [endsAt, setEndsAt] = useState(() => (milestone?.ends_at ? toLocalInput(milestone.ends_at) : ''))
  const [title, setTitle] = useState(milestone?.title ?? '')
  const [location, setLocation] = useState(milestone?.location ?? '')
  const [note, setNote] = useState('')
  const accept = useAcceptReply()

  const kind = MILESTONE_EVENTS[eventType]
  const starts = kind && startsAt ? fromLocalInput(allDay ? startsAt.slice(0, 10) : startsAt) : null
  const ends = kind === 'interview' && !allDay && endsAt ? fromLocalInput(endsAt) : null
  const invalid =
    !jobId ||
    (kind !== undefined && startsAt !== '' && !starts) ||
    (endsAt !== '' && kind === 'interview' && !allDay && (!ends || (starts !== null && Date.parse(ends) <= Date.parse(starts))))

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (invalid) return
    const body: ReplyDecision = {
      job_id: jobId,
      event_type: eventType,
      occurred_at: proposal?.occurred_at ?? null,
      note: note.trim() || null,
      milestone: starts
        ? {
            starts_at: starts,
            ends_at: ends,
            all_day: allDay,
            title: title.trim() || null,
            location: location.trim() || null,
          }
        : null,
    }
    accept.mutate({ replyId: item.reply_id, body }, { onSuccess: onDone })
  }

  return (
    <form onSubmit={submit} className="grid gap-5">
      <DialogHeader>
        <DialogTitle>{t('title')}</DialogTitle>
        <DialogDescription className="truncate">{item.subject || item.sender}</DialogDescription>
      </DialogHeader>

      {item.candidates.length > 1 && (
        <div className="space-y-2">
          <Label htmlFor="reply-job">{t('job')}</Label>
          <select
            id="reply-job"
            value={jobId}
            onChange={(e) => setJobId(Number(e.target.value))}
            className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
          >
            {item.candidates.map((c) => (
              <option key={c.job_id} value={c.job_id}>
                {c.title} · {c.company}
              </option>
            ))}
          </select>
        </div>
      )}

      <fieldset>
        <legend className="mb-2 text-sm font-medium">{t('what')}</legend>
        <div role="radiogroup" aria-label={t('whatAria')} className="grid gap-1.5 sm:grid-cols-2">
          {REPLY_EVENTS.map((value) => (
            <button
              key={value}
              type="button"
              role="radio"
              aria-checked={eventType === value}
              onClick={() => setEventType(value)}
              className={cn(
                'rounded-md border px-3 py-1.5 text-left text-sm outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50',
                eventType === value ? 'border-primary/40 bg-accent' : 'border-input hover:bg-foreground/[0.03]',
              )}
            >
              {REPLY_EVENT_LABEL[value]}
            </button>
          ))}
        </div>
      </fieldset>

      {kind && (
        <div className="grid gap-3 rounded-lg border border-dashed p-3 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="reply-starts">
              {kind === 'interview' ? t('dateTime') : t('due')}
            </Label>
            <Input
              id="reply-starts"
              type={allDay ? 'date' : 'datetime-local'}
              value={allDay ? startsAt.slice(0, 10) : startsAt}
              onChange={(e) => setStartsAt(e.target.value)}
            />
            <label className="flex items-center gap-2 text-xs text-muted-foreground">
              <input
                type="checkbox"
                checked={allDay}
                onChange={(e) => {
                  setAllDay(e.target.checked)
                  setStartsAt((v) => (e.target.checked ? v.slice(0, 10) : v ? `${v.slice(0, 10)}T09:00` : v))
                }}
              />
              {t('allDay')}
            </label>
          </div>
          {kind === 'interview' && !allDay && (
            <div className="space-y-2">
              <Label htmlFor="reply-ends">{t('end')}</Label>
              <Input id="reply-ends" type="datetime-local" value={endsAt} onChange={(e) => setEndsAt(e.target.value)} />
            </div>
          )}
          <div className="space-y-2">
            <Label htmlFor="reply-title">{t('title2')}</Label>
            <Input id="reply-title" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="reply-location">{t('location')}</Label>
            <Input id="reply-location" value={location} onChange={(e) => setLocation(e.target.value)} maxLength={500} />
          </div>
          <p className="text-xs text-muted-foreground sm:col-span-2">
            {t('madrid')}
          </p>
        </div>
      )}

      {eventType !== 'none' && (
        <div className="space-y-2">
          <Label htmlFor="reply-note">{t('note')}</Label>
          <Textarea
            id="reply-note"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            maxLength={2000}
            rows={2}
            className="resize-y bg-background"
          />
        </div>
      )}

      {accept.error && (
        <p role="alert" className="text-sm text-destructive">
          {errorMessage(accept.error)}
        </p>
      )}

      <DialogFooter>
        <Button type="button" variant="outline" onClick={onDone}>
          {t('cancel')}
        </Button>
        <Button type="submit" disabled={invalid || accept.isPending}>
          {accept.isPending ? t('saving') : eventType === 'none' ? t('archive') : t('register')}
        </Button>
      </DialogFooter>
    </form>
  )
}
