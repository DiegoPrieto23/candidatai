import { useCallback, useEffect, useSyncExternalStore } from 'react'

export type ThemeChoice = 'system' | 'light' | 'dark'

const STORAGE_KEY = 'cai-theme'
// Clave de antes de la fase 23 (Job Hunter): se lee si aún no hay la nueva.
const LEGACY_STORAGE_KEY = 'jh-theme'
const listeners = new Set<() => void>()

function readChoice(): ThemeChoice {
  try {
    const value = localStorage.getItem(STORAGE_KEY) ?? localStorage.getItem(LEGACY_STORAGE_KEY)
    return value === 'light' || value === 'dark' ? value : 'system'
  } catch {
    return 'system'
  }
}

function systemPrefersDark(): boolean {
  return typeof matchMedia === 'function' && matchMedia('(prefers-color-scheme: dark)').matches
}

/** Pone o quita la clase `dark` en <html>. Se llama antes del primer render para evitar el destello. */
export function applyTheme(choice: ThemeChoice = readChoice()): void {
  const dark = choice === 'dark' || (choice === 'system' && systemPrefersDark())
  document.documentElement.classList.toggle('dark', dark)
}

function setChoice(choice: ThemeChoice): void {
  try {
    if (choice === 'system') localStorage.removeItem(STORAGE_KEY)
    else localStorage.setItem(STORAGE_KEY, choice)
  } catch {
    // Sin almacenamiento (modo privado): el tema dura lo que la pestaña.
  }
  applyTheme(choice)
  listeners.forEach((notify) => notify())
}

function subscribe(notify: () => void): () => void {
  listeners.add(notify)
  return () => listeners.delete(notify)
}

export function useTheme() {
  const choice = useSyncExternalStore(subscribe, readChoice, () => 'system' as const)

  // Si sigue al sistema, reacciona cuando el sistema cambia.
  useEffect(() => {
    if (choice !== 'system' || typeof matchMedia !== 'function') return
    const query = matchMedia('(prefers-color-scheme: dark)')
    const onChange = () => applyTheme('system')
    query.addEventListener('change', onChange)
    return () => query.removeEventListener('change', onChange)
  }, [choice])

  const cycle = useCallback(() => {
    const next: Record<ThemeChoice, ThemeChoice> = { system: 'light', light: 'dark', dark: 'system' }
    setChoice(next[readChoice()])
  }, [])

  return { choice, cycle }
}
