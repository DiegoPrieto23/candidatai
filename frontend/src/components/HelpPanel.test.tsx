import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { isTyping } from '@/lib/keyboard'
import { mockApi, renderApp, status } from '@/test/utils'

const emptyPage = { items: [], total: 0, limit: 50, offset: 0 }

async function openApp() {
  mockApi({ 'GET /status': status(), 'GET /jobs': emptyPage })
  renderApp('/bandeja')
  await screen.findByText('La bandeja está vacía')
  return screen.getByRole('button', { name: 'Ayuda' })
}

describe('Ayuda del portal', () => {
  it('el botón abre las preguntas frecuentes, por grupos, con el foco en el buscador', async () => {
    const button = await openApp()
    expect(button).toHaveAttribute('aria-expanded', 'false')
    await userEvent.click(button)

    const panel = screen.getByRole('dialog', { name: 'Ayuda' })
    expect(within(panel).getByRole('searchbox', { name: 'Buscar en la ayuda' })).toHaveFocus()
    expect(within(panel).getByRole('heading', { name: 'Primeros pasos' })).toBeInTheDocument()
    expect(within(panel).getByRole('button', { name: '¿Cómo se crea el perfil?' })).toHaveAttribute('aria-expanded', 'false')
  })

  it('busca, despliega la respuesta y lleva a la pantalla donde se hace', async () => {
    await userEvent.click(await openApp())
    const panel = screen.getByRole('dialog', { name: 'Ayuda' })
    await userEvent.type(within(panel).getByRole('searchbox'), 'diseño de mi cv')

    const faq = within(panel).getByRole('region', { name: 'Preguntas frecuentes' })
    const question = within(faq).getAllByRole('button')[0]!
    expect(question).toHaveTextContent('¿Se puede usar el diseño de un CV propio?')
    await userEvent.click(question)
    expect(within(faq).getByText(/Convertir en plantilla/)).toBeInTheDocument()

    await userEvent.click(within(faq).getByRole('link', { name: 'Ir a «Plantillas de CV»' }))
    expect(screen.queryByRole('dialog', { name: 'Ayuda' })).not.toBeInTheDocument()
  })

  it('también busca en la guía de uso', async () => {
    await userEvent.click(await openApp())
    const panel = screen.getByRole('dialog', { name: 'Ayuda' })
    await userEvent.type(within(panel).getByRole('searchbox'), 'actualizar')
    const guide = await within(panel).findByRole('region', { name: 'En la guía de uso' })
    expect(within(guide).getAllByRole('button')[0]).toHaveTextContent(/^Actualizar/)
  })

  it('dice cuándo no encuentra nada', async () => {
    await userEvent.click(await openApp())
    const panel = screen.getByRole('dialog', { name: 'Ayuda' })
    await userEvent.type(within(panel).getByRole('searchbox'), 'xyzzyq')
    expect(await within(panel).findByText(/Sin resultados para «xyzzyq»/)).toBeInTheDocument()
  })

  it('«?» la abre y Esc la cierra, con el foco de vuelta en el botón', async () => {
    const button = await openApp()
    await userEvent.keyboard('?')
    expect(screen.getByRole('dialog', { name: 'Ayuda' })).toBeInTheDocument()
    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('dialog', { name: 'Ayuda' })).not.toBeInTheDocument()
    expect(button).toHaveFocus()
  })

  it('Esc también la cierra con el foco en la página, sin moverlo', async () => {
    await userEvent.click(await openApp())
    const main = screen.getByRole('main')
    main.focus()
    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('dialog', { name: 'Ayuda' })).not.toBeInTheDocument()
    expect(main).toHaveFocus()
  })

  it('con un menú abierto, «?» no la abre', async () => {
    await openApp()
    const menu = document.createElement('div')
    menu.setAttribute('role', 'menu')
    document.body.append(menu)
    await userEvent.keyboard('?')
    expect(screen.queryByRole('dialog', { name: 'Ayuda' })).not.toBeInTheDocument()
    menu.remove()
  })

  it('dentro del panel, las letras no son atajos de la página', async () => {
    await userEvent.click(await openApp())
    const question = screen.getByRole('button', { name: '¿Cómo se crea el perfil?' })
    expect(isTyping(question)).toBe(true)
    expect(isTyping(screen.getByRole('main'))).toBe(false)
  })

  it('«?» escrito en un campo no la abre', async () => {
    await openApp()
    const field = document.createElement('input')
    document.body.append(field)
    field.focus()
    await userEvent.keyboard('?')
    expect(screen.queryByRole('dialog', { name: 'Ayuda' })).not.toBeInTheDocument()
    field.remove()
  })
})
