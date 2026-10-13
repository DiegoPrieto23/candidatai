import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { mockApi, renderApp, status } from '@/test/utils'

const noFollowups = { days_without_reply: 7, followups: [] }
const emptyPage = { items: [], total: 0, limit: 50, offset: 0 }
const launcher = {
  available: true,
  agent: 'claude',
  reason: null,
  background: { available: true, agent: 'claude', reason: null },
  actions: [
    { id: 'search-jobs', label: 'Buscar ofertas', needs_job: false, prompt: 'Usa el skill search-jobs…', background: false },
    { id: 'process-jobs', label: 'Procesar ofertas', needs_job: false, prompt: 'Usa…', background: true },
  ],
}

function home(extra: Record<string, unknown>) {
  return mockApi({
    'GET /status': status(),
    'GET /followups': noFollowups,
    'GET /upcoming': { days: 7, items: [] },
    'GET /jobs': emptyPage,
    'GET /agent': launcher,
    ...extra,
  })
}

describe('Botones «en tu agente»', () => {
  it('«Buscar ofertas» abre el agente y lo dice', async () => {
    const calls = home({
      'POST /agent/launch': { ok: true, agent: 'claude', prompt: 'Usa el skill search-jobs…', message: 'ok' },
    })
    renderApp('/')
    await userEvent.click(await screen.findByRole('button', { name: 'Buscar ofertas' }))
    expect(await screen.findByText('Abierto en claude: sigue en la terminal.')).toBeInTheDocument()
    expect(calls.find((c) => c.path === '/agent/launch')?.body).toEqual({ action: 'search-jobs' })
  })

  it('si no puede abrir el agente, copia la orden', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
    home({
      'POST /agent/launch': {
        status: 503,
        body: {
          ok: false,
          error: {
            type: 'agent_unavailable',
            message: 'No se encuentra el programa del agente (claude) en el PATH.',
            details: [{ field: 'prompt', received: 'Usa el skill search-jobs de CandidatAI.', reason: '…' }],
          },
        },
      },
    })
    renderApp('/')
    await userEvent.click(await screen.findByRole('button', { name: 'Buscar ofertas' }))
    await waitFor(() => expect(writeText).toHaveBeenCalledWith('Usa el skill search-jobs de CandidatAI.'))
    expect(await screen.findByText(/He copiado la orden: pégala en tu agente\./)).toBeInTheDocument()
  })

  it('en Inicio, «Procesar» y «Evaluar» solo salen si hay ofertas para ellos', async () => {
    home({ 'GET /status': status(2, 0) })
    renderApp('/')
    expect(await screen.findByRole('button', { name: 'Procesar ofertas' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Evaluar encaje' })).not.toBeInTheDocument()
  })

  it('«En segundo plano» deja la ejecución en cola y enlaza a «Agente» (fase 19)', async () => {
    const calls = home({
      'GET /status': status(2, 0),
      'POST /agent/runs': { status: 202, body: { id: 1, status: 'queued' } },
    })
    renderApp('/')
    const main = await screen.findByRole('button', { name: 'Procesar ofertas' })
    await userEvent.click(within(main.parentElement!).getByRole('button', { name: 'Más formas de lanzarlo' }))
    await userEvent.click(await screen.findByRole('menuitem', { name: /En segundo plano/ }))
    expect(await screen.findByText('En cola en segundo plano.', { exact: false })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Ver en «Agente»' })).toHaveAttribute('href', '/agente')
    expect(calls.find((c) => c.method === 'POST' && c.path === '/agent/runs')?.body).toEqual({ action: 'process-jobs' })
  })

  it('los skills que preguntan no ofrecen segundo plano, pero sí dejarlo para luego', async () => {
    const calls = home({ 'POST /agent/requests': { id: 3, status: 'pending' } })
    renderApp('/')
    const main = await screen.findByRole('button', { name: 'Buscar ofertas' })
    await userEvent.click(within(main.parentElement!).getByRole('button', { name: 'Más formas de lanzarlo' }))
    expect(await screen.findByRole('menuitem', { name: /En terminal/ })).toBeInTheDocument()
    expect(screen.queryByRole('menuitem', { name: /En segundo plano/ })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('menuitem', { name: /Dejar para mi próxima sesión/ }))
    expect(await screen.findByText(/Encargo guardado/)).toBeInTheDocument()
    expect(calls.find((c) => c.method === 'POST' && c.path === '/agent/requests')?.body).toEqual({ action: 'search-jobs' })
  })
})
