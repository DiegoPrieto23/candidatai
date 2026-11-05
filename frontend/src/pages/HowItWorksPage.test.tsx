import { act, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { i18n } from '@/lib/i18n'
import { mockApi, renderApp, status } from '@/test/utils'

const open = () => {
  mockApi({ 'GET /status': status() })
  renderApp('/como-funciona')
}

const mainRegion = async () => {
  await screen.findByRole('heading', { level: 1 })
  return within(screen.getByRole('main'))
}

describe('Cómo funciona', () => {
  it('está al pie de la barra lateral', async () => {
    open()
    const bar = screen.getByRole('complementary', { name: 'Barra lateral' })
    const entry = within(bar).getByRole('link', { name: 'Cómo funciona' })
    expect(entry).toHaveAttribute('href', '/como-funciona')
    expect(await screen.findByRole('heading', { level: 1, name: 'Cómo funciona' })).toBeInTheDocument()
    expect(entry).toHaveAttribute('aria-current', 'page')
  })

  it('cuenta quién hace qué y promete que nada sale sin tu confirmación', async () => {
    open()
    const main = await mainRegion()
    const who = within(main.getByRole('region', { name: 'Quién hace qué' }))
    for (const name of ['Tú', 'Tu agente', 'La app']) {
      expect(who.getByRole('heading', { level: 3, name })).toBeInTheDocument()
    }
    expect(who.getByText(/Ninguna candidatura sale sin tu confirmación/)).toBeInTheDocument()
  })

  it('recorre los cinco pasos, en orden, con los nombres de verdad de botones y páginas', async () => {
    open()
    const main = await mainRegion()
    const journey = main.getByRole('region', { name: 'El recorrido, en cinco pasos' })
    const steps = within(journey).getAllByRole('listitem')
    expect(steps.map((step) => within(step).getByRole('heading', { level: 3 }).textContent)).toEqual([
      'Prepara tu búsqueda',
      'Reúne ofertas',
      'Decide cuáles merecen la pena',
      'Prepara y envía la candidatura',
      'Sigue tus procesos y aprende',
    ])
    expect(journey).toHaveTextContent('pulsa «Valorar las ofertas nuevas»')
    expect(journey).toHaveTextContent('pulsa «Generar CV»')
    expect(journey).not.toHaveTextContent('{{')
  })

  it('cada paso enlaza a su pantalla', async () => {
    open()
    const main = await mainRegion()
    const journey = within(main.getByRole('region', { name: 'El recorrido, en cinco pasos' }))
    const hrefs = journey.getAllByRole('link').map((link) => link.getAttribute('href'))
    expect(hrefs).toEqual([
      '/perfil',
      '/fuentes',
      '/agente',
      '/nueva',
      '/fuentes/correo',
      '/bandeja',
      '/',
      '/bandeja/revision',
      '/bandeja?stage=approved',
      '/perfil/plantillas',
      '/procesos',
      '/calendario',
      '/respuestas',
      '/embudo',
      '/perfil/skills',
    ])
  })

  it('las guías se abren aparte y en el idioma de la UI', async () => {
    open()
    const main = await mainRegion()
    const guide = main.getByRole('link', { name: /Empieza aquí/ })
    expect(guide).toHaveAttribute('href', expect.stringMatching(/\/docs\/EMPEZAR\.md$/))
    expect(guide).toHaveAttribute('target', '_blank')
    expect(main.getByRole('link', { name: /Guía de uso/ })).toHaveAttribute('href', expect.stringMatching(/\/docs\/GUIA\.md$/))
    expect(main.getByRole('link', { name: /Lista de funcionalidades/ })).toHaveAttribute(
      'href',
      expect.stringMatching(/\/docs\/FUNCIONALIDADES\.md$/),
    )
  })

  it('en inglés, textos y guías en inglés', async () => {
    await act(async () => {
      await i18n.changeLanguage('en')
    })
    open()
    expect(await screen.findByRole('heading', { level: 1, name: 'How it works' })).toBeInTheDocument()
    const main = within(screen.getByRole('main'))
    expect(main.getByRole('link', { name: /Start here/ })).toHaveAttribute('href', expect.stringMatching(/\/docs\/START_HERE\.md$/))
    expect(main.getByRole('link', { name: /User guide/ })).toHaveAttribute('href', expect.stringMatching(/\/docs\/GUIDE\.md$/))
    expect(main.getByRole('link', { name: /Feature list/ })).toHaveAttribute('href', expect.stringMatching(/\/docs\/FEATURES\.md$/))
  })
})
