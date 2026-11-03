import { describe, expect, it } from 'vitest'
import { biggestStop, layoutFlow, NODE_WIDTH, stopLink, type FlowStop } from './funnelFlow'

const COUNTS = { applied: 7, replied: 5, interview: 3, offer: 2, accepted: 0 }
const STOPS: FlowStop[] = [
  { step: 'applied', outcome: 'open', count: 2 },
  { step: 'replied', outcome: 'open', count: 1 },
  { step: 'replied', outcome: 'rejected', count: 1 },
  { step: 'interview', outcome: 'open', count: 1 },
  { step: 'offer', outcome: 'open', count: 1 },
  { step: 'offer', outcome: 'withdrawn', count: 1 },
]

describe('layoutFlow', () => {
  it('un paso por columna, de borde a borde, con el alto de lo que lleva', () => {
    const { nodes } = layoutFlow(COUNTS, STOPS, 1000)
    expect(nodes.map((n) => n.step)).toEqual(['applied', 'replied', 'interview', 'offer', 'accepted'])
    expect(nodes[0].x).toBe(0)
    expect(nodes[4].x + NODE_WIDTH).toBe(1000)
    expect(nodes[1].height / nodes[0].height).toBeCloseTo(5 / 7)
    expect(nodes[4].height).toBe(0)
  })

  it('una rama por cada grupo que se quedó, y ninguna franja hacia un paso vacío', () => {
    const { ribbons, ends } = layoutFlow(COUNTS, STOPS, 1000)
    expect(ends).toHaveLength(STOPS.length)
    expect(ribbons.filter((r) => r.outcome === null).map((r) => r.step)).toEqual(['applied', 'replied', 'interview'])
  })

  it('los textos de dos ramas del mismo paso no se pisan, por pequeñas que sean', () => {
    const big = { applied: 500, replied: 10, interview: 0, offer: 0, accepted: 0 }
    const { ends } = layoutFlow(
      big,
      [
        { step: 'replied', outcome: 'open', count: 1 },
        { step: 'replied', outcome: 'rejected', count: 1 },
      ],
      1000,
    )
    expect(ends[1].y - ends[0].y).toBeGreaterThanOrEqual(16)
  })

  it('lo muy pequeño se sigue viendo', () => {
    const { nodes } = layoutFlow({ applied: 1000, replied: 1, interview: 0, offer: 0, accepted: 0 }, [], 1000)
    expect(nodes[1].height).toBeGreaterThanOrEqual(3)
  })

  it('el alto total deja sitio a la última rama', () => {
    const { height, ends } = layoutFlow(COUNTS, STOPS, 1000)
    for (const end of ends) expect(height).toBeGreaterThanOrEqual(end.y + end.height)
  })

  it('sin nada enviado no dibuja nada, ni divide por cero', () => {
    const { ribbons, ends, nodes } = layoutFlow({ applied: 0, replied: 0, interview: 0, offer: 0, accepted: 0 }, [], 1000)
    expect(ribbons).toEqual([])
    expect(ends).toEqual([])
    expect(nodes.every((n) => n.height === 0)).toBe(true)
  })
})

describe('stopLink', () => {
  it('lleva a donde están esas candidaturas', () => {
    expect(stopLink('applied', 'open')).toBe('/bandeja?stage=applied')
    expect(stopLink('interview', 'open')).toBe('/procesos')
    expect(stopLink('replied', 'rejected')).toBe('/bandeja?stage=closed')
  })
})

describe('biggestStop', () => {
  it('el grupo más grande, o nada', () => {
    expect(biggestStop(STOPS)).toEqual(STOPS[0])
    expect(biggestStop([])).toBeNull()
  })
})
