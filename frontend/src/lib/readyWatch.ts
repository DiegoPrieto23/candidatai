import { useSyncExternalStore } from 'react'
import type { AgentAction } from '@/api/queries'

/**
 * Lo que la UI vigila tras abrir tu agente para avisarte en cuanto lo deje: el CV de
 * `generate-cv` o la guía de `prepare-interview`. La app no sabe cuándo acaba el agente (corre en
 * tu terminal): vuelve a pedir el CV o la ficha cada pocos segundos hasta que aparece algo
 * guardado después de pulsar el botón, o hasta que pasa `WATCH_MINUTES`.
 *
 * Se guarda en `sessionStorage` para que un F5 no lo pierda; si el navegador no deja, vive solo en
 * memoria.
 */

export type WatchKind = 'cv' | 'guide'

export interface Watch {
  id: string
  kind: WatchKind
  jobId: number
  milestoneId: number | null
  /** Cuándo se pulsó el botón (ISO): vale lo guardado después. */
  since: string
  /** Hasta cuándo se vigila (ms desde epoch). */
  until: number
}

export const WATCHED_ACTIONS: Partial<Record<AgentAction, WatchKind>> = {
  'generate-cv': 'cv',
  'prepare-interview': 'guide',
}
export const WATCH_MINUTES = 30
export const POLL_MS = 5000
const STORAGE_KEY = 'cai.readyWatches'

function load(): Watch[] {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    const parsed: unknown = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? (parsed as Watch[]).filter((w) => w.until > Date.now()) : []
  } catch {
    return []
  }
}

let watches: Watch[] = load()
const listeners = new Set<() => void>()

function save(next: Watch[]) {
  watches = next
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(next))
  } catch {
    // Sin almacenamiento (ventana privada, bloqueado): sigue en memoria.
  }
  for (const listener of listeners) listener()
}

/** Empieza a vigilar lo que deje `action` en esa oferta (o en esa entrevista). Otra vez el mismo
 * botón sustituye la vigilancia anterior. */
export function watchFor(action: AgentAction, jobId: number | null | undefined, milestoneId?: number | null) {
  const kind = WATCHED_ACTIONS[action]
  if (!kind || !jobId) return
  const id = `${kind}:${jobId}:${milestoneId ?? ''}`
  const now = Date.now()
  const watch: Watch = {
    id,
    kind,
    jobId,
    milestoneId: milestoneId ?? null,
    since: new Date(now).toISOString(),
    until: now + WATCH_MINUTES * 60_000,
  }
  save([...watches.filter((w) => w.id !== id), watch])
}

export function stopWatching(id: string) {
  save(watches.filter((w) => w.id !== id))
}

export function useWatches(): Watch[] {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
    () => watches,
  )
}

/** Solo para los tests: empieza sin vigilancias. */
export function resetWatches() {
  save([])
}
