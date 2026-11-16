import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { ApiError, type ApplicationChannel, type BoardCard, type DiscardReason, type EventType, type InterviewType, type Schemas } from '@/api/client'
import { useCheckJobEvent, useCreateMilestone, useJobEvent, type UserEventBody } from '@/api/queries'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { DatePicker, DateTimePicker, DEFAULT_TIME, TimeInput } from '@/components/ui/date-time-picker'
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
import { formatWhen, fromLocalInput, toLocalInput } from '@/lib/time'
import type { MoveOption } from '@/lib/moves'
import { errorMessage } from '@/lib/errors'
import { cn } from '@/lib/utils'
import { BusyLabel } from '@/components/StableLabel'

const MILESTONE_EVENTS: Partial<Record<EventType, 'interview' | 'test'>> = {
  interview_scheduled: 'interview',
  test_assigned: 'test',
}

interface Props {
  card: BoardCard | null
  options: MoveOption[]
  onOpenChange: (open: boolean) => void
  /** Título, si no es mover una tarjeta del tablero. */
  title?: string
}

/** Confirma un movimiento del kanban registrando su evento. Nada cambia de columna sin él. */
export function MoveDialog({ card, options, onOpenChange, title }: Props) {
  return (
    <Dialog open={card !== null} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-xl">
        {card && <MoveForm card={card} options={options} title={title} onDone={() => onOpenChange(false)} />}
      </DialogContent>
    </Dialog>
  )
}

function MoveForm({ card, options, onDone, title }: { card: BoardCard; options: MoveOption[]; onDone: () => void; title?: string }) {
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
  const check = useCheckJobEvent()
  // Lo anotado después que impide registrar el evento con esa fecha, y para qué evento y fecha.
  const [conflict, setConflict] = useState<{ body: UserEventBody; found: Schemas['EventConflicts'] } | null>(null)
  const pending = event.isPending || milestone.isPending || check.isPending
  const error = event.error ?? milestone.error ?? check.error

  const milestoneKind = choice ? MILESTONE_EVENTS[choice.event] : undefined
  const occurred = fromLocalInput(occurredAt)
  // La fecha es opcional: sin ella se registra solo el evento. La hora viene a las 14:00; si se borra, cuenta todo el día.
  const starts = startsDate ? fromLocalInput(startsTime ? `${startsDate}T${startsTime}` : startsDate) : null
  const missing =
    !choice ||
    !occurred ||
    (choice.event === 'discarded' && (!reason || (reason === 'other' && !note.trim()))) ||
    (startsDate !== '' && !starts)

  // Si algo anotado después no encaja con la fecha, se pregunta qué lo impide para proponer cómo arreglarlo.
  const record = (body: UserEventBody) =>
    event.mutate(
      { jobId: card.job_id, body },
      {
        onSuccess: onDone,
        onError: (err) => {
          if (!(err instanceof ApiError) || err.type !== 'later_events' || !body.occurred_at) return
          check.mutate(
            { jobId: card.job_id, body: { type: body.type, occurred_at: body.occurred_at } },
            {
              onSuccess: (found) => {
                if (found.conflicts.length === 0) return
                setConflict({ body, found })
                event.reset() // el panel ya explica el error: no se repite debajo
              },
            },
          )
        },
      },
    )

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (missing || !choice || !occurred) return
    setConflict(null)
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
    record({
      type: choice.event,
      occurred_at: occurred,
      note: trimmed,
      reason: choice.event === 'discarded' ? (reason ?? undefined) : undefined,
      channel: choice.event.startsWith('applied') && channel ? channel : undefined,
    })
  }

  // Al cambiar el evento o la fecha, la propuesta deja de valer.
  const shown = conflict && conflict.body.type === choice?.event && conflict.body.occurred_at === occurred ? conflict : null

  if (shown) {
    return (
      <ConflictPanel
        conflict={shown}
        pending={pending}
        error={event.error}
        onRemove={() =>
          event.mutate(
            { jobId: card.job_id, body: { ...shown.body, remove_event_ids: shown.found.conflicts.map((c) => c.id) } },
            { onSuccess: onDone },
          )
        }
        onLater={(at) => event.mutate({ jobId: card.job_id, body: { ...shown.body, occurred_at: at } }, { onSuccess: onDone })}
        onBack={() => {
          setConflict(null)
          event.reset()
        }}
      />
    )
  }

  return (
    <form onSubmit={submit} className="grid gap-5">
      <DialogHeader>
        <DialogTitle>{title ?? t('title')}</DialogTitle>
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
              <DatePicker
                id="move-starts"
                value={startsDate}
                // Al poner el día, la hora no se queda vacía: si no la sabes, son las 14:00. Si la borras, cuenta todo el día.
                onChange={(day) => {
                  setStartsDate(day)
                  setStartsTime((time) => (day ? time || DEFAULT_TIME : ''))
                }}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="move-starts-time">{t('time')}</Label>
              <TimeInput
                id="move-starts-time"
                disabled={!startsDate}
                value={startsTime}
                onChange={setStartsTime}
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

      <div className="grid gap-3 sm:grid-cols-[16rem_1fr]">
        <div className="space-y-2">
          <Label htmlFor="move-at">{t('when')}</Label>
          <DateTimePicker id="move-at" required value={occurredAt} onChange={setOccurredAt} />
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
          <BusyLabel busy={pending} busyText={t('saving')} text={t('register')} />
        </Button>
      </DialogFooter>
    </form>
  )
}

interface ConflictProps {
  conflict: { body: UserEventBody; found: Schemas['EventConflicts'] }
  pending: boolean
  error: Error | null
  onRemove: () => void
  onLater: (at: string) => void
  onBack: () => void
}

/** Propone cómo anotar un evento con fecha pasada cuando algo anotado después no encaja con él. */
function ConflictPanel({ conflict, pending, error, onRemove, onLater, onBack }: ConflictProps) {
  const { t } = useTranslation('move')
  const { body, found } = conflict
  const when = body.occurred_at ? formatWhen(body.occurred_at) : ''
  const count = found.conflicts.length
  return (
    <div className="grid gap-5">
      <DialogHeader>
        <DialogTitle>{t('conflict.title')}</DialogTitle>
        <DialogDescription>{t('conflict.intro', { event: eventLabel(body.type), when })}</DialogDescription>
      </DialogHeader>

      <ul className="grid gap-1 rounded-md border px-3 py-2 text-sm">
        {found.conflicts.map((c) => (
          <li key={c.id} className="flex items-baseline justify-between gap-3">
            <span className="font-medium">{eventLabel(c.type)}</span>
            <time dateTime={c.occurred_at} className="shrink-0 text-xs text-muted-foreground">
              {formatWhen(c.occurred_at)}
            </time>
          </li>
        ))}
      </ul>

      {found.can_remove ? (
        <div className="grid gap-2">
          <p className="text-sm">{t('conflict.removeHint')}</p>
          <Button type="button" onClick={onRemove} disabled={pending} className="justify-self-start">
            {count === 1 ? t('conflict.remove', { when }) : t('conflict.removeMany', { count, when })}
          </Button>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">{t('conflict.cannotRemove')}</p>
      )}

      {found.suggested_at ? (
        <div className="grid gap-2">
          <p className="text-sm text-muted-foreground">{t('conflict.laterHint')}</p>
          <Button
            type="button"
            variant="outline"
            onClick={() => found.suggested_at && onLater(found.suggested_at)}
            disabled={pending}
            className="justify-self-start"
          >
            {t('conflict.later', { when: formatWhen(found.suggested_at) })}
          </Button>
        </div>
      ) : (
        !found.can_remove && <p className="text-sm text-muted-foreground">{t('conflict.noLater')}</p>
      )}

      {error && (
        <p role="alert" className="text-sm text-destructive">
          {errorMessage(error)}
        </p>
      )}

      <DialogFooter>
        <Button type="button" variant="outline" onClick={onBack} disabled={pending}>
          {t('conflict.back')}
        </Button>
      </DialogFooter>
    </div>
  )
}
