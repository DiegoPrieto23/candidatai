/**
 * La última vista de la Bandeja (etapa, filtros, orden, página y búsqueda, que viven en la URL),
 * para que «Bandeja de ofertas» en la ficha de una oferta vuelva a ella, como el «atrás» del
 * navegador. Se guarda también en `sessionStorage` para que sobreviva a recargar la ficha; si no se
 * puede, basta con la memoria.
 */
const STORAGE_KEY = 'cai-inbox-return'
const DEFAULT = '/bandeja'

let last: string | null = null

function isInbox(url: string): boolean {
  return url === DEFAULT || url.startsWith(`${DEFAULT}?`)
}

export function rememberInboxView(pathname: string, search: string): void {
  const url = `${pathname}${search}`
  if (!isInbox(url)) return
  last = url
  try {
    sessionStorage.setItem(STORAGE_KEY, url)
  } catch {
    // sin almacenamiento: se queda en memoria
  }
}

export function inboxReturnUrl(): string {
  if (last) return last
  try {
    const stored = sessionStorage.getItem(STORAGE_KEY)
    if (stored && isInbox(stored)) return stored
  } catch {
    // sin almacenamiento: la Bandeja sin filtros
  }
  return DEFAULT
}

/** Solo para los tests. */
export function forgetInboxView(): void {
  last = null
  try {
    sessionStorage.removeItem(STORAGE_KEY)
  } catch {
    // nada que borrar
  }
}
