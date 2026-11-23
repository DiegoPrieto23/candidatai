import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { isForward } from '@/lib/moves'
import { board, boardCard, jobView, mockApi, pickDate, renderApp, status } from '@/test/utils'

const CARDS = [
  boardCard(1, 'approved'),
  boardCard(2, 'applied', { followup_due: true, days_waiting: 12 }),
  boardCard(3, 'in_process', {
    next_milestone: {
      milestone_id: 7,
      kind: 'interview',
      title: 'Entrevista',
      starts_at: '2026-10-07T08:30:00Z',
      all_day: false,
    },
  }),
  boardCard(4, 'closed', { closed_by: 'rejected', reopen_to: 'applied' }),
]

function routes(extra: Record<string, unknown> = {}) {
  return {
    'GET /status': status(),
    'GET /board': board(CARDS),
    'GET /upcoming': {
      days: 7,
      items: [
        {
          kind: 'interview',
          job_id: 3,
          job_title: 'Oferta 3',
          company: 'Empresa 3',
          stage: 'in_process',
          milestone_id: 7,
          title: 'Entrevista',
          starts_at: '2026-10-07T08:30:00Z',
          ends_at: null,
          all_day: false,
          location: null,
        },
      ],
    },
    ...extra,
  }
}

describe('Mover tarjetas', () => {
  const ORDER = ['approved', 'cv_ready', 'applied', 'in_process', 'closed'] as const

  it('solo hacia una etapa posterior', () => {
    expect(isForward(ORDER, 'applied', 'in_process')).toBe(true)
    expect(isForward(ORDER, 'applied', 'closed')).toBe(true)
    expect(isForward(ORDER, 'applied', 'cv_ready')).toBe(false)
    expect(isForward(ORDER, 'closed', 'in_process')).toBe(false)
    expect(isForward(ORDER, 'applied', 'applied')).toBe(false)
  })
})

describe('Procesos (kanban)', () => {
  it('reparte las tarjetas por columna con seguimiento, hito y cierre', async () => {
    mockApi(routes())
    renderApp('/procesos')
    const applied = await screen.findByRole('region', { name: 'Enviada' })
    expect(within(applied).getByText('Oferta 2')).toBeInTheDocument()
    expect(within(applied).getByText(/Seguimiento · 12 días/)).toBeInTheDocument()
    expect(screen.getByText('1 seguimiento pendiente')).toBeInTheDocument()
    // La intro va en una línea; cómo se usa el tablero, en su ayuda.
    expect(screen.getByText('Las candidaturas en curso, por etapa.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Cómo se usa el tablero' })).toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: 'Cerrada' })).getByText('Rechazada')).toBeInTheDocument()
    const upcoming = screen.getByRole('region', { name: 'Próximos 7 días' })
    expect(await within(upcoming).findByText(/Oferta 3 \(Empresa 3\)/)).toBeInTheDocument()
    expect(within(upcoming).getByRole('link', { name: 'Ver el calendario' })).toHaveAttribute('href', '/calendario')
  })

  it('las cerradas dicen hasta dónde llegaron y se filtran por cómo acabaron', async () => {
    const closed = [
      boardCard(5, 'closed', { closed_by: 'rejected', reached: 'interview' }),
      boardCard(6, 'closed', { closed_by: 'rejected', reached: 'applied' }),
      boardCard(7, 'closed', { closed_by: 'discarded', reached: 'before_applying' }),
      boardCard(8, 'closed', { closed_by: 'withdrawn', reached: 'interview' }),
    ]
    mockApi(routes({ 'GET /board': board([...CARDS.slice(0, 3), ...closed]) }))
    renderApp('/procesos')
    const column = await screen.findByRole('region', { name: 'Cerrada' })
    expect(within(column).getByText('Rechazada tras entrevista')).toHaveClass('text-destructive')
    expect(within(column).getByText('Rechazada sin entrevista')).toBeInTheDocument()
    expect(within(column).getByText('Descartada')).not.toHaveClass('text-destructive')

    await userEvent.click(within(column).getByRole('combobox', { name: 'Mostrar' }))
    await userEvent.click(await screen.findByRole('option', { name: 'Rechazadas tras entrevista' }))
    expect(within(column).getByText('Oferta 5')).toBeInTheDocument()
    for (const other of ['Oferta 6', 'Oferta 7', 'Oferta 8']) {
      expect(within(column).queryByText(other)).not.toBeInTheDocument()
    }
    // Las demás columnas no se filtran.
    expect(within(screen.getByRole('region', { name: 'Enviada' })).getByText('Oferta 2')).toBeInTheDocument()

    await userEvent.click(within(column).getByRole('combobox', { name: 'Mostrar' }))
    await userEvent.click(await screen.findByRole('option', { name: 'Descartadas a mano' }))
    expect(within(column).getByText('Oferta 7')).toBeInTheDocument()
    expect(within(column).queryByText('Oferta 5')).not.toBeInTheDocument()
  })

  it('registra el envío con canal y fecha desde «Mover»', async () => {
    const calls = mockApi(routes({ 'POST /jobs/1/events': { ok: true, event_id: 9, stage: 'applied' } }))
    renderApp('/procesos')
    await userEvent.click(await screen.findByRole('button', { name: 'Actualizar estado de «Oferta 1»' }))
    const dialog = await screen.findByRole('dialog')
    const register = within(dialog).getByRole('button', { name: 'Registrar' })
    expect(register).toBeDisabled()
    await userEvent.click(within(dialog).getByRole('radio', { name: /Enviada a mano/ }))
    await userEvent.selectOptions(within(dialog).getByLabelText('Canal (opcional)'), 'email')
    await userEvent.click(register)

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    const post = calls.find((c) => c.method === 'POST')
    expect(post?.path).toBe('/jobs/1/events')
    expect(post?.body).toMatchObject({ type: 'applied_manually', channel: 'email' })
    expect((post?.body as { occurred_at?: string } | undefined)?.occurred_at).toMatch(/[+-]0[12]:00$/)
  })

  it('descartar exige motivo', async () => {
    mockApi(routes())
    renderApp('/procesos')
    await userEvent.click(await screen.findByRole('button', { name: 'Actualizar estado de «Oferta 1»' }))
    const dialog = await screen.findByRole('dialog')
    await userEvent.click(within(dialog).getByRole('radio', { name: /Descartada/ }))
    expect(within(dialog).getByRole('button', { name: 'Registrar' })).toBeDisabled()
    await userEvent.click(within(dialog).getByRole('radio', { name: 'No encaja el stack' }))
    expect(within(dialog).getByRole('button', { name: 'Registrar' })).toBeEnabled()
  })

  it('programar una entrevista crea su hito (que registra el evento)', async () => {
    const calls = mockApi(routes({ 'POST /jobs/2/milestones': { id: 8 } }))
    renderApp('/procesos')
    await userEvent.click(await screen.findByRole('button', { name: 'Actualizar estado de «Oferta 2»' }))
    const dialog = await screen.findByRole('dialog')
    await userEvent.click(within(dialog).getByRole('radio', { name: /Entrevista programada/ }))
    const register = within(dialog).getByRole('button', { name: 'Registrar' })
    expect(within(dialog).getByLabelText('Hora (opcional)')).toBeDisabled() // sin fecha, no hay hora
    await pickDate(within(dialog).getByLabelText('Fecha de la entrevista (opcional)'), '2026-10-07')
    await userEvent.type(within(dialog).getByRole('textbox', { name: 'Horas' }), '10')
    await userEvent.type(within(dialog).getByRole('textbox', { name: 'Minutos' }), '30')
    await userEvent.type(within(dialog).getByLabelText('Lugar o enlace (opcional)'), 'https://meet.example/x')
    await userEvent.selectOptions(within(dialog).getByLabelText('Tipo de entrevista'), 'hr')
    await userEvent.click(register)

    await waitFor(() => expect(calls.some((c) => c.path === '/jobs/2/milestones')).toBe(true))
    const post = calls.find((c) => c.path === '/jobs/2/milestones')
    expect(post?.body).toMatchObject({
      kind: 'interview',
      starts_at: '2026-10-07T10:30:00+02:00',
      location: 'https://meet.example/x',
      all_day: false,
      interview_type: 'hr',
    })
    expect(calls.some((c) => c.path === '/jobs/2/events')).toBe(false)
  })

  it('una entrevista con fecha lleva las 14:00 si no sabes la hora', async () => {
    const calls = mockApi(routes({ 'POST /jobs/2/milestones': { id: 8 } }))
    renderApp('/procesos')
    await userEvent.click(await screen.findByRole('button', { name: 'Actualizar estado de «Oferta 2»' }))
    const dialog = await screen.findByRole('dialog')
    await userEvent.click(within(dialog).getByRole('radio', { name: /Entrevista programada/ }))
    await pickDate(within(dialog).getByLabelText('Fecha de la entrevista (opcional)'), '2026-10-07')
    expect(within(dialog).getByRole('textbox', { name: 'Horas' })).toHaveValue('14')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Registrar' }))

    await waitFor(() => expect(calls.some((c) => c.path === '/jobs/2/milestones')).toBe(true))
    expect(calls.find((c) => c.path === '/jobs/2/milestones')?.body).toMatchObject({
      starts_at: '2026-10-07T14:00:00+02:00',
      all_day: false,
    })
  })

  it('una entrevista con fecha y la hora borrada cuenta todo el día', async () => {
    const calls = mockApi(routes({ 'POST /jobs/2/milestones': { id: 8 } }))
    renderApp('/procesos')
    await userEvent.click(await screen.findByRole('button', { name: 'Actualizar estado de «Oferta 2»' }))
    const dialog = await screen.findByRole('dialog')
    await userEvent.click(within(dialog).getByRole('radio', { name: /Entrevista programada/ }))
    await pickDate(within(dialog).getByLabelText('Fecha de la entrevista (opcional)'), '2026-10-07')
    await userEvent.clear(within(dialog).getByRole('textbox', { name: 'Horas' }))
    await userEvent.clear(within(dialog).getByRole('textbox', { name: 'Minutos' }))
    await userEvent.tab()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Registrar' }))

    await waitFor(() => expect(calls.some((c) => c.path === '/jobs/2/milestones')).toBe(true))
    expect(calls.find((c) => c.path === '/jobs/2/milestones')?.body).toMatchObject({
      kind: 'interview',
      starts_at: '2026-10-07T00:00:00+02:00',
      all_day: true,
    })
  })

  it('una entrevista sin fecha registra solo el evento', async () => {
    const calls = mockApi(routes({ 'POST /jobs/2/events': { ok: true, event_id: 9, stage: 'in_process' } }))
    renderApp('/procesos')
    await userEvent.click(await screen.findByRole('button', { name: 'Actualizar estado de «Oferta 2»' }))
    const dialog = await screen.findByRole('dialog')
    await userEvent.click(within(dialog).getByRole('radio', { name: /Entrevista programada/ }))
    expect(within(dialog).queryByLabelText('Lugar o enlace (opcional)')).not.toBeInTheDocument()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Registrar' }))

    await waitFor(() => expect(calls.some((c) => c.path === '/jobs/2/events')).toBe(true))
    expect(calls.find((c) => c.path === '/jobs/2/events')?.body).toMatchObject({ type: 'interview_scheduled' })
    expect(calls.some((c) => c.path === '/jobs/2/milestones')).toBe(false)
  })

  it('una oferta cerrada solo ofrece reabrirla', async () => {
    mockApi(routes())
    renderApp('/procesos')
    await userEvent.click(await screen.findByRole('button', { name: 'Actualizar estado de «Oferta 4»' }))
    const dialog = await screen.findByRole('dialog')
    const options = within(dialog).getAllByRole('radio')
    expect(options).toHaveLength(1)
    expect(options[0]).toHaveTextContent('Reabierta')
    expect(options[0]).toHaveTextContent('→ Enviada')
  })

  it('los seguimientos vencidos se cuentan en «Tablero» de la barra lateral', async () => {
    mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView(),
      'GET /followups': {
        days_without_reply: 10,
        followups: [
          {
            job_id: 2,
            title: 'Oferta 2',
            company: 'Empresa 2',
            url: '',
            channel: null,
            applied_at: null,
            last_followup_at: null,
            days_waiting: 12,
          },
        ],
      },
    })
    renderApp('/jobs/1')
    expect(await screen.findByRole('link', { name: 'Tablero (1 sin respuesta)' })).toHaveAttribute('href', '/procesos')
  })

  it('ofrece redactar los borradores con tu agente si hay seguimientos o agradecimientos', async () => {
    mockApi({
      ...routes(),
      'GET /agent': { available: true, agent: 'claude', reason: null, actions: [] },
      'GET /followups': {
        days_without_reply: 10,
        max_followups: 2,
        followups: [],
        thank_you_days: 3,
        thanks_due: [
          {
            job_id: 3,
            title: 'Oferta 3',
            company: 'Empresa 3',
            milestone_id: 7,
            interview_title: 'Entrevista',
            interview_at: '2026-10-07T08:30:00Z',
            contacts: [],
            draft_id: null,
          },
        ],
      },
    })
    renderApp('/procesos')
    expect(await screen.findByText(/1 seguimiento pendiente · 1 entrevista por agradecer/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Redactar borradores/ })).toBeInTheDocument()
  })
})


describe('Columnas configurables', () => {
  async function openDialog() {
    await userEvent.click(screen.getByRole('button', { name: 'Personalizar columnas' }))
    return screen.findByRole('dialog')
  }

  it('junta etapas con su selector y renombra sin tocar las etapas; «Restablecer» se aplica al guardar', async () => {
    const calls = mockApi(routes())
    renderApp('/procesos')
    await screen.findByRole('region', { name: 'Enviada' })
    let dialog = await openDialog()
    expect(dialog).toHaveTextContent(/no cambia la etapa de ninguna oferta/)
    await userEvent.selectOptions(within(dialog).getByLabelText('CV listo'), 'Columna 1 · Aprobada')
    await userEvent.selectOptions(within(dialog).getByLabelText('En proceso'), 'Columna 2 · Enviada')
    // Con 3 columnas, ninguna etapa sola puede dejar la suya: la columna desaparecería. Y una sola no
    // pasa a una nueva; una de una columna con dos, sí.
    const closed = within(dialog).getByLabelText('Cerrada')
    expect(within(closed).getByRole('option', { name: 'Columna 1 · Aprobada · CV listo' })).toBeDisabled()
    expect(within(closed).getByRole('option', { name: 'Columna nueva' })).toBeDisabled()
    const cvReady = within(dialog).getByLabelText('CV listo')
    expect(within(cvReady).getByRole('option', { name: 'Columna nueva' })).toBeEnabled()
    const stagesOfFirst = within(dialog).getByRole('list', { name: 'Etapas de la columna 1' })
    expect(within(stagesOfFirst).getAllByRole('listitem').map((li) => li.textContent)).toEqual(['Aprobada', 'CV listo'])
    await userEvent.type(within(dialog).getByLabelText('Nombre de la columna 2'), 'En marcha')
    // La vista previa ya enseña cómo queda.
    const preview = within(dialog).getByRole('region', { name: 'Vista previa' })
    expect(preview).toHaveTextContent('En marcha')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Guardar' }))

    const running = await screen.findByRole('region', { name: 'En marcha' })
    expect(within(running).getByText('Oferta 2')).toBeInTheDocument()
    expect(within(running).getByText('Oferta 3')).toBeInTheDocument()
    // Cada tarjeta de una columna con varias etapas dice la suya.
    expect(within(running).getByText('En proceso')).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Aprobada · CV listo' })).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Enviada' })).not.toBeInTheDocument()
    // Solo es una vista: ninguna llamada que cambie nada.
    expect(calls.filter((c) => c.method !== 'GET')).toEqual([])

    dialog = await openDialog()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Restablecer' }))
    // Aún no se ha aplicado: solo en el diálogo (detrás, el tablero sigue igual).
    expect(within(dialog).getByRole('heading', { name: '5 columnas' })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'En marcha', hidden: true })).toBeInTheDocument()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Guardar' }))
    expect(await screen.findByRole('region', { name: 'Enviada' })).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'En marcha' })).not.toBeInTheDocument()
  })

  it('reordena columnas y junta etapas no seguidas; «Cancelar» no guarda', async () => {
    mockApi(routes())
    renderApp('/procesos')
    await screen.findByRole('region', { name: 'Enviada' })
    const order = () => screen.getAllByRole('region').map((r) => r.getAttribute('aria-label'))
    let dialog = await openDialog()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Subir la columna «Cerrada»' }))
    await userEvent.click(within(dialog).getByRole('button', { name: 'Cancelar' }))
    expect(order().indexOf('Cerrada')).toBeGreaterThan(order().indexOf('En proceso'))

    dialog = await openDialog()
    expect(within(dialog).getByRole('button', { name: 'Subir la columna «Aprobada»' })).toBeDisabled()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Subir la columna «Cerrada»' }))
    await userEvent.selectOptions(within(dialog).getByLabelText('Aprobada'), 'Columna 4 · Cerrada')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Guardar' }))
    await screen.findByRole('region', { name: 'Aprobada · Cerrada' })
    expect(order().indexOf('Aprobada · Cerrada')).toBeLessThan(order().indexOf('En proceso'))
  })
})
