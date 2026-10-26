import { describe, expect, it } from 'vitest'
import { LANGUAGES, resources } from '@/locales'

/**
 * La UI es para cualquiera, no solo para quien programa: nada de nombres de skills, comandos, rutas,
 * ficheros, variables de entorno ni palabras de desarrollador. Se dice qué botón pulsar o qué pedirle
 * al agente; lo técnico que de verdad haga falta va en «Detalles técnicos» o en la guía.
 */
// Los de una sola palabra («expand») también son palabras normales: solo cuentan los compuestos.
const SKILLS = Object.keys(import.meta.glob('../../../.agents/skills/*/SKILL.md'))
  .map((path) => path.split('/').at(-2)!)
  .filter((name) => name.includes('-'))

const FORBIDDEN: [string, RegExp][] = [
  ['nombre de un skill', new RegExp(`(?<![\\w-])(${SKILLS.join('|')})(?![\\w-])`)],
  ['comando', /(^|[\s`«“"(])(cai|uv|pnpm|npm|git|ollama) [a-z-]/],
  ['fichero de configuración', /\.(env|ya?ml)\b/],
  ['variable de entorno', /\b[A-Z][A-Z0-9]*_[A-Z0-9_]+\b/],
  ['nombre interno', /\b[a-z]+_[a-z0-9_]+\b/],
  ['fichero', /\.(ics|csv|json|html)\b/],
  // «.docx» sí: es el tipo de fichero que se sube. «docx» suelto es el motor de una plantilla.
  ['motor de plantilla', /(?<!\.)\bdocx\b/i],
  ['ruta de datos', /(^|[^\w/.-])data\//],
  ['documento del repositorio', /(^|[^\w/.-])docs\/|\b[A-Z][A-Z_]+\.md\b/],
  ['palabra de desarrollador', /\b(worker|API|endpoint|slug|backend|frontend|prefiltro|prefilter|renderiz\w*|render\w*|JSON|MCP|CLI|HTML)\b/i],
]

/**
 * Excepciones justificadas, por «zona:clave». Cada una dice por qué ese texto puede nombrar algo
 * técnico; lo demás se reescribe.
 */
const ALLOWED: Record<string, string> = {
  // Se ven solo dentro de «Detalles técnicos»: es donde va lo técnico.
  'mailboxes:row.fromEnvHint': 'detalles técnicos del buzón configurado al instalar',
  'mailboxes:row.secretRef': 'detalles técnicos: dónde está la contraseña',
  // Solo en Docker, que ya es de quien sabe usarlo: la app no puede guardar la contraseña por sí sola.
  'mailboxes:dialog.envLine': 'instrucción para Docker',
  // El fichero de contactos se deja a mano en esa carpeta: no hay otra forma de decir dónde.
  'network:import.hint': 'carpeta donde dejar la exportación de LinkedIn',
  // Modelos locales: solo los ve quien tiene Ollama, y lo que hay que hacer es en Ollama, no en la app.
  'agents:local.envContext': 'ajuste de Ollama',
  'agents:local.noEnvContext': 'ajuste de Ollama',
  'agents:local.contextLow': 'ajuste de Ollama',
  'agents:local.noModels': 'orden de Ollama para descargar un modelo',
}

function entries(texts: unknown, prefix = ''): [string, string][] {
  if (typeof texts === 'string') return [[prefix, texts]]
  if (typeof texts !== 'object' || texts === null) return []
  return Object.entries(texts).flatMap(([key, value]) => entries(value, prefix ? `${prefix}.${key}` : key))
}

describe('textos sin jerga técnica', () => {
  it('los skills se leen de verdad', () => {
    expect(SKILLS).toContain('generate-cv')
  })

  it('cada excepción es de un texto que existe en los dos idiomas', () => {
    for (const language of LANGUAGES) {
      const ids = new Set(
        Object.entries(resources[language]!).flatMap(([ns, texts]) =>
          entries(texts).map(([key]) => `${ns}:${key.replace(/_(zero|one|two|few|many|other)$/, '')}`),
        ),
      )
      expect(Object.keys(ALLOWED).filter((id) => !ids.has(id))).toEqual([])
    }
  })

  for (const language of LANGUAGES) {
    it(`«${language}» no enseña nombres de skills, comandos, rutas ni palabras de desarrollador`, () => {
      const found: string[] = []
      for (const [ns, texts] of Object.entries(resources[language]!)) {
        for (const [key, text] of entries(texts)) {
          const id = `${ns}:${key.replace(/_(zero|one|two|few|many|other)$/, '')}`
          if (id in ALLOWED) continue
          for (const [what, pattern] of FORBIDDEN) {
            if (pattern.test(text)) found.push(`${id} (${what}): ${text}`)
          }
        }
      }
      expect(found).toEqual([])
    })
  }
})
