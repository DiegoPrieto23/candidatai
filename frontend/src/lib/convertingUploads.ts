import { useSyncExternalStore } from 'react'

/**
 * Lo que tu agente está convirtiendo en plantilla («Mi CV»).
 *
 * Corre en tu terminal y la app no sabe cuándo acaba: tras abrirlo, la tarjeta dice que lo está
 * convirtiendo hasta que aparece la plantilla o pasan `CONVERT_MINUTES`. En `sessionStorage` para
 * que un F5 no lo pierda; si el navegador no deja, vive en memoria.
 */
const CONVERT_MINUTES = 30
const CONVERTING_KEY = 'cai.convertingUploads'

function loadConverting(): Record<string, number> {
  try {
    const parsed: unknown = JSON.parse(sessionStorage.getItem(CONVERTING_KEY) ?? '{}')
    if (!parsed || typeof parsed !== 'object') return {}
    return Object.fromEntries(
      Object.entries(parsed as Record<string, unknown>).filter(
        (entry): entry is [string, number] => typeof entry[1] === 'number' && entry[1] > Date.now(),
      ),
    )
  } catch {
    return {}
  }
}

let converting = loadConverting()
const convertingListeners = new Set<() => void>()

export function setConverting(name: string, on: boolean) {
  const next = { ...converting }
  if (on) next[name] = Date.now() + CONVERT_MINUTES * 60_000
  else delete next[name]
  converting = next
  try {
    sessionStorage.setItem(CONVERTING_KEY, JSON.stringify(next))
  } catch {
    // Sin almacenamiento: sigue en memoria.
  }
  for (const listener of convertingListeners) listener()
}

export function useConverting(): Record<string, number> {
  return useSyncExternalStore(
    (listener) => {
      convertingListeners.add(listener)
      return () => convertingListeners.delete(listener)
    },
    () => converting,
  )
}

/** Solo para los tests. */
export function resetConverting() {
  converting = {}
  try {
    sessionStorage.removeItem(CONVERTING_KEY)
  } catch {
    // nada
  }
  for (const listener of convertingListeners) listener()
}

/** «Mi CV», o «Mi CV 2», «Mi CV 3»… si ya hay una plantilla o una subida con ese nombre. */
export function nextTemplateName(base: string, taken: Iterable<string>): string {
  const used = new Set([...taken].map((name) => name.trim().toLocaleLowerCase()))
  if (!used.has(base.toLocaleLowerCase())) return base
  for (let n = 2; ; n += 1) {
    const candidate = `${base} ${n}`
    if (!used.has(candidate.toLocaleLowerCase())) return candidate
  }
}
