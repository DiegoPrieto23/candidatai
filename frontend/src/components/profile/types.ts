/**
 * Las secciones de `data/profile.yaml` tal como las devuelve `GET /profile/editable` (fase 25.7b).
 * La API las da sin tipar (`dict`): estos tipos siguen `backend/app/schemas/profile.py`. Las claves
 * que la UI no conoce se conservan, porque cada formulario parte del objeto que recibió y solo
 * cambia lo que edita (la API borra las claves que no vuelven).
 */

export type SkillLevel = 'F' | 'C+' | 'C' | 'B'
export type Seniority = 'intern' | 'junior' | 'mid' | 'senior' | 'lead'
export type RemoteMode = 'onsite' | 'hybrid' | 'remote'

export interface Personal {
  name: string
  email?: string | null
  phone?: string | null
  linkedin?: string | null
  github?: string | null
  city?: string | null
  profile_location?: string | null
  availability?: string | null
  mobility?: string | null
  [key: string]: unknown
}

export interface Localized {
  es?: string | null
  en?: string | null
  [key: string]: unknown
}

export interface Achievement {
  id?: string
  text: string
  metrics?: string | null
  skills?: string[]
  nda?: boolean
  source?: string | null
  [key: string]: unknown
}

export interface Experience {
  id?: string
  company: string
  city?: string | null
  role: string
  start: string
  end: string
  context?: string | null
  achievements?: Achievement[]
  [key: string]: unknown
}

export interface Project {
  id?: string
  name: string
  date?: string | null
  text: string
  url?: string | null
  skills?: string[]
  nda?: boolean
  source?: string | null
  [key: string]: unknown
}

export interface Education {
  id?: string
  title: string
  center: string
  start?: string | null
  end?: string | null
  [key: string]: unknown
}

export interface Certification {
  id?: string
  name: string
  issuer?: string | null
  date?: string | null
  source?: string | null
  [key: string]: unknown
}

export interface ExtraItem {
  id?: string
  text: string
  date?: string | null
  source?: string | null
  [key: string]: unknown
}

export interface ExtraSection {
  id?: string
  title: Localized
  items: ExtraItem[]
  [key: string]: unknown
}

export interface Language {
  language: string
  level: string
  regional?: string | null
  [key: string]: unknown
}

export interface Skill {
  name: string
  level: SkillLevel
  category?: string | null
  [key: string]: unknown
}

export interface Story {
  id?: string
  title: string
  situation: string
  task: string
  action: string
  result: string
  evidence: string[]
  [key: string]: unknown
}

export interface CvPreferences {
  default_template?: string | null
  photo_file?: string
  max_pages?: number | null
  photo_policy: { default: boolean; by_country?: Record<string, boolean>; [key: string]: unknown }
  template_rules?: { when: Record<string, string[]>; use: string }[]
  instructions?: string | null
  avoid?: string[]
  [key: string]: unknown
}

export interface CoverLetterPreferences {
  max_words?: number | null
  tone?: string | null
  sign_off?: Localized
  instructions?: string | null
  avoid?: string[]
  default_format?: 'text' | 'pdf' | null
  [key: string]: unknown
}

export interface Preferences {
  roles: string[]
  seniority_target: Seniority[]
  max_years_required?: number | null
  remote_modes: RemoteMode[]
  locations?: { preferred?: string[]; allowed?: string[]; excluded?: string[]; [key: string]: unknown }
  languages_for_work: string[]
  cv: CvPreferences
  cover_letter?: CoverLetterPreferences | null
  [key: string]: unknown
}

export interface ProfileData {
  personal?: Personal
  headline?: string
  summary?: Localized
  experience?: Experience[]
  projects?: Project[]
  education?: Education[]
  certifications?: Certification[]
  extra_sections?: ExtraSection[]
  languages?: Language[]
  skills?: Skill[]
  basic_skills?: string[]
  stories?: Story[]
  preferences?: Preferences
  [key: string]: unknown
}

export const PRESENT = 'present'
export const SKILL_LEVELS: SkillLevel[] = ['F', 'C+', 'C', 'B']
export const SENIORITIES: Seniority[] = ['intern', 'junior', 'mid', 'senior', 'lead']
export const REMOTE_MODES: RemoteMode[] = ['remote', 'hybrid', 'onsite']
export const LANGUAGE_LEVELS = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2', 'Nativo'] as const

/** Lo que una historia STAR puede citar como evidencia, con un nombre legible. */
export function evidenceOptions(profile: ProfileData): { ref: string; label: string; group: string }[] {
  const out: { ref: string; label: string; group: string }[] = []
  for (const exp of profile.experience ?? []) {
    for (const ach of exp.achievements ?? []) {
      if (exp.id && ach.id) out.push({ ref: `${exp.id}/${ach.id}`, label: ach.text, group: `${exp.role} · ${exp.company}` })
    }
  }
  for (const prj of profile.projects ?? []) if (prj.id) out.push({ ref: prj.id, label: prj.name, group: 'projects' })
  for (const edu of profile.education ?? []) if (edu.id) out.push({ ref: edu.id, label: `${edu.title}, ${edu.center}`, group: 'education' })
  for (const cert of profile.certifications ?? []) if (cert.id) out.push({ ref: cert.id, label: cert.name, group: 'certifications' })
  for (const sec of profile.extra_sections ?? []) {
    for (const item of sec.items ?? []) {
      if (sec.id && item.id) out.push({ ref: `${sec.id}/${item.id}`, label: item.text, group: sec.title.es ?? sec.title.en ?? sec.id })
    }
  }
  return out
}

/** Nombres de las skills del perfil (con nivel y básicas): lo único que admite un logro. */
export function skillNames(profile: ProfileData): string[] {
  return [...(profile.skills ?? []).map((s) => s.name), ...(profile.basic_skills ?? [])]
}
