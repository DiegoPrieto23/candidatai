import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { board, jobView, matchView, mockApi, processView, renderApp, status } from '@/test/utils'

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

  it('enseña el encaje con el score y el desglose', async () => {
    mockApi({ 'GET /status': status(), 'GET /jobs/1': jobView(), 'GET /jobs/1/match': matchView() })
    renderApp('/jobs/1')
    const panel = await screen.findByRole('region', { name: 'Encaje' })
    expect(await within(panel).findByLabelText('Score 78 de 100')).toBeInTheDocument()
    expect(within(panel).getByText('Kafka')).toBeInTheDocument()
    expect(within(panel).getByText('Obligatorias')).toBeInTheDocument()
  })

  it('sin perfil, el encaje explica cómo conseguir el score', async () => {
    mockApi({ 'GET /status': status(), 'GET /jobs/1': jobView() }) // /match sin simular: 404
    renderApp('/jobs/1')
    const panel = await screen.findByRole('region', { name: 'Encaje' })
    expect(await within(panel).findByText(/Sin score/)).toBeInTheDocument()
  })

  it('aprueba desde la ficha', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView(),
      'GET /jobs/1/match': matchView(),
      'POST /jobs/1/events': { ok: true, event_id: 3, stage: 'approved' },
    })
    renderApp('/jobs/1')
    await userEvent.click(await screen.findByRole('button', { name: /Aprobar/ }))
    await waitFor(() =>
      expect(calls.find((c) => c.method === 'POST')?.body).toEqual({ type: 'approved' }),
    )
  })

  it('descarta desde la ficha con motivo', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView(),
      'GET /jobs/1/match': matchView(),
      'POST /jobs/1/events': { ok: true, event_id: 3, stage: 'closed' },
    })
    renderApp('/jobs/1')
    await userEvent.click(await screen.findByRole('button', { name: /Descartar/ }))
    const dialog = await screen.findByRole('dialog')
    await userEvent.click(within(dialog).getByRole('radio', { name: /Salario/ }))
    await userEvent.click(within(dialog).getByRole('button', { name: 'Descartar' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(calls.find((c) => c.method === 'POST')?.body).toEqual({ type: 'discarded', reason: 'salary' })
  })

  it('reabre una oferta cerrada por los filtros y explica por qué se cerró', async () => {
    const now = new Date().toISOString()
    const view = jobView({
      stage: 'closed',
      events: [
        ...jobView().events,
        {
          id: 3,
          type: 'hard_filter_failed',
          actor: 'system',
          agent_name: null,
          payload: { failures: [{ filter: 'years', reason: 'Pide 8 años de experiencia.' }] },
          occurred_at: now,
          recorded_at: now,
        },
      ],
    })
    const calls = mockApi({
      'GET /status': status(),
      'GET /jobs/1': view,
      'GET /jobs/1/match': matchView(),
      'POST /jobs/1/events': { ok: true, event_id: 4, stage: 'pending_triage' },
    })
    renderApp('/jobs/1')
    expect(await screen.findByText('Pide 8 años de experiencia.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Aprobar/ })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Reabrir/ }))
    await waitFor(() =>
      expect(calls.find((c) => c.method === 'POST')?.body).toEqual({ type: 'reopened' }),
    )
  })
})

describe('Ficha de una oferta ya enviada', () => {
  it('«¿Qué ha pasado?» va lo primero y lo de antes de enviar queda plegado', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView({ stage: 'applied' }),
      'GET /jobs/1/process': processView({ stage: 'applied' }),
      'GET /board': board([]),
    })
    renderApp('/jobs/1')
    const update = await screen.findByRole('region', { name: '¿Qué ha pasado?' })
    const earlier = screen.getByRole('region', { name: 'Antes de enviar' })
    // Antes que el resto en el documento.
    expect(update.compareDocumentPosition(earlier) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    // Extracción y encaje siguen a la vista; el resto, plegado y sin cargar.
    expect(screen.getByRole('heading', { name: 'Extracción' })).toBeInTheDocument()
    expect(calls.some((c) => c.path === '/jobs/1/package')).toBe(false)
    await userEvent.click(within(earlier).getByRole('button', { name: /Antes de enviar/ }))
    await waitFor(() => expect(calls.some((c) => c.path === '/jobs/1/package')).toBe(true))
  })
})

describe('Historial compacto', () => {
  it('con muchos eventos enseña el alta y los últimos, y despliega el resto', async () => {
    const now = new Date().toISOString()
    const types = ['found', 'extracted', 'scored', 'fit_assessed', 'approved', 'cv_generated', 'cv_verified', 'applied']
    const events = types.map((type, i) => ({
      id: i + 1, type, actor: 'system', agent_name: null, payload: {}, occurred_at: now, recorded_at: now,
    }))
    mockApi({ 'GET /status': status(), 'GET /jobs/1': jobView({ stage: 'cv_ready', events }) })
    renderApp('/jobs/1')
    const more = await screen.findByRole('button', { name: 'Ver 3 eventos más' })
    const history = more.closest('ol')!
    expect(within(history).getAllByRole('listitem')).toHaveLength(6) // 4 últimos + botón + alta
    await userEvent.click(more)
    expect(within(history).getAllByRole('listitem')).toHaveLength(9) // 8 + «Ver menos»
    await userEvent.click(within(history).getByRole('button', { name: 'Ver menos' }))
    expect(within(history).getByRole('button', { name: 'Ver 3 eventos más' })).toBeInTheDocument()
  })
})
