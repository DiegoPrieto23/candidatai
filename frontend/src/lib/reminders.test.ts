import { describe, expect, it } from 'vitest'
import type { UpcomingItem } from '@/api/client'
import { dueReminders, markSent, readSent, reminderStart } from '@/lib/reminders'

function item(changes: Partial<UpcomingItem> = {}): UpcomingItem {
  return {
    kind: 'interview',
    job_id: 3,
    job_title: 'Data Engineer',
    company: 'Brétema Analytics',
    stage: 'in_process',
    milestone_id: 7,
    title: 'Entrevista',
    starts_at: '2026-10-07T08:30:00Z', // 10:30 en Madrid
    ends_at: null,
    all_day: false,
    location: null,
    ...changes,
  }
}

// Plazo de todo el día del 9 de octubre: empieza a las 00:00 de Madrid (22:00 UTC del día 8).
const deadline = item({ kind: 'deadline', milestone_id: 8, all_day: true, starts_at: '2026-10-08T22:00:00Z' })

describe('Avisos del navegador', () => {
  it('un hito con hora avisa desde una hora antes hasta que empieza', () => {
    expect(reminderStart(item()).toISOString()).toBe('2026-10-07T07:30:00.000Z')
    expect(dueReminders([item()], 0, new Date('2026-10-07T07:29:00Z'), new Set())).toEqual([])
    expect(dueReminders([item()], 0, new Date('2026-10-07T07:45:00Z'), new Set()).map((r) => r.kind)).toEqual(['milestone'])
    expect(dueReminders([item()], 0, new Date('2026-10-07T08:31:00Z'), new Set())).toEqual([])
  })

  it('uno de todo el día, desde las 9:00 del día anterior', () => {
    expect(reminderStart(deadline).toISOString()).toBe('2026-10-08T07:00:00.000Z') // 9:00 en Madrid
    expect(dueReminders([deadline], 0, new Date('2026-10-08T06:59:00Z'), new Set())).toEqual([])
    expect(dueReminders([deadline], 0, new Date('2026-10-08T07:00:00Z'), new Set())).toHaveLength(1)
  })

  it('los seguimientos, una vez al día desde las 9:00', () => {
    const morning = new Date('2026-10-07T06:00:00Z') // 8:00 en Madrid
    expect(dueReminders([], 2, morning, new Set())).toEqual([])
    const due = dueReminders([], 2, new Date('2026-10-07T07:10:00Z'), new Set())
    expect(due).toEqual([{ key: 'followups-2026-10-07', kind: 'followups', count: 2 }])
    expect(dueReminders([], 0, new Date('2026-10-07T07:10:00Z'), new Set())).toEqual([])
  })

  it('no repite lo ya avisado, también tras recargar', () => {
    const now = new Date('2026-10-07T07:45:00Z')
    const first = dueReminders([item()], 1, now, readSent())
    expect(first).toHaveLength(2)
    markSent(readSent(), first.map((r) => r.key))
    expect(dueReminders([item()], 1, now, readSent())).toEqual([])
    // Una entrevista cambiada de hora vuelve a avisar.
    expect(dueReminders([item({ starts_at: '2026-10-07T08:15:00Z' })], 1, now, readSent())).toHaveLength(1)
  })
})
