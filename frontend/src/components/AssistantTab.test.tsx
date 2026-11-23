import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import type { AssistantView } from '@/api/client'
import { mockApi, renderApp, status } from '@/test/utils'

const emptyPage = { items: [], total: 0, limit: 50, offset: 0 }

/** `terminal`: tu agente no trabaja en segundo plano pero se puede abrir en una terminal. */
function launcher(background = true, noAgent = false, terminal = false) {
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
        ...(terminal && {
          agent: { agent: 'antigravity', display_name: 'Antigravity CLI', reason: 'first_installed', reason_text: '', blocked: null },
        }),
      },
    ],
  }
}

function request(changes: Partial<AssistantView> = {}): AssistantView {
  return {
    id: 1,
    conversation_id: 1,
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

/** La conversación 1 con estas peticiones (en orden), en el historial y abierta. */
function conversation(requests: AssistantView[], title = '¿Qué tengo pendiente?') {
  const summary = {
    id: 1,
    title,
    created_at: requests[0]?.created_at ?? '2026-11-14T10:00:00Z',
    updated_at: requests.at(-1)?.created_at ?? '2026-11-14T10:00:00Z',
    active: requests.some((item) => item.status === 'queued' || item.status === 'running'),
  }
  return {
    'GET /agent/assistant/conversations': { conversations: [summary] },
    'GET /agent/assistant/conversations/1': { ...summary, requests },
  }
}

beforeEach(() => localStorage.clear())

async function openAssistant(extra: Record<string, unknown>) {
  const calls = mockApi({
    'GET /status': status(),
    'GET /jobs': emptyPage,
    'GET /agent': launcher(),
    'GET /agent/assistant/conversations': { conversations: [] },
    'GET /agent/assistant/conversations/1': { id: 1, title: 'x', created_at: '2026-11-14T10:00:00Z', updated_at: '2026-11-14T10:00:00Z', requests: [] },
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

/** Abre la barra de conversaciones y, en ella, la conversación con este título. */
async function openFromHistory(panel: HTMLElement, title: string | RegExp) {
  await userEvent.click(within(panel).getByRole('button', { name: 'Conversaciones anteriores' }))
  const sidebar = within(panel).getByRole('navigation', { name: 'Conversaciones' })
  await userEvent.click(await within(sidebar).findByRole('button', { name: title }))
  return sidebar
}

/** Las clases que dan el tamaño al panel: alto, ancho y su tope. */
const sizeOf = (panel: HTMLElement) =>
  panel.className
    .split(/\s+/)
    .filter((c) => /^(h|w|max-w|max-h)-/.test(c))
    .sort()
    .join(' ')

describe('Asistente', () => {
  it('el panel mide lo mismo en las dos pestañas y con la barra abierta; solo el cuerpo hace scroll', async () => {
    const { panel } = await openAssistant({})
    const size = sizeOf(panel)
    expect(size).toContain('h-[min(36rem,calc(100dvh-6rem))]')
    const conversation = within(panel).getByRole('region', { name: 'Conversación' })
    expect(conversation).toHaveAttribute('tabindex', '0')
    expect(conversation).toHaveClass('overflow-y-auto', 'min-h-0', 'flex-1')

    await userEvent.click(within(panel).getByRole('button', { name: 'Conversaciones anteriores' }))
    expect(sizeOf(screen.getByRole('dialog', { name: 'Tu asistente' }))).toBe(size)

    await userEvent.click(within(panel).getByRole('tab', { name: 'Ayuda' }))
    const help = screen.getByRole('dialog', { name: 'Ayuda' })
    expect(sizeOf(help)).toBe(size)
    const body = within(help).getByRole('region', { name: 'Preguntas frecuentes y guía' })
    expect(body).toHaveAttribute('tabindex', '0')
    expect(body).toHaveClass('overflow-y-auto')
  })

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
    expect(post?.body).toEqual({ text: '¿Qué tengo\npendiente?', mode: 'background', conversation_id: null, lang: 'es' })
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
    expect(calls.find((call) => call.method === 'POST')?.body).toEqual({ text: 'Resume mis procesos', mode: 'background', conversation_id: null, lang: 'es' })
  })

  it('enseña la respuesta con enlaces a la oferta y a la pantalla', async () => {
    const { panel } = await openAssistant(conversation([request()]))
    await openFromHistory(panel, '¿Qué tengo pendiente?')
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
      ...conversation([running]),
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
      ...conversation([running]),
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
    const { panel } = await openAssistant(conversation([failed]))
    await openFromHistory(panel, '¿Qué tengo pendiente?')
    expect(await within(panel).findByText('No se pudo completar. Superó el tiempo máximo (30 min).')).toBeInTheDocument()
  })

  it('sin segundo plano, la misma flecha lo deja como encargo y el hilo lo dice', async () => {
    const waiting = request({ id: 2, status: 'waiting', mode: 'session', answer: null, links: [], finished_at: null })
    let sent = false
    const { calls, panel } = await openAssistant({
      'GET /agent': launcher(false),
      'GET /agent/assistant/conversations/1': () => ({ ...conversation([waiting])['GET /agent/assistant/conversations/1'], requests: sent ? [waiting] : [] }),
      'POST /agent/assistant': () => {
        sent = true
        return waiting
      },
    })
    await userEvent.type(within(panel).getByRole('textbox'), 'Resume mis procesos{Enter}')
    await waitFor(() => expect(calls.some((call) => call.method === 'POST')).toBe(true))
    expect(calls.find((call) => call.method === 'POST')?.body).toEqual({ text: 'Resume mis procesos', mode: 'session', conversation_id: null, lang: 'es' })
    expect(await within(panel).findByText('Se lo pasaré a tu agente en tu próxima sesión')).toBeInTheDocument()
  })

  it('sin segundo plano pero con terminal, la abre y la respuesta llega aquí', async () => {
    const open = request({ id: 2, status: 'terminal', mode: 'terminal', answer: null, links: [], run_id: null, finished_at: null, agent: 'antigravity' })
    let sent = false
    const { calls, panel } = await openAssistant({
      'GET /agent': launcher(false, false, true),
      'GET /agent/assistant/conversations/1': () => ({ ...conversation([open])['GET /agent/assistant/conversations/1'], requests: sent ? [open] : [] }),
      'POST /agent/assistant': () => {
        sent = true
        return open
      },
    })
    await userEvent.type(within(panel).getByRole('textbox'), 'Resume mis procesos{Enter}')
    await waitFor(() => expect(calls.some((call) => call.method === 'POST')).toBe(true))
    expect(calls.find((call) => call.method === 'POST')?.body).toEqual({ text: 'Resume mis procesos', mode: 'terminal', conversation_id: null, lang: 'es' })
    expect(
      await within(panel).findByText('Tu agente está trabajando en la terminal que se ha abierto: la respuesta aparecerá aquí'),
    ).toBeInTheDocument()
    expect(within(panel).getByRole('button', { name: 'Cancelar' })).toBeInTheDocument()
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
    expect(calls.find((call) => call.method === 'POST')?.body).toEqual({ text: 'Hola', mode: 'background', conversation_id: null, lang: 'es' })
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
    const { panel } = await openAssistant(conversation([older, newer], 'Primera'))
    await openFromHistory(panel, 'Primera')
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

  it('al abrir empieza una conversación nueva; las anteriores, en la barra por fechas', async () => {
    const now = new Date().toISOString()
    const lastWeek = new Date(Date.now() - 3 * 86_400_000).toISOString()
    const long = 'Resúmeme cómo va mi búsqueda este mes y dime qué ofertas…'
    const { panel } = await openAssistant({
      'GET /agent/assistant/conversations': {
        conversations: [
          { id: 1, title: '¿Qué tengo pendiente?', created_at: now, updated_at: now, active: false },
          { id: 2, title: long, created_at: lastWeek, updated_at: lastWeek, active: false },
        ],
      },
    })
    // Nada de la conversación anterior: los ejemplos de una nueva.
    expect(await within(panel).findByRole('region', { name: 'Ejemplos de peticiones' })).toBeInTheDocument()
    expect(within(panel).queryByRole('log')).not.toBeInTheDocument()
    const toggle = within(panel).getByRole('button', { name: 'Conversaciones anteriores' })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    await userEvent.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    const sidebar = within(panel).getByRole('navigation', { name: 'Conversaciones' })
    const today = await within(sidebar).findByRole('region', { name: 'Hoy' })
    expect(within(today).getByRole('button', { name: '¿Qué tengo pendiente?' })).toBeInTheDocument()
    const week = within(sidebar).getByRole('region', { name: 'Últimos 7 días' })
    // El título entero en la ayuda; la barra lo corta con «…» si no cabe.
    expect(within(week).getByRole('button', { name: long })).toHaveAttribute('title', long)
  })

  it('una pregunta en una conversación abierta va en ella; «Nueva conversación» empieza otra', async () => {
    const { calls, panel } = await openAssistant({
      ...conversation([request()]),
      'POST /agent/assistant': request({ id: 2, text: '¿Y mañana?', status: 'queued', answer: null, links: [] }),
    })
    const sidebar = await openFromHistory(panel, '¿Qué tengo pendiente?')
    expect(within(sidebar).getByRole('button', { name: '¿Qué tengo pendiente?' })).toHaveAttribute('aria-current', 'true')
    expect(await within(panel).findByText('Tienes 1 oferta por revisar.')).toBeInTheDocument()
    const field = within(panel).getByRole('textbox', { name: 'Qué quieres pedirle a tu agente' })
    await userEvent.type(field, '¿Y mañana?{Enter}')
    await waitFor(() => expect(calls.some((call) => call.method === 'POST')).toBe(true))
    expect(calls.find((call) => call.method === 'POST')?.body).toEqual({ text: '¿Y mañana?', mode: 'background', conversation_id: 1, lang: 'es' })

    // El de la cabecera (la barra tiene otro igual).
    await userEvent.click(within(panel.querySelector('header')!).getByRole('button', { name: 'Nueva conversación' }))
    expect(await within(panel).findByRole('region', { name: 'Ejemplos de peticiones' })).toBeInTheDocument()
    expect(within(panel).queryByText('Tienes 1 oferta por revisar.')).not.toBeInTheDocument()
    expect(within(sidebar).getByRole('button', { name: '¿Qué tengo pendiente?' })).not.toHaveAttribute('aria-current')
    expect(field).toHaveFocus()
  })

  it('con tu agente trabajando en una, el panel abre esa', async () => {
    const running = request({ status: 'running', answer: null, links: [], finished_at: null })
    const { panel } = await openAssistant(conversation([running]))
    expect(await within(panel).findByText('Tu agente está trabajando')).toBeInTheDocument()
  })

  it('borrar una conversación pide confirmación y, si era la abierta, deja una nueva', async () => {
    let deleted = false
    const routes = conversation([request()])
    const { calls, panel } = await openAssistant({
      ...routes,
      'GET /agent/assistant/conversations': () => (deleted ? { conversations: [] } : routes['GET /agent/assistant/conversations']),
      'DELETE /agent/assistant/conversations/1': () => {
        deleted = true
        return { status: 200, body: {} }
      },
    })
    const sidebar = await openFromHistory(panel, '¿Qué tengo pendiente?')
    await within(panel).findByText('Tienes 1 oferta por revisar.')
    await userEvent.click(within(sidebar).getByRole('button', { name: 'Borrar «¿Qué tengo pendiente?»' }))
    expect(within(sidebar).getByText(/si tu agente sigue con ella, se cancela/i)).toBeInTheDocument()
    expect(calls.some((call) => call.method === 'DELETE')).toBe(false)
    // «Cancelar» no borra nada.
    await userEvent.click(within(sidebar).getByRole('button', { name: 'Cancelar' }))
    expect(calls.some((call) => call.method === 'DELETE')).toBe(false)
    await userEvent.click(within(sidebar).getByRole('button', { name: 'Borrar «¿Qué tengo pendiente?»' }))
    await userEvent.click(within(sidebar).getByRole('button', { name: 'Borrar' }))
    await waitFor(() => expect(calls.some((call) => call.method === 'DELETE')).toBe(true))
    expect(await within(panel).findByRole('region', { name: 'Ejemplos de peticiones' })).toBeInTheDocument()
    expect(await within(sidebar).findByText('Tus conversaciones aparecerán aquí.')).toBeInTheDocument()
  })

  it('Esc en la confirmación de borrar la cancela sin cerrar el panel', async () => {
    const { calls, panel } = await openAssistant(conversation([request()]))
    const sidebar = await openFromHistory(panel, '¿Qué tengo pendiente?')
    const trash = within(sidebar).getByRole('button', { name: 'Borrar «¿Qué tengo pendiente?»' })
    await userEvent.click(trash)
    // El foco, en lo que no borra.
    expect(within(sidebar).getByRole('button', { name: 'Cancelar' })).toHaveFocus()
    await userEvent.keyboard('{Escape}')
    expect(screen.getByRole('dialog', { name: 'Tu asistente' })).toBeInTheDocument()
    expect(within(sidebar).queryByRole('button', { name: 'Cancelar' })).not.toBeInTheDocument()
    expect(within(sidebar).getByRole('button', { name: 'Borrar «¿Qué tengo pendiente?»' })).toHaveFocus()
    expect(calls.some((call) => call.method === 'DELETE')).toBe(false)
  })

  it('si pasas a otra conversación mientras se envía, no te devuelve a la anterior', async () => {
    let release: (value: unknown) => void = () => {}
    const slow = new Promise((resolve) => (release = resolve))
    const { panel } = await openAssistant({
      ...conversation([request()]),
      'POST /agent/assistant': () => slow,
    })
    await openFromHistory(panel, '¿Qué tengo pendiente?')
    await within(panel).findByText('Tienes 1 oferta por revisar.')
    await userEvent.type(within(panel).getByRole('textbox', { name: 'Qué quieres pedirle a tu agente' }), '¿Y mañana?{Enter}')
    await userEvent.click(within(panel.querySelector('header')!).getByRole('button', { name: 'Nueva conversación' }))
    expect(await within(panel).findByRole('region', { name: 'Ejemplos de peticiones' })).toBeInTheDocument()
    release(request({ id: 2, text: '¿Y mañana?', status: 'queued', answer: null, links: [] }))
    // Sigue en la nueva.
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(within(panel).getByRole('region', { name: 'Ejemplos de peticiones' })).toBeInTheDocument()
    expect(within(panel).queryByText('Tienes 1 oferta por revisar.')).not.toBeInTheDocument()
  })

  it('la barra recuerda si la dejaste abierta', async () => {
    const { panel } = await openAssistant({})
    await userEvent.click(within(panel).getByRole('button', { name: 'Conversaciones anteriores' }))
    expect(localStorage.getItem('cai.assistant.sidebar')).toBe('open')
    await userEvent.click(within(panel).getByRole('button', { name: 'Cerrar la ayuda' }))
    await userEvent.click(screen.getByRole('button', { name: 'Asistente' }))
    expect(screen.getByRole('navigation', { name: 'Conversaciones' })).toBeInTheDocument()
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
