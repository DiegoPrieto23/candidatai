import { afterEach, describe, expect, it } from 'vitest'
import '@/api/client'
import { i18n, portalLang } from '@/lib/i18n'
import { mockApi } from '@/test/utils'

/** Fase 47.3: el idioma del portal llega a lo que lanza el agente. */
describe('Idioma del portal para el agente', () => {
  afterEach(async () => {
    await i18n.changeLanguage('es')
  })

  it('cada lanzamiento dice el idioma y, al cambiarlo, la app lo guarda', async () => {
    const calls = mockApi({ 'PUT /agent/language': { lang: 'en' } })
    expect(portalLang()).toBe('es')

    await i18n.changeLanguage('en')
    expect(portalLang()).toBe('en')
    await expect.poll(() => calls.find((c) => c.method === 'PUT' && c.path === '/agent/language')?.body).toEqual({ lang: 'en' })
  })
})
