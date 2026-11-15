import type { InterviewType, MilestoneKind } from '@/api/client'
import type { MilestoneCreate } from '@/api/queries'

/** Lo que se rellena en el formulario de un hito (ficha y calendario). */
export interface MilestoneDraft {
  kind: MilestoneKind
  title: string
  date: string // datetime-local o date
  allDay: boolean
  location: string
  notes: string
  interviewType: InterviewType | ''
}

/** Lo que se envía al crear un hito desde el borrador del formulario. */
export function milestoneBody(draft: MilestoneDraft, startsAt: string): MilestoneCreate {
  return {
    kind: draft.kind,
    title: draft.title.trim() || undefined,
    starts_at: startsAt,
    all_day: draft.allDay,
    location: draft.location.trim() || undefined,
    notes: draft.notes.trim() || undefined,
    interview_type: (draft.kind === 'interview' && draft.interviewType) || undefined,
  }
}
