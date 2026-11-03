import { describe, expect, it } from 'vitest'
import { FUNNEL_MIN_WIDTH, funnelStrips } from './funnelStrips'

describe('funnelStrips', () => {
  it('respeta la proporción real cuando supera el mínimo', () => {
    const strips = funnelStrips([
      { step: 'found', count: 100 },
      { step: 'approved', count: 40 },
    ])
    expect(strips.map((s) => s.width)).toEqual([100, 40])
  })

  it('da ancho mínimo a las etapas a 0 o casi, y las de 0 se distinguen', () => {
    const strips = funnelStrips([
      { step: 'found', count: 1000 },
      { step: 'approved', count: 1 },
      { step: 'applied', count: 0 },
    ])
    expect(strips.map((s) => s.width)).toEqual([1000, 1000 * FUNNEL_MIN_WIDTH, 1000 * FUNNEL_MIN_WIDTH])
    expect(strips[1].fill).toBe('var(--chart-1)')
    expect(strips[2].fill).toBe('var(--muted-foreground)')
  })

  it('con una sola oferta o sin ninguna no hay anchos a 0 ni NaN', () => {
    for (const first of [1, 0]) {
      const widths = funnelStrips([
        { step: 'found', count: first },
        { step: 'approved', count: 0 },
      ]).map((s) => s.width)
      for (const width of widths) {
        expect(width).toBeGreaterThan(0)
        expect(Number.isFinite(width)).toBe(true)
      }
    }
  })
})
