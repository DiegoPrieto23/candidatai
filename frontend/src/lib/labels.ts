import type {
  ApplicationChannel,
  ContactRelation,
  CvRenderOptions,
  DiscardReason,
  EventType,
  MilestoneKind,
  ReferralStatus,
  Schemas,
  SectionName,
  Stage,
} from '@/api/client'
import { i18n, intlLocale } from '@/lib/i18n'
import labels from '@/locales/es/labels.json'

type Extraction = Schemas['JobExtraction']
type Group = keyof typeof labels

/** Un texto de `locales/<idioma>/labels.json`, en el idioma activo. */
function tr(key: string, options?: Record<string, unknown>): string {
  return String(i18n.t(`labels:${key}` as never, options as never))
}

/**
 * Un diccionario de etiquetas que se traduce al leerlo: `STAGE_LABEL.applied` devuelve el texto
 * del idioma activo. Las claves salen del fichero de referencia (español).
 */
function translated<K extends string>(group: Group): Record<K, string> {
  return translatedMap<K>(`labels:${group}`, Object.keys(labels[group]) as K[])
}

/** Lo mismo para cualquier grupo de textos (`ns:grupo`), con sus claves. */
export function translatedMap<K extends string>(prefix: string, keys: readonly K[]): Record<K, string> {
  const map = {} as Record<K, string>
  for (const key of keys) {
    Object.defineProperty(map, key, {
      enumerable: true,
      get: () => String(i18n.t(`${prefix}.${key}` as never)),
    })
  }
  return map
}

/** Etapas en el orden del embudo. */
export const STAGES: readonly Stage[] = [
  'pending_detail',
  'pending_extraction',
  'pending_triage',
  'approved',
  'cv_ready',
  'applied',
  'in_process',
  'closed',
]

export const STAGE_LABEL = translated<Stage>('stage')

export const EVENT_LABEL = translated<Schemas['EventType']>('event')

export function eventLabel(type: string): string {
  return EVENT_LABEL[type as Schemas['EventType']] ?? type
}

export const REMOTE_LABEL = translated<Extraction['remote_mode']>('remote')

export const SENIORITY_LABEL = translated<Extraction['seniority']>('seniority')

export const EMPLOYMENT_LABEL = translated<Extraction['employment_type']>('employment')

const RISK_LABEL = translated<string>('risk')

export function riskLabel(flag: string): string {
  return RISK_LABEL[flag] ?? flag
}

export function actorLabel(actor: string, agentName?: string | null): string {
  if (actor === 'user') return tr('actor.user')
  if (actor === 'agent') return agentName ? tr('actor.agentNamed', { name: agentName }) : tr('actor.agent')
  return tr('actor.system')
}

const PERIOD_LABEL = translated<'year' | 'month' | 'hour'>('period')

export function formatSalary(salary: Extraction['salary']): string | null {
  if (!salary || (salary.min == null && salary.max == null)) return null
  const currency = salary.currency ?? ''
  const locale = intlLocale()
  const fmt = (n: number) => {
    try {
      return new Intl.NumberFormat(locale, {
        style: currency ? 'currency' : 'decimal',
        currency: currency || undefined,
        maximumFractionDigits: 0,
      }).format(n)
    } catch {
      return `${n.toLocaleString(locale)} ${currency}`.trim()
    }
  }
  const range =
    salary.min != null && salary.max != null && salary.min !== salary.max
      ? `${fmt(salary.min)} - ${fmt(salary.max)}`
      : fmt((salary.min ?? salary.max) as number)
  return salary.period ? `${range} / ${PERIOD_LABEL[salary.period]}` : range
}

/** Un importe con su moneda, sin decimales («45.000 €»). */
export function formatMoney(amount: number, currency = 'EUR'): string {
  const locale = intlLocale()
  try {
    return new Intl.NumberFormat(locale, { style: 'currency', currency, maximumFractionDigits: 0 }).format(amount)
  } catch {
    return `${amount.toLocaleString(locale)} ${currency}`
  }
}

/** Una diferencia con signo («+4.000 €», «−3.000 €»). */
export function formatMoneyDiff(diff: number, currency = 'EUR'): string {
  if (diff === 0) return formatMoney(0, currency)
  return `${diff > 0 ? '+' : '−'}${formatMoney(Math.abs(diff), currency)}`
}

/** Dólares con los decimales que hacen falta (fase 25.4: el coste de una ejecución son céntimos). */
export function formatUsd(value: number | null | undefined): string {
  if (value == null) return '—'
  const digits = value !== 0 && Math.abs(value) < 1 ? 4 : 2
  return `${formatNumber(value, { minimumFractionDigits: digits, maximumFractionDigits: digits })} USD`
}

/** Tokens redondeados, con separadores. */
export function formatTokens(value: number | null | undefined): string {
  return value == null ? '—' : formatNumber(Math.round(value))
}

/** Un número con los separadores del idioma activo («1.234» o «1,234»). */
export function formatNumber(n: number, options?: Intl.NumberFormatOptions): string {
  return new Intl.NumberFormat(intlLocale(), options).format(n)
}

/** Formateadores de fecha del idioma activo: uno por locale y opciones. */
const dateFormatters = new Map<string, Intl.DateTimeFormat>()

export function dateFormatter(options: Intl.DateTimeFormatOptions): Intl.DateTimeFormat {
  const locale = intlLocale()
  const key = `${locale}|${JSON.stringify(options)}`
  let fmt = dateFormatters.get(key)
  if (!fmt) {
    fmt = new Intl.DateTimeFormat(locale, options)
    dateFormatters.set(key, fmt)
  }
  return fmt
}

export function formatDate(iso: string): string {
  return dateFormatter({ day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(iso))
}

export function formatDateTime(iso: string): string {
  return dateFormatter({
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(iso))
}

/** «hoy», «ayer», «hace 3 días»… y la fecha a partir de un mes. */
export function formatRelative(iso: string, now: Date = new Date()): string {
  const date = new Date(iso)
  const startOf = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()
  const days = Math.round((startOf(now) - startOf(date)) / 86_400_000)
  if (days < 0) return formatDate(iso)
  const relativeFmt = new Intl.RelativeTimeFormat(intlLocale(), { numeric: 'auto' })
  if (days < 7) return relativeFmt.format(-days, 'day')
  if (days < 30) return relativeFmt.format(-Math.floor(days / 7), 'week')
  return formatDate(iso)
}

// --- Matching y «Por revisar» -------------------------------------------------------------------------

const DISCARD_REASON_LABEL = translated<DiscardReason>('discardReason')

/** Motivos rápidos de descarte, en el orden de sus atajos (1-7). */
export const DISCARD_REASONS: readonly { value: DiscardReason; readonly label: string }[] = (
  ['skills', 'seniority', 'location', 'salary', 'company', 'closed', 'other'] as const
).map((value) => ({
  value,
  get label() {
    return DISCARD_REASON_LABEL[value]
  },
}))

export function discardReasonLabel(reason: string): string {
  return DISCARD_REASON_LABEL[reason as DiscardReason] ?? reason
}

export const COMPONENT_LABEL = translated<Schemas['ScoreComponent']['name']>('component')

export const LEVEL_LABEL = translated<Schemas['CoveredSkill']['level']>('level')

export const VERDICT_LABEL = translated<Schemas['FitAssessment']['verdict']>('verdict')

// --- CV -----------------------------------------------------------------------------------------

export const SECTION_LABEL = translated<SectionName>('section')

export const PHOTO_MODE_LABEL = translated<NonNullable<CvRenderOptions['photo']>>('photoMode')

/** Nombres de los colores de las plantillas integradas; el resto se muestran en hexadecimal. */
const COLOR_NAMES = translated<string>('color')

export function colorLabel(hex: string): string {
  return COLOR_NAMES[hex.toUpperCase()] ?? hex.toUpperCase()
}

// --- Seguimiento (fase 10) ------------------------------------------------------------------------

export const MILESTONE_KIND_LABEL = translated<MilestoneKind>('milestoneKind')

export const UPCOMING_KIND_LABEL = translated<Schemas['UpcomingItem']['kind']>('upcomingKind')

// --- Contactos y red (fase 18) -------------------------------------------------------------------

export const CONTACT_RELATION_LABEL = translated<ContactRelation>('contactRelation')

export const REFERRAL_LABEL = translated<ReferralStatus>('referral')

export const MILESTONE_STATUS_LABEL = translated<Schemas['MilestoneOut']['status']>('milestoneStatus')

export const CHANNEL_LABEL = translated<ApplicationChannel>('channel')

export function channelLabel(channel: string | null | undefined): string | null {
  return channel ? (CHANNEL_LABEL[channel as ApplicationChannel] ?? channel) : null
}

/** Qué significa cada movimiento del kanban, en el diálogo que lo confirma. */
export const MOVE_HINT: Partial<Record<EventType, string>> = translated<EventType>('moveHint')

// --- Analítica ---------------------------------------------------------------------------------

/** Filtros duros (`hard_filter_failed.payload.failures[].filter`). */
export const HARD_FILTER_LABEL: Partial<Record<string, string>> =
  translated<Schemas['FilterFailure']['filter']>('hardFilter')

/** Tipos de fuente (`sources.kind`). */
export const SOURCE_KIND_LABEL: Partial<Record<string, string>> = translated<string>('sourceKind')
