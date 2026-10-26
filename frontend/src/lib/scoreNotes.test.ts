import { afterEach, describe, expect, it } from 'vitest'
import { i18n } from '@/lib/i18n'
import { scoreNote } from '@/lib/scoreNotes'

describe('notas del score (fase 23.5b)', () => {
  afterEach(async () => {
    await i18n.changeLanguage('es')
  })

  it('en español también pasan por los textos: así no enseñan la variable de entorno', () => {
    expect(scoreNote('Similitud semántica desactivada (CAI_EMBEDDINGS=off).')).toBe(
      'La comparación por significado está desactivada: el score solo cuenta las skills por su nombre.',
    )
    expect(scoreNote('Otra nota cualquiera.')).toBe('Otra nota cualquiera.')
  })

  it('en inglés se traducen las conocidas y las demás se quedan como llegan', async () => {
    await i18n.changeLanguage('en')
    expect(scoreNote('Similitud semántica desactivada (CAI_EMBEDDINGS=off).')).toBe(
      'Meaning-based comparison is turned off: the score only matches skills by name.',
    )
    expect(scoreNote('No se pudo calcular la similitud semántica (OSError: sin red).')).toBe(
      "Couldn't run the meaning-based comparison (OSError: sin red): the score only matches skills by name.",
    )
    expect(scoreNote('La oferta no lista skills deseables: la cobertura deseable no cuenta.')).toBe(
      "The job doesn't say which skills are nice-to-have, so that part doesn't count in the score.",
    )
    expect(scoreNote('No se pudo calcular la similitud semántica (línea 1\nlínea 2).')).toBe(
      "Couldn't run the meaning-based comparison (línea 1\nlínea 2): the score only matches skills by name.",
    )
    expect(scoreNote('Otra nota cualquiera.')).toBe('Otra nota cualquiera.')
  })
})
