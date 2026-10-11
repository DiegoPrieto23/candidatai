import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { mockApi, renderApp, status } from '@/test/utils'

const noFollowups = { days_without_reply: 7, followups: [] }
const emptyPage = { items: [], total: 0, limit: 50, offset: 0 }
const launcher = {
  available: true,
  agent: 'claude',
  reason: null,
  actions: [{ id: 'buscar-ofertas', label: 'Buscar ofertas', needs_job: false, prompt: 'Usa el skill buscar-ofertas…' }],
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
      'POST /agent/launch': { ok: true, agent: 'claude', prompt: 'Usa el skill buscar-ofertas…', message: 'ok' },
    })
    renderApp('/')
    await userEvent.click(await screen.findByRole('button', { name: 'Buscar ofertas' }))
    expect(await screen.findByText('Abierto en claude: sigue en la terminal.')).toBeInTheDocument()
    expect(calls.find((c) => c.path === '/agent/launch')?.body).toEqual({ action: 'buscar-ofertas' })
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
            details: [{ field: 'prompt', received: 'Usa el skill buscar-ofertas de Job Hunter.', reason: '…' }],
          },
        },
      },
    })
    renderApp('/')
    await userEvent.click(await screen.findByRole('button', { name: 'Buscar ofertas' }))
    await waitFor(() => expect(writeText).toHaveBeenCalledWith('Usa el skill buscar-ofertas de Job Hunter.'))
    expect(await screen.findByText(/He copiado la orden: pégala en tu agente\./)).toBeInTheDocument()
  })

  it('en Inicio, «Procesar» y «Evaluar» solo salen si hay ofertas para ellos', async () => {
    home({ 'GET /status': status(2, 0) })
    renderApp('/')
    expect(await screen.findByRole('button', { name: 'Procesar ofertas' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Evaluar encaje' })).not.toBeInTheDocument()
  })
})
