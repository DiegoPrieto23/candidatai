import type {
  ApplicationChannel,
  CvRenderOptions,
  DiscardReason,
  EventType,
  MilestoneKind,
  Schemas,
  SectionName,
  Stage,
} from '@/api/client'

type Extraction = Schemas['JobExtraction']

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

export const STAGE_LABEL: Record<Stage, string> = {
  pending_detail: 'Por completar',
  pending_extraction: 'Por extraer',
  pending_triage: 'Por revisar',
  approved: 'Aprobada',
  cv_ready: 'CV listo',
  applied: 'Enviada',
  in_process: 'En proceso',
  closed: 'Cerrada',
}

export const EVENT_LABEL: Record<Schemas['EventType'], string> = {
  found: 'Dada de alta',
  detail_captured: 'Descripción capturada',
  duplicate_detected: 'Duplicado detectado',
  extracted: 'Extracción guardada',
  hard_filter_failed: 'No pasa los filtros',
  extraction_failed: 'Extracción fallida',
  injection_suspected: 'Posible contenido dirigido a una IA',
  scored: 'Puntuada',
  fit_assessed: 'Encaje valorado',
  approved: 'Aprobada',
  discarded: 'Descartada',
  cv_generated: 'CV redactado',
  cv_rendered: 'CV renderizado',
  cv_verified: 'CV verificado',
  cv_rejected: 'CV rechazado',
  application_prepared: 'Candidatura preparada',
  applied: 'Candidatura enviada',
  applied_manually: 'Enviada por tu cuenta',
  reply_received: 'Respuesta recibida',
  interview_scheduled: 'Entrevista programada',
  interview_done: 'Entrevista hecha',
  test_assigned: 'Prueba técnica',
  followup_sent: 'Seguimiento enviado',
  offer_received: 'Oferta recibida',
  rejected: 'Rechazada',
  withdrawn: 'Retirada',
  expired: 'Caducada',
  accepted: 'Aceptada',
  reopened: 'Reabierta',
  note: 'Nota',
}

export function eventLabel(type: string): string {
  return EVENT_LABEL[type as Schemas['EventType']] ?? type
}

export const REMOTE_LABEL: Record<Extraction['remote_mode'], string> = {
  onsite: 'Presencial',
  hybrid: 'Híbrido',
  remote: 'Remoto',
  unknown: 'Sin especificar',
}

export const SENIORITY_LABEL: Record<Extraction['seniority'], string> = {
  intern: 'Prácticas',
  junior: 'Junior',
  mid: 'Intermedio',
  senior: 'Senior',
  lead: 'Lead',
  unknown: 'Sin especificar',
}

export const EMPLOYMENT_LABEL: Record<Extraction['employment_type'], string> = {
  full_time: 'Jornada completa',
  part_time: 'Media jornada',
  contract: 'Contrato temporal',
  internship: 'Prácticas',
  unknown: 'Sin especificar',
}

const RISK_LABEL: Record<string, string> = {
  injection_phrase: 'Frases que parecen instrucciones para una IA',
  hidden_text: 'Texto oculto en la página original',
}

export function riskLabel(flag: string): string {
  return RISK_LABEL[flag] ?? flag
}

export function actorLabel(actor: string, agentName?: string | null): string {
  if (actor === 'user') return 'Tú'
  if (actor === 'agent') return agentName ? `Agente ${agentName}` : 'Agente'
  return 'Sistema'
}

const PERIOD_LABEL = { year: 'año', month: 'mes', hour: 'hora' } as const

export function formatSalary(salary: Extraction['salary']): string | null {
  if (!salary || (salary.min == null && salary.max == null)) return null
  const currency = salary.currency ?? ''
  const fmt = (n: number) => {
    try {
      return new Intl.NumberFormat('es-ES', {
        style: currency ? 'currency' : 'decimal',
        currency: currency || undefined,
        maximumFractionDigits: 0,
      }).format(n)
    } catch {
      return `${n.toLocaleString('es-ES')} ${currency}`.trim()
    }
  }
  const range =
    salary.min != null && salary.max != null && salary.min !== salary.max
      ? `${fmt(salary.min)} - ${fmt(salary.max)}`
      : fmt((salary.min ?? salary.max) as number)
  return salary.period ? `${range} / ${PERIOD_LABEL[salary.period]}` : range
}

const dateFmt = new Intl.DateTimeFormat('es-ES', { day: 'numeric', month: 'short', year: 'numeric' })
const dateTimeFmt = new Intl.DateTimeFormat('es-ES', {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
})
const relativeFmt = new Intl.RelativeTimeFormat('es', { numeric: 'auto' })

export function formatDate(iso: string): string {
  return dateFmt.format(new Date(iso))
}

export function formatDateTime(iso: string): string {
  return dateTimeFmt.format(new Date(iso))
}

/** «hoy», «ayer», «hace 3 días»… y la fecha a partir de un mes. */
export function formatRelative(iso: string, now: Date = new Date()): string {
  const date = new Date(iso)
  const startOf = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()
  const days = Math.round((startOf(now) - startOf(date)) / 86_400_000)
  if (days < 0) return formatDate(iso)
  if (days < 7) return relativeFmt.format(-days, 'day')
  if (days < 30) return relativeFmt.format(-Math.floor(days / 7), 'week')
  return formatDate(iso)
}

// --- Matching y triaje -------------------------------------------------------------------------

/** Motivos rápidos de descarte, en el orden de sus atajos (1-6). */
export const DISCARD_REASONS: readonly { value: DiscardReason; label: string }[] = [
  { value: 'skills', label: 'No encaja el stack' },
  { value: 'seniority', label: 'Seniority o años' },
  { value: 'location', label: 'Ubicación o modalidad' },
  { value: 'salary', label: 'Salario o condiciones' },
  { value: 'company', label: 'Empresa o sector' },
  { value: 'other', label: 'Otro motivo' },
]

export function discardReasonLabel(reason: string): string {
  return DISCARD_REASONS.find((r) => r.value === reason)?.label ?? reason
}

export const COMPONENT_LABEL: Record<Schemas['ScoreComponent']['name'], string> = {
  must_have_coverage: 'Obligatorias',
  semantic_similarity: 'Similitud',
  preferences_fit: 'Preferencias',
  nice_to_have_coverage: 'Deseables',
}

export const LEVEL_LABEL: Record<Schemas['CoveredSkill']['level'], string> = {
  F: 'Fuerte',
  'C+': 'Entre conozco y fuerte',
  C: 'Conozco',
  B: 'Básico',
  basic: 'Conocimientos básicos',
}

export const VERDICT_LABEL: Record<Schemas['FitAssessment']['verdict'], string> = {
  strong: 'Encaje fuerte',
  possible: 'Encaje posible',
  weak: 'Encaje débil',
}

// --- CV -----------------------------------------------------------------------------------------

export const SECTION_LABEL: Record<SectionName, string> = {
  summary: 'Perfil',
  experience: 'Experiencia',
  projects: 'Proyectos',
  education: 'Formación',
  certifications: 'Certificaciones',
  extra_sections: 'Secciones extra',
  skills: 'Habilidades',
  languages: 'Idiomas',
}

export const PHOTO_MODE_LABEL: Record<NonNullable<CvRenderOptions['photo']>, string> = {
  auto: 'Automática',
  include: 'Con foto',
  exclude: 'Sin foto',
}

/** Nombres de los colores de las plantillas integradas; el resto se muestran en hexadecimal. */
const COLOR_NAMES: Record<string, string> = {
  '#1F4E79': 'Azul',
  '#2E5E4E': 'Verde',
  '#7A2E39': 'Granate',
  '#3F3F46': 'Grafito',
}

export function colorLabel(hex: string): string {
  return COLOR_NAMES[hex.toUpperCase()] ?? hex.toUpperCase()
}

// --- Seguimiento (fase 10) ------------------------------------------------------------------------

export const MILESTONE_KIND_LABEL: Record<MilestoneKind, string> = {
  interview: 'Entrevista',
  test: 'Prueba técnica',
  deadline: 'Plazo',
  other: 'Otro hito',
}

export const UPCOMING_KIND_LABEL: Record<Schemas['UpcomingItem']['kind'], string> = {
  ...MILESTONE_KIND_LABEL,
  application_deadline: 'Plazo de la oferta',
}

export const MILESTONE_STATUS_LABEL: Record<Schemas['MilestoneOut']['status'], string> = {
  scheduled: 'Programado',
  done: 'Hecho',
  cancelled: 'Cancelado',
}

export const CHANNEL_LABEL: Record<ApplicationChannel, string> = {
  ats_form: 'Formulario de la empresa',
  email: 'Correo',
  linkedin_manual: 'LinkedIn (a mano)',
  portal_manual: 'Portal de empleo (a mano)',
}

export function channelLabel(channel: string | null | undefined): string | null {
  return channel ? (CHANNEL_LABEL[channel as ApplicationChannel] ?? channel) : null
}

/** Qué significa cada movimiento del kanban, en el diálogo que lo confirma. */
export const MOVE_HINT: Partial<Record<EventType, string>> = {
  applied: 'La enviaste con el CV seleccionado en la app.',
  applied_manually: 'La enviaste por tu cuenta (con o sin el CV de la app).',
  reply_received: 'Te han contestado.',
  interview_scheduled: 'Tienes una entrevista: se crea su hito con fecha y hora.',
  interview_done: 'Ya hiciste una entrevista que no tenías anotada.',
  test_assigned: 'Te han mandado una prueba: se crea su hito con la fecha de entrega.',
  offer_received: 'Te han hecho una oferta.',
  discarded: 'La dejas antes de enviarla.',
  rejected: 'La empresa te ha descartado.',
  withdrawn: 'Te retiras del proceso.',
  expired: 'La oferta ha caducado o no hubo respuesta.',
  accepted: 'Has aceptado la oferta.',
  reopened: 'Vuelve a la etapa en la que estaba al cerrarse.',
}

// --- Analítica ---------------------------------------------------------------------------------

/** Filtros duros (`hard_filter_failed.payload.failures[].filter`). */
export const HARD_FILTER_LABEL: Partial<Record<string, string>> = {
  seniority: 'Seniority',
  years: 'Años de experiencia',
  remote_mode: 'Modalidad',
  location: 'Ubicación',
  language: 'Idioma',
  title_keyword: 'Palabras del título',
} satisfies Record<Schemas['FilterFailure']['filter'], string>

/** Tipos de fuente (`sources.kind`). */
export const SOURCE_KIND_LABEL: Partial<Record<string, string>> = {
  manual_url: 'Enlace',
  manual_text: 'Texto pegado',
  greenhouse: 'Greenhouse',
  lever: 'Lever',
  ashby: 'Ashby',
  infojobs: 'InfoJobs',
  adzuna: 'Adzuna',
  email_alerts: 'Alertas por correo',
  browser_capture: 'Botón del navegador',
  agent_browse: 'Búsqueda con navegador',
}
