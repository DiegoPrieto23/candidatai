import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { AgentBrowseSource, LinkedInPublicView, SourceView } from '@/api/client'
import { mockApi, renderApp, status } from '@/test/utils'

const LIMITS = { max_result_pages: 2, delay_seconds: 5, default_max_offers: 15 }

function platform(id: number, browse: Partial<AgentBrowseSource>, overrides: Partial<SourceView> = {}): SourceView {
  const full: AgentBrowseSource = {
    name: 'Tecnoempleo',
    platform: 'tecnoempleo',
    search_urls: ['https://www.tecnoempleo.com/ofertas-trabajo/?te=data'],
    priority: 2,
    access: 'free',
    allow_agent_browsing: true,
    max_offers: 10,
    notes: null,
    ...browse,
  }
  const { name, ...config } = full
  return {
    id,
    kind: 'agent_browse',
    kind_label: 'Búsqueda con navegador',
    name,
    active: true,
    config,
    keys_missing: false,
    browse: full,
    last_run_at: null,
    last_run: null,
    ...overrides,
  }
}

const tecno = platform(1, {}, {
  last_run_at: '2026-10-02T09:04:00Z',
  last_run: {
    id: 7,
    actor: 'agent',
    started_at: '2026-10-02T09:00:00Z',
    finished_at: '2026-10-02T09:04:00Z',
    found: 12,
    after_filters: 4,
    created: 3,
    errors: [{ code: 'captcha', message: 'Captcha en la página 2: se para.', item: null }],
  },
})
const linkedin = platform(2, {
  name: 'LinkedIn',
  platform: 'linkedin',
  search_urls: ['https://www.linkedin.com/jobs/search/?keywords=data'],
  priority: 1,
  allow_agent_browsing: false,
})

function publicView(overrides: Partial<LinkedInPublicView> = {}): LinkedInPublicView {
  return {
    source_id: null,
    enabled: false,
    fetch_detail: false,
    enabled_at: null,
    platform_source_id: 2,
    searches: [
      {
        url: 'https://www.linkedin.com/jobs/search/?keywords=data',
        keywords: 'data',
        location: null,
        params: { keywords: 'data', f_TPR: 'r86400' },
      },
    ],
    ignored: [],
    blocked_at: null,
    next_run_at: null,
    last_run: null,
    limits: {
      max_searches_per_run: 5,
      max_pages_per_search: 2,
      delay_seconds: 10,
      min_hours_between_runs: 20,
      block_cooldown_days: 3,
      max_details_per_run: 10,
    },
    ...overrides,
  }
}

describe('Plataformas', () => {
  it('lista por prioridad con búsquedas, límites y resultados', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /sources': { sources: [tecno, linkedin], agent_browse: LIMITS },
      'GET /sources/linkedin-public': publicView(),
    })
    renderApp('/plataformas')

    const headings = await screen.findAllByRole('heading', { level: 3 })
    expect(headings.map((h) => h.textContent)).toEqual(['LinkedIn', 'Tecnoempleo'])
    expect(calls.find((c) => c.path === '/sources')?.search.get('kind')).toBe('agent_browse')
    expect(screen.getByText(/2 páginas de resultados por búsqueda, 5 s/)).toBeInTheDocument()
    const search = screen
      .getAllByRole('link', { name: 'data' })
      .find((link) => link.getAttribute('href') === tecno.browse!.search_urls[0])
    expect(search).toBeDefined()
    expect(search).toHaveAttribute('rel', 'noopener noreferrer')
    expect(screen.getByRole('link', { name: 'tecnoempleo.com' })).toHaveAttribute('href', 'https://www.tecnoempleo.com')
    // La URL completa, solo al desplegar.
    expect(screen.queryByText(tecno.browse!.search_urls[0])).not.toBeInTheDocument()
    for (const button of screen.getAllByRole('button', { name: 'Ver las URLs' })) await userEvent.click(button)
    expect(screen.getByText(tecno.browse!.search_urls[0])).toBeInTheDocument()
    expect(screen.getByText(/12 encontradas,\s+3 nuevas, 1 ya conocida/)).toBeInTheDocument()
    expect(screen.getByText('Captcha en la página 2: se para.')).toBeInTheDocument()
    expect(screen.getByText('El agente aún no la ha recorrido')).toBeInTheDocument()
  })

  it('«Ampliar búsqueda» abre el agente con su skill', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /sources': { sources: [tecno], agent_browse: LIMITS },
      'GET /agent': { available: true, agent: 'claude', reason: null, actions: [] },
      'POST /agent/launch': { ok: true, agent: 'claude', prompt: 'Usa el skill broaden-search…', message: 'ok' },
    })
    renderApp('/plataformas')
    await userEvent.click(await screen.findByRole('button', { name: 'Ampliar búsqueda' }))
    expect(await screen.findByText('Abierto en claude: sigue en la terminal.')).toBeInTheDocument()
    expect(calls.find((c) => c.path === '/agent/launch')?.body).toEqual({ action: 'broaden-search' })
  })

  it('activar LinkedIn pide confirmar el riesgo y manda confirm_risk', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /sources': { sources: [linkedin], agent_browse: LIMITS },
      'GET /sources/linkedin-public': publicView(),
      'POST /sources/2/browse': { status: 200, body: platform(2, { ...linkedin.browse, allow_agent_browsing: true }) },
    })
    renderApp('/plataformas')

    await userEvent.click(await screen.findByRole('switch', { name: 'Búsqueda con navegador en LinkedIn' }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText(/puede restringir o cerrar tu\s+cuenta/)).toBeInTheDocument()

    await userEvent.click(within(dialog).getByRole('button', { name: 'Cancelar' }))
    expect(calls.some((c) => c.path === '/sources/2/browse')).toBe(false)

    await userEvent.click(screen.getByRole('switch', { name: 'Búsqueda con navegador en LinkedIn' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Activar bajo mi responsabilidad' }))
    expect(calls.find((c) => c.path === '/sources/2/browse')?.body).toEqual({
      confirm_risk: true,
      allow_agent_browsing: true,
    })
  })

  it('otra plataforma se desactiva sin diálogo', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /sources': { sources: [tecno], agent_browse: LIMITS },
      'POST /sources/1/browse': { status: 200, body: platform(1, { allow_agent_browsing: false }) },
    })
    renderApp('/plataformas')

    await userEvent.click(await screen.findByRole('switch', { name: /Tecnoempleo/ }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(calls.find((c) => c.path === '/sources/1/browse')?.body).toEqual({
      confirm_risk: false,
      allow_agent_browsing: false,
    })
  })

  it('cambia las ofertas que abre en cada recorrido', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /sources': { sources: [tecno], agent_browse: LIMITS },
      'POST /sources/1/browse': { status: 200, body: platform(1, { max_offers: 40 }) },
    })
    renderApp('/plataformas')

    await userEvent.click(await screen.findByRole('combobox', { name: 'Ofertas por recorrido en Tecnoempleo' }))
    await userEvent.click(screen.getByRole('option', { name: '40' }))
    expect(calls.find((c) => c.path === '/sources/1/browse')?.body).toEqual({ confirm_risk: false, max_offers: 40 })
  })

  it('el selector de prioridad dice quién ocupa cada puesto y avisa del intercambio (fase 27.3)', async () => {
    const indeed = platform(3, { name: 'Indeed', platform: 'indeed', priority: 3, search_urls: ['https://es.indeed.com/jobs?q=data'] })
    let sources = [tecno, linkedin, indeed]
    const calls = mockApi({
      'GET /status': status(),
      'GET /sources': () => ({ sources, agent_browse: LIMITS }),
      'GET /sources/linkedin-public': publicView(),
      'POST /sources/1/browse': () => {
        // Tecnoempleo (2) pasa a la 3 e Indeed se queda con su 2.
        sources = [platform(1, { priority: 3 }), linkedin, platform(3, { ...indeed.browse, priority: 2 })]
        return { status: 200, body: sources[0] }
      },
    })
    renderApp('/plataformas')

    await userEvent.click(await screen.findByRole('combobox', { name: 'Prioridad de Tecnoempleo' }))
    expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual([
      '1 · LinkedIn(pasará al puesto 2)',
      '2 · Tecnoempleo(actual)',
      '3 · Indeed(pasará al puesto 2)',
    ])
    await userEvent.click(screen.getByRole('option', { name: /3 · Indeed/ }))
    expect(calls.find((c) => c.path === '/sources/1/browse')?.body).toEqual({
      confirm_risk: false,
      priority: 3,
      expected_priority: 2,
    })
    // Tras guardar, la lista se vuelve a pedir y se reordena.
    await vi.waitFor(() =>
      expect(screen.getAllByRole('heading', { level: 3 }).map((h) => h.textContent)).toEqual([
        'LinkedIn',
        'Indeed',
        'Tecnoempleo',
      ]),
    )
  })

  it('si otra pestaña cambió el orden (409), lo dice y vuelve a cargar la lista', async () => {
    let gets = 0
    mockApi({
      'GET /status': status(),
      'GET /sources': () => {
        gets += 1
        return { sources: [tecno, linkedin], agent_browse: LIMITS }
      },
      'GET /sources/linkedin-public': publicView(),
      'POST /sources/1/browse': {
        status: 409,
        body: {
          ok: false,
          error: { type: 'conflict', message: 'El orden ha cambiado desde que lo cargaste.', details: [] },
        },
      },
    })
    renderApp('/plataformas')

    await userEvent.click(await screen.findByRole('combobox', { name: 'Prioridad de Tecnoempleo' }))
    const before = gets
    await userEvent.click(screen.getByRole('option', { name: /1 · LinkedIn/ }))
    expect(await screen.findByRole('alert')).toHaveTextContent('El orden ha cambiado')
    await vi.waitFor(() => expect(gets).toBeGreaterThan(before))
  })

  it('prioridad, acceso y ofertas por recorrido se explican en un globo (fase 27.1)', async () => {
    mockApi({ 'GET /status': status(), 'GET /sources': { sources: [tecno], agent_browse: LIMITS } })
    renderApp('/plataformas')

    ;(await screen.findByRole('button', { name: 'Qué es la prioridad' })).focus()
    expect(await screen.findByRole('tooltip')).toHaveTextContent(/El orden en que tu agente recorre las plataformas/)
    await userEvent.keyboard('{Escape}')
    screen.getByRole('button', { name: 'Qué es el acceso' }).focus()
    expect(await screen.findByRole('tooltip')).toHaveTextContent(/Cómo entra el agente/)
    await userEvent.keyboard('{Escape}')
    screen.getByRole('button', { name: 'Qué son las ofertas por recorrido' }).focus()
    expect(await screen.findByRole('tooltip')).toHaveTextContent(/Cuántas ofertas nuevas da de alta/)
  })

  it('sin plataformas, explica cómo configurarlas', async () => {
    mockApi({ 'GET /status': status(), 'GET /sources': { sources: [], agent_browse: LIMITS } })
    renderApp('/plataformas')
    expect(await screen.findByText('Aún no hay plataformas')).toBeInTheDocument()
    expect(screen.getByText(/pide a tu agente que configure tu búsqueda/)).toBeInTheDocument()
  })
})

describe('Búsqueda pública de LinkedIn', () => {
  const SWITCH = 'Búsqueda pública de LinkedIn sin sesión'

  it('apagada por defecto; encenderla pide confirmar el riesgo y manda confirm_risk', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /sources': { sources: [linkedin], agent_browse: LIMITS },
      'GET /sources/linkedin-public': publicView(),
      'POST /sources/linkedin-public/settings': { status: 200, body: publicView({ enabled: true }) },
    })
    renderApp('/plataformas')

    const toggle = await screen.findByRole('switch', { name: SWITCH })
    expect(toggle).toHaveAttribute('aria-checked', 'false')
    expect(screen.getByText('Qué consultará')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Buscar ahora' })).not.toBeInTheDocument()

    await userEvent.click(toggle)
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText(/prohíben el acceso automatizado/)).toBeInTheDocument()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Cancelar' }))
    expect(calls.some((c) => c.path === '/sources/linkedin-public/settings')).toBe(false)

    await userEvent.click(screen.getByRole('switch', { name: SWITCH }))
    await userEvent.click(await screen.findByRole('button', { name: 'Activar bajo mi responsabilidad' }))
    expect(calls.find((c) => c.path === '/sources/linkedin-public/settings')?.body).toEqual({
      confirm_risk: true,
      enabled: true,
    })
  })

  it('apagarla no pide confirmación', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /sources': { sources: [linkedin], agent_browse: LIMITS },
      'GET /sources/linkedin-public': publicView({ enabled: true, source_id: 9 }),
      'POST /sources/linkedin-public/settings': { status: 200, body: publicView() },
    })
    renderApp('/plataformas')
    await userEvent.click(await screen.findByRole('switch', { name: SWITCH }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(calls.find((c) => c.path === '/sources/linkedin-public/settings')?.body).toEqual({
      confirm_risk: false,
      enabled: false,
    })
  })

  it('tras un bloqueo lo avisa y no deja buscar', async () => {
    // Una sola referencia: con dos `Date.now()` podía pasar 1 ms entre medias y el bloqueo no cuadraba.
    const now = Date.now()
    const blockedAt = new Date(now - 3_600_000).toISOString()
    const until = new Date(now + 3 * 86_400_000 - 3_600_000).toISOString()
    mockApi({
      'GET /status': status(),
      'GET /sources': { sources: [linkedin], agent_browse: LIMITS },
      'GET /sources/linkedin-public': publicView({
        enabled: true,
        source_id: 9,
        blocked_at: blockedAt,
        next_run_at: until,
        last_run: {
          id: 4,
          actor: 'system',
          started_at: blockedAt,
          finished_at: blockedAt,
          found: 5,
          after_filters: 2,
          created: 2,
          errors: [{ code: 'blocked', message: 'LinkedIn respondió HTTP 429: corta la búsqueda.', item: null }],
        },
      }),
    })
    renderApp('/plataformas')
    expect(await screen.findByText(/LinkedIn cortó la última búsqueda/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Buscar ahora' })).toBeDisabled()
    expect(screen.getByText(/5 encontradas,\s+2 tras filtros, 2 nuevas/)).toBeInTheDocument()
  })

  it('«Buscar ahora» la ejecuta y enseña el resultado', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /sources': { sources: [linkedin], agent_browse: LIMITS },
      'GET /sources/linkedin-public': publicView({ enabled: true, source_id: 9 }),
      'POST /sources/linkedin-public/run': {
        status: 200,
        body: {
          source_id: 9,
          run_id: 1,
          skipped: null,
          blocked: false,
          requests: 2,
          found: 5,
          after_filters: 3,
          created: 3,
          summaries: 3,
          existing: 0,
          job_ids: [1, 2, 3],
          errors: [],
          message: 'LinkedIn · búsqueda pública: 5 ofertas encontradas, 3 tras filtros, 3 nuevas',
        },
      },
    })
    renderApp('/plataformas')
    await userEvent.click(await screen.findByRole('button', { name: 'Buscar ahora' }))
    expect(await screen.findByText(/3 tras filtros, 3 nuevas/)).toBeInTheDocument()
    expect(calls.find((c) => c.path === '/sources/linkedin-public/run')?.body).toEqual({})
  })
})

describe('Añadir plataforma', () => {
  function routes() {
    return {
      'GET /status': status(),
      'GET /sources': { sources: [tecno], agent_browse: LIMITS },
      'POST /sources/platforms': {
        status: 201,
        body: { source_id: 3, created: true, allow_agent_browsing: false, message: 'ok' },
      },
    }
  }

  it('LinkedIn: avisa de por qué conviene dejarla desactivada y la crea desactivada', async () => {
    const calls = mockApi(routes())
    renderApp('/plataformas')
    await userEvent.click(await screen.findByRole('button', { name: 'Añadir plataforma' }))
    const dialog = await screen.findByRole('dialog')
    await userEvent.selectOptions(within(dialog).getByLabelText('Portal'), 'linkedin')
    expect(within(dialog).getByRole('note')).toHaveTextContent('puede restringir o cerrar tu cuenta')
    const add = within(dialog).getByRole('button', { name: 'Añadir' })
    expect(add).toBeDisabled()
    await userEvent.type(
      within(dialog).getByLabelText('Búsquedas (una URL por línea)'),
      'https://www.linkedin.com/jobs/search/?keywords=data',
    )
    await userEvent.click(add)
    const call = calls.find((c) => c.method === 'POST' && c.path === '/sources/platforms')
    expect(call?.body).toMatchObject({ name: 'LinkedIn', platform: 'linkedin', allow_agent_browsing: false })
  })

  it('la prioridad de una nueva es por defecto la última; se puede poner delante de otra (fase 27.3)', async () => {
    const calls = mockApi({
      ...routes(),
      'GET /sources': { sources: [tecno, linkedin], agent_browse: LIMITS },
      'GET /sources/linkedin-public': publicView(),
    })
    renderApp('/plataformas')
    await userEvent.click(await screen.findByRole('button', { name: 'Añadir plataforma' }))
    const dialog = await screen.findByRole('dialog')
    await userEvent.selectOptions(within(dialog).getByLabelText('Portal'), 'indeed')
    const priority = within(dialog).getByLabelText('Prioridad (1 = primero)')
    expect(priority).toHaveValue('3')
    expect(within(priority).getAllByRole('option').map((o) => o.textContent)).toEqual([
      '1 · antes de LinkedIn',
      '2 · antes de Tecnoempleo',
      '3 · la última',
    ])
    await userEvent.selectOptions(priority, '2')
    await userEvent.type(within(dialog).getByLabelText('Búsquedas (una URL por línea)'), 'https://es.indeed.com/jobs?q=bi')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Añadir' }))
    const call = calls.find((c) => c.method === 'POST' && c.path === '/sources/platforms')
    expect(call?.body).toMatchObject({ name: 'Indeed', priority: 2 })
  })

  it('otro portal: hay que escribir su id', async () => {
    const calls = mockApi(routes())
    renderApp('/plataformas')
    await userEvent.click(await screen.findByRole('button', { name: 'Añadir plataforma' }))
    const dialog = await screen.findByRole('dialog')
    await userEvent.selectOptions(within(dialog).getByLabelText('Portal'), 'otra')
    await userEvent.type(within(dialog).getByLabelText('Nombre'), 'Mi portal')
    await userEvent.type(within(dialog).getByLabelText('Id corto'), 'miportal')
    await userEvent.type(within(dialog).getByLabelText('Búsquedas (una URL por línea)'), 'https://miportal.example/q')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Añadir' }))
    const call = calls.find((c) => c.method === 'POST' && c.path === '/sources/platforms')
    expect(call?.body).toMatchObject({ name: 'Mi portal', platform: 'miportal', search_urls: ['https://miportal.example/q'] })
    expect(call ? (call.body as Record<string, unknown>).allow_agent_browsing : 'sin llamada').toBeUndefined()
    // Sin elegir prioridad no se manda: el servidor la pone al final (fase 27.3).
    expect(call ? (call.body as Record<string, unknown>).priority : 'sin llamada').toBeUndefined()
  })
})
