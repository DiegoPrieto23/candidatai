import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { ReplyInboxItem } from '@/api/client'
import { jobView, mockApi, renderApp, status } from '@/test/utils'

const launcher = { available: true, agent: 'claude', reason: null, actions: [] }

/** Respuesta ficticia (como las de demo/emails/respuestas/). */
function reply(id: number, changes: Partial<ReplyInboxItem> = {}): ReplyInboxItem {
  return {
    reply_id: id,
    status: 'proposed',
    received_at: '2026-10-05T07:12:00Z',
    sender: 'laura.pazos@bretema.example',
    sender_name: 'Laura Pazos',
    subject: 'Entrevista para Data Engineer',
    risk_flags: [],
    candidates: [{ job_id: 1, title: 'Data Engineer', company: 'Brétema Analytics', stage: 'applied', reason: 'company_name' }],
    job_id: 1,
    proposal: {
      job_id: 1,
      event_type: 'interview_scheduled',
      occurred_at: null,
      milestone: {
        title: 'Entrevista con el equipo',
        starts_at: '2026-10-08T10:00:00+02:00',
        ends_at: '2026-10-08T10:45:00+02:00',
        all_day: false,
        location: 'Google Meet',
      },
      summary: 'Proponen entrevista por Meet el jueves 8 a las 10:00; piden confirmar.',
      confidence: 'high',
      injection_suspected: false,
    },
    proposed_by: 'claude-code',
    valid_now: true,
    event_id: null,
    resolved_at: null,
    ...changes,
  }
}

function inbox(replies: ReplyInboxItem[]) {
  const counts = { new: 0, proposed: 0, accepted: 0, ignored: 0 }
  for (const r of replies) counts[r.status] += 1
  return { replies, counts }
}

const decided = (status: 'accepted' | 'ignored') => ({
  ok: true,
  reply_id: 1,
  status,
  job_id: 1,
  event_id: status === 'accepted' ? 30 : null,
  milestone_id: null,
  stage: status === 'accepted' ? 'in_process' : null,
  message: 'Hecho.',
})

function mockReplies(replies: ReplyInboxItem[], extra: Record<string, unknown> = {}) {
  return mockApi({
    'GET /status': status(),
    'GET /agent': launcher,
    'GET /replies': inbox(replies),
    ...Object.fromEntries(
      replies.map((r) => [`GET /replies/${r.reply_id}`, { ...r, body_text: `Hola:\n<b>Texto del correo ${r.reply_id}</b>` }]),
    ),
    ...extra,
  })
}

describe('Respuestas', () => {
  it('enseña la propuesta en una frase y el correo como texto', async () => {
    mockReplies([reply(1)])
    renderApp('/respuestas')

    expect(
      await screen.findByText('Parece una invitación a entrevista el jueves 8 de octubre a las 10:00.'),
    ).toBeInTheDocument()
    expect(screen.getByText('Clara')).toBeInTheDocument()
    // El correo se ve como texto: las etiquetas no se interpretan.
    expect(await screen.findByText(/<b>Texto del correo 1<\/b>/)).toBeInTheDocument()
    // Sin correos sin clasificar no sale el botón del agente.
    expect(screen.queryByRole('button', { name: /Revisar respuestas/ })).not.toBeInTheDocument()
    const nav = screen.getByRole('link', { name: /^Respuestas/ })
    expect(await within(nav).findByText('1')).toBeInTheDocument()
  })

  it('Aceptar manda la propuesta tal cual', async () => {
    const calls = mockReplies([reply(1)], { 'POST /replies/1/accept': decided('accepted') })
    renderApp('/respuestas')

    await userEvent.click(await screen.findByRole('button', { name: 'Aceptar' }))

    await waitFor(() => expect(calls.some((c) => c.path === '/replies/1/accept')).toBe(true))
    const body = calls.find((c) => c.path === '/replies/1/accept')?.body as Record<string, unknown>
    expect(body).toMatchObject({
      job_id: 1,
      event_type: 'interview_scheduled',
      milestone: { starts_at: '2026-10-08T10:00:00+02:00', location: 'Google Meet' },
    })
  })

  it('Cambiar deja corregir el tipo antes de registrar', async () => {
    const calls = mockReplies([reply(1)], { 'POST /replies/1/accept': decided('accepted') })
    renderApp('/respuestas')

    await userEvent.click(await screen.findByRole('button', { name: 'Cambiar' }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByLabelText('Fecha y hora (opcional)')).toHaveValue('2026-10-08T10:00')
    await userEvent.click(within(dialog).getByRole('radio', { name: 'Rechazo' }))
    await userEvent.type(within(dialog).getByLabelText('Nota (opcional)'), 'Lo leo así.')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Registrar' }))

    await waitFor(() => expect(calls.some((c) => c.path === '/replies/1/accept')).toBe(true))
    const body = calls.find((c) => c.path === '/replies/1/accept')?.body
    expect(body).toMatchObject({ job_id: 1, event_type: 'rejected', milestone: null, note: 'Lo leo así.' })
  })

  it('Ignorar no registra nada', async () => {
    const calls = mockReplies([reply(1)], { 'POST /replies/1/ignore': decided('ignored') })
    renderApp('/respuestas')

    await userEvent.click(await screen.findByRole('button', { name: 'Ignorar' }))

    await waitFor(() => expect(calls.some((c) => c.path === '/replies/1/ignore')).toBe(true))
    expect(calls.find((c) => c.path === '/replies/1/ignore')?.body).toEqual({})
    expect(calls.some((c) => c.path.endsWith('/accept'))).toBe(false)
  })

  it('sin ninguna respuesta, lleva a conectar el correo', async () => {
    mockApi({ 'GET /status': status(), 'GET /replies': { replies: [], counts: {} } })
    renderApp('/respuestas')
    expect(await screen.findByText('Aún no hay respuestas')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Conectar tu correo' })).toHaveAttribute('href', '/alertas')
  })

  it('con correos sin clasificar ofrece abrir tu agente y avisa del riesgo', async () => {
    mockReplies([
      reply(2, {
        status: 'new',
        proposal: null,
        valid_now: null,
        sender: 'seleccion@castrolabs.example',
        sender_name: 'Castro Labs',
        risk_flags: ['hidden_text', 'injection_phrase'],
      }),
    ])
    renderApp('/respuestas')

    expect(await screen.findByRole('button', { name: /Revisar respuestas/ })).toBeInTheDocument()
    expect(screen.getByText(/1 correo sin clasificar/)).toBeInTheDocument()
    expect(screen.getByText(/Sin clasificar todavía/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Aceptar' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Decidir' })).toBeInTheDocument()
    expect(screen.getByRole('note')).toHaveTextContent('texto oculto y frases que parecen instrucciones para una IA')
  })

  it('«Revisar correo ahora» lee el correo y enseña el resultado', async () => {
    const calls = mockReplies([], {
      'POST /replies/poll': { processes: 2, checked: 40, created: 0, reply_ids: [], errors: [], message: 'Sin respuestas nuevas.' },
    })
    renderApp('/respuestas')

    await userEvent.click(await screen.findByRole('button', { name: /Revisar correo ahora/ }))

    expect(await screen.findByText('Sin respuestas nuevas.')).toBeInTheDocument()
    expect(calls.some((c) => c.method === 'POST' && c.path === '/replies/poll')).toBe(true)
  })
})

describe('Ficha de la oferta con una respuesta por revisar', () => {
  it('avisa con la propuesta y deja aceptarla allí mismo', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /agent': launcher,
      'GET /jobs/1': jobView({ stage: 'applied' }),
      'GET /replies': (_req: Request, url: URL) =>
        url.searchParams.get('job_id') === '1' ? inbox([reply(1)]) : inbox([]),
      'POST /replies/1/accept': decided('accepted'),
    })
    renderApp('/jobs/1')

    const notice = await screen.findByRole('region', { name: 'Respuesta de la empresa por revisar' })
    expect(
      within(notice).getByText('Parece una invitación a entrevista el jueves 8 de octubre a las 10:00.'),
    ).toBeInTheDocument()
    expect(within(notice).getByRole('link', { name: 'Ver el correo' })).toHaveAttribute('href', '/respuestas?correo=1')
    expect(within(notice).getByRole('button', { name: 'Cambiar' })).toBeInTheDocument()
    await userEvent.click(within(notice).getByRole('button', { name: 'Aceptar' }))
    await waitFor(() => expect(calls.some((c) => c.path === '/replies/1/accept')).toBe(true))
  })
})
