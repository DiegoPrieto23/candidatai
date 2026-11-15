import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import type { InterviewType, MilestoneKind, MilestoneOut, Stage } from '@/api/client'
import type { MilestoneDraft } from '@/lib/milestoneDraft'
import { BusyLabel } from '@/components/StableLabel'
import { Button } from '@/components/ui/button'
import { DatePicker, DateTimePicker } from '@/components/ui/date-time-picker'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { errorMessage } from '@/lib/errors'
import { INTERVIEW_TYPE_LABEL, MILESTONE_KIND_LABEL } from '@/lib/labels'
import { fromLocalInput, toLocalDateInput, toLocalInput } from '@/lib/time'

/** Entrevistas y pruebas registran su evento: solo tras enviar la candidatura. */
const AFTER_APPLIED = new Set<Stage>(['applied', 'in_process'])


/** El borrador de un hito: el que se edita o uno nuevo, con la fecha puesta si se sabe. */
function draftFrom(m?: MilestoneOut, date = ''): MilestoneDraft {
  if (!m) return { kind: 'interview', title: '', date, allDay: false, location: '', notes: '', interviewType: '' }
  return {
    kind: m.kind,
    title: m.title,
    date: m.all_day ? toLocalDateInput(m.starts_at) : toLocalInput(m.starts_at),
    allDay: m.all_day,
    location: m.location ?? '',
    notes: m.notes ?? '',
    interviewType: m.interview_type ?? '',
  }
}

export function MilestoneForm({
  stage,
  initial,
  initialDate,
  pending,
  error,
  onSubmit,
  onCancel,
}: {
  stage: Stage | null
  initial?: MilestoneOut
  /** En un hito nuevo, la fecha de partida (`AAAA-MM-DDTHH:MM`). */
  initialDate?: string
  pending: boolean
  error: Error | null
  onSubmit: (draft: MilestoneDraft, startsAt: string) => void
  onCancel: () => void
}) {
  const { t } = useTranslation('process', { keyPrefix: 'milestoneForm' })
  const [draft, setDraft] = useState<MilestoneDraft>(() => draftFrom(initial, initialDate))
  const set = (changes: Partial<MilestoneDraft>) => setDraft((d) => ({ ...d, ...changes }))
  const startsAt = draft.date ? fromLocalInput(draft.date) : null
  const eventKind = draft.kind === 'interview' || draft.kind === 'test'
  const blocked = !initial && eventKind && (!stage || !AFTER_APPLIED.has(stage))

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (startsAt && !blocked) onSubmit(draft, startsAt)
  }

  return (
    <form onSubmit={submit} className="grid gap-3 rounded-lg border bg-background p-3">
      <div className="grid gap-3 sm:grid-cols-2">
        {!initial && (
          <div className="space-y-1.5">
            <Label htmlFor="ms-kind">{t('kind')}</Label>
            <select
              id="ms-kind"
              value={draft.kind}
              onChange={(e) => set({ kind: e.target.value as MilestoneKind })}
              className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
            >
              {Object.entries(MILESTONE_KIND_LABEL).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
        )}
        {draft.kind === 'interview' && (
          <div className="space-y-1.5">
            <Label htmlFor="ms-interview-type">{t('interviewType')}</Label>
            <select
              id="ms-interview-type"
              value={draft.interviewType}
              onChange={(e) => set({ interviewType: e.target.value as InterviewType | '' })}
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
        <div className="space-y-1.5">
          <Label htmlFor="ms-title">{t('title')}</Label>
          <Input
            id="ms-title"
            value={draft.title}
            maxLength={200}
            placeholder={MILESTONE_KIND_LABEL[draft.kind]}
            onChange={(e) => set({ title: e.target.value })}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="ms-date">{draft.allDay ? t('day') : t('dateTime')}</Label>
          {draft.allDay ? (
            <DatePicker id="ms-date" required value={draft.date} onChange={(date) => set({ date })} />
          ) : (
            <DateTimePicker id="ms-date" required value={draft.date} onChange={(date) => set({ date })} />
          )}
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            <input
              type="checkbox"
              checked={draft.allDay}
              onChange={(e) =>
                set({ allDay: e.target.checked, date: e.target.checked ? draft.date.slice(0, 10) : '' })
              }
            />
            {t('allDay')}
          </label>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="ms-location">{t('location')}</Label>
          <Input
            id="ms-location"
            value={draft.location}
            maxLength={500}
            onChange={(e) => set({ location: e.target.value })}
          />
        </div>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="ms-notes">{t('notes')}</Label>
        <Textarea
          id="ms-notes"
          rows={2}
          maxLength={4000}
          value={draft.notes}
          onChange={(e) => set({ notes: e.target.value })}
          className="resize-y"
        />
      </div>
      {blocked && (
        <p className="text-xs text-muted-foreground">
          {t('blocked')}
        </p>
      )}
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {errorMessage(error)}
        </p>
      )}
      <div className="flex justify-end gap-2">
        <Button type="button" variant="outline" size="sm" onClick={onCancel}>
          {t('cancel')}
        </Button>
        <Button type="submit" size="sm" disabled={!startsAt || blocked || pending}>
          <BusyLabel busy={pending} busyText={t('saving')} text={t('save')} />
        </Button>
      </div>
    </form>
  )
}
