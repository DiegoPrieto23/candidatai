/**
 * Lo que enseña la franja de «Buscar ofertas» a partir de tu perfil y de tus portales, sin React:
 * los lugares de tu búsqueda, cómo se añade o se quita uno y el resumen de la última búsqueda.
 */
import type { SourceView } from '@/api/client'
import type { Preferences } from '@/components/profile/types'
import { fold } from '@/lib/text'

type Locations = NonNullable<Preferences['locations']>

/** Qué aceptas en un lugar: cualquier modalidad, solo híbrido o remoto, o nada (descartado). */
export const PLACE_MODES = ['preferred', 'allowed', 'excluded'] as const
export type PlaceMode = (typeof PLACE_MODES)[number]

export interface Place {
  place: string
  mode: PlaceMode
}

const same = (a: string, b: string) => fold(a) === fold(b)

/** Tus lugares, uno por sitio y en el orden de las tres listas (si uno está en dos, manda la primera). */
export function placesOf(locations: Locations | undefined): Place[] {
  const rows = PLACE_MODES.flatMap((mode) => (locations?.[mode] ?? []).map((place) => ({ place, mode })))
  return rows.filter((row, i) => rows.findIndex((r) => same(r.place, row.place)) === i)
}

/** Quita un lugar de tus tres listas. Las demás claves de `locations` van tal cual. */
export function removePlace(locations: Locations | undefined, place: string): Locations {
  const drop = (list: string[] | undefined) => list?.filter((p) => !same(p, place))
  return { ...locations, preferred: drop(locations?.preferred), allowed: drop(locations?.allowed), excluded: drop(locations?.excluded) }
}

/** Pone un lugar en una modalidad (por defecto, cualquiera), al final de esa lista. */
export function addPlace(locations: Locations | undefined, place: string, mode: PlaceMode = 'preferred'): Locations {
  const rest = removePlace(locations ?? {}, place)
  return { ...rest, [mode]: [...(rest[mode] ?? []), place] }
}

/** Cambia qué aceptas en un lugar sin moverlo de sitio en la franja si ya estaba en esa lista. */
export function setPlaceMode(locations: Locations | undefined, place: string, mode: PlaceMode): Locations {
  const current = placesOf(locations).find((p) => same(p.place, place))
  if (current?.mode === mode) return locations ?? {}
  return addPlace(locations, current?.place ?? place, mode)
}

export const hasItem = (list: readonly string[], item: string) => list.some((x) => same(x, item))

/** Lo que dio la última búsqueda: los recorridos de tus portales en las 12 horas antes del último. */
export interface LastSearch {
  at: string
  found: number
  created: number
  portals: number
}

const WINDOW_MS = 12 * 60 * 60 * 1000

export function lastSearchOf(sources: readonly SourceView[]): LastSearch | null {
  const runs = sources.flatMap((s) => (s.last_run ? [{ at: s.last_run_at ?? s.last_run.started_at, run: s.last_run }] : []))
  if (runs.length === 0) return null
  const latest = Math.max(...runs.map((r) => Date.parse(r.at)))
  const recent = runs.filter((r) => latest - Date.parse(r.at) <= WINDOW_MS)
  return {
    at: new Date(latest).toISOString(),
    found: recent.reduce((sum, r) => sum + r.run.found, 0),
    created: recent.reduce((sum, r) => sum + r.run.created, 0),
    portals: recent.length,
  }
}
