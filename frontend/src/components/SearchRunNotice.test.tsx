import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { mockApi, renderApp, status } from '@/test/utils'

function run(overrides: Record<string, unknown> = {}) {
  return {
    id: 7,
    status: 'running',
    outcome: null,
    portals_total: 3,
    portals_done: 1,
    found: 12,
    created: 4,
    problems: 0,
    started_at: '2026-11-03T10:00:00Z',
    finished_at: null,
    ...overrides,
  }
}

function routes(current: unknown, extra: Record<string, unknown> = {}) {
  return { 'GET /status': status(), 'GET /agent/search-run': { run: current }, ...extra }
}

describe('Aviso de la búsqueda', () => {
  it('no sale sin búsqueda', async () => {
    const calls = mockApi(routes(null))
    renderApp('/como-funciona')
    await waitFor(() => expect(calls.some((c) => c.path === '/agent/search-run')).toBe(true))
    expect(screen.queryByText('Buscando ofertas…')).not.toBeInTheDocument()
  })

  it('dice que sigue buscando y cuánto lleva, en cualquier página', async () => {
    mockApi(routes(run()))
    renderApp('/como-funciona')
    expect(await screen.findByText('Buscando ofertas…')).toBeInTheDocument()
    expect(screen.getByText('1 de 3 portales · 4 ofertas nuevas')).toBeInTheDocument()
  })

  it('al terminar lleva a la Bandeja, y cuenta solo los problemas de verdad', async () => {
    mockApi(routes(run({ status: 'finished', outcome: 'done', portals_done: 3, problems: 1, finished_at: '2026-11-03T10:30:00Z' })))
    renderApp('/como-funciona')
    expect(await screen.findByText('Búsqueda terminada')).toBeInTheDocument()
    expect(screen.getByText('4 ofertas nuevas de 12 vistas.')).toBeInTheDocument()
    expect(screen.getByText(/^1 problema en los portales/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Ver en la Bandeja' })).toHaveAttribute('href', '/bandeja')
  })

  it('dice si tu agente no ha podido buscar, y no finge que hay resultado', async () => {
    mockApi(routes(run({ status: 'finished', outcome: 'no_browser', portals_done: 0, created: 0, found: 0 })))
    renderApp('/como-funciona')
    expect(await screen.findByText('Tu agente no ha podido buscar')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Ver en la Bandeja' })).not.toBeInTheDocument()
  })

  it('si se queda sin noticias, lo dice en vez de seguir «buscando»', async () => {
    mockApi(routes(run({ status: 'stale' })))
    renderApp('/como-funciona')
    expect(await screen.findByText('Sin noticias de tu agente')).toBeInTheDocument()
    expect(screen.queryByText('Buscando ofertas…')).not.toBeInTheDocument()
  })

  it('se minimiza y se vuelve a abrir, sin dejar de seguir la búsqueda', async () => {
    const calls = mockApi(routes(run()))
    renderApp('/como-funciona')
    await userEvent.click(await screen.findByRole('button', { name: 'Minimizar el aviso' }))
    expect(screen.queryByText('Tu agente sigue trabajando en su ventana.')).not.toBeInTheDocument()
    expect(screen.getByText('1/3')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Buscando ofertas…: abrir el aviso' }))
    expect(screen.getByText('Tu agente sigue trabajando en su ventana.')).toBeInTheDocument()
    expect(calls.some((c) => c.method === 'POST')).toBe(false)
  })

  it('minimizado, se abre solo al terminar: que no se te pase', async () => {
    let current = run()
    mockApi(routes(null, { 'GET /agent/search-run': () => ({ run: current }) }))
    renderApp('/como-funciona')
    await userEvent.click(await screen.findByRole('button', { name: 'Minimizar el aviso' }))
    current = run({ status: 'finished', outcome: 'done', portals_done: 3 })
    await waitFor(() => expect(screen.getByText('Búsqueda terminada')).toBeInTheDocument(), { timeout: 6000 })
    expect(screen.getByText('4 ofertas nuevas de 12 vistas.')).toBeInTheDocument()
  }, 10_000)

  it('mientras busca también se puede cerrar con la X', async () => {
    const calls = mockApi(routes(run(), { 'POST /agent/search-run/7/dismiss': { run: null } }))
    renderApp('/como-funciona')
    await userEvent.click(await screen.findByRole('button', { name: 'Cerrar el aviso' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'POST' && c.path === '/agent/search-run/7/dismiss')).toBe(true))
  })

  it('se cierra y no vuelve a salir', async () => {
    let current: unknown = run({ status: 'finished', outcome: 'done', portals_done: 3 })
    const calls = mockApi(
      routes(null, {
        'GET /agent/search-run': () => ({ run: current }),
        'POST /agent/search-run/7/dismiss': () => {
          current = null
          return { run: null }
        },
      }),
    )
    renderApp('/como-funciona')
    await userEvent.click(await screen.findByRole('button', { name: 'Cerrar el aviso' }))
    await waitFor(() => expect(screen.queryByText('Búsqueda terminada')).not.toBeInTheDocument())
    expect(calls.some((c) => c.method === 'POST' && c.path === '/agent/search-run/7/dismiss')).toBe(true)
  })
})
