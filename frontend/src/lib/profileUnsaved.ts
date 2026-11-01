import { useSyncExternalStore } from 'react'

/**
 * Cuántos bloques del perfil tienen cambios sin guardar: los sabe el editor y los enseña la barra
 * lateral, que está fuera de él.
 */
let unsaved = 0
const listeners = new Set<() => void>()

export function setProfileUnsaved(count: number): void {
  if (count === unsaved) return
  unsaved = count
  listeners.forEach((notify) => notify())
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function useProfileUnsaved(): number {
  return useSyncExternalStore(subscribe, () => unsaved)
}
