import { describe, expect, it } from 'vitest'
import { UNUSED_ICON_WEIGHTS } from './iconWeights'

// Todo el código de la UI, sin los tests, como texto.
const sources = import.meta.glob<string>(['/src/**/*.{ts,tsx}', '!/src/**/*.test.{ts,tsx}', '!/src/test/**'], {
  query: '?raw',
  import: 'default',
  eager: true,
})

describe('pesos de los iconos', () => {
  it('ningún componente pide un peso que el build quita', () => {
    const used = new Set<string>()
    for (const code of Object.values(sources)) {
      for (const [, expression] of code.matchAll(/\bweight=(\{[^}]*\}|"[^"]*"|'[^']*')/g)) {
        // Un peso que no se puede leer (una variable) podría ser cualquiera: que se escriba literal.
        const literals = [...expression!.matchAll(/['"]([a-z]+)['"]/g)].map(([, w]) => w!)
        expect(literals.length, `peso sin literal: weight=${expression}`).toBeGreaterThan(0)
        literals.forEach((w) => used.add(w))
      }
    }
    expect(used.size).toBeGreaterThan(0)
    for (const weight of UNUSED_ICON_WEIGHTS) expect(used).not.toContain(weight)
  })
})
