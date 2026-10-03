/**
 * Fechas en la zona de la app (Europe/Madrid), sea cual sea la del navegador.
 *
 * Los `<input type="datetime-local">` trabajan con «hora de pared» sin zona: estas funciones la
 * convierten desde y hacia instantes ISO con zona, que es lo que acepta la API.
 */

export const APP_TIME_ZONE = 'Europe/Madrid'

const partsFmt = new Intl.DateTimeFormat('en-GB', {
  timeZone: APP_TIME_ZONE,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hourCycle: 'h23',
})

function wallParts(date: Date) {
  const get = (type: string) => Number(partsFmt.formatToParts(date).find((p) => p.type === type)?.value)
  return { year: get('year'), month: get('month'), day: get('day'), hour: get('hour'), minute: get('minute'), second: get('second') }
}

/** Minutos que Madrid va por delante de UTC en ese instante (60 o 120). */
function offsetMinutes(date: Date): number {
  const p = wallParts(date)
  const asUtc = Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute, p.second)
  return Math.round((asUtc - Math.floor(date.getTime() / 1000) * 1000) / 60_000)
}

const pad = (n: number) => String(n).padStart(2, '0')

/** Instante ISO → `YYYY-MM-DDTHH:mm` en hora de Madrid (para un `datetime-local`). */
export function toLocalInput(iso: string | Date): string {
  const p = wallParts(typeof iso === 'string' ? new Date(iso) : iso)
  return `${p.year}-${pad(p.month)}-${pad(p.day)}T${pad(p.hour)}:${pad(p.minute)}`
}

/** `YYYY-MM-DD` en hora de Madrid. */
export function toLocalDateInput(iso: string | Date): string {
  return toLocalInput(iso).slice(0, 10)
}

/** `YYYY-MM-DDTHH:mm` (o `YYYY-MM-DD`) en hora de Madrid → ISO con zona. `null` si no vale. */
export function fromLocalInput(value: string): string | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2}))?$/.exec(value)
  if (!match) return null
  const [, y, mo, d, h = '00', mi = '00'] = match
  const wall = Date.UTC(Number(y), Number(mo) - 1, Number(d), Number(h), Number(mi))
  // Fechas que no existen (31 de febrero, 25:00): Date.UTC las desborda al día siguiente.
  const check = new Date(wall)
  if (
    check.getUTCMonth() !== Number(mo) - 1 ||
    check.getUTCDate() !== Number(d) ||
    check.getUTCHours() !== Number(h) ||
    check.getUTCMinutes() !== Number(mi)
  )
    return null
  // Dos pasadas: el desfase depende del instante (horario de verano).
  let instant = wall - offsetMinutes(new Date(wall)) * 60_000
  instant = wall - offsetMinutes(new Date(instant)) * 60_000
  const offset = offsetMinutes(new Date(instant))
  const sign = offset >= 0 ? '+' : '-'
  const abs = Math.abs(offset)
  return `${y}-${mo}-${d}T${h}:${mi}:00${sign}${pad(Math.floor(abs / 60))}:${pad(abs % 60)}`
}

const dayFmt = new Intl.DateTimeFormat('es-ES', {
  timeZone: APP_TIME_ZONE,
  weekday: 'short',
  day: 'numeric',
  month: 'short',
})
const timeFmt = new Intl.DateTimeFormat('es-ES', { timeZone: APP_TIME_ZONE, hour: '2-digit', minute: '2-digit' })

/** «lun, 5 oct · 10:30» (o solo el día si es de todo el día), en hora de Madrid. */
export function formatWhen(iso: string, allDay = false): string {
  const date = new Date(iso)
  return allDay ? dayFmt.format(date) : `${dayFmt.format(date)} · ${timeFmt.format(date)}`
}
