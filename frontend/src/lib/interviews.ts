import { type MilestoneOut, type Stage } from '@/api/client'

/** Si la entrevista ya ha empezado. Una de todo el día (guardada a las 00:00 de Madrid) cuenta
 * como empezada al acabar ese día, igual que en el backend. */
export function hasStarted(milestone: MilestoneOut, now: Date = new Date()): boolean {
  const start = new Date(milestone.starts_at)
  if (!milestone.all_day) return start <= now
  const end = new Date(start)
  end.setDate(end.getDate() + 1)
  return end <= now
}

/**
 * Qué se puede hacer con el agente en una entrevista (fase 17): prepararla y ensayarla
 * mientras está programada y por empezar; repasarla en cuanto empieza, si no se canceló.
 */
export function interviewPhase(
  milestone: MilestoneOut,
  stage: Stage | null,
  now: Date = new Date(),
): 'upcoming' | 'past' | null {
  if (milestone.kind !== 'interview' || milestone.status === 'cancelled') return null
  if (hasStarted(milestone, now)) return 'past'
  return milestone.status === 'scheduled' && stage !== 'closed' ? 'upcoming' : null
}

/** `AAAA-MM-DD` del día de la entrevista en la zona del navegador (Madrid). */
function localDay(iso: string): string {
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

/** El plan tiene bloques después del día de la entrevista: se reprogramó después de hacerlo. */
export function planIsStale(milestone: MilestoneOut): boolean {
  const plan = milestone.prep_plan
  if (!plan) return false
  const day = localDay(milestone.starts_at)
  return plan.blocks.some((b) => b.date > day)
}
