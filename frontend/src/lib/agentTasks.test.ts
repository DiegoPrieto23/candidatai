import { describe, expect, it } from 'vitest'
import type { AgentRunEvent } from '@/api/queries'
import { pairTools } from '@/lib/agentTasks'

let seq = 0
function event(kind: AgentRunEvent['kind'], tool: string | null, more: Partial<AgentRunEvent> = {}): AgentRunEvent {
  return { seq: ++seq, at: '2026-11-03T10:00:00Z', kind, tool, text: null, ok: null, sub: false, ...more }
}

describe('pairTools: cada herramienta con su resultado', () => {
  it('empareja en orden dos llamadas iguales', () => {
    const items = pairTools([
      event('tool_start', 'get_profile'),
      event('tool_start', 'get_profile'),
      event('tool_result', 'get_profile', { ok: true }),
      event('tool_result', 'get_profile', { ok: false }),
    ])
    expect(items.map((i) => (i.kind === 'tool' ? i.result?.ok : null))).toEqual([true, false])
  })

  it('no mezcla lo del subagente con lo del agente principal', () => {
    const items = pairTools([
      event('tool_start', 'get_profile', { sub: true }),
      event('tool_start', 'get_profile'),
      event('tool_result', 'get_profile', { ok: true }),
    ])
    expect(items.map((i) => (i.kind === 'tool' ? [i.start.sub, i.result?.ok ?? null] : null))).toEqual([
      [true, null],
      [false, true],
    ])
  })

  it('un resultado sin inicio se ve igual (p. ej. una denegación)', () => {
    const items = pairTools([event('text', null, { text: 'hola' }), event('tool_result', 'file_change', { ok: false, text: 'denied' })])
    expect(items).toHaveLength(2)
    const tool = items[1]
    expect(tool.kind === 'tool' && tool.start.tool === 'file_change' && tool.result?.text === 'denied').toBe(true)
  })
})
