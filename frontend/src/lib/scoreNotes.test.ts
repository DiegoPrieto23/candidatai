import { afterEach, describe, expect, it } from 'vitest'
import { i18n } from '@/lib/i18n'
import { scoreNote } from '@/lib/scoreNotes'

describe('notas del score (fase 23.5b)', () => {
  afterEach(async () => {
    await i18n.changeLanguage('es')
  })

  it('en español también pasan por los textos: así no enseñan la variable de entorno', () => {
    expect(scoreNote('Similitud semántica desactivada (CAI_EMBEDDINGS=off).')).toBe(
      'La app solo reconoce las skills del perfil si se llaman igual que en la oferta: no ve sinónimos ni frases parecidas, como «ETL» y «pipelines de datos».',
    )
    expect(scoreNote('Otra nota cualquiera.')).toBe('Otra nota cualquiera.')
  })

  it('en inglés se traducen las conocidas y las demás se quedan como llegan', async () => {
    await i18n.changeLanguage('en')
    expect(scoreNote('Similitud semántica desactivada (CAI_EMBEDDINGS=off).')).toBe(
      'The app only recognises your skills when they are named as in the job: it misses synonyms and similar phrases, like “ETL” and “data pipelines”.',
    )
    expect(scoreNote('No se pudo calcular la similitud semántica (OSError: sin red).')).toBe(
      "Could not compare synonyms (OSError: sin red): the app only recognises your skills when they are named as in the job.",
    )
    expect(scoreNote('La oferta no lista skills deseables: la cobertura deseable no cuenta.')).toBe(
      "The job does not say which skills are nice-to-have, so that part does not count in the fit.",
    )
    expect(scoreNote('No se pudo calcular la similitud semántica (línea 1\nlínea 2).')).toBe(
      "Could not compare synonyms (línea 1\nlínea 2): the app only recognises your skills when they are named as in the job.",
    )
    expect(scoreNote('Otra nota cualquiera.')).toBe('Otra nota cualquiera.')
  })
})
