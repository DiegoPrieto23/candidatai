import { ApiError } from '@/api/client'
import { i18n, SOURCE_LANGUAGE } from '@/lib/i18n'

/**
 * El mensaje de un error para enseñarlo en la UI (fase 23.6). Los mensajes de la API vienen del
 * servidor en español; en otro idioma se antepone el nombre traducido de su `type` (código
 * estable) y el mensaje del servidor queda como detalle.
 */
export function errorMessage(error: unknown): string {
  if (!(error instanceof Error)) return i18n.t('errors.generic')
  if (!(error instanceof ApiError) || error.type === 'offline' || error.type === 'unknown') return error.message
  if ((i18n.resolvedLanguage ?? i18n.language) === SOURCE_LANGUAGE) return error.message
  const key = `errors.types.${error.type}`
  return i18n.exists(key) ? `${i18n.t(key as never)}: ${error.message}` : error.message
}
