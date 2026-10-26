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
    // Sin encaje (el perfil no da score), las skills salen en la extracción.
    expect(await screen.findByText('Python')).toBeInTheDocument()
    expect(screen.getByText('Terraform')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('tab', { name: 'Historial y notas' }))
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

  it('invita a ejecutar process-jobs si aún no hay extracción', async () => {
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
    renderApp('/jobs/1?tab=history')

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

  it('enseña el score en la cabecera y el desglose en el encaje, sin repetir las skills', async () => {
    mockApi({ 'GET /status': status(), 'GET /jobs/1': jobView(), 'GET /jobs/1/match': matchView() })
    renderApp('/jobs/1')
    const header = (await screen.findByRole('heading', { level: 1, name: 'Data Engineer' })).closest('header')!
    expect(await within(header).findByLabelText('Score 78 de 100')).toBeInTheDocument()
    const panel = screen.getByRole('region', { name: 'Encaje' })
    expect(within(panel).getByText('Kafka')).toBeInTheDocument()
    expect(within(panel).getByText('Obligatorias')).toBeInTheDocument()
    // Con el encaje, la extracción no vuelve a listar las skills.
    expect(screen.getAllByText('Obligatorias')).toHaveLength(1)
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
    renderApp('/jobs/1?tab=history')
    expect(await screen.findByText('Pide 8 años de experiencia.')).toBeInTheDocument()
    expect(screen.queryByRole('tab', { name: 'Candidatura' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Aprobar/ })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Reabrir/ }))
    await waitFor(() =>
      expect(calls.find((c) => c.method === 'POST')?.body).toEqual({ type: 'reopened' }),
    )
  })
})

describe('Pestañas de la ficha', () => {
  it('antes de aprobar se abre en la oferta y no hay candidatura ni proceso', async () => {
    mockApi({ 'GET /status': status(), 'GET /jobs/1': jobView() })
    renderApp('/jobs/1')
    expect(await screen.findByRole('tab', { name: 'Oferta', selected: true })).toBeInTheDocument()
    expect(screen.queryByRole('tab', { name: 'Candidatura' })).not.toBeInTheDocument()
    expect(screen.queryByRole('tab', { name: 'Proceso' })).not.toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Empresa' })).toBeInTheDocument()
  })

  it('aprobada, se abre en la candidatura', async () => {
    mockApi({ 'GET /status': status(), 'GET /jobs/1': jobView({ stage: 'approved' }) })
    renderApp('/jobs/1')
    expect(await screen.findByRole('tab', { name: 'Candidatura', selected: true })).toBeInTheDocument()
  })

  it('enviada, se abre en el proceso con «¿Qué ha pasado?» y lo demás no se carga hasta abrirlo', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView({ stage: 'applied' }),
      'GET /jobs/1/process': processView({ stage: 'applied' }),
      'GET /board': board([]),
    })
    renderApp('/jobs/1')
    expect(await screen.findByRole('region', { name: '¿Qué ha pasado?' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Proceso', selected: true })).toBeInTheDocument()
    expect(calls.some((c) => c.path === '/jobs/1/package')).toBe(false)
    await userEvent.click(screen.getByRole('tab', { name: 'Candidatura' }))
    await waitFor(() => expect(calls.some((c) => c.path === '/jobs/1/package')).toBe(true))
  })

  it('la pestaña va en la URL y una que no toca se ignora', async () => {
    mockApi({ 'GET /status': status(), 'GET /jobs/1': jobView() })
    renderApp('/jobs/1?tab=process')
    expect(await screen.findByRole('tab', { name: 'Oferta', selected: true })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('tab', { name: 'Historial y notas' }))
    expect(screen.getByRole('tab', { name: 'Historial y notas', selected: true })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Historial' })).toBeInTheDocument()
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
    renderApp('/jobs/1?tab=history')
    const more = await screen.findByRole('button', { name: 'Ver 3 eventos más' })
    const history = more.closest('ol')!
    expect(within(history).getAllByRole('listitem')).toHaveLength(6) // 4 últimos + botón + alta
    await userEvent.click(more)
    expect(within(history).getAllByRole('listitem')).toHaveLength(9) // 8 + «Ver menos»
    await userEvent.click(within(history).getByRole('button', { name: 'Ver menos' }))
    expect(within(history).getByRole('button', { name: 'Ver 3 eventos más' })).toBeInTheDocument()
  })
})
