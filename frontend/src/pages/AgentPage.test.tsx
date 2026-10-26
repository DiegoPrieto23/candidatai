import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { AgentRequestView, AgentRunView } from '@/api/client'
import { mockApi, renderApp, status } from '@/test/utils'

const launcher = {
  available: true,
  agent: 'claude',
  reason: null,
  background: { available: true, agent: 'claude', reason: null },
  actions: [],
}

function run(changes: Partial<AgentRunView> = {}): AgentRunView {
  return {
    id: 1,
    action: 'process-jobs',
    label: 'Procesar ofertas',
    job_id: null,
    milestone_id: null,
    agent: 'claude',
    model: null,
    status: 'done',
    prompt: 'Usa el skill process-jobs…',
    allowed_tools: ['get_status', 'list_jobs', 'get_job', 'save_extraction'],
    progress: [
      { at: '2026-10-12T10:00:00Z', kind: 'tool', text: 'list_jobs' },
      { at: '2026-10-12T10:00:01Z', kind: 'tool', text: 'Subagente «extractor»' },
    ],
    result: 'Procesadas 2 ofertas.',
    questions: [],
    error: null,
    usage: null,
    cancel_requested: false,
    can_resume: true,
    created_at: '2026-10-12T10:00:00Z',
    started_at: '2026-10-12T10:00:00Z',
    finished_at: '2026-10-12T10:01:30Z',
    ...changes,
  }
}

function request(changes: Partial<AgentRequestView> = {}): AgentRequestView {
  return {
    id: 7,
    action: 'generate-cv',
    label: 'Generar CV',
    job_id: 42,
    milestone_id: null,
    prompt: 'Usa el skill generate-cv de CandidatAI para la oferta 42.',
    status: 'pending',
    summary: null,
    agent_name: null,
    created_at: '2026-10-12T09:00:00Z',
    completed_at: null,
    ...changes,
  }
}

describe('Página «Agente» (fase 19)', () => {
  it('cada ejecución dice con qué agente y modelo se lanzó (fase 24.4)', async () => {
    mockApi({
      'GET /status': status(),
      'GET /agent': launcher,
      'GET /agent/runs': { active: 0, runs: [run({ id: 4, model: 'sonnet' }), run({ id: 5, agent: 'opencode' })] },
      'GET /agent/requests': { pending: 0, requests: [] },
    })
    renderApp('/agente')
    expect(await screen.findByText(/Con claude \(sonnet\)/)).toBeInTheDocument()
    expect(screen.getByText(/Con opencode ·/)).toBeInTheDocument()
  })

  it('cada ejecución enseña su uso: turnos, tokens y coste (fase 24.5)', async () => {
    const usage = { turns: 3, input_tokens: 35464, output_tokens: 61, cost_usd: 0.0123 }  // claves comunes (25.4)
    mockApi({
      'GET /status': status(),
      'GET /agent': launcher,
      'GET /agent/runs': { active: 0, runs: [run({ id: 6, agent: 'opencode', usage }), run({ id: 7 })] },
      'GET /agent/requests': { pending: 0, requests: [] },
    })
    renderApp('/agente')
    const line = await screen.findByText(/3 turnos/)
    expect(line).toHaveTextContent(/35.?464 tokens de entrada y 61 de salida/)
    expect(line).toHaveTextContent('0.0123 USD estimados')
    expect(screen.getAllByText(/\d+ turnos?\b/)).toHaveLength(1) // sin uso, no se enseña nada
  })

  it('enseña las ejecuciones con su estado, progreso y preguntas', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /agent': launcher,
      'GET /agent/runs': {
        active: 1,
        runs: [
          run({ id: 3, status: 'running', finished_at: null, result: null, can_resume: false }),
          run({
            id: 2,
            action: 'generate-cv',
            label: 'Generar CV',
            job_id: 42,
            status: 'needs_user',
            questions: ['La oferta parece cerrada, ¿redacto igualmente?'],
          }),
          run(),
        ],
      },
      'GET /agent/requests': { pending: 0, requests: [] },
      'POST /agent/runs/3/cancel': run({ id: 3, status: 'running', cancel_requested: true }),
      'POST /agent/runs/2/open': {
        ok: true,
        agent: 'claude',
        prompt: '…',
        message: 'Se ha abierto claude con la misma sesión.',
      },
    })
    renderApp('/agente')
    expect(await screen.findByRole('heading', { name: 'Agente' })).toBeInTheDocument()
    const cards = await screen.findAllByRole('listitem', {}, { timeout: 3000 })
    expect(screen.getByText('En curso')).toBeInTheDocument()
    expect(screen.getByText('Necesita tu respuesta')).toBeInTheDocument()
    expect(screen.getByText('La oferta parece cerrada, ¿redacto igualmente?')).toBeInTheDocument()
    expect(screen.getAllByText(/Solo con:/)[0]).toHaveTextContent('get_status, list_jobs, get_job, save_extraction')
    expect(screen.getAllByText('Subagente «extractor»').length).toBeGreaterThan(0)
    expect(screen.getByRole('link', { name: 'oferta 42' })).toHaveAttribute('href', '/jobs/42')
    expect(cards.length).toBeGreaterThan(0)

    await userEvent.click(screen.getByRole('button', { name: 'Cancelar' }))
    await userEvent.click(screen.getByRole('button', { name: 'Contestar en terminal' }))
    expect(await screen.findByText('Se ha abierto claude con la misma sesión.')).toBeInTheDocument()
    const posts = calls.filter((c) => c.method === 'POST')
    expect(posts.map((c) => c.path)).toEqual(['/agent/runs/3/cancel', '/agent/runs/2/open'])
    // Cuerpo JSON: `require_ui` lo exige (sin él, la API responde 403).
    expect(posts.map((c) => c.body)).toEqual([{}, {}])
  })

  it('lista los encargos pendientes y los quita', async () => {
    const calls = mockApi({
      'GET /status': { ...status(), agent_requests: 1 },
      'GET /agent': launcher,
      'GET /agent/runs': { active: 0, runs: [] },
      'GET /agent/requests': {
        pending: 1,
        requests: [
          request(),
          request({
            id: 5,
            action: 'process-jobs',
            label: 'Procesar ofertas',
            job_id: null,
            status: 'done',
            summary: 'Procesadas 3.',
            agent_name: 'claude-code',
          }),
        ],
      },
      'POST /agent/requests/7/cancel': request({ status: 'cancelled' }),
    })
    renderApp('/agente')
    const pending = await screen.findByRole('list', { name: 'Encargos pendientes' })
    // La orden técnica que recibe el agente, solo al desplegar.
    expect(within(pending).queryByText(/Usa el skill/)).not.toBeInTheDocument()
    await userEvent.click(within(pending).getByRole('button', { name: 'Detalles técnicos' }))
    expect(within(pending).getByText('Usa el skill generate-cv de CandidatAI para la oferta 42.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Atender encargos' })).toBeInTheDocument()
    expect(screen.getByText(/Aún no has lanzado nada en segundo plano/)).toBeInTheDocument()
    await userEvent.click(within(pending).getByRole('button', { name: 'Quitar' }))
    expect(calls.find((c) => c.method === 'POST' && c.path === '/agent/requests/7/cancel')?.body).toEqual({})
  })

  it('avisa si hay algo en cola y ninguna en curso (¿worker parado?)', async () => {
    mockApi({
      'GET /status': status(),
      'GET /agent': {
        ...launcher,
        background: { available: false, agent: null, reason: 'Tu agente (codex) no tiene `launch.headless`.' },
      },
      'GET /agent/runs': {
        active: 1,
        runs: [
          run({
            status: 'queued',
            created_at: '2020-01-01T00:00:00Z',
            started_at: null,
            finished_at: null,
            result: null,
            progress: [],
          }),
        ],
      },
      'GET /agent/requests': { pending: 0, requests: [] },
    })
    renderApp('/agente')
    expect(await screen.findByText(/ninguna en curso/)).toHaveTextContent('¿Está CandidatAI abierta entera?')
    expect(await screen.findByText(/no tiene `launch.headless`/)).toBeInTheDocument()
  })

  describe('coste y umbral (fase 25.4)', () => {
    const totals = (runs: number, tokens: number, cost: number | null) => ({
      runs,
      with_usage: runs,
      input_tokens: tokens,
      output_tokens: 0,
      cached_tokens: 0,
      turns: 0,
      duration_ms: runs * 60_000,
      cost_usd: cost,
      avg_tokens: runs ? tokens / runs : null,
      avg_duration_ms: runs ? 60_000 : null,
      avg_cost_usd: cost != null && runs ? cost / runs : null,
    })
    const group = (key: string, label: string, runs: number, tokens: number, cost: number | null, instruction_tokens: number | null = null) => ({
      key,
      label,
      instruction_tokens,
      ...totals(runs, tokens, cost),
    })
    const window = (days: number) => ({
      days,
      since: '2026-10-01T00:00:00Z',
      total: totals(3, 30_000, 0.6),
      by_action: [group('process-jobs', 'Procesar ofertas', 2, 20_000, 0.4, 251), group('assess-fit', 'Evaluar encaje', 1, 10_000, null, 839)],
      by_agent: [group('claude', 'claude', 2, 20_000, 0.4), group('opencode', 'opencode', 1, 10_000, null)],
      by_model: [group('claude/default', 'claude · por defecto', 2, 20_000, 0.4)],
    })
    const threshold = { value: 45, source: 'default', triage_threshold: 55, default: 45 }

    function page(extra: Record<string, unknown> = {}) {
      return mockApi({
        'GET /status': status(),
        'GET /agent': launcher,
        'GET /agent/runs': { active: 0, runs: [] },
        'GET /agent/requests': { pending: 0, requests: [] },
        'GET /agent/costs': { windows: [window(7), window(30)], terminal_note: '…' },
        'GET /agent/assess-threshold': threshold,
        ...extra,
      })
    }

    it('suma por acción, agente y modelo, con lo que pesa cada skill', async () => {
      page()
      renderApp('/agente')
      await userEvent.click(await screen.findByRole('button', { name: 'Umbral y coste' }))
      const actions = await screen.findByRole('table', { name: 'Por acción' })
      const row = within(actions).getByRole('row', { name: /Procesar ofertas/ })
      const cells = within(row).getAllByRole('cell').map((c) => c.textContent)
      expect(cells[0]).toBe('2')
      expect(cells[3]).toMatch(/0[.,]4000 USD/)
      expect(cells[5]).toBe('251')
      const assess = within(actions).getByRole('row', { name: /Evaluar encaje/ })
      expect(within(assess).getAllByRole('cell')[3]).toHaveTextContent('—')  // sin coste: no se estima
      expect(screen.getByRole('table', { name: 'Por agente' })).toHaveTextContent('opencode')
      expect(screen.getByRole('tab', { name: 'Últimos 30 días' })).toBeInTheDocument()
      expect(screen.getByText(/lo que haces en una terminal no llega a la app/)).toBeInTheDocument()
    })

    it('sin ejecuciones lo dice una sola vez, sin cifras ni tablas vacías', async () => {
      const empty = { days: 7, since: '2026-10-01T00:00:00Z', total: totals(0, 0, null), by_action: [], by_agent: [], by_model: [] }
      page({ 'GET /agent/costs': { windows: [empty], terminal_note: '…' } })
      renderApp('/agente')
      await userEvent.click(await screen.findByRole('button', { name: 'Umbral y coste' }))
      expect(await screen.findAllByText('Ninguna ejecución en este periodo.')).toHaveLength(1)
      expect(screen.queryByRole('table')).not.toBeInTheDocument()
    })

    it('cambia el umbral de «Evaluar encaje»', async () => {
      const calls = page({ 'PUT /agent/assess-threshold': { ...threshold, value: 60, source: 'ui' } })
      renderApp('/agente')
      await userEvent.click(await screen.findByRole('button', { name: 'Umbral y coste' }))
      const input = await screen.findByRole('spinbutton', { name: 'Score mínimo' })
      expect(input).toHaveValue(45)
      expect(screen.getByText(/el umbral de score menos 10/)).toBeInTheDocument()
      await userEvent.clear(input)
      await userEvent.type(input, '60')
      await userEvent.click(screen.getByRole('button', { name: 'Guardar' }))
      expect(await screen.findByText('Lo has cambiado aquí.')).toBeInTheDocument()
      expect(calls.find((c) => c.method === 'PUT' && c.path === '/agent/assess-threshold')?.body).toEqual({ value: 60 })
    })
  })
})
