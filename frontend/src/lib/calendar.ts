/**
 * Cuentas de la página «Calendario» con días de pared (`YYYY-MM-DD`) en hora de Madrid, sea cual sea
 * la zona del navegador. Las semanas empiezan en lunes.
 */

import { dateFormatter } from '@/lib/labels'
import { toLocalDateInput, toLocalInput } from '@/lib/time'

/** Un día de calendario, `YYYY-MM-DD`. */
export type Day = string

export type CalendarView = 'month' | 'week' | 'day' | 'agenda'

export const CALENDAR_VIEWS: readonly CalendarView[] = ['month', 'week', 'day', 'agenda']

/** Días que cubre la agenda desde la fecha elegida. */
export const AGENDA_DAYS = 30

const DAY_RE = /^(\d{4})-(\d{2})-(\d{2})$/

/** Las 00:00 UTC de ese día: así se suma y se formatea sin que cuente la zona del navegador. */
function utc(day: Day): Date {
  const [, y, m, d] = DAY_RE.exec(day) ?? []
  return new Date(Date.UTC(Number(y), Number(m) - 1, Number(d)))
}

const fromUtc = (date: Date): Day => date.toISOString().slice(0, 10)

export function isDay(value: string | null | undefined): value is Day {
  if (!value || !DAY_RE.test(value)) return false
  return fromUtc(utc(value)) === value
}

export function today(): Day {
  return toLocalDateInput(new Date())
}

export function addDays(day: Day, days: number): Day {
  const date = utc(day)
  date.setUTCDate(date.getUTCDate() + days)
  return fromUtc(date)
}

export function addMonths(day: Day, months: number): Day {
  const date = utc(day)
  const wanted = date.getUTCMonth() + months
  date.setUTCDate(1)
  date.setUTCMonth(wanted)
  // El 31 de un mes de 30 días se queda en el último día del mes, no salta al siguiente.
  const last = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + 1, 0)).getUTCDate()
  date.setUTCDate(Math.min(utc(day).getUTCDate(), last))
  return fromUtc(date)
}

/** 0 = lunes … 6 = domingo. */
export function weekday(day: Day): number {
  return (utc(day).getUTCDay() + 6) % 7
}

export function startOfWeek(day: Day): Day {
  return addDays(day, -weekday(day))
}

export function sameMonth(a: Day, b: Day): boolean {
  return a.slice(0, 7) === b.slice(0, 7)
}

export function daysBetween(start: Day, end: Day): Day[] {
  const days: Day[] = []
  for (let day = start; day <= end; day = addDays(day, 1)) days.push(day)
  return days
}

/** Del lunes de la semana del día 1 al domingo de la del último día: 4, 5 o 6 semanas enteras. */
export function monthGrid(day: Day): Day[] {
  const first = `${day.slice(0, 7)}-01`
  const last = addDays(addMonths(first, 1), -1)
  return daysBetween(startOfWeek(first), addDays(startOfWeek(last), 6))
}

/** Los días que pide cada vista a la API (`start` y `end` incluidos). */
export function viewRange(view: CalendarView, day: Day): { start: Day; end: Day } {
  switch (view) {
    case 'month': {
      const grid = monthGrid(day)
      return { start: grid[0], end: grid[grid.length - 1] }
    }
    case 'week':
      return { start: startOfWeek(day), end: addDays(startOfWeek(day), 6) }
    case 'day':
      return { start: day, end: day }
    case 'agenda':
      return { start: day, end: addDays(day, AGENDA_DAYS - 1) }
  }
}

/** El día al que llevan «Anterior» y «Siguiente». */
export function shift(view: CalendarView, day: Day, step: 1 | -1): Day {
  switch (view) {
    case 'month':
      return addMonths(day, step)
    case 'week':
      return addDays(day, 7 * step)
    case 'day':
      return addDays(day, step)
    case 'agenda':
      return addDays(day, AGENDA_DAYS * step)
  }
}

// --- Instantes ------------------------------------------------------------------------------

/** El día de pared (Madrid) de un instante ISO. */
export function dayOf(iso: string): Day {
  return toLocalDateInput(iso)
}

/** Minutos desde las 00:00 (Madrid) de un instante ISO. */
export function minutesOf(iso: string): number {
  const [h, m] = toLocalInput(iso).slice(11, 16).split(':').map(Number)
  return h * 60 + m
}

// --- Textos ---------------------------------------------------------------------------------

const fmt = (options: Intl.DateTimeFormatOptions) => dateFormatter({ timeZone: 'UTC', ...options })

export function formatDay(day: Day, options: Intl.DateTimeFormatOptions): string {
  return fmt(options).format(utc(day))
}

/** «octubre de 2026», «19–25 oct 2026», «viernes, 23 de octubre de 2026»… */
export function rangeLabel(view: CalendarView, day: Day): string {
  const { start, end } = viewRange(view, day)
  switch (view) {
    case 'month':
      return formatDay(day, { month: 'long', year: 'numeric' })
    case 'day':
      return formatDay(day, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
    default:
      return fmt({ day: 'numeric', month: 'short', year: 'numeric' }).formatRange(utc(start), utc(end))
  }
}
