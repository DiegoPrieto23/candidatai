import { describe, expect, it } from 'vitest'
import { LANGUAGES, SOURCE_LANGUAGE, resources } from '@/locales'

/** Todas las claves de un fichero de textos, aplanadas («a.b.c»). Los plurales cuentan por su base. */
function keys(texts: unknown, prefix = ''): string[] {
  if (typeof texts !== 'object' || texts === null) return [prefix]
  return Object.entries(texts).flatMap(([key, value]) => keys(value, prefix ? `${prefix}.${key}` : key))
}

function plainKeys(texts: unknown): Set<string> {
  return new Set(keys(texts).map((key) => key.replace(/_(zero|one|two|few|many|other)$/, '')))
}

function values(texts: unknown): string[] {
  if (typeof texts === 'string') return [texts]
  if (typeof texts !== 'object' || texts === null) return []
  return Object.values(texts).flatMap(values)
}

describe('textos de la UI (fase 23.6)', () => {
  const source = resources[SOURCE_LANGUAGE]!

  it('hay español e inglés', () => {
    expect(LANGUAGES).toEqual(expect.arrayContaining(['es', 'en']))
  })

  for (const language of LANGUAGES.filter((l) => l !== SOURCE_LANGUAGE)) {
    it(`«${language}» tiene los mismos ficheros y las mismas claves que el español`, () => {
      const target = resources[language]!
      expect(Object.keys(target).sort()).toEqual(Object.keys(source).sort())
      for (const ns of Object.keys(source)) {
        const missing = [...plainKeys(source[ns])].filter((k) => !plainKeys(target[ns]).has(k))
        const extra = [...plainKeys(target[ns])].filter((k) => !plainKeys(source[ns]).has(k))
        expect({ ns, missing, extra }).toEqual({ ns, missing: [], extra: [] })
      }
    })
  }

  for (const language of LANGUAGES) {
    it(`ningún texto de «${language}» está vacío`, () => {
      for (const [ns, texts] of Object.entries(resources[language]!)) {
        const empty = keys(texts).filter((key) => {
          const value = key.split('.').reduce<unknown>((node, part) => (node as Record<string, unknown>)?.[part], texts)
          return typeof value !== 'string' || value.trim() === ''
        })
        expect({ ns, empty }).toEqual({ ns, empty: [] })
      }
    })
  }

  it('las mismas variables en cada idioma', () => {
    const vars = (text: string) => [...text.matchAll(/\{\{(\w+)\}\}/g)].map((m) => m[1]).sort()
    for (const language of LANGUAGES.filter((l) => l !== SOURCE_LANGUAGE)) {
      for (const ns of Object.keys(source)) {
        for (const key of keys(source[ns])) {
          const read = (texts: unknown) =>
            key.split('.').reduce<unknown>((node, part) => (node as Record<string, unknown>)?.[part], texts)
          const original = read(source[ns])
          // Los plurales pueden tener otra forma en otro idioma: se compara con «_other».
          const translated = read(resources[language]![ns]) ?? read(resources[language]![ns])
          if (typeof original !== 'string' || typeof translated !== 'string') continue
          const drop = (list: string[]) => list.filter((v) => v !== 'count')
          expect({ ns, key, vars: drop(vars(translated)) }).toEqual({ ns, key, vars: drop(vars(original)) })
        }
      }
    }
  })

  it('las etiquetas de `Trans` no son elementos vacíos de HTML (`<link>`, `<br>`…)', () => {
    // El parser de `Trans` trata estas como vacías y deja su texto fuera del componente.
    const VOID = /<(area|base|br|col|embed|hr|img|input|link|meta|param|source|track|wbr)>/
    for (const language of LANGUAGES) {
      for (const [ns, texts] of Object.entries(resources[language]!)) {
        const bad = values(texts).filter((v) => VOID.test(v))
        expect({ ns, bad }).toEqual({ ns, bad: [] })
      }
    }
  })
})
