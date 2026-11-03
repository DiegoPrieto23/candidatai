import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { mockApi, renderApp, status } from '@/test/utils'

const page = (items: unknown[]) => ({ items, total: items.length, limit: 50, offset: 0 })

function platform(id: number, name: string, overrides: Record<string, unknown> = {}) {
  return {
    id,
    kind: 'agent_browse',
    kind_label: 'Portal',
    name,
    active: true,
    config: {},
    keys_missing: false,
    browse: { allow_agent_browsing: true, search_urls: [], priority: id, access: 'free', max_offers: 10, notes: '' },
    website: null,
    last_run_at: null,
    last_run: null,
    ...overrides,
  }
}

const launcher = {
  available: true,
  agent: 'claude',
  reason: null,
  actions: [{ id: 'search-jobs', background: false, agent: { display_name: 'Claude Code', blocked: null } }],
}

function routes(sources: unknown[], extra: Record<string, unknown> = {}) {
  return {
    'GET /status': status(),
    'GET /sources': { sources, agent_browse: { max_result_pages: 3, delay_seconds: 5 } },
    'GET /jobs': page([]),
    'GET /agent': launcher,
    ...extra,
  }
}

const launched = { label: 'Buscar ofertas', prompt: 'x', agent: 'Claude Code', job_id: null }

describe('Buscar ofertas', () => {
  it('lanza a tu agente en todos los portales activos, sin añadir nada a la orden', async () => {
    const calls = mockApi(
      routes(
        [
          platform(1, 'InfoJobs', {
            last_run_at: '2026-10-30T08:00:00Z',
            last_run: { id: 1, actor: 'agent', started_at: '2026-10-30T08:00:00Z', finished_at: null, found: 9, after_filters: 9, created: 4, errors: [] },
          }),
          platform(2, 'Tecnoempleo'),
          platform(3, 'LinkedIn', { browse: { allow_agent_browsing: false, search_urls: [], priority: 3, access: 'login', max_offers: 10, notes: '' } }),
        ],
        { 'POST /agent/launch': { status: 202, body: launched } },
      ),
    )
    renderApp('/buscar')
    const list = await screen.findByRole('list', { name: 'Portales en los que buscar' })
    expect(within(list).getByText('4 nuevas')).toBeInTheDocument()
    // LinkedIn sin activar no se ofrece: lo activa el usuario en «Dónde buscar».
    expect(within(list).queryByText('LinkedIn')).not.toBeInTheDocument()
    expect(screen.getByText(/1 portal más desactivado/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /^Buscar ahora/ }))
    await waitFor(() => expect(calls.some((c) => c.method === 'POST')).toBe(true))
    const body = calls.find((c) => c.method === 'POST')?.body as { action: string; search: Record<string, unknown> }
    expect(body.action).toBe('search-jobs')
    expect(body.search).toEqual({ platform_ids: [] })
  })

  it('manda los portales elegidos y la búsqueda puntual', async () => {
    const calls = mockApi(
      routes([platform(1, 'InfoJobs'), platform(2, 'Tecnoempleo')], { 'POST /agent/launch': { status: 202, body: launched } }),
    )
    renderApp('/buscar')
    await userEvent.click(await screen.findByRole('checkbox', { name: /Tecnoempleo/ }))
    await userEvent.click(screen.getByRole('button', { name: /Afinar esta búsqueda/ }))
    await userEvent.type(screen.getByLabelText('Puesto'), 'Data Engineer')
    await userEvent.type(screen.getByLabelText('Dónde'), 'Madrid')
    await userEvent.click(screen.getByRole('button', { name: /^Buscar ahora/ }))
    await waitFor(() => expect(calls.some((c) => c.method === 'POST')).toBe(true))
    const body = calls.find((c) => c.method === 'POST')?.body as { search: unknown }
    expect(body.search).toEqual({ platform_ids: [1], role: 'Data Engineer', location: 'Madrid' })
  })

  it('no deja lanzar sin portales ni con caracteres que no se admiten', async () => {
    mockApi(routes([platform(1, 'InfoJobs')]))
    renderApp('/buscar')
    const box = await screen.findByRole('checkbox', { name: /InfoJobs/ })
    await userEvent.click(box)
    expect(screen.getByText('Elige al menos un portal.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^Buscar ahora/ })).toBeDisabled()
    await userEvent.click(box)
    await userEvent.click(screen.getByRole('button', { name: /Afinar esta búsqueda/ }))
    await userEvent.type(screen.getByLabelText('Puesto'), 'x"; rm')
    expect(screen.getByRole('alert')).toHaveTextContent(/solo letras/i)
    expect(screen.getByRole('button', { name: /^Buscar ahora/ })).toBeDisabled()
  })

  it('sin portales, lleva a elegirlos', async () => {
    mockApi(routes([]))
    renderApp('/buscar')
    expect(await screen.findByText('Aún no hay portales en los que buscar')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Ir a «Dónde buscar»' })).toHaveAttribute('href', '/fuentes/plataformas')
    expect(screen.queryByRole('button', { name: /^Buscar ahora/ })).not.toBeInTheDocument()
  })
})
