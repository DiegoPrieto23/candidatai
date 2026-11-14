import { screen, within } from '@testing-library/react'
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
        label: 'Pídeselo a tu agente',
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
  await userEvent.click(screen.getByRole('button', { name: 'Ayuda' }))
  const panel = screen.getByRole('dialog', { name: 'Ayuda' })
  await userEvent.click(within(panel).getByRole('tab', { name: 'Pídeselo a tu agente' }))
  return { calls, panel }
}

describe('Pídeselo a tu agente', () => {
  it('envía el texto ahora, en segundo plano, y vacía la caja', async () => {
    const { calls, panel } = await openAssistant({ 'POST /agent/assistant': request({ status: 'queued', answer: null, links: [] }) })
    const field = within(panel).getByRole('textbox', { name: 'Qué quieres pedirle a tu agente' })
    expect(field).toHaveFocus()
    expect(field).toHaveAttribute('maxlength', '2000')
    const send = await within(panel).findByRole('button', { name: 'Enviar ahora' })
    expect(send).toBeDisabled()

    await userEvent.type(field, '  ¿Qué tengo pendiente?  ')
    await userEvent.click(send)
    const post = calls.find((call) => call.method === 'POST' && call.path === '/agent/assistant')
    expect(post?.body).toEqual({ text: '¿Qué tengo pendiente?', mode: 'background' })
    expect(field).toHaveValue('')
  })

  it('«Dejar para mi próxima sesión» lo guarda como encargo', async () => {
    const { calls, panel } = await openAssistant({ 'POST /agent/assistant': request({ status: 'waiting', mode: 'session' }) })
    await userEvent.type(within(panel).getByRole('textbox'), 'Resume mis procesos')
    await userEvent.click(within(panel).getByRole('button', { name: 'Dejar para mi próxima sesión' }))
    const post = calls.find((call) => call.method === 'POST' && call.path === '/agent/assistant')
    expect(post?.body).toEqual({ text: 'Resume mis procesos', mode: 'session' })
  })

  it('enseña la respuesta con enlaces a la oferta y a la pantalla', async () => {
    const { panel } = await openAssistant({ 'GET /agent/assistant': { requests: [request()] } })
    const history = await within(panel).findByRole('region', { name: 'Peticiones anteriores' })
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

  it('sin segundo plano, solo se puede dejar para la próxima sesión', async () => {
    const { panel } = await openAssistant({ 'GET /agent': launcher(false) })
    expect(await within(panel).findByText(/no trabaja en segundo plano desde la app/)).toBeInTheDocument()
    await userEvent.type(within(panel).getByRole('textbox'), 'hola')
    expect(within(panel).getByRole('button', { name: 'Enviar ahora' })).toBeDisabled()
    expect(within(panel).getByRole('button', { name: 'Dejar para mi próxima sesión' })).toBeEnabled()
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
