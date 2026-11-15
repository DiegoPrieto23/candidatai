import { useSyncExternalStore } from 'react'
import type { UpcomingItem } from '@/api/client'
import { dayOf, minutesOf } from '@/lib/calendar'

/**
 * Avisos del navegador de lo pendiente, mientras la app está abierta (la app no envía correos):
 * - un hito con hora, una hora antes;
 * - uno de todo el día (los plazos), desde las 9:00 del día anterior;
 * - los seguimientos vencidos, una vez al día a partir de las 9:00.
 * Son los mismos tiempos que las alarmas del calendario (`.ics`). Lo ya avisado se recuerda en este
 * navegador para no repetirlo.
 */
export const TIMED_LEAD_MINUTES = 60
export const ALL_DAY_LEAD_HOURS = 15 // las 00:00 del día menos 15 horas: las 9:00 del anterior
export const DAILY_HOUR = 9

const ENABLED_KEY = 'cai-browser-reminders'
const SENT_KEY = 'cai-reminders-sent'
const MAX_SENT = 200
const listeners = new Set<() => void>()

export interface Reminder {
  key: string
  kind: 'milestone' | 'followups'
  item?: UpcomingItem
  count?: number
}

export function notificationsSupported(): boolean {
  return typeof window !== 'undefined' && 'Notification' in window
}

export function remindersEnabled(): boolean {
  try {
    return localStorage.getItem(ENABLED_KEY) === '1'
  } catch {
    return false
  }
}

export function setRemindersEnabled(enabled: boolean): void {
  try {
    if (enabled) localStorage.setItem(ENABLED_KEY, '1')
    else localStorage.removeItem(ENABLED_KEY)
  } catch {
    // Sin almacenamiento: no se puede recordar la elección.
  }
  listeners.forEach((notify) => notify())
}

/** Avisa a los suscriptores (p. ej. tras cambiar el permiso del navegador). */
export function refreshReminders(): void {
  listeners.forEach((notify) => notify())
}

function subscribe(notify: () => void): () => void {
  listeners.add(notify)
  return () => listeners.delete(notify)
}

/** Activados y con permiso del navegador. */
function activeSnapshot(): string {
  const permission = notificationsSupported() ? Notification.permission : 'unsupported'
  return `${remindersEnabled() ? 'on' : 'off'}:${permission}`
}

export function useReminderState(): { enabled: boolean; permission: NotificationPermission | 'unsupported' } {
  const snapshot = useSyncExternalStore(subscribe, activeSnapshot, activeSnapshot)
  const [enabled, permission] = snapshot.split(':')
  return { enabled: enabled === 'on', permission: permission as NotificationPermission | 'unsupported' }
}

export function readSent(): Set<string> {
  try {
    const raw = localStorage.getItem(SENT_KEY)
    const parsed: unknown = raw ? JSON.parse(raw) : []
    return new Set(Array.isArray(parsed) ? parsed.filter((k): k is string => typeof k === 'string') : [])
  } catch {
    return new Set()
  }
}

export function markSent(sent: Set<string>, keys: string[]): void {
  keys.forEach((key) => sent.add(key))
  try {
    localStorage.setItem(SENT_KEY, JSON.stringify([...sent].slice(-MAX_SENT)))
  } catch {
    // Sin almacenamiento: puede repetirse un aviso si se recarga la página.
  }
}

/** El momento desde el que se avisa de un hito. */
export function reminderStart(item: UpcomingItem): Date {
  const start = new Date(item.starts_at).getTime()
  const lead = item.all_day ? ALL_DAY_LEAD_HOURS * 60 : TIMED_LEAD_MINUTES
  return new Date(start - lead * 60_000)
}

/** Lo que toca avisar ahora y aún no se ha avisado. */
export function dueReminders(
  items: UpcomingItem[],
  followupsDue: number,
  now: Date,
  sent: ReadonlySet<string>,
): Reminder[] {
  const due: Reminder[] = []
  for (const item of items) {
    const key = `${item.kind}-${item.milestone_id ?? item.job_id}-${item.starts_at}`
    if (sent.has(key)) continue
    if (now >= reminderStart(item) && now < new Date(item.starts_at)) due.push({ key, kind: 'milestone', item })
  }
  const today = dayOf(now.toISOString())
  const key = `followups-${today}`
  if (followupsDue > 0 && !sent.has(key) && minutesOf(now.toISOString()) >= DAILY_HOUR * 60) {
    due.push({ key, kind: 'followups', count: followupsDue })
  }
  return due
}
