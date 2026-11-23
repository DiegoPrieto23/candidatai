import { describe, expect, it } from 'vitest'
import { LANGUAGES, loadAllTexts } from '@/locales'
import {
  buildIndex,
  GUIDE_SCREENS,
  HELP_GROUPS,
  HELP_SCREENS,
  HELP_TOPICS,
  loadGuide,
  parseGuide,
  snippet,
} from '@/lib/helpSearch'
import app from '@/App.tsx?raw'

const resources = await loadAllTexts()

interface HelpTexts {
  screens: Record<string, string>
  groups: Record<string, string>
  faq: Record<string, { q: string; a: string; keywords: string }>
}
const help = (language: string) => resources[language]!.help as unknown as HelpTexts

function faqIndex(language: string) {
  const { faq } = help(language)
  return buildIndex(HELP_TOPICS.map(({ id }) => ({ id, title: faq[id]!.q, body: faq[id]!.a, keywords: faq[id]!.keywords })))
}

describe('buscador de la ayuda', () => {
  const index = buildIndex([
    { id: 'a', title: '¿Cómo se crea el perfil?', body: 'Sube tu CV.', keywords: 'currículum' },
    { id: 'b', title: 'Plantillas de CV', body: 'El diseño de tu perfil en un CV.' },
    { id: 'c', title: 'Calendario', body: 'Entrevistas y plazos.' },
  ])
  const ids = (query: string) => index.search(query).map((item) => item.id)

  it('no distingue mayúsculas ni tildes', () => {
    expect(ids('COMO CREO')).toEqual(['a'])
    expect(ids('curriculum')).toEqual(['a'])
  })

  it('el título pesa más que el cuerpo', () => {
    expect(ids('perfil')).toEqual(['a', 'b'])
  })

  it('admite plurales y palabras a medio escribir', () => {
    expect(ids('plantilla')).toEqual(['b'])
    expect(ids('entrevista')).toEqual(['c'])
    expect(ids('calend')).toEqual(['c'])
    expect(ids('calendarios')).toEqual(['c'])
  })

  it('sin nada que buscar o sin coincidencias, no devuelve nada', () => {
    expect(ids('  ')).toEqual([])
    expect(ids('zzzz')).toEqual([])
  })
})

describe('preguntas frecuentes', () => {
  it('cada tema tiene su texto y cada texto, su tema', () => {
    const ids = HELP_TOPICS.map((topic) => topic.id)
    expect(new Set(ids).size).toBe(ids.length)
    for (const language of LANGUAGES) {
      expect(Object.keys(help(language).faq).sort()).toEqual([...ids].sort())
      expect(Object.keys(help(language).screens).sort()).toEqual(Object.keys(HELP_SCREENS).sort())
      expect(Object.keys(help(language).groups).sort()).toEqual([...HELP_GROUPS].sort())
    }
  })

  it('cada tema está en un grupo y lleva a una pantalla que existe', () => {
    for (const topic of HELP_TOPICS) {
      expect(HELP_GROUPS).toContain(topic.group)
      if (topic.screen !== null) expect(Object.keys(HELP_SCREENS)).toContain(topic.screen)
    }
  })

  it('cada pantalla es una ruta de la app', () => {
    for (const route of Object.values(HELP_SCREENS)) {
      for (const segment of route.split('/').filter(Boolean)) {
        expect(app, route).toContain(`path="${segment}"`)
      }
    }
  })

  it('encuentra lo que se pregunta, en los dos idiomas', () => {
    const first = (language: string, query: string) => faqIndex(language).search(query)[0]?.id
    expect(first('es', 'foto')).toBe('photo')
    expect(first('es', 'cuánto cuesta')).toBe('cost')
    expect(first('es', 'usar mi propia plantilla')).toBe('ownTemplate')
    expect(first('es', 'copia de seguridad')).toBe('backup')
    expect(first('en', 'cover letter')).toBe('letter')
    expect(first('en', 'is it safe to connect email')).toBe('mailSafe')
  })
})

describe('guía de uso', () => {
  it('se parte en apartados sin marcado, sin el índice ni lo que va antes', () => {
    const sections = parseGuide(
      [
        '# Guía',
        'Texto de entrada.',
        '## Índice',
        '- [Uno](#uno)',
        '## 1. Uno',
        'Un **párrafo** con `código` y un [enlace](otro.md). <!-- media:provisional -->',
        'que sigue.',
        '',
        '- primera',
        '  continúa',
        '```powershell',
        '## no es un título',
        '```',
        '### Sub',
        '| Qué | Cómo |',
        '|---|---|',
        '| A | B |',
      ].join('\n'),
    )
    expect(sections.map((s) => [s.number, s.title])).toEqual([
      ['1', 'Uno'],
      ['1', 'Uno · Sub'],
    ])
    expect(sections[0]!.blocks).toEqual([
      { kind: 'text', text: 'Un párrafo con código y un enlace. que sigue.' },
      { kind: 'item', text: 'primera continúa' },
      { kind: 'code', text: '## no es un título' },
    ])
    expect(sections[1]!.blocks).toEqual([
      { kind: 'item', text: 'Qué · Cómo' },
      { kind: 'item', text: 'A · B' },
    ])
    expect(snippet(sections[0]!, 'primera')).toBe('primera continúa')
  })

  it('las dos guías tienen los mismos apartados y cada uno sabe a qué pantalla lleva', async () => {
    const [es, en] = await Promise.all([loadGuide('es'), loadGuide('en')])
    expect(es.length).toBeGreaterThan(15)
    const numbers = (sections: typeof es) => [...new Set(sections.map((s) => s.number))]
    expect(numbers(en)).toEqual(numbers(es))
    expect(numbers(es).sort()).toEqual(Object.keys(GUIDE_SCREENS).sort())
    for (const screen of Object.values(GUIDE_SCREENS)) {
      if (screen !== null) expect(Object.keys(HELP_SCREENS)).toContain(screen)
    }
  })

  it('un idioma sin guía propia usa la inglesa', async () => {
    expect((await loadGuide('fr'))[0]?.title).toBe((await loadGuide('en'))[0]?.title)
  })
})
