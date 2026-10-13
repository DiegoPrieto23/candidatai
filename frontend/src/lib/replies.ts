import type { ReplyProposal, Schemas } from '@/api/client'
import { i18n } from '@/lib/i18n'
import { dateFormatter, translatedMap } from '@/lib/labels'
import { APP_TIME_ZONE } from '@/lib/time'

/** Respuestas de las empresas (fase 15): textos de las propuestas del agente. */

export type ProposalEvent = ReplyProposal['event_type']
export type Confidence = ReplyProposal['confidence']
export type ReplyMilestone = Schemas['ReplyMilestone']

/** En el orden del selector de «Cambiar». */
export const REPLY_EVENTS: readonly ProposalEvent[] = [
  'interview_scheduled',
  'test_assigned',
  'offer_received',
  'rejected',
  'reply_received',
  'none',
]

export const REPLY_EVENT_LABEL = translatedMap<ProposalEvent>('replies:event', REPLY_EVENTS)

export const MILESTONE_EVENTS: Partial<Record<ProposalEvent, 'interview' | 'test'>> = {
  interview_scheduled: 'interview',
  test_assigned: 'test',
}

export const CONFIDENCE_LABEL = translatedMap<Confidence>('replies:confidence', ['high', 'medium', 'low'])

export const MATCH_REASON_LABEL = translatedMap<Schemas['ReplyJob']['reason']>('replies:matchReason', [
  'contact',
  'domain',
  'ats',
  'company_name',
])

const LIKELY = translatedMap<ProposalEvent>('replies:likely', REPLY_EVENTS)

const WEEKDAY = { timeZone: APP_TIME_ZONE, weekday: 'long' } as const
const DAY_MONTH = { timeZone: APP_TIME_ZONE, day: 'numeric', month: 'long' } as const
const TIME = { timeZone: APP_TIME_ZONE, hour: 'numeric', minute: '2-digit', hourCycle: 'h23' } as const

/** «el jueves 8 de octubre a las 10:00» (o sin hora si es de todo el día), en hora de Madrid. */
export function spokenWhen(iso: string, allDay = false): string {
  const t = i18n.getFixedT(null, 'replies', 'when')
  const date = new Date(iso)
  const day = t('day', { weekday: dateFormatter(WEEKDAY).format(date), date: dateFormatter(DAY_MONTH).format(date) })
  if (allDay) return day
  const time = dateFormatter(TIME).format(date)
  return t(time.startsWith('1:') ? 'atOne' : 'at', { day, time })
}

/** «Parece una invitación a entrevista el jueves 8 de octubre a las 10:00». */
export function proposalSentence(proposal: Pick<ReplyProposal, 'event_type' | 'milestone'>): string {
  const t = i18n.getFixedT(null, 'replies', 'sentence')
  const base = LIKELY[proposal.event_type]
  const milestone = proposal.milestone
  if (!milestone) return base
  const when = spokenWhen(milestone.starts_at, milestone.all_day)
  return t(proposal.event_type === 'test_assigned' ? 'withDue' : 'withWhen', { base, when })
}
