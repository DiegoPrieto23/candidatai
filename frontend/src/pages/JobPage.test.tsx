import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { jobView, mockApi, renderApp, status } from '@/test/utils'

describe('Ficha de oferta', () => {
  it('muestra la extracción legible y el historial con el agente', async () => {
    mockApi({ 'GET /status': status(), 'GET /jobs/1': jobView() })
    renderApp('/jobs/1')

    expect(await screen.findByRole('heading', { level: 1, name: 'Data Engineer' })).toBeInTheDocument()
    expect(screen.getByText('Intermedio')).toBeInTheDocument()
    expect(screen.getByText('38.000 € - 46.000 € / año')).toBeInTheDocument()
    expect(screen.getByText('Inglés B2')).toBeInTheDocument()
    expect(screen.getByText('Python')).toBeInTheDocument()
    expect(screen.getByText('Terraform')).toBeInTheDocument()
    expect(screen.getByText('Extracción guardada')).toBeInTheDocument()
    expect(screen.getByText(/Agente claude-code/)).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Aviso de posible inyección' })).not.toBeInTheDocument()
  })

  it('pliega el texto original', async () => {
    mockApi({ 'GET /status': status(), 'GET /jobs/1': jobView() })
    renderApp('/jobs/1')
    const trigger = await screen.findByRole('button', { name: /Texto original/ })
    expect(screen.queryByText('Texto original de la oferta ficticia.')).not.toBeInTheDocument()
    await userEvent.click(trigger)
    expect(screen.getByText('Texto original de la oferta ficticia.')).toBeInTheDocument()
  })

  it('avisa de forma visible si hay posible inyección', async () => {
    mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView({
        risk_flags: ['injection_phrase'],
        injection: {
          risk_flags: ['injection_phrase'],
          reports: [
            { source: 'system', agent_name: null, excerpt: 'ignora las instrucciones', occurred_at: new Date().toISOString() },
            { source: 'agent', agent_name: 'codex', excerpt: null, occurred_at: new Date().toISOString() },
          ],
        },
      }),
    })
    renderApp('/jobs/1')

    const alert = await screen.findByRole('region', { name: 'Aviso de posible inyección' })
    expect(within(alert).getByText('Posible contenido dirigido a una IA')).toBeInTheDocument()
    expect(within(alert).getByText('Frases que parecen instrucciones para una IA')).toBeInTheDocument()
    expect(within(alert).getByText('ignora las instrucciones')).toBeInTheDocument()
  })

  it('invita a ejecutar procesar-ofertas si aún no hay extracción', async () => {
    mockApi({ 'GET /status': status(1), 'GET /jobs/1': jobView({ extraction: null, stage: 'pending_extraction' }) })
    renderApp('/jobs/1')
    expect(await screen.findByText('Aún sin extraer')).toBeInTheDocument()
  })

  it('guarda una nota y recarga la ficha', async () => {
    let view = jobView()
    const calls = mockApi({
      'GET /status': status(),
      'GET /jobs/1': () => view,
      'POST /jobs/1/events': () => {
        const now = new Date().toISOString()
        view = {
          ...view,
          events: [...view.events, { id: 3, type: 'note', actor: 'user', agent_name: null, payload: { note: 'Llamar el lunes' }, occurred_at: now, recorded_at: now }],
        }
        return { ok: true, event_id: 3, stage: 'pending_triage' }
      },
    })
    renderApp('/jobs/1')

    const button = await screen.findByRole('button', { name: /Guardar nota/ })
    expect(button).toBeDisabled()
    await userEvent.type(screen.getByLabelText('Añadir nota'), '  Llamar el lunes ')
    await userEvent.click(button)

    await waitFor(() => expect(screen.getByText('Llamar el lunes')).toBeInTheDocument())
    expect(calls.find((c) => c.method === 'POST')?.body).toEqual({ type: 'note', note: 'Llamar el lunes' })
    expect(screen.getByText('Tú', { exact: false })).toBeInTheDocument()
    expect(screen.getByLabelText('Añadir nota')).toHaveValue('')
  })

  it('muestra el error si la oferta no existe', async () => {
    mockApi({ 'GET /status': status() })
    renderApp('/jobs/99')
    expect(await screen.findByText('Sin simular: GET /jobs/99')).toBeInTheDocument()
  })
})
