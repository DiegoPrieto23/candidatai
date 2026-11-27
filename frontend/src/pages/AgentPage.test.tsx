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
    label: 'Valorar las ofertas nuevas',
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

describe('Lo primero de «Agente» (fase 31)', () => {
  const quiet = {
    'GET /status': status(),
    'GET /agent/runs': { active: 0, runs: [] },
    'GET /agent/requests': { pending: 0, requests: [] },
  }
  const entry = (name: string, display: string, installed: boolean) => ({
    name,
    installed,
    enabled: true,
    config: 'generated',
    version: installed ? '1.0' : null,
    info: { display_name: display, vendor: 'Anthropic', license: 'propietaria', open_source: false, install: { windows: `instala ${name}` } },
    capabilities: { mcp: true, subagents: 'isolated', isolation_level: 'A', vision: null, web: true, browser: null, local_models: false, headless: true },
    models: { by_name: false, presets: [], fast: null, capable: null, example: null },
  })

  it('con un agente listo, lo dice arriba y pliega el detalle', async () => {
    mockApi({
      ...quiet,
      'GET /agent': { ...launcher, no_agent_installed: false },
      'GET /agent/agents': { agents: [entry('claude', 'Claude Code', true)], launchable: ['claude'], preferences: {}, effective: [] },
    })
    renderApp('/agente')
    expect(await screen.findByRole('heading', { name: 'Agente: Claude Code, listo' })).toBeInTheDocument()
    const details = screen.getByRole('button', { name: /^Configurar agentes/ })
    expect(details).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByLabelText('Agente por defecto')).not.toBeInTheDocument()
  })

  it('sin ninguno, explica cómo instalar uno y deja a la vista los agentes', async () => {
    mockApi({
      ...quiet,
      'GET /agent': { ...launcher, available: false, agent: null, reason: 'Sin agente.', no_agent_installed: true },
      'GET /agent/agents': { agents: [entry('claude', 'Claude Code', false)], launchable: ['claude'], preferences: {}, effective: [] },
    })
    renderApp('/agente')
    const notice = await screen.findByRole('region', { name: 'Hace falta un agente de IA' })
    expect(await within(notice).findByLabelText('Orden para instalar Claude Code')).toHaveTextContent('instala claude')
    // Ya está en «Agente»: no se enlaza a sí misma.
    expect(within(notice).queryByRole('link', { name: /Otros agentes/ })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^Ocultar la configuración/ })).toHaveAttribute('aria-expanded', 'true')
    expect(screen.queryByRole('switch', { name: 'Abrir en una ventana' })).not.toBeInTheDocument()
  })

  it('lista lo permitido siempre y lo quita (fase 48.1b)', async () => {
    const rule = { id: 4, tool: 'Read', detail: 'C:/notas.txt', created_at: '2026-11-27T10:00:00Z' }
    const calls = mockApi({
      ...quiet,
      'GET /agent': { ...launcher, no_agent_installed: false },
      'GET /agent/agents': { agents: [entry('claude', 'Claude Code', true)], launchable: ['claude'], preferences: {}, effective: [] },
      'GET /agent/permission-rules': { rules: [rule] },
      'DELETE /agent/permission-rules/4': { rules: [] },
    })
    renderApp('/agente')
    const section = await screen.findByRole('region', { name: 'Permitido siempre' })
    expect(within(section).getByText('C:/notas.txt')).toBeInTheDocument()
    await userEvent.click(within(section).getByRole('button', { name: 'Quitar el permiso de Read: C:/notas.txt' }))
    expect(calls.some((c) => c.method === 'DELETE' && c.path === '/agent/permission-rules/4')).toBe(true)
    expect(screen.queryByRole('region', { name: 'Permitido siempre' })).not.toBeInTheDocument()
  })

  it('«Abrir en una ventana» está apagado por defecto y se guarda al cambiarlo (fase 48.1a)', async () => {
    const calls = mockApi({
      ...quiet,
      'GET /agent': { ...launcher, no_agent_installed: false, open_in_window: false },
      'GET /agent/agents': { agents: [entry('claude', 'Claude Code', true)], launchable: ['claude'], preferences: {}, effective: [] },
      'PUT /agent/window-preference': { open_in_window: true },
    })
    renderApp('/agente')
    const toggle = await screen.findByRole('switch', { name: 'Abrir en una ventana' })
    expect(toggle).toHaveAttribute('aria-checked', 'false')
    expect(screen.getByText(/se sigue en el aviso de abajo a la derecha/)).toBeInTheDocument()
    await userEvent.click(toggle)
    expect(calls.find((c) => c.method === 'PUT' && c.path === '/agent/window-preference')?.body).toEqual({ open_in_window: true })
  })
})

describe('Página «Agente» (fase 19)', () => {
  it('no enseña las ejecuciones en segundo plano: solo los avisos dicen cuándo terminan', async () => {
    mockApi({
      'GET /status': status(),
      'GET /agent': launcher,
      'GET /agent/runs': { active: 1, runs: [run({ id: 3, status: 'running', finished_at: null, result: null })] },
      'GET /agent/requests': { pending: 0, requests: [] },
    })
    renderApp('/agente')
    expect(await screen.findByRole('heading', { name: 'Para la próxima sesión' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'En segundo plano' })).not.toBeInTheDocument()
    expect(screen.queryByText('Subagente «extractor»')).not.toBeInTheDocument()
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
            label: 'Valorar las ofertas nuevas',
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
    await userEvent.click(within(pending).getByRole('button', { name: 'Quitar' }))
    expect(calls.find((c) => c.method === 'POST' && c.path === '/agent/requests/7/cancel')?.body).toEqual({})
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
      by_action: [group('process-jobs', 'Valorar las ofertas nuevas', 2, 20_000, 0.4, 251), group('assess-fit', 'Valorar las que están por revisar', 1, 10_000, null, 839)],
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
      const row = within(actions).getByRole('row', { name: /Valorar las ofertas nuevas/ })
      const cells = within(row).getAllByRole('cell').map((c) => c.textContent)
      expect(cells[0]).toBe('2')
      expect(cells[3]).toMatch(/0[.,]4000 USD/)
      expect(cells[5]).toBe('251')
      const assess = within(actions).getByRole('row', { name: /Valorar las que están por revisar/ })
      expect(within(assess).getAllByRole('cell')[3]).toHaveTextContent('—')  // sin coste: no se estima
      expect(screen.getByRole('table', { name: 'Por agente' })).toHaveTextContent('opencode')
      expect(screen.getByRole('tab', { name: 'Últimos 30 días' })).toBeInTheDocument()
      expect(screen.getByText(/lo que se hace en una terminal no llega a la app/)).toBeInTheDocument()
    })

    it('sin ejecuciones lo dice una sola vez, sin cifras ni tablas vacías', async () => {
      const empty = { days: 7, since: '2026-10-01T00:00:00Z', total: totals(0, 0, null), by_action: [], by_agent: [], by_model: [] }
      page({ 'GET /agent/costs': { windows: [empty], terminal_note: '…' } })
      renderApp('/agente')
      await userEvent.click(await screen.findByRole('button', { name: 'Umbral y coste' }))
      expect(await screen.findAllByText('Ninguna ejecución en este periodo.')).toHaveLength(1)
      expect(screen.queryByRole('table')).not.toBeInTheDocument()
    })

    it('cambia el umbral de «Valorar las que están por revisar»', async () => {
      const calls = page({ 'PUT /agent/assess-threshold': { ...threshold, value: 60, source: 'ui' } })
      renderApp('/agente')
      await userEvent.click(await screen.findByRole('button', { name: 'Umbral y coste' }))
      const input = await screen.findByRole('spinbutton', { name: 'Encaje mínimo' })
      expect(input).toHaveValue(45)
      expect(screen.getByText(/el mínimo de «Por revisar» menos 10/)).toBeInTheDocument()
      await userEvent.clear(input)
      await userEvent.type(input, '60')
      await userEvent.click(screen.getByRole('button', { name: 'Guardar' }))
      expect(await screen.findByText('Cambiado aquí.')).toBeInTheDocument()
      expect(calls.find((c) => c.method === 'PUT' && c.path === '/agent/assess-threshold')?.body).toEqual({ value: 60 })
    })
  })
  it('la comparación por significado se activa también desde aquí y se ve cuando se instala', async () => {
    const extra = { installed: false, wanted: false, disabled: false, in_docker: false, installing: false, error: null }
    const calls = mockApi({
      'GET /status': status(),
      'GET /agent': launcher,
      'GET /agent/runs': { active: 0, runs: [] },
      'GET /agent/requests': { pending: 0, requests: [] },
      'GET /matching/semantic': extra,
      'POST /matching/semantic/install': { ...extra, wanted: true, installing: true },
    })
    renderApp('/agente')
    const section = await screen.findByRole('region', { name: 'Comparación por significado' })
    expect(await within(section).findByText('Comparación por significado: sin activar')).toBeInTheDocument()
    await userEvent.click(within(section).getByRole('button', { name: 'Qué aporta y cómo activarla' }))
    await userEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Instalar' }))
    expect(calls.some((c) => c.method === 'POST' && c.path === '/matching/semantic/install')).toBe(true)
    expect(await within(section).findByText('Instalando la comparación por significado…')).toBeInTheDocument()
    expect(within(section).getByText(/la app se puede seguir usando/)).toBeInTheDocument()
  })
})
