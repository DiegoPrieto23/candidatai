/**
 * Idiomas y países por su nombre (fase 41.4): el usuario escribe «francés» o «Reino Unido» y se
 * guarda el código de siempre (`fr`, `GB`). Los nombres los da el navegador (`Intl.DisplayNames`)
 * en el idioma de la UI; la lista de códigos se saca de ahí también, sin diccionario propio.
 */

export type CodeKind = 'language' | 'region'

/** Sin tildes, mayúsculas ni signos: «Reino  Unido» y «reino unido» son lo mismo. */
const fold = (text: string) =>
  text
    .normalize('NFD')
    .replace(/\p{M}/gu, '')
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, ' ')
    .trim()

const LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
// Lo que el navegador conoce como región pero no es un país: Unión Europea, ONU, «desconocida»…
// También territorios que solo existen como región técnica (isla Ascensión, Canarias, Ceuta y Melilla…).
const NOT_COUNTRIES = new Set(['EU', 'EZ', 'UN', 'QO', 'XA', 'XB', 'ZZ', 'AC', 'CP', 'DG', 'EA', 'IC', 'TA'])

/** La forma de guardarlo: idiomas en minúsculas (`fr`) y países en mayúsculas (`GB`). */
const shape = (kind: CodeKind, code: string) => (kind === 'language' ? code.toLowerCase() : code.toUpperCase())

/** El código vigente de uno antiguo o en otro formato («UK» → `GB`, «iw» → `he`), o `null`. */
function canonical(kind: CodeKind, code: string): string | null {
  if (!/^[a-z]{2}$/i.test(code)) return null
  try {
    const tag = Intl.getCanonicalLocales(kind === 'language' ? code.toLowerCase() : `und-${code.toUpperCase()}`)[0]
    const part = kind === 'language' ? tag.split('-')[0] : tag.split('-')[1]
    return part && part.length === 2 ? shape(kind, part) : null
  } catch {
    return null
  }
}

function displayNames(kind: CodeKind, locale: string): Intl.DisplayNames | null {
  try {
    return new Intl.DisplayNames([locale], { type: kind, fallback: 'none' })
  } catch {
    return null
  }
}

const codeCache = new Map<CodeKind, string[]>()

/** Los códigos de dos letras que el navegador sabe nombrar, sin los antiguos ni los que no son países. */
export function knownCodes(kind: CodeKind): string[] {
  const cached = codeCache.get(kind)
  if (cached) return cached
  const names = displayNames(kind, 'en')
  const codes: string[] = []
  if (names) {
    for (const a of LETTERS) {
      for (const b of LETTERS) {
        const code = shape(kind, a + b)
        if (kind === 'region' && NOT_COUNTRIES.has(code)) continue
        if (canonical(kind, code) !== code) continue
        try {
          if (names.of(code)) codes.push(code)
        } catch {
          // Un código que el navegador no acepta: no cuenta.
        }
      }
    }
  }
  codeCache.set(kind, codes)
  return codes
}

/** El nombre de un código en el idioma de la UI («fr» → «francés»), o el código si no lo conoce. */
export function codeName(kind: CodeKind, code: string, locale: string): string {
  try {
    return displayNames(kind, locale)?.of(shape(kind, code)) ?? code
  } catch {
    return code
  }
}

/** Nombre y código de cada uno, por orden alfabético del nombre. */
export function codeOptions(kind: CodeKind, locale: string): { code: string; name: string }[] {
  const collator = new Intl.Collator(locale)
  return knownCodes(kind)
    .map((code) => ({ code, name: codeName(kind, code, locale) }))
    .sort((a, b) => collator.compare(a.name, b.name))
}

/**
 * El código de lo que escribe el usuario: un nombre en el idioma de la UI o en inglés, sin
 * importar tildes ni mayúsculas («Francés», «french»), o un código («fr», «UK»). `null` si no es
 * ninguno.
 */
export function findCode(kind: CodeKind, text: string, locale: string): string | null {
  const value = text.trim()
  if (!value) return null
  const wanted = fold(value)
  for (const lang of [locale, 'en', 'es']) {
    const match = knownCodes(kind).find((code) => fold(codeName(kind, code, lang)) === wanted)
    if (match) return match
  }
  const code = canonical(kind, value)
  return code && knownCodes(kind).includes(code) ? code : null
}
