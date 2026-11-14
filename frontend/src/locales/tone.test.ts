import { describe, expect, it } from 'vitest'
import { LANGUAGES, loadAllTexts } from '@/locales'

const resources = await loadAllTexts()

/**
 * Tono de la UI (reglas en CONTRIBUTING.md, «UI texts»): profesional, en positivo y sin
 * sobreexplicar. El test de jerga vigila lo técnico; este, las expresiones que se cambiaron por
 * coloquiales o en negativo y la longitud de las intros de página.
 */
const FORBIDDEN: [string, RegExp][] = [
  ['coloquial: di «con tu confirmación» o «tú decides qué se guarda»', /\b(tu|el|your|the) OK\b/],
  ['en negativo: di lo que es («Opcional: …»)', /\bNo hace falta\b|\bYou don't need (one|it)\b/i],
  ['«sin riesgo»: di en concreto qué riesgo hay y cuál no', /riesgo cero|sin riesgo|no es cero|risk-free|zero risk|not zero/i],
  ['«(opcional)» va en la etiqueta, no en la ayuda', /\((opcional|optional)\)\./i],
  ['«Entra en…»: di «Inicia sesión en…»', /\bEntra (en|con) /],
  ['etiqueta aclarada entre paréntesis', /^(Usuario|User) \(/],
]

/**
 * Las intros de página (bajo el título de cada página) caben en una o dos líneas: lo demás va a una
 * ayuda o a la configuración. Las de una sección dentro de la página (p. ej. los pasos de Outlook)
 * pueden ser más largas: solo las ve quien abre esa sección.
 */
const MAX_INTRO = 150
const INTRO_PATHS = ['intro', 'page.intro', 'email.intro', 'settings.intro']

function entries(texts: unknown, prefix = ''): [string, string][] {
  if (typeof texts === 'string') return [[prefix, texts]]
  if (typeof texts !== 'object' || texts === null) return []
  return Object.entries(texts).flatMap(([key, value]) => entries(value, prefix ? `${prefix}.${key}` : key))
}

describe('tono de los textos', () => {
  for (const language of LANGUAGES) {
    it(`«${language}» no usa expresiones coloquiales, en negativo ni aclaraciones de más`, () => {
      const found: string[] = []
      for (const [ns, texts] of Object.entries(resources[language]!)) {
        for (const [key, text] of entries(texts)) {
          for (const [what, pattern] of FORBIDDEN) {
            if (pattern.test(text)) found.push(`${ns}:${key} (${what}): ${text}`)
          }
        }
      }
      expect(found).toEqual([])
    })

    it(`«${language}»: las intros de página tienen como mucho ${MAX_INTRO} caracteres`, () => {
      const long: string[] = []
      let seen = 0
      for (const [ns, texts] of Object.entries(resources[language]!)) {
        for (const [key, text] of entries(texts)) {
          if (!INTRO_PATHS.includes(key)) continue
          seen++
          if (text.length > MAX_INTRO) long.push(`${ns}:${key} (${text.length}): ${text}`)
        }
      }
      expect(seen).toBeGreaterThan(10)
      expect(long).toEqual([])
    })
  }
})
