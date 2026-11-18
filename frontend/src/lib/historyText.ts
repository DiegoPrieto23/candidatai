/**
 * Textos del historial de «Mi perfil»: cuándo se hizo cada versión, el nombre de cada campo y cómo
 * se lee cada valor, sin claves del YAML a la vista.
 */
import type { Schemas } from '@/api/client'

// La posición llega como tupla en el esquema y como lista tras `unwrap`: vale cualquiera de las dos.
export type ItemChange = Omit<Schemas['ItemChange'], 'position'> & { position?: readonly number[] | null }
export type FieldChange = Schemas['FieldChange']
export type HistoryBlock = ItemChange['block']

/** `t` de `profileEditor` (o uno de prueba que devuelva la clave). */
export type Say = (key: string, values?: Record<string, unknown>) => string

const LANGS = new Set(['es', 'en'])
const MONTH = /^(\d{4})-(\d{2})$/

/** «Hoy, 18:05», «Ayer, 20:15», «12 nov, 09:31» y, de otro año, «12 nov 2025, 09:31». `inline`,
 * para dentro de una frase: «hoy, 18:05». */
export function versionWhen(iso: string, say: Say, locale: string, { now = new Date(), inline = false }: { now?: Date; inline?: boolean } = {}): string {
  const date = new Date(iso)
  const time = new Intl.DateTimeFormat(locale, { hour: '2-digit', minute: '2-digit' }).format(date)
  const startOf = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()
  const days = Math.round((startOf(now) - startOf(date)) / 86_400_000)
  const suffix = inline ? 'Inline' : ''
  if (days === 0) return say(`history.when.today${suffix}`, { time })
  if (days === 1) return say(`history.when.yesterday${suffix}`, { time })
  const sameYear = date.getFullYear() === now.getFullYear()
  const day = new Intl.DateTimeFormat(locale, { day: 'numeric', month: 'short', ...(sameYear ? {} : { year: 'numeric' }) }).format(date)
  return say('history.when.other', { date: day, time })
}

/** El título de un bloque: el mismo que en el editor. */
export function blockTitle(block: HistoryBlock, say: Say): string {
  return block === 'search' || block === 'private' ? say(`history.blocks.${block}`) : say(`blocks.${block}.title`)
}

function humanize(key: string): string {
  const text = key.replace(/_/g, ' ')
  return text.charAt(0).toUpperCase() + text.slice(1)
}

/** El nombre de un campo: «Nivel», «Resumen (inglés)», «Foto en Francia». */
export function fieldLabel(path: readonly string[], say: Say, country: (code: string) => string): string {
  if (path.length === 0) return ''
  const last = path[path.length - 1]
  if (path.length > 1 && LANGS.has(last)) {
    return say('history.inLanguage', { label: fieldLabel(path.slice(0, -1), say, country), language: say(`history.languages.${last}`) })
  }
  if (path.length === 3 && path[0] === 'photo_policy' && path[1] === 'by_country') {
    return say('history.fields.photo_in', { country: country(last) })
  }
  for (const key of [path.join('_'), last]) {
    const label = say(`history.fields.${key}`)
    if (label !== `history.fields.${key}`) return label
  }
  return humanize(last)
}

/** Un valor como se lee: «Sí», «marzo 2026», «F · fuerte», «Actualidad»… */
export function valueText(path: readonly string[], value: unknown, say: Say, locale: string): string {
  const key = path[path.length - 1] ?? ''
  if (value === null || value === undefined || value === '') return say('history.empty')
  if (typeof value === 'boolean') return say(value ? 'history.yes' : 'history.no')
  if (Array.isArray(value)) return value.map((v) => valueText(path, v, say, locale)).join(', ')
  if (typeof value === 'object') return JSON.stringify(value)
  const text = String(value)
  if (key === 'end' && text === 'present') return say('fields.present')
  const month = MONTH.exec(text)
  if (month) {
    const date = new Date(Number(month[1]), Number(month[2]) - 1, 1)
    return new Intl.DateTimeFormat(locale, { month: 'long', year: 'numeric' }).format(date)
  }
  const coded: Record<string, string> = { level: 'levels', seniority_target: 'seniority', remote_modes: 'remote' }
  if (coded[key]) {
    const label = say(`${coded[key]}.${text}`)
    if (label !== `${coded[key]}.${text}`) return label
  }
  return text
}

/** El resumen de una versión: «Experiencia (2 cambios) · Skills (1 cambio)». */
export function versionSummary(
  entry: { first: boolean; summary: readonly { block: HistoryBlock; changes: number }[] },
  say: Say,
): string {
  if (entry.first) return say('history.first')
  if (entry.summary.length === 0) return say('history.noChanges')
  return entry.summary
    .map(({ block, changes }) =>
      block === 'private' ? say('history.privateChanged', { block: blockTitle(block, say) }) : say('history.count', { block: blockTitle(block, say), count: changes }),
    )
    .join(' · ')
}

/** Los cambios agrupados por bloque, en el orden en que llegan (el del editor). */
export function byBlock(changes: readonly ItemChange[]): [HistoryBlock, ItemChange[]][] {
  const groups = new Map<HistoryBlock, ItemChange[]>()
  for (const change of changes) {
    const list = groups.get(change.block) ?? []
    list.push(change)
    groups.set(change.block, list)
  }
  return [...groups]
}
