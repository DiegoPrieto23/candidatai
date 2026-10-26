import { afterEach, describe, expect, it } from 'vitest'
import { i18n } from '@/lib/i18n'
import { scoreNote } from '@/lib/scoreNotes'

describe('notas del score (fase 23.5b)', () => {
  afterEach(async () => {
    await i18n.changeLanguage('es')
  })

  it('en español también pasan por los textos: así no enseñan la variable de entorno', () => {
    expect(scoreNote('Similitud semántica desactivada (CAI_EMBEDDINGS=off).')).toBe('Similitud semántica desactivada.')
    expect(scoreNote('Otra nota cualquiera.')).toBe('Otra nota cualquiera.')
  })

  it('en inglés se traducen las conocidas y las demás se quedan como llegan', async () => {
    await i18n.changeLanguage('en')
    expect(scoreNote('Similitud semántica desactivada (CAI_EMBEDDINGS=off).')).toBe(
      'Semantic similarity turned off.',
    )
    expect(scoreNote('No se pudo calcular la similitud semántica (OSError: sin red).')).toBe(
      "Couldn't calculate the semantic similarity (OSError: sin red).",
    )
    expect(scoreNote('La oferta no lista skills deseables: la cobertura deseable no cuenta.')).toBe(
      "The job lists no nice-to-have skills: nice-to-have coverage doesn't count.",
    )
    expect(scoreNote('No se pudo calcular la similitud semántica (línea 1\nlínea 2).')).toBe(
      "Couldn't calculate the semantic similarity (línea 1\nlínea 2).",
    )
    expect(scoreNote('Otra nota cualquiera.')).toBe('Otra nota cualquiera.')
  })
})
