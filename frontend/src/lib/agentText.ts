/**
 * Textos de la elección de agente (fase 24.4). El servidor explica en español por qué no se puede
 * usar un agente o qué conviene saber; en otro idioma se enseña el texto de su código estable.
 */
import type { AgentResolution } from '@/api/client'
import { i18n, SOURCE_LANGUAGE } from '@/lib/i18n'

const spanish = () => i18n.language === SOURCE_LANGUAGE

export function reasonText(res: Pick<AgentResolution, 'reason'>): string {
  return i18n.t(`agents:reason.${res.reason}`)
}

export function blockedText(res: Pick<AgentResolution, 'blocked' | 'blocked_code'>): string | null {
  if (!res.blocked) return null
  return spanish() ? res.blocked : i18n.t(`agents:blocked.${res.blocked_code ?? 'no_agent'}`)
}

export function warningText(res: Pick<AgentResolution, 'warning'>): string | null {
  if (!res.warning) return null
  return spanish() ? res.warning : i18n.t('agents:warning')
}

/** El modelo o el preset elegido, para enseñarlo (`null`: el del agente). */
export function modelText(res: Pick<AgentResolution, 'model' | 'preset'>): string | null {
  return res.preset ? `${i18n.t('agents:preset')} ${res.preset}` : (res.model ?? null)
}

/** Motivos por los que no hay agente que abrir: el botón copia la orden en vez de deshabilitarse. */
export const COPY_PROMPT_CODES: ReadonlySet<string> = new Set(['no_agent', 'not_launchable', 'not_installed'])
