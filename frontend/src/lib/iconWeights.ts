/**
 * Pesos de los iconos de Phosphor que la app no usa nunca. Cada icono trae sus seis pesos; el build
 * (`vite.config.ts`) quita estos de sus definiciones y cada icono pesa un tercio menos. Un test
 * comprueba que ningún componente los pide: si hace falta uno, se quita de aquí.
 */
export const UNUSED_ICON_WEIGHTS = ['thin', 'light'] as const
