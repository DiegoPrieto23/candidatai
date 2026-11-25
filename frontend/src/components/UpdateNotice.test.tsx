import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it } from 'vitest'
import { mockApi, renderApp, status } from '@/test/utils'

const COMMAND = 'powershell -ExecutionPolicy Bypass -NoExit -Command "…"'

function update(overrides: Record<string, unknown> = {}) {
  return {
    current: '1.0.1',
    latest: '1.1.0',
    available: true,
    release_url: 'https://github.com/DiegoPrieto23/candidatai/releases/tag/v1.1.0',
    install: 'installer',
    can_apply: true,
    command: COMMAND,
    ...overrides,
  }
}

afterEach(() => localStorage.clear())

describe('Aviso de versión nueva', () => {
  it('con el instalador de Windows, actualiza tras confirmarlo y espera a que la app vuelva', async () => {
    const calls = mockApi({ 'GET /status': status(), 'GET /updates': update(), 'POST /updates/apply': { version: '1.1.0' } })
    renderApp('/')
    const band = await screen.findByRole('region', { name: 'Versión nueva' })
    expect(within(band).getByText('Hay una versión nueva de CandidatAI: la 1.1.0')).toBeInTheDocument()
    expect(within(band).getByRole('link', { name: /Ver novedades/ })).toHaveAttribute('href', update().release_url)
    // Con el botón no hace falta la orden.
    expect(within(band).queryByText(COMMAND)).not.toBeInTheDocument()

    await userEvent.click(within(band).getByRole('button', { name: 'Actualizar ahora' }))
    const dialog = await screen.findByRole('dialog', { name: '¿Actualizar a la 1.1.0?' })
    expect(within(dialog).getByText(/hay que cerrarlo/)).toBeInTheDocument()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Actualizar' }))

    expect(await screen.findByRole('status', { name: 'Actualizando a la 1.1.0…' })).toBeInTheDocument()
    const posted = calls.find((c) => c.method === 'POST' && c.path === '/updates/apply')
    expect(posted?.body).toEqual({ version: '1.1.0' })
  })

  it('si no se puede desde la app, da la orden para copiarla', async () => {
    mockApi({ 'GET /status': status(), 'GET /updates': update({ can_apply: false }) })
    renderApp('/')
    const band = await screen.findByRole('region', { name: 'Versión nueva' })
    expect(within(band).getByLabelText('Orden para actualizar')).toHaveTextContent(COMMAND)
    expect(within(band).queryByRole('button', { name: 'Actualizar ahora' })).not.toBeInTheDocument()
  })

  it('en el repositorio, lleva a la guía', async () => {
    mockApi({ 'GET /status': status(), 'GET /updates': update({ install: 'repository', can_apply: false, command: null }) })
    renderApp('/')
    const band = await screen.findByRole('region', { name: 'Versión nueva' })
    expect(within(band).getByRole('link', { name: 'Actualizar' })).toHaveAttribute(
      'href',
      expect.stringContaining('docs/GUIA.md#13-actualizar'),
    )
  })

  it('«Ahora no» la pospone hasta la siguiente versión', async () => {
    mockApi({ 'GET /status': status(), 'GET /updates': update() })
    const { unmount } = renderApp('/')
    const band = await screen.findByRole('region', { name: 'Versión nueva' })
    await userEvent.click(within(band).getByRole('button', { name: 'Ahora no' }))
    expect(screen.queryByRole('region', { name: 'Versión nueva' })).not.toBeInTheDocument()
    unmount()

    const calls = mockApi({ 'GET /status': status(), 'GET /updates': update() })
    renderApp('/')
    await waitFor(() => expect(calls.some((c) => c.path === '/updates')).toBe(true))
    expect(screen.queryByRole('region', { name: 'Versión nueva' })).not.toBeInTheDocument()

    mockApi({ 'GET /status': status(), 'GET /updates': update({ latest: '1.2.0' }) })
    renderApp('/')
    expect(await screen.findByText('Hay una versión nueva de CandidatAI: la 1.2.0')).toBeInTheDocument()
  })

  it('no sale sin versión nueva ni en la demo (donde ni se pregunta)', async () => {
    const calls = mockApi({ 'GET /status': status(), 'GET /updates': update({ available: false }) })
    const { unmount } = renderApp('/')
    await waitFor(() => expect(calls.some((c) => c.path === '/updates')).toBe(true))
    expect(screen.queryByRole('region', { name: 'Versión nueva' })).not.toBeInTheDocument()
    unmount()

    const demo = mockApi({ 'GET /status': { ...status(), demo_mode: true }, 'GET /updates': update() })
    renderApp('/')
    await waitFor(() => expect(demo.some((c) => c.path === '/status')).toBe(true))
    expect(demo.some((c) => c.path === '/updates')).toBe(false)
    expect(screen.queryByRole('region', { name: 'Versión nueva' })).not.toBeInTheDocument()
  })
})
