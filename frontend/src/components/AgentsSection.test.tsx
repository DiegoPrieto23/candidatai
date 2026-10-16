import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { AgentEntry, AgentResolution, AgentsOverview } from '@/api/client'
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

function page(data: AgentsOverview = overview()) {
  return mockApi({
    'GET /status': status(),
    'GET /agent': launcher,
    'GET /agent/runs': { active: 0, runs: [] },
    'GET /agent/requests': { pending: 0, requests: [] },
    'GET /agent/agents': data,
    'PUT /agent/preferences': (request: Request) => request.json(),
  })
}

function lastPut(calls: ReturnType<typeof mockApi>) {
  return calls.filter((c) => c.method === 'PUT' && c.path === '/agent/preferences').at(-1)?.body
}

describe('Sección «Agentes» (fase 24.4)', () => {
  it('enseña una tarjeta por agente con insignias, instalación y subagentes', async () => {
    page()
    renderApp('/agente')
    const claude = await screen.findByRole('listitem', { name: 'Claude Code' })
    expect(within(claude).getByText('claude 1.0')).toBeInTheDocument()
    expect(within(claude).getByText('Subagentes aislados (nivel A)')).toBeInTheDocument()
    expect(within(claude).getByText('Segundo plano')).toBeInTheDocument()
    expect(within(claude).queryByText('Open-source')).not.toBeInTheDocument()
    expect(within(claude).getByText(/usan haiku \/ sonnet/)).toBeInTheDocument()

    const codex = screen.getByRole('listitem', { name: 'Codex' })
    expect(within(codex).getByText('Open-source')).toBeInTheDocument()
    expect(within(codex).getByText('Modelos locales')).toBeInTheDocument()
    expect(within(codex).getByText(/heredan el modelo de la sesión/)).toBeInTheDocument()

    const opencode = screen.getByRole('listitem', { name: 'OpenCode' })
    expect(within(opencode).getByText('No instalado')).toBeInTheDocument()
    expect(within(opencode).getByText('npm i -g opencode')).toBeInTheDocument()
    expect(within(opencode).getByPlaceholderText('p. ej. ollama/qwen3:8b')).toBeInTheDocument()

    const cursor = screen.getByRole('listitem', { name: 'Cursor CLI' })
    expect(within(cursor).getByText(/Solo compatible vía AGENTS\.md/)).toBeInTheDocument()
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
    const row = within(await screen.findByRole('table')).getByRole('row', { name: /Evaluar encaje/ })
    await userEvent.type(within(row).getByLabelText('Modelo'), 'o4{Enter}')
    await waitFor(() =>
      expect(lastPut(calls)).toMatchObject({ actions: { 'assess-fit': { agent: 'codex', model: 'o4' } } }),
    )
    await userEvent.selectOptions(within(row).getByLabelText('Agente'), '')
    await waitFor(() => expect(lastPut(calls)).toMatchObject({ actions: {} }))
  })

  it('dice por qué no se pudo guardar', async () => {
    mockApi({
      'GET /status': status(),
      'GET /agent': launcher,
      'GET /agent/runs': { active: 0, runs: [] },
      'GET /agent/requests': { pending: 0, requests: [] },
      'GET /agent/agents': overview(),
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
    const opencode = await screen.findByRole('listitem', { name: 'OpenCode' })
    await userEvent.type(within(opencode).getByLabelText('Modelo'), 'qwen3{Enter}')
    expect(await screen.findByRole('alert')).toHaveTextContent('no tiene el formato de OpenCode')
  })
})
