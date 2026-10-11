import type { ReplyProposal, Schemas } from '@/api/client'
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

export const REPLY_EVENT_LABEL: Record<ProposalEvent, string> = {
  interview_scheduled: 'Entrevista',
  test_assigned: 'Prueba técnica',
  offer_received: 'Oferta de trabajo',
  rejected: 'Rechazo',
  reply_received: 'Respuesta (el proceso sigue)',
  none: 'Nada que registrar',
}

export const MILESTONE_EVENTS: Partial<Record<ProposalEvent, 'interview' | 'test'>> = {
  interview_scheduled: 'interview',
  test_assigned: 'test',
}

export const CONFIDENCE_LABEL: Record<Confidence, string> = {
  high: 'Clara',
  medium: 'Revísala',
  low: 'Dudosa',
}

export const MATCH_REASON_LABEL: Record<Schemas['ReplyJob']['reason'], string> = {
  contact: 'contacto de la ficha',
  domain: 'dominio de la empresa',
  ats: 'plataforma de selección',
  company_name: 'nombre de la empresa',
}

const LIKELY: Record<ProposalEvent, string> = {
  interview_scheduled: 'Parece una invitación a entrevista',
  test_assigned: 'Parece una prueba técnica',
  offer_received: 'Parece una oferta de trabajo',
  rejected: 'Parece un rechazo',
  reply_received: 'Parece una respuesta de la empresa',
  none: 'No parece que haya nada que registrar',
}

const weekdayFmt = new Intl.DateTimeFormat('es-ES', { timeZone: APP_TIME_ZONE, weekday: 'long' })
const dayMonthFmt = new Intl.DateTimeFormat('es-ES', { timeZone: APP_TIME_ZONE, day: 'numeric', month: 'long' })
const timeFmt = new Intl.DateTimeFormat('es-ES', {
  timeZone: APP_TIME_ZONE,
  hour: 'numeric',
  minute: '2-digit',
  hourCycle: 'h23',
})

/** «el jueves 8 de octubre a las 10:00» (o sin hora si es de todo el día), en hora de Madrid. */
export function spokenWhen(iso: string, allDay = false): string {
  const date = new Date(iso)
  const day = `el ${weekdayFmt.format(date)} ${dayMonthFmt.format(date)}`
  if (allDay) return day
  const time = timeFmt.format(date)
  return `${day} ${time.startsWith('1:') ? 'a la' : 'a las'} ${time}`
}

/** «Parece una invitación a entrevista el jueves 8 de octubre a las 10:00». */
export function proposalSentence(proposal: Pick<ReplyProposal, 'event_type' | 'milestone'>): string {
  const base = LIKELY[proposal.event_type]
  const milestone = proposal.milestone
  if (!milestone) return base
  const when = spokenWhen(milestone.starts_at, milestone.all_day)
  return proposal.event_type === 'test_assigned' ? `${base} con entrega ${when}` : `${base} ${when}`
}
