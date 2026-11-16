import { describe, expect, it } from 'vitest'
import type { SourceView } from '@/api/client'
import { addPlace, lastSearchOf, placesOf, removePlace } from './searchStrip'

describe('lugares de la franja', () => {
  it('junta los de cualquier modalidad y los de solo remoto, sin repetir', () => {
    expect(placesOf({ preferred: ['Vigo', 'madrid'], allowed: ['Madrid', 'Lugo'], excluded: ['Ourense'] })).toEqual([
      { place: 'Vigo', onlyRemote: false },
      { place: 'madrid', onlyRemote: false },
      { place: 'Lugo', onlyRemote: true },
    ])
    expect(placesOf(undefined)).toEqual([])
  })

  it('quitar lo saca de su lista y añadir lo pone en cualquier modalidad, aunque estuviera descartado', () => {
    expect(removePlace({ preferred: ['Vigo'], allowed: ['Lugo'] }, 'lugo')).toEqual({ preferred: ['Vigo'], allowed: [] })
    // Quitar una etiqueta no borra un descarte con el mismo nombre.
    expect(removePlace({ preferred: ['Vigo'], excluded: ['vigo'] }, 'Vigo')).toEqual({ preferred: [], allowed: undefined, excluded: ['vigo'] })
    expect(addPlace({ preferred: ['Vigo'], excluded: ['Málaga'], radius: 3 }, 'malaga')).toEqual({
      preferred: ['Vigo', 'malaga'],
      allowed: undefined,
      excluded: [],
      radius: 3,
    })
    expect(addPlace(undefined, 'Vigo')).toEqual({ preferred: ['Vigo'], allowed: undefined, excluded: undefined })
  })
})

describe('última búsqueda', () => {
  const source = (at: string | null, found = 0, created = 0) =>
    ({
      last_run_at: at,
      last_run: at ? { id: 1, actor: 'agent', started_at: at, finished_at: null, found, after_filters: found, created, errors: [] } : null,
    }) as SourceView

  it('suma los portales recorridos en las 12 horas antes del último', () => {
    expect(lastSearchOf([source(null)])).toBeNull()
    expect(
      lastSearchOf([source('2026-11-10T08:00:00Z', 30, 4), source('2026-11-10T09:30:00Z', 10, 1), source('2026-11-01T08:00:00Z', 99, 9), source(null)]),
    ).toEqual({ at: '2026-11-10T09:30:00.000Z', found: 40, created: 5, portals: 2 })
  })
})
