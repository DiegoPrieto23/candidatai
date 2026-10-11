import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { AgentBrowseSource, SourceView } from '@/api/client'
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

describe('Plataformas', () => {
  it('lista por prioridad con búsquedas, límites y resultados', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /sources': { sources: [tecno, linkedin], agent_browse: LIMITS },
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

  it('activar LinkedIn pide confirmar el riesgo y manda confirm_risk', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /sources': { sources: [linkedin], agent_browse: LIMITS },
      'POST /sources/2/browse': { status: 200, body: platform(2, { ...linkedin.browse, allow_agent_browsing: true }) },
    })
    renderApp('/plataformas')

    await userEvent.click(await screen.findByRole('switch', { name: /LinkedIn/ }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText(/puede restringir o cerrar tu\s+cuenta/)).toBeInTheDocument()

    await userEvent.click(within(dialog).getByRole('button', { name: 'Cancelar' }))
    expect(calls.some((c) => c.path === '/sources/2/browse')).toBe(false)

    await userEvent.click(screen.getByRole('switch', { name: /LinkedIn/ }))
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

  it('sin plataformas, explica cómo configurarlas', async () => {
    mockApi({ 'GET /status': status(), 'GET /sources': { sources: [], agent_browse: LIMITS } })
    renderApp('/plataformas')
    expect(await screen.findByText('Aún no hay plataformas')).toBeInTheDocument()
    expect(screen.getByText(/buscar-ofertas configurar/)).toBeInTheDocument()
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
  })
})
