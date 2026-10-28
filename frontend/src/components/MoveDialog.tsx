import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import type { ApplicationChannel, BoardCard, DiscardReason, EventType, InterviewType } from '@/api/client'
import { useCreateMilestone, useJobEvent } from '@/api/queries'
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
import {
  CHANNEL_LABEL,
  DISCARD_REASONS,
  eventLabel,
  INTERVIEW_TYPE_LABEL,
  MOVE_HINT,
  STAGE_LABEL,
} from '@/lib/labels'
import { fromLocalInput, toLocalInput } from '@/lib/time'
import type { MoveOption } from '@/lib/moves'
import { errorMessage } from '@/lib/errors'
import { cn } from '@/lib/utils'

const MILESTONE_EVENTS: Partial<Record<EventType, 'interview' | 'test'>> = {
  interview_scheduled: 'interview',
  test_assigned: 'test',
}

interface Props {
  card: BoardCard | null
  options: MoveOption[]
  onOpenChange: (open: boolean) => void
}

/** Confirma un movimiento del kanban registrando su evento. Nada cambia de columna sin él. */
export function MoveDialog({ card, options, onOpenChange }: Props) {
  return (
    <Dialog open={card !== null} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-xl">
        {card && <MoveForm card={card} options={options} onDone={() => onOpenChange(false)} />}
      </DialogContent>
    </Dialog>
  )
}

function MoveForm({ card, options, onDone }: { card: BoardCard; options: MoveOption[]; onDone: () => void }) {
  const { t } = useTranslation('move')
  const [choice, setChoice] = useState<MoveOption | null>(options.length === 1 ? options[0] : null)
  const [occurredAt, setOccurredAt] = useState(() => toLocalInput(new Date()))
  const [note, setNote] = useState('')
  const [reason, setReason] = useState<DiscardReason | null>(null)
  const [channel, setChannel] = useState<ApplicationChannel | ''>('')
  const [startsDate, setStartsDate] = useState('')
  const [startsTime, setStartsTime] = useState('')
  const [location, setLocation] = useState('')
  const [interviewType, setInterviewType] = useState<InterviewType | ''>('')
  const event = useJobEvent()
  const milestone = useCreateMilestone()
  const pending = event.isPending || milestone.isPending
  const error = event.error ?? milestone.error

  const milestoneKind = choice ? MILESTONE_EVENTS[choice.event] : undefined
  const occurred = fromLocalInput(occurredAt)
  // La fecha es opcional: sin ella se registra solo el evento; sin hora, cuenta todo el día.
  const starts = startsDate ? fromLocalInput(startsTime ? `${startsDate}T${startsTime}` : startsDate) : null
  const missing =
    !choice ||
    !occurred ||
    (choice.event === 'discarded' && (!reason || (reason === 'other' && !note.trim()))) ||
    (startsDate !== '' && !starts)

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (missing || !choice || !occurred) return
    const trimmed = note.trim() || undefined
    if (milestoneKind && starts) {
      milestone.mutate(
        {
          jobId: card.job_id,
          body: {
            kind: milestoneKind,
            starts_at: starts,
            all_day: !startsTime,
            occurred_at: occurred,
            location: location.trim() || undefined,
            notes: trimmed,
            interview_type: (milestoneKind === 'interview' && interviewType) || undefined,
          },
        },
        { onSuccess: onDone },
      )
      return
    }
    event.mutate(
      {
        jobId: card.job_id,
        body: {
          type: choice.event,
          occurred_at: occurred,
          note: trimmed,
          reason: choice.event === 'discarded' ? (reason ?? undefined) : undefined,
          channel: choice.event.startsWith('applied') && channel ? channel : undefined,
        },
      },
      { onSuccess: onDone },
    )
  }

  return (
    <form onSubmit={submit} className="grid gap-5">
      <DialogHeader>
        <DialogTitle>{t('title')}</DialogTitle>
        <DialogDescription className="truncate">
          {card.title} · {card.company}
        </DialogDescription>
      </DialogHeader>

      <fieldset>
        <legend className="mb-2 text-sm font-medium">{t('what')}</legend>
        <div role="radiogroup" aria-label={t('event')} className="grid gap-1.5">
          {options.map((option) => {
            const selected = choice?.event === option.event
            return (
              <button
                key={option.event}
                type="button"
                role="radio"
                aria-checked={selected}
                onClick={() => setChoice(option)}
                className={cn(
                  'rounded-md border px-3 py-2 text-left text-sm transition-colors outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50',
                  selected ? 'border-primary/40 bg-accent text-accent-foreground' : 'border-input hover:bg-foreground/[0.03]',
                )}
              >
                <span className="flex items-baseline justify-between gap-3">
                  <span className="font-medium">{eventLabel(option.event)}</span>
                  <span className="shrink-0 text-xs text-muted-foreground">→ {STAGE_LABEL[option.to]}</span>
                </span>
                {MOVE_HINT[option.event] && (
                  <span className="mt-0.5 block text-xs text-muted-foreground">{MOVE_HINT[option.event]}</span>
                )}
              </button>
            )
          })}
        </div>
      </fieldset>

      {choice?.event === 'discarded' && (
        <fieldset>
          <legend className="mb-2 text-sm font-medium">{t('reason')}</legend>
          <div role="radiogroup" aria-label={t('reason')} className="grid gap-1.5 sm:grid-cols-2">
            {DISCARD_REASONS.map((option) => (
              <button
                key={option.value}
                type="button"
                role="radio"
                aria-checked={reason === option.value}
                onClick={() => setReason(option.value)}
                className={cn(
                  'rounded-md border px-3 py-1.5 text-left text-sm outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50',
                  reason === option.value ? 'border-primary/40 bg-accent' : 'border-input hover:bg-foreground/[0.03]',
                )}
              >
                {option.label}
              </button>
            ))}
          </div>
        </fieldset>
      )}

      {choice?.event.startsWith('applied') && (
        <div className="space-y-2">
          <Label htmlFor="move-channel">{t('channel')}</Label>
          <select
            id="move-channel"
            value={channel}
            onChange={(e) => setChannel(e.target.value as ApplicationChannel | '')}
            className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
          >
            <option value="">{t('noChannel')}</option>
            {Object.entries(CHANNEL_LABEL).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
      )}

      {milestoneKind && (
        <div className="grid gap-3 rounded-lg border border-dashed p-3">
          <div className="grid gap-3 sm:grid-cols-[1fr_8rem]">
            <div className="space-y-2">
              <Label htmlFor="move-starts">
                {milestoneKind === 'interview' ? t('interviewDate') : t('dueDate')}
              </Label>
              <Input id="move-starts" type="date" value={startsDate} onChange={(e) => setStartsDate(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="move-starts-time">{t('time')}</Label>
              <Input
                id="move-starts-time"
                type="time"
                step={300}
                disabled={!startsDate}
                value={startsTime}
                onChange={(e) => setStartsTime(e.target.value)}
              />
            </div>
          </div>
          <p className="-mt-1 text-xs text-muted-foreground">
            {milestoneKind === 'interview' ? t('dateHintInterview') : t('dateHintTest')}
          </p>
          {startsDate && milestoneKind === 'interview' && (
            <div className="space-y-2">
              <Label htmlFor="move-interview-type">{t('interviewType')}</Label>
              <select
                id="move-interview-type"
                value={interviewType}
                onChange={(e) => setInterviewType(e.target.value as InterviewType | '')}
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
              >
                <option value="">{t('noInterviewType')}</option>
                {Object.entries(INTERVIEW_TYPE_LABEL).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
          )}
          {startsDate && (
            <div className="space-y-2">
              <Label htmlFor="move-location">{t('location')}</Label>
              <Input id="move-location" value={location} onChange={(e) => setLocation(e.target.value)} maxLength={500} />
            </div>
          )}
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-[12rem_1fr]">
        <div className="space-y-2">
          <Label htmlFor="move-at">{t('when')}</Label>
          <Input
            id="move-at"
            type="datetime-local"
            required
            value={occurredAt}
            onChange={(e) => setOccurredAt(e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="move-note">
            {t('note')} {choice?.event === 'discarded' && reason === 'other' ? t('noteRequired') : t('noteOptional')}
          </Label>
          <Textarea
            id="move-note"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            maxLength={2000}
            rows={2}
            className="resize-y bg-background"
          />
        </div>
      </div>
      <p className="-mt-3 text-xs text-muted-foreground">{t('madrid')}</p>

      {error && (
        <p role="alert" className="text-sm text-destructive">
          {errorMessage(error)}
        </p>
      )}

      <DialogFooter>
        <Button type="button" variant="outline" onClick={onDone}>
          {t('cancel')}
        </Button>
        <Button type="submit" disabled={missing || pending}>
          {pending ? t('saving') : t('register')}
        </Button>
      </DialogFooter>
    </form>
  )
}
