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
  ['en negativo: di lo que es («Opcional: …»)', /\bNo hace falta\b|\bYou (do not|don't) need (one|it)\b/i],
  ['«sin riesgo»: di en concreto qué riesgo hay y cuál no', /riesgo cero|sin riesgo|no es cero|risk-free|zero risk|not zero/i],
  ['«(opcional)» va en la etiqueta, no en la ayuda', /\((opcional|optional)\)\./i],
  ['«Entra en…»: di «Iniciar sesión en…»', /\bEntra (en|con) /],
  ['etiqueta aclarada entre paréntesis', /^(Usuario|User) \(/],
]

/**
 * En español, formal e impersonal: sin «tú» ni sus formas. «Se pulsa», «pulsar» o «el perfil», no
 * «pulsa» ni «tu perfil». Lo citado entre «» no cuenta: son órdenes que se le dicen al agente o
 * textos de otras webs, como el menú de LinkedIn. Los límites de palabra valen para cualquier letra:
 * `\b` no ve las tildes y no encontraría «tú» ni «estás».
 */
const WORD_START = String.raw`(?<![\p{L}\p{N}_])`
const WORD_END = String.raw`(?![\p{L}\p{N}_])`
const words = (list: string) => `${WORD_START}(?:${list})${WORD_END}`
const SECOND_PERSON = new RegExp(
  [
    // Pronombres y posesivos.
    words('tú|tu|tus|te|ti|contigo|tuy[oa]s?'),
    // Presente (y subjuntivo) de tú, en verbos que no se confunden con otra persona.
    words(
      'tienes|puedes|quieres|necesitas|debes|sabes|estás|eres|vas|haces|has|hayas|tengas|puedas|quieras|eliges|usas|buscas|recibes|envías|escribes|pides|pulsas|cambias|añades|subes|marcas|guardas|decides|apruebas|descartas|revisas|confirmas|prefieres|conoces|aceptas|ves|escribas|elijas|pulses|añadas|subas|uses|busques',
    ),
    // Pasado de tú («cerraste», «tenías»), en los verbos que salen en la app.
    words(
      'enviaste|cerraste|descartaste|aprobaste|aceptaste|retiraste|pediste|subiste|hiciste|abriste|editaste|deshiciste|volviste|quitaste|marcaste|elegiste|tenías|estabas|sabías|querías',
    ),
    // Imperativos de tú con pronombre pegado.
    words(
      'ábrel[ao]s?|créal[ao]s?|pídele|pídeselo|dile|súbel[ao]s?|déjal[ao]s?|escríbel[ao]s?|inténtalo|actívala|añádel[ao]s?|descártala|apruébala|revísal[ao]s?|cópial[ao]|pégal[ao]|suéltalo|asegúrate|fíjate',
    ),
    // Imperativos de tú al empezar una frase («Pulsa…»), no la forma con «se» («se pulsa»). Solo los
    // que no pueden ser la tercera persona de un texto como «Añade al perfil…» (lo que hace el agente).
    String.raw`(?:^|[.:;!?¿¡]\s+)(?:Pulsa|Haz|Pon|Pega|Recarga|Inicia)` + WORD_END,
  ].join('|'),
  'iu',
)
/** En inglés, sin contracciones; el posesivo («the job's») sí vale. */
const CONTRACTION = /\b\w+(?:n['’]t|['’](?:ll|ve|re|d|m))\b|\b(?:it|that|there|what|here)['’]s\b/i

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

    if (language === 'es') {
      it('«es» es impersonal: sin «tú», sus formas ni sus imperativos', () => {
        const found: string[] = []
        for (const [ns, texts] of Object.entries(resources[language]!)) {
          for (const [key, text] of entries(texts)) {
            const own = text.replace(/«[^»]*»/g, '«»')
            const match = own.match(SECOND_PERSON)
            if (match) found.push(`${ns}:${key} («${match[0].trim()}»): ${text}`)
          }
        }
        expect(found).toEqual([])
      })
    }

    if (language === 'en') {
      it('«en» es formal: sin contracciones', () => {
        const found: string[] = []
        for (const [ns, texts] of Object.entries(resources[language]!)) {
          for (const [key, text] of entries(texts)) {
            const match = text.match(CONTRACTION)
            if (match) found.push(`${ns}:${key} («${match[0]}»): ${text}`)
          }
        }
        expect(found).toEqual([])
      })
    }

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
