import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type {
  AgentEntry,
  AgentResolution,
  AgentsOverview,
  LocalModelsStatus,
  SpendTier,
  SpendTiers,
} from '@/api/client'
import { mockApi, renderApp, status } from '@/test/utils'

const launcher = {
  available: true,
  agent: 'claude',
  reason: null,
  background: { available: true, agent: 'claude', reason: null },
  actions: [],
}

const capabilities = {
  mcp: true,
  subagents: 'isolated' as const,
  isolation_level: 'B' as const,
  vision: null,
  web: true,
  browser: null,
  local_models: true,
  headless: false,
}

function agent(name: string, display: string, changes: Partial<AgentEntry> = {}): AgentEntry {
  return {
    name,
    enabled: true,
    config: 'generated',
    info: {
      display_name: display,
      vendor: 'Vendor',
      open_source: true,
      license: 'MIT',
      homepage: 'https://example.test',
      install: { windows: `npm i -g ${name}`, macos: null, linux: null },
      detect: [name, '--version'],
      invoke: 'natural',
      instructions: 'AGENTS.md',
      note: null,
    },
    capabilities,
    models: { by_name: true, presets: [], example: null, fast: null, capable: null },
    installed: true,
    version: `${name} 1.0`,
    detect_error: null,
    ...changes,
  }
}

function resolution(changes: Partial<AgentResolution> = {}): AgentResolution {
  return {
    agent: 'claude',
    display_name: 'Claude Code',
    model: null,
    preset: null,
    reason: 'first_installed',
    reason_text: 'el primero instalado',
    blocked: null,
    blocked_code: null,
    warning: null,
    ...changes,
  }
}

function overview(changes: Partial<AgentsOverview> = {}): AgentsOverview {
  return {
    agents: [
      agent('claude', 'Claude Code', {
        info: { ...agent('claude', 'Claude Code').info, open_source: false, license: 'propietaria' },
        capabilities: { ...capabilities, isolation_level: 'A', headless: true, local_models: false, browser: true },
        models: { by_name: true, presets: [], example: null, fast: 'haiku', capable: 'sonnet' },
      }),
      agent('codex', 'Codex', { models: { by_name: true, presets: ['local'], example: null, fast: null, capable: null } }),
      agent('opencode', 'OpenCode', {
        installed: false,
        version: null,
        models: { by_name: true, presets: [], example: 'ollama/qwen3:8b', fast: null, capable: null },
      }),
      agent('cursor', 'Cursor CLI', { enabled: false, config: 'none' }),
    ],
    launchable: ['claude', 'codex', 'opencode'],
    preferences: { default_agent: null, agents: {}, actions: {} },
    effective: [
      { action: 'assess-fit', label: 'Evaluar encaje', terminal: resolution(), background: resolution() },
      {
        action: 'search-jobs',
        label: 'Buscar ofertas',
        terminal: resolution({
          agent: 'codex',
          display_name: 'Codex',
          reason: 'action',
          reason_text: 'elegido para esta acción',
          blocked: 'Codex no tiene navegador, y esta acción lo necesita.',
          blocked_code: 'capability',
        }),
        background: null,
      },
    ],
    ...changes,
  }
}

function page(data: AgentsOverview = overview(), extra: Record<string, unknown> = {}) {
  return mockApi({
    'GET /status': status(),
    'GET /agent': launcher,
    'GET /agent/runs': { active: 0, runs: [] },
    'GET /agent/requests': { pending: 0, requests: [] },
    'GET /agent/agents': data,
    'PUT /agent/preferences': (request: Request) => request.json(),
    'GET /agent/tiers': tiers(),
    'GET /agent/local-models': localModels(),
    ...extra,
  })
}

const pref = (agent: string, model: string | null = null, preset: string | null = null) => ({ agent, model, preset })

function tiers(changes: Partial<SpendTiers> = {}): SpendTiers {
  const closed = ['process-jobs', 'assess-fit', 'review-replies'] as const
  const make = (id: SpendTier['id'], label: string, closedPref: ReturnType<typeof pref>, extra: Partial<SpendTier> = {}) => ({
    id,
    label,
    actions: { ...Object.fromEntries(closed.map((a) => [a, closedPref])), 'generate-cv': pref('claude') },
    custom: false,
    active: false,
    notes: [],
    ...extra,
  })
  return {
    actions: [...closed, 'generate-cv'],
    tiers: [
      make('economy', 'Económico', pref('opencode'), { notes: ['needs_local_model'] }),
      make('balanced', 'Equilibrado', pref('claude', 'haiku')),
      make('max', 'Máximo', pref('claude')),
    ],
    can_undo: false,
    ...changes,
  }
}

function localModels(changes: Partial<LocalModelsStatus> = {}): LocalModelsStatus {
  return {
    provider: 'ollama',
    url: 'http://127.0.0.1:11434',
    running: true,
    version: '0.12.6',
    error: null,
    env_context: null,
    default_context: 4096,
    min_context: 32768,
    models: [
      {
        name: 'gpt-oss:20b',
        family: 'gptoss',
        parameter_size: '20.9B',
        params_b: 20.9,
        quantization: 'MXFP4',
        size_gb: 13.8,
        max_context: 131072,
        context: 4096,
        context_source: 'default',
        tools: true,
        small: false,
      },
    ],
    warnings: [{ code: 'context_low', text: 'texto del servidor', model: 'gpt-oss:20b', action: null }],
    ...changes,
  }
}

function lastPut(calls: ReturnType<typeof mockApi>) {
  return calls.filter((c) => c.method === 'PUT' && c.path === '/agent/preferences').at(-1)?.body
}

/** Los agentes sin instalar y el ajuste por acción van plegados. */
async function openOthers() {
  await userEvent.click(await screen.findByRole('button', { name: /^Otros? agentes? compatibles? \(/ }))
}

async function openFineTune() {
  await userEvent.click(await screen.findByRole('button', { name: 'Elegir agente y modelo por acción' }))
}

describe('Sección «Agentes» (fase 24.4)', () => {
  it('enseña una tarjeta por agente con insignias, instalación y subagentes', async () => {
    page()
    renderApp('/agente')
    const claude = await screen.findByRole('listitem', { name: 'Claude Code' })
    expect(within(claude).getByText('claude 1.0')).toBeInTheDocument()
    expect(within(claude).getByText('Delega con seguridad (nivel A)')).toBeInTheDocument()
    expect(within(claude).getByText('Segundo plano')).toBeInTheDocument()
    expect(within(claude).queryByText('Open-source')).not.toBeInTheDocument()
    expect(within(claude).getByText(/usan haiku \/ sonnet/)).toBeInTheDocument()

    const codex = screen.getByRole('listitem', { name: 'Codex' })
    expect(within(codex).getByText('Open-source')).toBeInTheDocument()
    expect(within(codex).getByText('Modelos locales')).toBeInTheDocument()
    expect(within(codex).getByText(/usan este mismo modelo/)).toBeInTheDocument()

    // Sin instalar, plegado.
    expect(screen.queryByRole('listitem', { name: 'OpenCode' })).not.toBeInTheDocument()
    await openOthers()
    const opencode = screen.getByRole('listitem', { name: 'OpenCode' })
    expect(within(opencode).getByText('No instalado')).toBeInTheDocument()
    expect(within(opencode).getByText('npm i -g opencode')).toBeInTheDocument()
    expect(within(opencode).getByPlaceholderText('p. ej. ollama/qwen3:8b')).toBeInTheDocument()

    const cursor = screen.getByRole('listitem', { name: 'Cursor CLI' })
    expect(within(cursor).getByText(/la app no tiene botón para él/)).toBeInTheDocument()
    expect(within(cursor).queryByLabelText('Modelo')).not.toBeInTheDocument()
  })

  it('el selector cambia el agente por defecto', async () => {
    const calls = page()
    renderApp('/agente')
    const select = await screen.findByLabelText('Agente por defecto')
    expect(within(select).getByRole('option', { name: 'OpenCode (No instalado)' })).toBeInTheDocument()
    await userEvent.selectOptions(select, 'codex')
    await waitFor(() => expect(lastPut(calls)).toEqual({ default_agent: 'codex', agents: {}, actions: {} }))
  })

  it('guarda el modelo o el preset de un agente', async () => {
    const calls = page()
    renderApp('/agente')
    const claude = await screen.findByRole('listitem', { name: 'Claude Code' })
    await userEvent.type(within(claude).getByLabelText('Modelo'), 'sonnet{Enter}')
    await waitFor(() =>
      expect(lastPut(calls)).toMatchObject({ agents: { claude: { model: 'sonnet', preset: null } } }),
    )
    const codex = screen.getByRole('listitem', { name: 'Codex' })
    await userEvent.selectOptions(within(codex).getByLabelText('Preset'), 'local')
    await waitFor(() =>
      expect(lastPut(calls)).toMatchObject({ agents: { codex: { model: null, preset: 'local' } } }),
    )
  })

  it('la tabla «Por acción» anula el agente y enseña el efectivo con su motivo', async () => {
    const calls = page()
    renderApp('/agente')
    await openFineTune()
    const table = await screen.findByRole('table')
    const search = within(table).getByRole('row', { name: /Buscar ofertas/ })
    expect(within(search).getByText(/elegido para esta acción/)).toBeInTheDocument()
    expect(within(search).getByText('Codex no tiene navegador, y esta acción lo necesita.')).toBeInTheDocument()

    const assess = within(table).getByRole('row', { name: /Evaluar encaje/ })
    expect(within(assess).getByText(/el primero instalado/)).toBeInTheDocument()
    await userEvent.selectOptions(within(assess).getByLabelText('Agente'), 'opencode')
    await waitFor(() =>
      expect(lastPut(calls)).toEqual({
        default_agent: null,
        agents: {},
        actions: { 'assess-fit': { agent: 'opencode', model: null, preset: null } },
      }),
    )
  })

  it('con una anulación, se le puede poner modelo y quitarla', async () => {
    const data = overview({
      preferences: { default_agent: null, agents: {}, actions: { 'assess-fit': { agent: 'codex', model: null, preset: null } } },
    })
    const calls = page(data)
    renderApp('/agente')
    await openFineTune()
    const row = within(await screen.findByRole('table')).getByRole('row', { name: /Evaluar encaje/ })
    await userEvent.type(within(row).getByLabelText('Modelo'), 'o4{Enter}')
    await waitFor(() =>
      expect(lastPut(calls)).toMatchObject({ actions: { 'assess-fit': { agent: 'codex', model: 'o4' } } }),
    )
    await userEvent.selectOptions(within(row).getByLabelText('Agente'), '')
    await waitFor(() => expect(lastPut(calls)).toMatchObject({ actions: {} }))
  })

  it('sin ningún agente instalado, los compatibles salen a la vista con cómo instalarlos', async () => {
    const data = overview()
    page({ ...data, agents: data.agents.map((a) => ({ ...a, installed: false, version: null })) })
    renderApp('/agente')
    const claude = await screen.findByRole('listitem', { name: 'Claude Code' })
    expect(within(claude).getByText('npm i -g claude')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /compatibles? \(/ })).not.toBeInTheDocument()
  })

  it('dice por qué no se pudo guardar', async () => {
    mockApi({
      'GET /status': status(),
      'GET /agent': launcher,
      'GET /agent/runs': { active: 0, runs: [] },
      'GET /agent/requests': { pending: 0, requests: [] },
      'GET /agent/agents': overview(),
      'GET /agent/tiers': tiers(),
      'GET /agent/local-models': localModels(),
      'GET /agent/costs': { windows: [], terminal_note: '' }, // fase 25.4: sin su error en la página
      'PUT /agent/preferences': {
        status: 422,
        body: {
          ok: false,
          error: {
            type: 'invalid_request',
            message: 'El modelo «qwen3» no tiene el formato de OpenCode (p. ej. ollama/qwen3:8b).',
            details: [{ field: 'agents.opencode', received: null, reason: '…' }],
          },
        },
      },
    })
    renderApp('/agente')
    await openOthers()
    const opencode = await screen.findByRole('listitem', { name: 'OpenCode' })
    await userEvent.type(within(opencode).getByLabelText('Modelo'), 'qwen3{Enter}')
    expect(await screen.findByRole('alert')).toHaveTextContent('no tiene el formato de OpenCode')
  })
})

describe('Niveles de gasto y modelos locales (fase 24.6)', () => {
  it('enseña los tres niveles con su propuesta y aplica uno con un clic', async () => {
    const applied = tiers({
      can_undo: true,
      tiers: tiers().tiers.map((t) => (t.id === 'balanced' ? { ...t, active: true } : t)),
    })
    const calls = page(overview(), { 'POST /agent/tiers/balanced/apply': applied })
    renderApp('/agente')
    await openFineTune()
    const economy = await screen.findByRole('listitem', { name: 'Económico' })
    expect(within(economy).getAllByText('OpenCode')).toHaveLength(3)
    expect(within(economy).getByText(/Pon el modelo local/)).toBeInTheDocument()
    const balanced = screen.getByRole('listitem', { name: 'Equilibrado' })
    expect(within(balanced).getAllByText('Claude Code · haiku')).toHaveLength(3)
    await userEvent.click(within(balanced).getByRole('button', { name: 'Aplicar' }))
    await waitFor(() =>
      expect(calls.some((c) => c.method === 'POST' && c.path === '/agent/tiers/balanced/apply')).toBe(true),
    )
  })

  it('«Deshacer» aparece si hay algo que deshacer', async () => {
    const calls = page(overview(), {
      'GET /agent/tiers': tiers({ can_undo: true }),
      'POST /agent/tiers/undo': tiers(),
    })
    renderApp('/agente')
    await openFineTune()
    await userEvent.click(await screen.findByRole('button', { name: 'Deshacer el último' }))
    await waitFor(() => expect(calls.some((c) => c.path === '/agent/tiers/undo')).toBe(true))
  })

  it('edita un nivel y guarda el modelo local', async () => {
    const calls = page(overview(), { 'PUT /agent/tiers/economy': tiers() })
    renderApp('/agente')
    await openFineTune()
    const economy = await screen.findByRole('listitem', { name: 'Económico' })
    await userEvent.click(within(economy).getByRole('button', { name: 'Editar' }))
    await userEvent.type(within(economy).getByLabelText('Modelo para Procesar ofertas'), 'ollama/gpt-oss:20b')
    await userEvent.click(within(economy).getByRole('button', { name: 'Guardar' }))
    await waitFor(() => {
      const put = calls.find((c) => c.method === 'PUT' && c.path === '/agent/tiers/economy')
      expect(put?.body).toMatchObject({
        actions: { 'process-jobs': { agent: 'opencode', model: 'ollama/gpt-oss:20b' }, 'generate-cv': { agent: 'claude' } },
      })
    })
  })

  it('la tarjeta de un agente con modelos locales enseña Ollama y avisa del contexto', async () => {
    page()
    renderApp('/agente')
    const codex = await screen.findByRole('listitem', { name: 'Codex' })
    const local = await within(codex).findByLabelText('Modelos locales (Ollama)')
    expect(within(local).getByText('gpt-oss:20b')).toBeInTheDocument()
    expect(within(local).getByText(/sin OLLAMA_CONTEXT_LENGTH/)).toBeInTheDocument()
    expect(within(local).getByText(/contexto de 4096 tokens/)).toBeInTheDocument()
    // Claude Code no admite modelos locales: sin bloque.
    const claude = screen.getByRole('listitem', { name: 'Claude Code' })
    expect(within(claude).queryByLabelText('Modelos locales (Ollama)')).not.toBeInTheDocument()
  })

  it('dice si Ollama no responde', async () => {
    page(overview(), {
      'GET /agent/local-models': localModels({ running: false, version: null, models: [], warnings: [], error: 'x' }),
    })
    renderApp('/agente')
    const codex = await screen.findByRole('listitem', { name: 'Codex' })
    expect(await within(codex).findByText(/Ollama no responde en http:\/\/127\.0\.0\.1:11434/)).toBeInTheDocument()
  })
})
