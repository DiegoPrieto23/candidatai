/**
 * Textos de la UI por idioma (fase 23.6). Cada carpeta (`es/`, `en/`…) es un idioma y cada fichero
 * JSON, un espacio de nombres. Para añadir un idioma basta con una carpeta nueva con los mismos
 * ficheros y las mismas claves (un test lo comprueba); su nombre sale de `common.json`
 * (`language.name`).
 */
import type { Resource } from 'i18next'

type Texts = Record<string, unknown>

const files = import.meta.glob<Texts>('./*/*.json', { eager: true, import: 'default' })

export const resources: Resource = {}
for (const [path, texts] of Object.entries(files)) {
  const [, language, file] = /^\.\/([^/]+)\/([^/]+)\.json$/.exec(path) ?? []
  if (!language || !file) continue
  resources[language] ??= {}
  resources[language][file] = texts
}

/** El idioma de referencia: el original de la app y el que se usa si falta algo. */
export const SOURCE_LANGUAGE = 'es'

export const LANGUAGES: readonly string[] = Object.keys(resources).sort((a, b) =>
  a === SOURCE_LANGUAGE ? -1 : b === SOURCE_LANGUAGE ? 1 : a.localeCompare(b),
)

export const NAMESPACES: readonly string[] = Object.keys(resources[SOURCE_LANGUAGE] ?? {})

/** El nombre de cada idioma en su propio idioma («Español», «English»). */
export function languageName(language: string): string {
  const common = resources[language]?.common as { language?: { name?: string } } | undefined
  return common?.language?.name ?? language
}
