/**
 * Textos de la UI por idioma (fase 23.6). Cada carpeta (`es/`, `en/`…) es un idioma y cada fichero
 * JSON, un espacio de nombres. Para añadir un idioma basta con una carpeta nueva con los mismos
 * ficheros y las mismas claves (un test lo comprueba); su nombre sale de `common.json`
 * (`language.name`).
 *
 * Solo se descarga el idioma en uso: los textos de cada uno van en su propio chunk
 * (`vite.config.ts`) y se cargan con `loadTexts`. `common.json` va siempre, porque el menú de
 * idioma enseña el nombre de todos.
 */
type Texts = Record<string, unknown>

const PATH = /^\.\/([^/]+)\/([^/]+)\.json$/

const commons = import.meta.glob<Texts>('./*/common.json', { eager: true, import: 'default' })
const loaders = import.meta.glob<Texts>(['./*/*.json', '!./*/common.json'], { import: 'default' })

function parse(path: string): [language: string, namespace: string] {
  const [, language = '', namespace = ''] = PATH.exec(path) ?? []
  return [language, namespace]
}

/** El idioma de referencia: el original de la app y el que se usa si falta algo. */
export const SOURCE_LANGUAGE = 'es'

const common: Record<string, Texts> = {}
for (const [path, texts] of Object.entries(commons)) common[parse(path)[0]] = texts

export const LANGUAGES: readonly string[] = Object.keys(common).sort((a, b) =>
  a === SOURCE_LANGUAGE ? -1 : b === SOURCE_LANGUAGE ? 1 : a.localeCompare(b),
)

export const NAMESPACES: readonly string[] = [
  'common',
  ...Object.keys(loaders)
    .map(parse)
    .filter(([language]) => language === SOURCE_LANGUAGE)
    .map(([, namespace]) => namespace),
]

/** Todos los textos de un idioma, por espacio de nombres. */
export async function loadTexts(language: string): Promise<Record<string, Texts>> {
  const entries = await Promise.all(
    Object.entries(loaders)
      .filter(([path]) => parse(path)[0] === language)
      .map(async ([path, load]) => [parse(path)[1], await load()] as const),
  )
  return { common: common[language] ?? {}, ...Object.fromEntries(entries) }
}

/** Los textos de todos los idiomas (los tests comprueban con ellos que coinciden). */
export async function loadAllTexts(): Promise<Record<string, Record<string, Texts>>> {
  const all = await Promise.all(LANGUAGES.map(async (language) => [language, await loadTexts(language)] as const))
  return Object.fromEntries(all)
}

/** El nombre de cada idioma en su propio idioma («Español», «English»). */
export function languageName(language: string): string {
  const texts = common[language] as { language?: { name?: string } } | undefined
  return texts?.language?.name ?? language
}
