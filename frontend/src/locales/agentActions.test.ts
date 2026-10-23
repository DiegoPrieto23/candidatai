import { describe, expect, it } from 'vitest'
import openapi from '@/api/openapi.json'
import { LANGUAGES, resources } from '@/locales'

/**
 * Las acciones que lanzan un skill, tal como las publica la API (`ACTIONS` del backend). El nombre
 * de cada una está en `agent.json` (`actions.*`) y su ayuda, en `agentActions.json`.
 */
const ACTIONS: string[] = openapi.components.schemas.LaunchBody.properties.action.enum

describe('ayudas de los botones de skills (fase 27.1)', () => {
  it('la API publica las acciones', () => {
    expect(ACTIONS.length).toBeGreaterThan(0)
  })

  for (const language of LANGUAGES) {
    it(`cada acción tiene nombre y ayuda en «${language}», y no sobra ninguna`, () => {
      const hints = (resources[language]!.agentActions ?? {}) as Record<string, string>
      const names = (resources[language]!.agent as { actions?: Record<string, string> }).actions ?? {}
      const missing = ACTIONS.filter((a) => !hints[a]?.trim() || !names[a]?.trim())
      const extra = Object.keys(hints).filter((a) => !ACTIONS.includes(a))
      expect({ missing, extra }).toEqual({ missing: [], extra: [] })
    })
  }
})
