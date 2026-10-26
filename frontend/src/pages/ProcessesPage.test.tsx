import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { board, boardCard, jobView, mockApi, renderApp, status } from '@/test/utils'

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

describe('Procesos (kanban)', () => {
  it('reparte las tarjetas por columna con seguimiento, hito y cierre', async () => {
    mockApi(routes())
    renderApp('/procesos')
    const applied = await screen.findByRole('region', { name: 'Enviada' })
    expect(within(applied).getByText('Oferta 2')).toBeInTheDocument()
    expect(within(applied).getByText(/Seguimiento · 12 días/)).toBeInTheDocument()
    expect(screen.getByText('1 seguimiento pendiente')).toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: 'Cerrada' })).getByText('Rechazada')).toBeInTheDocument()
    const upcoming = screen.getByRole('region', { name: 'Próximos 7 días' })
    expect(await within(upcoming).findByText(/Oferta 3 \(Empresa 3\)/)).toBeInTheDocument()
    expect(within(upcoming).getByRole('link', { name: 'Ver el calendario' })).toHaveAttribute('href', '/calendario')
  })

  it('registra el envío con canal y fecha desde «Mover»', async () => {
    const calls = mockApi(routes({ 'POST /jobs/1/events': { ok: true, event_id: 9, stage: 'applied' } }))
    renderApp('/procesos')
    await userEvent.click(await screen.findByRole('button', { name: 'Actualizar estado de «Oferta 1»' }))
    const dialog = await screen.findByRole('dialog')
    const register = within(dialog).getByRole('button', { name: 'Registrar' })
    expect(register).toBeDisabled()
    await userEvent.click(within(dialog).getByRole('radio', { name: /Enviada por tu cuenta/ }))
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
    await userEvent.type(within(dialog).getByLabelText('Fecha de la entrevista (opcional)'), '2026-10-07')
    await userEvent.type(within(dialog).getByLabelText('Hora (opcional)'), '10:30')
    await userEvent.type(within(dialog).getByLabelText('Lugar o enlace (opcional)'), 'https://meet.example/x')
    await userEvent.click(register)

    await waitFor(() => expect(calls.some((c) => c.path === '/jobs/2/milestones')).toBe(true))
    const post = calls.find((c) => c.path === '/jobs/2/milestones')
    expect(post?.body).toMatchObject({
      kind: 'interview',
      starts_at: '2026-10-07T10:30:00+02:00',
      location: 'https://meet.example/x',
      all_day: false,
    })
    expect(calls.some((c) => c.path === '/jobs/2/events')).toBe(false)
  })

  it('una entrevista con fecha y sin hora cuenta todo el día', async () => {
    const calls = mockApi(routes({ 'POST /jobs/2/milestones': { id: 8 } }))
    renderApp('/procesos')
    await userEvent.click(await screen.findByRole('button', { name: 'Actualizar estado de «Oferta 2»' }))
    const dialog = await screen.findByRole('dialog')
    await userEvent.click(within(dialog).getByRole('radio', { name: /Entrevista programada/ }))
    await userEvent.type(within(dialog).getByLabelText('Fecha de la entrevista (opcional)'), '2026-10-07')
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

  it('los seguimientos vencidos se cuentan en «Procesos» de la barra lateral', async () => {
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
    expect(await screen.findByRole('link', { name: 'Procesos (1 sin respuesta)' })).toHaveAttribute('href', '/procesos')
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

