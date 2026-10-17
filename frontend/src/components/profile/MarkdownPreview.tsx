/**
 * Vista previa mínima del Markdown del contexto (fase 25.7b): títulos, párrafos, listas, negrita y
 * cursiva, sin los comentarios-guía. Sin dependencias ni HTML: todo se pinta como texto de React,
 * así que nada del fichero puede colarse como marcado.
 */
import { Fragment, type ReactNode } from 'react'

const COMMENT = /<!--[\s\S]*?(?:-->|$)/g

function inline(text: string): ReactNode[] {
  const parts: ReactNode[] = []
  const pattern = /(\*\*[^*]+\*\*|\*[^*]+\*|_[^_]+_)/g
  let last = 0
  let index = 0
  for (const match of text.matchAll(pattern)) {
    const at = match.index ?? 0
    if (at > last) parts.push(text.slice(last, at))
    const token = match[0]
    parts.push(token.startsWith('**') ? <strong key={index++}>{token.slice(2, -2)}</strong> : <em key={index++}>{token.slice(1, -1)}</em>)
    last = at + token.length
  }
  if (last < text.length) parts.push(text.slice(last))
  return parts
}

export function MarkdownPreview({ text, empty }: { text: string; empty: string }) {
  const lines = text.replace(/\r\n/g, '\n').replace(COMMENT, '').split('\n')
  const blocks: ReactNode[] = []
  let list: string[] = []
  let paragraph: string[] = []
  const flush = () => {
    if (paragraph.length) blocks.push(<p key={blocks.length}>{inline(paragraph.join(' '))}</p>)
    if (list.length)
      blocks.push(
        <ul key={blocks.length} className="list-disc pl-5">
          {list.map((item, i) => (
            <li key={i}>{inline(item)}</li>
          ))}
        </ul>,
      )
    paragraph = []
    list = []
  }
  for (const raw of lines) {
    const line = raw.trim()
    const heading = /^(#{1,6})\s+(.*)$/.exec(line)
    const item = /^[-*+]\s+(.*)$/.exec(line) ?? /^\d+[.)]\s+(.*)$/.exec(line)
    if (!line) {
      flush()
    } else if (heading) {
      flush()
      const level = heading[1].length
      blocks.push(
        <p key={blocks.length} className={level === 1 ? 'text-base font-semibold' : 'font-medium'}>
          {inline(heading[2])}
        </p>,
      )
    } else if (item) {
      if (paragraph.length) flush()
      list.push(item[1])
    } else {
      if (list.length) flush()
      paragraph.push(line)
    }
  }
  flush()
  const hasText = blocks.length > 0
  return (
    <div className="grid gap-2 text-sm leading-relaxed" data-testid="markdown-preview">
      {hasText ? blocks.map((b, i) => <Fragment key={i}>{b}</Fragment>) : <p className="text-muted-foreground">{empty}</p>}
    </div>
  )
}
