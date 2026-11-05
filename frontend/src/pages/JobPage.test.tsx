import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { board, jobView, matchView, mockApi, processView, renderApp, status } from '@/test/utils'

const noProfile = { exists: false, file_hash: null, profile: null, issues: [], profile_version_id: null, undo_available: 0 }
const withProfile = { ...noProfile, exists: true, file_hash: 'h', profile: {}, profile_version_id: 1 }

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
    expect(screen.getByText('Leída por tu agente')).toBeInTheDocument()
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

  it('sin leer y con perfil: el perfil está hecho y falta que tu agente la lea', async () => {
    mockApi({
      'GET /status': status(1),
      'GET /jobs/1': jobView({ extraction: null, stage: 'pending_extraction' }),
      'GET /profile/editable': withProfile,
    })
    renderApp('/jobs/1')
    const box = await screen.findByRole('region', { name: 'Para saber si te encaja' })
    expect(within(box).getByText('Crea tu perfil')).toHaveTextContent('Crea tu perfil: Hecho')
    expect(within(box).getByText('Que tu agente la lea')).toHaveTextContent('Que tu agente la lea: Falta')
    expect(within(box).queryByRole('link', { name: /Ir a «Mi perfil»/ })).not.toBeInTheDocument()
    expect(within(box).getByRole('button', { name: 'Valorar las ofertas nuevas' })).toBeInTheDocument()
  })

  it('sin perfil ni leer: los dos pasos pendientes, cada uno con su botón', async () => {
    mockApi({
      'GET /status': status(1),
      'GET /jobs/1': jobView({ extraction: null, stage: 'pending_extraction' }),
      'GET /profile/editable': noProfile,
    })
    renderApp('/jobs/1')
    const box = await screen.findByRole('region', { name: 'Para saber si te encaja' })
    expect(within(box).getByText('Crea tu perfil')).toHaveTextContent('Crea tu perfil: Falta')
    expect(within(box).getByRole('link', { name: /Ir a «Mi perfil»/ })).toHaveAttribute('href', '/perfil')
    expect(within(box).getByText('Que tu agente la lea')).toHaveTextContent('Que tu agente la lea: Falta')
    expect(within(box).getByRole('button', { name: 'Valorar las ofertas nuevas' })).toBeInTheDocument()
  })

  it('«Por completar»: dice que falta el texto, cómo completarla con la extensión y dónde instalarla', async () => {
    mockApi({
      'GET /status': status(0, 1),
      'GET /jobs/1': jobView({ extraction: null, stage: 'pending_detail', url: 'https://www.linkedin.com/jobs/view/1' }),
    })
    renderApp('/jobs/1')
    const box = await screen.findByRole('region', { name: 'Falta el texto de la oferta' })
    expect(within(box).getByRole('link', { name: /Abrir la oferta/ })).toHaveAttribute('href', 'https://www.linkedin.com/jobs/view/1')
    expect(box).toHaveTextContent('Enviar a CandidatAI')
    expect(within(box).getByRole('link', { name: 'Instálalo en unos minutos' })).toHaveAttribute('href', '/fuentes/extension')
    expect(screen.queryByRole('region', { name: 'Para saber si te encaja' })).not.toBeInTheDocument()
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

  it('enseña el score junto al desglose del encaje, sin repetir las skills', async () => {
    mockApi({ 'GET /status': status(), 'GET /jobs/1': jobView(), 'GET /jobs/1/match': matchView() })
    renderApp('/jobs/1')
    const header = (await screen.findByRole('heading', { level: 1, name: 'Data Engineer' })).closest('header')!
    const panel = screen.getByRole('region', { name: 'Encaje' })
    expect(await within(panel).findByLabelText(/Encaje de 78 sobre 100/)).toBeInTheDocument()
    expect(within(header).queryByLabelText(/Encaje de 78 sobre 100/)).not.toBeInTheDocument()
    expect(within(panel).getByText('Kafka')).toBeInTheDocument()
    expect(within(panel).getByText('Obligatorias')).toBeInTheDocument()
    // Con el encaje, la extracción no vuelve a listar las skills.
    expect(screen.getAllByText('Obligatorias')).toHaveLength(1)
  })

  it('el encaje dice su escala y qué tal es, y explica el número y cada parte del desglose', async () => {
    mockApi({ 'GET /status': status(), 'GET /jobs/1': jobView(), 'GET /jobs/1/match': matchView() })
    renderApp('/jobs/1')
    const panel = await screen.findByRole('region', { name: 'Encaje' })
    // 78 con el mínimo de «Por revisar» en 55: desde 70, buen encaje.
    const badge = await within(panel).findByLabelText('Encaje de 78 sobre 100, buen encaje')
    expect(badge).toHaveTextContent('78/100')
    expect(badge).toHaveTextContent('buen encaje')

    within(panel).getByRole('button', { name: 'Qué significa este número' }).focus()
    expect(await screen.findByRole('tooltip')).toHaveTextContent(/Desde 55 es un encaje posible; desde 70, un buen encaje/)
    await userEvent.keyboard('{Escape}')

    expect(within(panel).getByText('De dónde sale el número')).toBeInTheDocument()
    within(panel).getByRole('button', { name: 'Qué mide «Obligatorias»' }).focus()
    expect(await screen.findByRole('tooltip')).toHaveTextContent(/skills obligatorias.*Aquí suma 51 de los 64 puntos/)
    await userEvent.keyboard('{Escape}')
    within(panel).getByRole('button', { name: 'Qué mide «Similitud»' }).focus()
    expect(await screen.findByRole('tooltip')).toHaveTextContent(/No cuenta: hace falta la comparación por significado/)

    // Las letras de nivel, con su leyenda.
    expect(within(panel).getByText(/Tu nivel en cada skill/)).toHaveTextContent('F fuerte · bás. conocimientos básicos')
  })

  it('leída y sin perfil: el encaje dice que falta el perfil y que la lectura ya está', async () => {
    mockApi({ 'GET /status': status(), 'GET /jobs/1': jobView() }) // /match sin simular: 404
    renderApp('/jobs/1')
    const box = await screen.findByRole('region', { name: 'Para saber si te encaja' })
    expect(within(box).getByText('Crea tu perfil')).toHaveTextContent('Crea tu perfil: Falta')
    expect(within(box).getByText('Que tu agente la lea')).toHaveTextContent('Que tu agente la lea: Hecho')
    expect(within(box).queryByRole('button', { name: 'Valorar las ofertas nuevas' })).not.toBeInTheDocument()
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

  it.each(['approved', 'cv_ready', 'pending_extraction'] as const)('en «%s» se descarta con motivo', async (stage) => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView({ stage }),
      'POST /jobs/1/events': { ok: true, event_id: 1, stage: 'closed' },
    })
    renderApp('/jobs/1')
    await userEvent.click(await screen.findByRole('button', { name: 'Descartar' }))
    const dialog = await screen.findByRole('dialog')
    await userEvent.click(within(dialog).getByRole('radio', { name: /ya no está|cerrada/i }))
    await userEvent.click(within(dialog).getByRole('button', { name: 'Descartar' }))
    await waitFor(() =>
      expect(calls.find((c) => c.method === 'POST' && c.path === '/jobs/1/events')?.body).toMatchObject({
        type: 'discarded',
        reason: 'closed',
      }),
    )
    expect(screen.queryByRole('button', { name: 'Aprobar' })).not.toBeInTheDocument()
  })

  it.each(['applied', 'in_process'] as const)('en «%s» se cierra la candidatura con su motivo, no se descarta', async (stage) => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView({ stage }),
      'POST /jobs/1/events': { ok: true, event_id: 1, stage: 'closed' },
    })
    renderApp('/jobs/1')
    await userEvent.click(await screen.findByRole('button', { name: 'Cerrar candidatura' }))
    expect(screen.queryByRole('button', { name: 'Descartar' })).not.toBeInTheDocument()
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByRole('heading', { name: 'Cerrar candidatura' })).toBeInTheDocument()
    await userEvent.click(within(dialog).getByRole('radio', { name: /Te retiras del proceso/ }))
    await userEvent.type(within(dialog).getByRole('textbox', { name: /Nota/ }), 'Acepté otra')
    await userEvent.click(within(dialog).getByRole('button', { name: /Registrar|Guardar|Confirmar|Mover/ }))
    await waitFor(() =>
      expect(calls.find((c) => c.method === 'POST' && c.path === '/jobs/1/events')?.body).toMatchObject({
        type: 'withdrawn',
        note: 'Acepté otra',
      }),
    )
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
