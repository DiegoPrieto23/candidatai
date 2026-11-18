/** Resúmenes de una línea de las preferencias de CV y de carta («Mi perfil › Documentos»). */

interface CvPrefs {
  default_template?: string | null
  max_pages?: number | null
  photo_policy: { default: boolean; by_country?: Record<string, unknown> }
  instructions?: string | null
  avoid?: string[]
}

interface LetterPrefs {
  max_words?: number | null
  tone?: string | null
  sign_off?: { es?: string | null; en?: string | null; [key: string]: unknown } | null
  instructions?: string | null
  avoid?: string[]
  default_format?: 'text' | 'pdf' | null
}

/** Las claves de `profile:summary.*` que usa, con sus valores. */
export type Say = (key: string, values?: Record<string, unknown>) => string

const SEP = ' · '
const filled = (text: string | null | undefined) => Boolean(text?.trim())

export function cvSummary(
  cv: CvPrefs,
  say: Say,
  names: { template: (id: string) => string; region: (code: string) => string },
): string {
  const parts = [cv.default_template ? say('cv.template', { name: names.template(cv.default_template) }) : say('cv.templateAuto')]
  if (cv.max_pages) parts.push(say('cv.pages', { count: cv.max_pages }))
  // Los países que llevan lo contrario de lo general.
  const except = Object.entries(cv.photo_policy.by_country ?? {})
    .filter(([, on]) => typeof on === 'boolean' && on !== cv.photo_policy.default)
    .map(([code]) => names.region(code))
  const photo = say(cv.photo_policy.default ? 'cv.photoOn' : 'cv.photoOff')
  parts.push(except.length ? say('cv.photoExcept', { photo, places: except.join(', ') }) : photo)
  if (filled(cv.instructions)) parts.push(say('cv.instructions'))
  if (cv.avoid?.length) parts.push(say('cv.avoid', { count: cv.avoid.length }))
  return parts.join(SEP)
}

export function letterSummary(letter: LetterPrefs | null | undefined, say: Say, language: string): string {
  const l = letter ?? {}
  const parts: string[] = []
  if (filled(l.tone)) parts.push(say('letter.tone', { tone: l.tone!.trim() }))
  if (l.max_words) parts.push(say('letter.words', { count: l.max_words }))
  if (l.default_format) parts.push(say(l.default_format === 'pdf' ? 'letter.pdf' : 'letter.text'))
  const signOff = l.sign_off?.[language === 'en' ? 'en' : 'es'] ?? l.sign_off?.es ?? l.sign_off?.en
  if (typeof signOff === 'string' && filled(signOff)) parts.push(say('letter.signOff', { text: signOff.trim() }))
  if (filled(l.instructions)) parts.push(say('letter.instructions'))
  if (l.avoid?.length) parts.push(say('letter.avoid', { count: l.avoid.length }))
  return parts.length ? parts.join(SEP) : say('letter.none')
}
