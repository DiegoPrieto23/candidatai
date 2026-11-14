/**
 * Buscador de la ayuda del portal: sobre las preguntas frecuentes (`locales/<idioma>/help.json`) y
 * los apartados de la guía de uso (`docs/GUIA.md`, `docs/GUIDE.md`). Todo en el navegador, sin red y
 * sin agente. No distingue mayúsculas ni tildes, y admite plurales y palabras a medio escribir.
 */
import topics from '@/lib/helpTopics.json'

export type ScreenKey = keyof typeof topics.screens
export type GroupKey = (typeof topics.groups)[number]

export interface HelpTopic {
  id: string
  group: string
  screen: string | null
}

export const HELP_SCREENS: Record<string, string> = topics.screens
export const HELP_GROUPS: readonly string[] = topics.groups
export const HELP_TOPICS: readonly HelpTopic[] = topics.topics
/** A qué pantalla lleva cada apartado numerado de la guía (`null`: a ninguna). */
export const GUIDE_SCREENS: Record<string, string | null> = topics.guide

/** Lo que se busca: un título (lo que más pesa), unas palabras clave y un cuerpo. */
export interface Searchable {
  title: string
  keywords?: string
  body: string
}

const WEIGHTS = { title: 5, keywords: 3, body: 1 } as const

export function normalize(text: string): string {
  return text
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
}

/** Sin la «s» del plural: «plantillas» encuentra «plantilla», y al revés. */
function stem(word: string): string {
  return word.length > 3 && word.endsWith('s') ? word.slice(0, -1) : word
}

function words(text: string): string[] {
  return normalize(text)
    .split(/[^a-z0-9]+/)
    .filter((word) => word.length > 1)
    .map(stem)
}

/** Vale el principio de una palabra («plant» → «plantilla») y una terminación distinta («portales» → «portal»). */
function matches(word: string, token: string): boolean {
  return word.startsWith(token) || (word.length >= 4 && token.startsWith(word) && token.length - word.length <= 2)
}

interface Indexed<T> {
  item: T
  fields: Record<keyof typeof WEIGHTS, string[]>
}

export interface SearchIndex<T> {
  search: (query: string) => T[]
}

export function buildIndex<T extends Searchable>(items: readonly T[]): SearchIndex<T> {
  const indexed: Indexed<T>[] = items.map((item) => ({
    item,
    fields: { title: words(item.title), keywords: words(item.keywords ?? ''), body: words(item.body) },
  }))
  return {
    search(query) {
      const tokens = [...new Set(words(query))]
      if (tokens.length === 0) return []
      // Una palabra larga dice más que una corta («perfil» frente a «mi»): pesa más.
      const weight = (token: string) => Math.min(token.length, 8)
      const total = tokens.reduce((sum, token) => sum + weight(token), 0)
      const found: { item: T; score: number }[] = []
      for (const { item, fields } of indexed) {
        let matched = 0
        let score = 0
        for (const token of tokens) {
          const best = (Object.keys(WEIGHTS) as (keyof typeof WEIGHTS)[]).find((field) =>
            fields[field].some((word) => matches(word, token)),
          )
          if (!best) continue
          matched += weight(token)
          score += weight(token) * WEIGHTS[best]
        }
        // Al menos la mitad de lo que se pregunta tiene que estar: lo demás es ruido.
        if (matched * 2 >= total) found.push({ item, score })
      }
      return found.sort((a, b) => b.score - a.score).map(({ item }) => item)
    },
  }
}

export interface GuideBlock {
  kind: 'text' | 'item' | 'code'
  text: string
}

export interface GuideSection extends Searchable {
  id: string
  /** El número del apartado principal («7» en «7. Configurar las fuentes de ofertas»). */
  number: string
  blocks: GuideBlock[]
}

/** El texto de una línea de Markdown sin su marcado: enlaces, negritas, código y etiquetas. */
function plain(line: string): string {
  return line
    .replace(/<!--.*?-->/g, '')
    .replace(/!\[[^\]]*\]\([^)]*\)/g, '')
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
    .replace(/<[^>]+>/g, '')
    .replace(/\*\*|`/g, '')
    .replace(/\s+/g, ' ')
    .trim()
}

function toBlocks(lines: string[]): GuideBlock[] {
  const blocks: GuideBlock[] = []
  let current: GuideBlock | null = null
  let code: string[] | null = null
  const close = () => {
    if (current && current.text) blocks.push(current)
    current = null
  }
  for (const raw of lines) {
    if (raw.trimStart().startsWith('```')) {
      if (code) {
        blocks.push({ kind: 'code', text: code.join('\n') })
        code = null
      } else {
        close()
        code = []
      }
      continue
    }
    if (code) {
      code.push(raw)
      continue
    }
    const line = raw.trim()
    if (!line) {
      close()
      continue
    }
    if (line.startsWith('|')) {
      close()
      if (/^\|[\s:|-]+\|$/.test(line)) continue // la raya bajo la cabecera de una tabla
      const cells = line.split(/(?<!\\)\|/).map(plain).filter(Boolean)
      if (cells.length) blocks.push({ kind: 'item', text: cells.join(' · ') })
      continue
    }
    const item = /^(?:[-*]|\d+\.)\s+(.*)$/.exec(line)
    if (item) {
      close()
      current = { kind: 'item', text: plain(item[1] ?? '') }
      continue
    }
    const text = plain(line.replace(/^>\s?/, ''))
    if (!text) continue
    if (current) current.text = `${current.text} ${text}`.trim()
    else current = { kind: 'text', text }
  }
  close()
  return blocks
}

/**
 * Los apartados numerados de la guía («## 7. …») y sus subapartados («### …»), cada uno con su
 * texto sin marcado. El índice y lo que va antes del primer apartado no cuentan.
 */
export function parseGuide(markdown: string): GuideSection[] {
  const sections: GuideSection[] = []
  let number = ''
  let parent = ''
  let title = ''
  let lines: string[] = []
  let inCode = false
  const flush = () => {
    const blocks = toBlocks(lines)
    if (number && blocks.length) {
      sections.push({
        id: `${number}-${sections.length}`,
        number,
        title,
        blocks,
        body: blocks.map((block) => block.text).join(' '),
      })
    }
    lines = []
  }
  for (const line of markdown.split(/\r?\n/)) {
    if (line.trimStart().startsWith('```')) inCode = !inCode
    const main = inCode ? null : /^## (?:(\d+)\.\s+)?(.+)$/.exec(line)
    const sub = inCode ? null : /^### (.+)$/.exec(line)
    if (main) {
      flush()
      number = main[1] ?? ''
      parent = plain(main[2] ?? '')
      title = parent
    } else if (sub) {
      flush()
      title = `${parent} · ${plain(sub[1] ?? '')}`
    } else {
      lines.push(line)
    }
  }
  flush()
  return sections
}

/** La guía de cada idioma. Las demás lenguas usan la inglesa. */
const GUIDE_FILES: Record<string, string> = { es: 'GUIA', en: 'GUIDE' }
const guides = import.meta.glob<string>('../../../docs/{GUIA,GUIDE}.md', { query: '?raw', import: 'default' })

/** Se descarga al abrir la ayuda, y solo la del idioma en uso. */
export async function loadGuide(language: string): Promise<GuideSection[]> {
  const file = GUIDE_FILES[language] ?? 'GUIDE'
  const load = guides[`../../../docs/${file}.md`]
  return load ? parseGuide(await load()) : []
}

/** El trozo del apartado donde sale lo que se busca, para enseñarlo bajo el título. */
export function snippet(section: GuideSection, query: string, max = 180): string {
  const tokens = words(query)
  const block =
    section.blocks.find((b) => b.kind !== 'code' && words(b.text).some((word) => tokens.some((t) => matches(word, t)))) ??
    section.blocks.find((b) => b.kind !== 'code') ??
    section.blocks[0]
  const text = block?.text ?? ''
  return text.length > max ? `${text.slice(0, max).trimEnd()}…` : text
}
