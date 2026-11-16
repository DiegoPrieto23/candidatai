import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { AssistantView } from '@/api/client'
import { mockApi, renderApp, status } from '@/test/utils'

const emptyPage = { items: [], total: 0, limit: 50, offset: 0 }

function launcher(background = true, noAgent = false) {
  return {
    available: !noAgent,
    agent: noAgent ? null : 'claude',
    reason: null,
    no_agent_installed: noAgent,
    background: { available: background, agent: background ? 'claude' : null, reason: null },
    actions: [
      {
        id: 'assistant',
        label: 'Asistente',
        needs_job: false,
        prompt: null,
        background: true,
        background_agent: { available: background, agent: background ? 'claude' : null, reason: null },
      },
    ],
  }
}

function request(changes: Partial<AssistantView> = {}): AssistantView {
  return {
    id: 1,
    text: '¿Qué tengo pendiente?',
    mode: 'background',
    status: 'done',
    answer: 'Tienes 1 oferta por revisar.',
    links: [
      { job_id: 7, screen: null, label: 'Data Engineer · Acme' },
      { job_id: null, screen: 'inbox', label: null },
    ],
    questions: [],
    error: null,
    progress: [],
    agent: 'claude',
    run_id: 3,
    created_at: '2026-11-14T10:00:00Z',
    finished_at: '2026-11-14T10:01:00Z',
    ...changes,
  }
}

async function openAssistant(extra: Record<string, unknown>) {
  const calls = mockApi({
    'GET /status': status(),
    'GET /jobs': emptyPage,
    'GET /agent': launcher(),
    'GET /agent/assistant': { requests: [] },
    'GET /prompts/pending': { prompts: [] },
    ...extra,
  })
  renderApp('/bandeja')
  await screen.findByText('Tu bandeja está vacía')
  // El botón con rótulo de la esquina abre el panel directamente en la pestaña del agente.
  await userEvent.click(screen.getByRole('button', { name: 'Asistente' }))
  const panel = screen.getByRole('dialog', { name: 'Tu asistente' })
  expect(within(panel).getByRole('tab', { name: 'Asistente' })).toHaveAttribute('aria-selected', 'true')
  return { calls, panel }
}

describe('Asistente', () => {
  it('la primera vez propone ejemplos que se escriben en la caja sin enviarse', async () => {
    const { calls, panel } = await openAssistant({})
    const examples = await within(panel).findByRole('region', { name: 'Ejemplos de peticiones' })
    await userEvent.click(within(examples).getByRole('button', { name: '¿Qué empresas no me han contestado?' }))
    const field = within(panel).getByRole('textbox', { name: 'Qué quieres pedirle a tu agente' })
    expect(field).toHaveValue('¿Qué empresas no me han contestado?')
    expect(field).toHaveFocus()
    expect(calls.some((call) => call.method === 'POST')).toBe(false)
    expect(within(examples).getByText(/los confirmas siempre tú/)).toBeInTheDocument()
  })

  it('el botón del agente y el «?» cambian de pestaña y, pulsados otra vez, cierran', async () => {
    await openAssistant({})
    const help = screen.getByRole('button', { name: 'Ayuda' })
    await userEvent.click(help)
    expect(screen.getByRole('dialog', { name: 'Ayuda' })).toBeInTheDocument()
    expect(help).toHaveAttribute('aria-expanded', 'true')
    await userEvent.click(help)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('Intro envía en segundo plano y vacía la caja; Mayús+Intro salta de línea', async () => {
    const { calls, panel } = await openAssistant({ 'POST /agent/assistant': request({ status: 'queued', answer: null, links: [] }) })
    const field = within(panel).getByRole('textbox', { name: 'Qué quieres pedirle a tu agente' })
    expect(field).toHaveFocus()
    expect(field).toHaveAttribute('maxlength', '2000')
    const send = await within(panel).findByRole('button', { name: 'Enviar' })
    expect(send).toBeDisabled()
    // Ni rastro de los dos botones de antes.
    expect(within(panel).queryByRole('button', { name: 'Enviar ahora' })).not.toBeInTheDocument()
    expect(within(panel).queryByRole('button', { name: 'Dejar para mi próxima sesión' })).not.toBeInTheDocument()

    await userEvent.type(field, '  ¿Qué tengo{Shift>}{Enter}{/Shift}pendiente?  ')
    expect(field).toHaveValue('  ¿Qué tengo\npendiente?  ')
    expect(calls.some((call) => call.method === 'POST')).toBe(false)
    expect(send).toBeEnabled()

    await userEvent.keyboard('{Enter}')
    const post = calls.find((call) => call.method === 'POST' && call.path === '/agent/assistant')
    expect(post?.body).toEqual({ text: '¿Qué tengo\npendiente?', mode: 'background' })
    expect(field).toHaveValue('')
  })

  it('la flecha también envía, y con la caja vacía o en blanco no hace nada', async () => {
    const { calls, panel } = await openAssistant({ 'POST /agent/assistant': request({ status: 'queued', answer: null, links: [] }) })
    const field = within(panel).getByRole('textbox', { name: 'Qué quieres pedirle a tu agente' })
    await userEvent.type(field, '   {Enter}')
    expect(calls.some((call) => call.method === 'POST')).toBe(false)
    expect(within(panel).getByRole('button', { name: 'Enviar' })).toBeDisabled()
    await userEvent.type(field, 'Resume mis procesos')
    await userEvent.click(within(panel).getByRole('button', { name: 'Enviar' }))
    expect(calls.find((call) => call.method === 'POST')?.body).toEqual({ text: 'Resume mis procesos', mode: 'background' })
  })

  it('enseña la respuesta con enlaces a la oferta y a la pantalla', async () => {
    const { panel } = await openAssistant({ 'GET /agent/assistant': { requests: [request()] } })
    const history = await within(panel).findByRole('log', { name: 'Peticiones anteriores' })
    expect(within(history).getByText('Tienes 1 oferta por revisar.')).toBeInTheDocument()
    expect(within(history).getByRole('link', { name: 'Data Engineer · Acme' })).toHaveAttribute('href', '/jobs/7')
    expect(within(history).getByRole('link', { name: 'Ir a «Bandeja de ofertas»' })).toHaveAttribute('href', '/bandeja')
    expect(within(history).queryByRole('button', { name: 'Cancelar' })).not.toBeInTheDocument()
  })

  it('mientras trabaja, enseña el progreso y deja cancelar', async () => {
    const running = request({
      status: 'running',
      answer: null,
      links: [],
      finished_at: null,
      progress: [{ at: '2026-11-14T10:00:05Z', kind: 'tool', text: 'list_jobs' }],
    })
    const { calls, panel } = await openAssistant({
      'GET /agent/assistant': { requests: [running] },
      'POST /agent/assistant/1/cancel': { status: 200, body: request({ status: 'cancelled', answer: null, links: [] }) },
    })
    expect(await within(panel).findByText('Tu agente está trabajando · list_jobs')).toBeInTheDocument()
    await userEvent.click(within(panel).getByRole('button', { name: 'Cancelar' }))
    expect(calls.some((call) => call.method === 'POST' && call.path === '/agent/assistant/1/cancel')).toBe(true)
  })

  it('con una pregunta del agente pendiente, dice que espera tu respuesta', async () => {
    const running = request({ status: 'running', answer: null, links: [], finished_at: null })
    const question = {
      id: 4,
      kind: 'question',
      title: 'Tu agente pregunta',
      message: '¿De qué oferta hablas?',
      url: null,
      source_id: null,
      source_name: null,
      attempt_id: null,
      status: 'pending',
      created_at: '2026-11-14T10:00:00Z',
      expires_at: '2026-11-14T10:10:00Z',
      answered_at: null,
      seconds_left: 590,
      options: ['La 1', 'La 2'],
      answer: null,
      job_id: null,
    }
    // La pregunta llega con el panel ya abierto: el aviso es un diálogo modal.
    let asked = false
    const { panel } = await openAssistant({
      'GET /agent/assistant': { requests: [running] },
      'GET /prompts/pending': () => ({ prompts: asked ? [question] : [] }),
    })
    await within(panel).findByText('Tu agente está trabajando')
    asked = true
    // La pregunta en sí la enseña el aviso de la app (`UserPrompts`), que es un diálogo aparte.
    // Los avisos se consultan cada 4 s.
    expect(await within(panel).findByText('Tu agente espera tu respuesta en el aviso', {}, { timeout: 8000 })).toBeInTheDocument()
    expect(await screen.findByText('¿De qué oferta hablas?')).toBeInTheDocument()
  }, 15000)

  it('si falla, dice por qué', async () => {
    const failed = request({ status: 'failed', answer: null, links: [], error: 'Superó el tiempo máximo (30 min).' })
    const { panel } = await openAssistant({ 'GET /agent/assistant': { requests: [failed] } })
    expect(await within(panel).findByText('No se pudo completar. Superó el tiempo máximo (30 min).')).toBeInTheDocument()
  })

  it('sin segundo plano, la misma flecha lo deja como encargo y el hilo lo dice', async () => {
    const waiting = request({ id: 2, status: 'waiting', mode: 'session', answer: null, links: [], finished_at: null })
    let sent = false
    const { calls, panel } = await openAssistant({
      'GET /agent': launcher(false),
      'GET /agent/assistant': () => ({ requests: sent ? [waiting] : [] }),
      'POST /agent/assistant': () => {
        sent = true
        return waiting
      },
    })
    await userEvent.type(within(panel).getByRole('textbox'), 'Resume mis procesos{Enter}')
    await waitFor(() => expect(calls.some((call) => call.method === 'POST')).toBe(true))
    expect(calls.find((call) => call.method === 'POST')?.body).toEqual({ text: 'Resume mis procesos', mode: 'session' })
    expect(await within(panel).findByText('Se lo pasaré a tu agente en tu próxima sesión')).toBeInTheDocument()
  })

  it('si se envía antes de saber si hay segundo plano, espera a saberlo y no se pierde', async () => {
    let release: (value: unknown) => void = () => {}
    const slow = new Promise((resolve) => (release = resolve))
    const { calls, panel } = await openAssistant({
      'GET /agent': () => slow,
      'POST /agent/assistant': request({ status: 'queued', answer: null, links: [] }),
    })
    const field = within(panel).getByRole('textbox', { name: 'Qué quieres pedirle a tu agente' })
    await userEvent.type(field, 'Hola{Enter}')
    expect(calls.some((call) => call.method === 'POST')).toBe(false)
    expect(within(panel).getByRole('button', { name: 'Enviar' })).toBeDisabled()
    // Mientras espera, la caja no se edita: se envía justo lo que pulsaste.
    expect(field).toHaveAttribute('readonly')
    await userEvent.type(field, ' y adiós')
    expect(field).toHaveValue('Hola')
    release(launcher())
    await waitFor(() => expect(calls.some((call) => call.method === 'POST')).toBe(true))
    expect(calls.find((call) => call.method === 'POST')?.body).toEqual({ text: 'Hola', mode: 'background' })
    expect(field).toHaveValue('')
  })

  it('pregunta a la derecha y respuesta a la izquierda, en orden y con un separador por día', async () => {
    // Hace diez días a mediodía: ni «Hoy» ni «Ayer», y del año en curso salvo a primeros de enero.
    const tenDaysAgo = new Date(Date.now() - 10 * 86_400_000)
    tenDaysAgo.setUTCHours(11, 0, 0, 0)
    const older = request({ id: 1, text: 'Primera', answer: 'Respuesta uno', links: [], created_at: tenDaysAgo.toISOString() })
    const sameYear = tenDaysAgo.getUTCFullYear() === new Date().getUTCFullYear()
    const olderLabel = new Intl.DateTimeFormat('es-ES', {
      timeZone: 'Europe/Madrid',
      day: 'numeric',
      month: 'short',
      ...(sameYear ? {} : { year: 'numeric' }),
    }).format(tenDaysAgo)
    const newer = request({ id: 2, text: 'Segunda', answer: 'Respuesta dos', links: [], created_at: new Date().toISOString() })
    // El servidor las da de la más nueva a la más antigua.
    const { panel } = await openAssistant({ 'GET /agent/assistant': { requests: [newer, older] } })
    const history = await within(panel).findByRole('log', { name: 'Peticiones anteriores' })
    const turns = within(history).getAllByRole('listitem')
    expect(turns.map((turn) => turn.getAttribute('aria-label'))).toEqual(['Tú', 'Tu asistente', 'Tú', 'Tu asistente'])
    expect(turns[0]).toHaveTextContent('Primera')
    expect(turns[1]).toHaveTextContent('Respuesta uno')
    expect(turns[2]).toHaveTextContent('Segunda')
    expect(within(history).getByText(olderLabel)).toBeInTheDocument()
    expect(within(history).getByText('Hoy')).toBeInTheDocument()
    // La fecha ya no va delante de cada pregunta.
    expect(within(history).queryByText(/Pedido el/)).not.toBeInTheDocument()
    // Lo que confirmas tú, en una ayuda junto a la caja.
    expect(within(panel).getByRole('button', { name: 'Qué confirmas tú' })).toBeInTheDocument()
  })

  it('sin agente instalado lo dice y la pestaña «Ayuda» sigue funcionando', async () => {
    const { panel } = await openAssistant({ 'GET /agent': launcher(false, true) })
    expect(await within(panel).findByText('Para pedirle algo a tu agente, instala uno')).toBeInTheDocument()
    expect(within(panel).queryByRole('textbox')).not.toBeInTheDocument()
    expect(within(panel).getByRole('link', { name: 'Ir a «Agente»' })).toHaveAttribute('href', '/agente')
    await userEvent.click(within(panel).getByRole('tab', { name: 'Ayuda' }))
    expect(within(panel).getByRole('searchbox', { name: 'Buscar en la ayuda' })).toHaveFocus()
  })
})
