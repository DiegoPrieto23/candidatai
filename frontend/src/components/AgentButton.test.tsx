import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { mockApi, renderApp, status } from '@/test/utils'

const noFollowups = { days_without_reply: 7, followups: [] }
const emptyPage = { items: [], total: 0, limit: 50, offset: 0 }
const launcher = {
  available: true,
  agent: 'claude',
  reason: null,
  background: { available: true, agent: 'claude', reason: null },
  actions: [
    { id: 'search-jobs', label: 'Buscar ofertas', needs_job: false, prompt: 'Usa el skill search-jobs…', background: false },
    { id: 'process-jobs', label: 'Procesar ofertas', needs_job: false, prompt: 'Usa…', background: true },
  ],
}

/** El botón y su desplegable ▾. */
const group = (main: HTMLElement) => main.closest<HTMLElement>('[data-slot="agent-button"]')!

function home(extra: Record<string, unknown>) {
  return mockApi({
    'GET /status': status(),
    'GET /followups': noFollowups,
    'GET /upcoming': { days: 7, items: [] },
    'GET /jobs': emptyPage,
    'GET /agent': launcher,
    ...extra,
  })
}

describe('Botones «en tu agente»', () => {
  it('«Buscar ofertas» abre el agente y lo dice', async () => {
    const calls = home({
      'POST /agent/launch': { ok: true, agent: 'claude', prompt: 'Usa el skill search-jobs…', message: 'ok' },
    })
    renderApp('/')
    await userEvent.click(await screen.findByRole('button', { name: 'Buscar ofertas' }))
    expect(await screen.findByText('Abierto en claude: sigue en la terminal.')).toBeInTheDocument()
    expect(calls.find((c) => c.path === '/agent/launch')?.body).toEqual({ action: 'search-jobs' })
  })

  it('si no puede abrir el agente, copia la orden', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
    home({
      'POST /agent/launch': {
        status: 503,
        body: {
          ok: false,
          error: {
            type: 'agent_unavailable',
            message: 'No se encuentra el programa del agente (claude) en el PATH.',
            details: [{ field: 'prompt', received: 'Usa el skill search-jobs de CandidatAI.', reason: '…' }],
          },
        },
      },
    })
    renderApp('/')
    await userEvent.click(await screen.findByRole('button', { name: 'Buscar ofertas' }))
    await waitFor(() => expect(writeText).toHaveBeenCalledWith('Usa el skill search-jobs de CandidatAI.'))
    expect(await screen.findByText(/He copiado la orden: pégala en tu agente\./)).toBeInTheDocument()
  })

  it('al enfocarlo con el teclado, un globo dice qué hace y cómo se abre (fase 27.1)', async () => {
    home({})
    renderApp('/')
    const main = await screen.findByRole('button', { name: 'Buscar ofertas' })
    expect(main).not.toHaveAttribute('title')
    expect(main).toHaveAccessibleDescription(/Tu agente recorre con tu navegador los portales/)
    main.focus()
    const tooltip = await screen.findByRole('tooltip')
    expect(tooltip).toHaveTextContent(/Tu agente recorre con tu navegador los portales/)
    expect(tooltip).toHaveTextContent('Abre claude en una terminal con la orden ya escrita')
  })

  it('el desplegable empieza por la ayuda, para leerla sin ratón (fase 27.1)', async () => {
    home({})
    renderApp('/')
    await screen.findByRole('button', { name: 'Buscar ofertas' })
    await userEvent.click(screen.getAllByRole('button', { name: 'Más formas de lanzarlo' })[0]!)
    const menu = await screen.findByRole('menu')
    expect(menu.firstElementChild).toHaveTextContent(/Tu agente recorre con tu navegador los portales/)
  })

  it('en Inicio, «Procesar» y «Evaluar» solo salen si hay ofertas para ellos', async () => {
    home({ 'GET /status': status(2, 0) })
    renderApp('/')
    expect(await screen.findByRole('button', { name: 'Procesar ofertas' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Evaluar encaje' })).not.toBeInTheDocument()
  })

  it('«En segundo plano» deja la ejecución en cola y enlaza a «Agente» (fase 19)', async () => {
    const calls = home({
      'GET /status': status(2, 0),
      'POST /agent/runs': { status: 202, body: { id: 1, status: 'queued' } },
    })
    renderApp('/')
    const main = await screen.findByRole('button', { name: 'Procesar ofertas' })
    await userEvent.click(within(group(main)).getByRole('button', { name: 'Más formas de lanzarlo' }))
    await userEvent.click(await screen.findByRole('menuitem', { name: /En segundo plano/ }))
    expect(await screen.findByText('En cola en segundo plano.', { exact: false })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Ver en «Agente»' })).toHaveAttribute('href', '/agente')
    expect(calls.find((c) => c.method === 'POST' && c.path === '/agent/runs')?.body).toEqual({ action: 'process-jobs' })
  })

  it('los skills que preguntan no ofrecen segundo plano, pero sí dejarlo para luego', async () => {
    const calls = home({ 'POST /agent/requests': { id: 3, status: 'pending' } })
    renderApp('/')
    const main = await screen.findByRole('button', { name: 'Buscar ofertas' })
    await userEvent.click(within(group(main)).getByRole('button', { name: 'Más formas de lanzarlo' }))
    expect(await screen.findByRole('menuitem', { name: /En terminal/ })).toBeInTheDocument()
    expect(screen.queryByRole('menuitem', { name: /En segundo plano/ })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('menuitem', { name: /Dejar para mi próxima sesión/ }))
    expect(await screen.findByText(/Encargo guardado/)).toBeInTheDocument()
    expect(calls.find((c) => c.method === 'POST' && c.path === '/agent/requests')?.body).toEqual({ action: 'search-jobs' })
  })

  describe('elegir agente (fase 24.4)', () => {
    const claude = {
      agent: 'claude',
      display_name: 'Claude Code',
      model: null,
      preset: null,
      reason: 'default',
      reason_text: 'tu agente por defecto',
      blocked: null,
      blocked_code: null,
      warning: null,
    }
    const codex = { ...claude, agent: 'codex', display_name: 'Codex', reason: 'explicit', reason_text: 'elegido para esta ejecución' }
    const qwen = {
      ...codex,
      agent: 'qwen',
      display_name: 'Qwen Code',
      blocked: 'Qwen Code no está instalado.',
      blocked_code: 'not_installed',
    }
    function withAgents(search: Record<string, unknown>) {
      return {
        ...launcher,
        actions: [{ ...launcher.actions[0], ...search }, launcher.actions[1]],
      }
    }

    it('el desplegable dice «con Claude Code» y abre con otro agente solo esta vez', async () => {
      const calls = home({
        'GET /agent': withAgents({ agent: claude, alternatives: [codex, qwen], background_agent: null }),
        'POST /agent/launch': { ok: true, agent: 'codex', prompt: '…', message: 'ok', model: null, warning: null },
      })
      renderApp('/')
      const main = await screen.findByRole('button', { name: 'Buscar ofertas' })
      const more = await within(group(main)).findByRole('button', {
        name: 'Más formas de lanzarlo (con Claude Code)',
      })
      expect(more).toHaveTextContent('con Claude Code')
      await userEvent.click(more)
      expect(await screen.findByText('Solo esta vez, con:')).toBeInTheDocument()
      expect(screen.getByRole('menuitem', { name: /Abrir con Qwen Code/ })).toHaveAttribute('aria-disabled', 'true')
      expect(screen.getByText('Qwen Code no está instalado.')).toBeInTheDocument()
      await userEvent.click(screen.getByRole('menuitem', { name: /Abrir con Codex/ }))
      expect(await screen.findByText('Abierto en codex: sigue en la terminal.')).toBeInTheDocument()
      expect(calls.find((c) => c.path === '/agent/launch')?.body).toEqual({ action: 'search-jobs', agent: 'codex' })
    })

    it('si al agente le falta una capacidad, el botón se deshabilita y dice por qué', async () => {
      const blocked = {
        ...codex,
        reason: 'action',
        blocked: 'Codex no tiene navegador, y esta acción lo necesita.',
        blocked_code: 'capability',
      }
      home({ 'GET /agent': withAgents({ agent: blocked, alternatives: [{ ...claude, reason: 'explicit' }], background_agent: null }) })
      renderApp('/')
      const main = await screen.findByRole('button', { name: 'Buscar ofertas' })
      await waitFor(() => expect(main).toBeDisabled())
      expect(main).not.toHaveAttribute('title')
      expect(main).toHaveAccessibleDescription(/Codex no tiene navegador, y esta acción lo necesita\./)
      // Deshabilitado no recibe el foco: lo recibe su envoltorio y el globo sale igual.
      const wrapper = screen.getByRole('group', { name: 'Buscar ofertas' })
      expect(wrapper).toHaveAttribute('tabindex', '0')
      wrapper.focus()
      const tooltip = await screen.findByRole('tooltip')
      expect(tooltip).toHaveTextContent('Codex no tiene navegador, y esta acción lo necesita.')
      expect(tooltip).toHaveTextContent(/Tu agente recorre con tu navegador los portales/)
      await userEvent.keyboard('{Escape}')
      await userEvent.click(within(group(main)).getByRole('button', { name: /con Codex/ }))
      expect(await screen.findByRole('menuitem', { name: /En terminal/ })).toHaveAttribute('aria-disabled', 'true')
      expect(screen.getByRole('menuitem', { name: /Abrir con Claude Code/ })).not.toHaveAttribute('aria-disabled')
    })

    it('si su agente no tiene segundo plano, propone otro que sí (fase 24.5)', async () => {
      const reason = 'El rol «writer» de «Generar CV» necesita read…'
      const calls = home({
        'GET /status': status(2, 0),
        'GET /agent': {
          ...launcher,
          actions: [
            launcher.actions[0],
            {
              ...launcher.actions[1],
              agent: { ...claude, agent: 'opencode', display_name: 'OpenCode' },
              alternatives: [],
              background_agent: { available: false, agent: null, reason, suggested: 'claude', suggested_name: 'Claude Code' },
            },
          ],
        },
        'POST /agent/runs': { status: 202, body: { id: 2, status: 'queued' } },
      })
      renderApp('/')
      const main = await screen.findByRole('button', { name: 'Procesar ofertas' })
      await userEvent.click(await within(group(main)).findByRole('button', { name: /con OpenCode/ }))
      const own = await screen.findByRole('menuitem', { name: new RegExp(`En segundo plano.*${reason}`) })
      expect(own).toHaveAttribute('aria-disabled', 'true')
      await userEvent.click(screen.getByRole('menuitem', { name: /En segundo plano con Claude Code/ }))
      expect(await screen.findByText('En cola en segundo plano.', { exact: false })).toBeInTheDocument()
      expect(calls.find((c) => c.method === 'POST' && c.path === '/agent/runs')?.body).toEqual({
        action: 'process-jobs',
        agent: 'claude',
      })
    })

    it('un agente de nivel C avisa al abrirse', async () => {
      const warning = 'Qwen Code es de nivel C: esta acción lee contenido no confiable.'
      home({
        'GET /agent': withAgents({ agent: { ...claude, warning }, alternatives: [], background_agent: null }),
        'POST /agent/launch': { ok: true, agent: 'qwen', prompt: '…', message: 'ok', model: null, warning },
      })
      renderApp('/')
      const main = await screen.findByRole('button', { name: 'Buscar ofertas' })
      await userEvent.click(await within(group(main)).findByRole('button', { name: /con Claude Code/ }))
      expect(await screen.findByRole('menuitem', { name: new RegExp(warning) })).toBeInTheDocument()
      await userEvent.keyboard('{Escape}')
      await userEvent.click(main)
      expect(await screen.findByText(`Abierto en qwen: sigue en la terminal. Ojo: ${warning}`)).toBeInTheDocument()
    })
  })
})
