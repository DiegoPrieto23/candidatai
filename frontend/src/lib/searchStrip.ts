/**
 * Lo que enseña la franja de «Buscar ofertas» a partir de tu perfil y de tus portales, sin React:
 * los lugares de tu búsqueda, cómo se añade o se quita uno y el resumen de la última búsqueda.
 */
import type { SourceView } from '@/api/client'
import type { Preferences } from '@/components/profile/types'
import { fold } from '@/lib/text'

type Locations = NonNullable<Preferences['locations']>

export interface Place {
  place: string
  /** `allowed`: solo en híbrido o remoto. */
  onlyRemote: boolean
}

const same = (a: string, b: string) => fold(a) === fold(b)

/** Los lugares donde buscas: los de cualquier modalidad y los de solo híbrido o remoto, sin repetir. */
export function placesOf(locations: Locations | undefined): Place[] {
  const rows = [
    ...(locations?.preferred ?? []).map((place) => ({ place, onlyRemote: false })),
    ...(locations?.allowed ?? []).map((place) => ({ place, onlyRemote: true })),
  ]
  return rows.filter((row, i) => rows.findIndex((r) => same(r.place, row.place)) === i)
}

function without(locations: Locations, place: string): Locations {
  const drop = (list: string[] | undefined) => list?.filter((p) => !same(p, place))
  return { ...locations, preferred: drop(locations.preferred), allowed: drop(locations.allowed), excluded: drop(locations.excluded) }
}

/** Quita un lugar de tu búsqueda (de cualquier modalidad o de solo remoto). Lo descartado no se toca. */
export function removePlace(locations: Locations | undefined, place: string): Locations {
  const drop = (list: string[] | undefined) => list?.filter((p) => !same(p, place))
  return { ...locations, preferred: drop(locations?.preferred), allowed: drop(locations?.allowed) }
}

/** Añade un lugar en cualquier modalidad. Si lo tenías descartado, deja de estarlo. */
export function addPlace(locations: Locations | undefined, place: string): Locations {
  const rest = without(locations ?? {}, place)
  return { ...rest, preferred: [...(rest.preferred ?? []), place] }
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
