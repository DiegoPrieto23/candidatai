import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { mockApi, renderApp, status } from '@/test/utils'

const page = (items: unknown[]) => ({ items, total: items.length, limit: 50, offset: 0 })

function platform(id: number, name: string, overrides: Record<string, unknown> = {}) {
  return {
    id,
    kind: 'agent_browse',
    kind_label: 'Portal',
    name,
    active: true,
    config: {},
    keys_missing: false,
    browse: { allow_agent_browsing: true, search_urls: [], priority: id, access: 'free', max_offers: 10, notes: '' },
    website: null,
    last_run_at: null,
    last_run: null,
    ...overrides,
  }
}

const launcher = {
  available: true,
  agent: 'claude',
  reason: null,
  actions: [{ id: 'search-jobs', background: false, agent: { display_name: 'Claude Code', blocked: null } }],
}

function routes(sources: unknown[], extra: Record<string, unknown> = {}) {
  return {
    'GET /status': status(),
    'GET /sources': { sources, agent_browse: { max_result_pages: 3, delay_seconds: 5 } },
    'GET /jobs': page([]),
    'GET /agent': launcher,
    ...extra,
  }
}

const launched = { label: 'Buscar ofertas', prompt: 'x', agent: 'Claude Code', job_id: null }
const started = { run_id: 5, portals: 2, companies: 0, companies_skipped: 0, message: '' }

/** La franja de arriba: lo que buscas, la columna de «Buscar ahora» y «Más ajustes». */
const strip = () => screen.getByRole('region', { name: 'Lo que vas a buscar' })
const findStrip = () => screen.findByRole('region', { name: 'Lo que vas a buscar' })

describe('Buscar ofertas', () => {
  it('lanza a tu agente en todos los portales activos, sin añadir nada a la orden', async () => {
    const calls = mockApi(
      routes(
        [
          platform(1, 'InfoJobs', {
            last_run_at: '2026-10-30T08:00:00Z',
            last_run: { id: 1, actor: 'agent', started_at: '2026-10-30T08:00:00Z', finished_at: null, found: 9, after_filters: 9, created: 4, errors: [] },
          }),
          platform(2, 'Tecnoempleo'),
          platform(3, 'LinkedIn', { browse: { allow_agent_browsing: false, search_urls: [], priority: 3, access: 'login', max_offers: 10, notes: '' } }),
        ],
        { 'POST /search/run': started, 'POST /agent/launch': { status: 202, body: launched } },
      ),
    )
    renderApp('/buscar')
    const list = await screen.findByRole('list', { name: 'Portales en los que buscar' })
    expect(within(list).getByRole('checkbox', { name: /InfoJobs/ })).toBeChecked()
    expect(within(list).getByText('4 nuevas')).toBeInTheDocument()
    expect(within(list).getByText('de 9', { exact: false })).toBeInTheDocument()
    expect(strip()).toHaveTextContent('2 portales')
    expect(strip()).toHaveTextContent('hasta 20 ofertas nuevas en portales')
    // LinkedIn sin permiso no se ofrece: se ve aparte, con lo que le pasa y dónde se cambia.
    expect(within(list).queryByText('LinkedIn')).not.toBeInTheDocument()
    const off = screen.getByRole('list', { name: 'Portales en los que ahora no se busca' })
    expect(within(off).getByText('LinkedIn')).toBeInTheDocument()
    expect(within(off).getByText('Sin permiso para tu agente')).toBeInTheDocument()
    expect(within(off).getByRole('link', { name: 'Cambiar en «Dónde buscar»' })).toHaveAttribute('href', '/fuentes/plataformas')
    // La última búsqueda, al pie, con la bandeja a un clic.
    expect(screen.getByText(/1 oferta nueva de 9 vistas|4 ofertas nuevas de 9 vistas/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Ver en la bandeja' })).toHaveAttribute('href', '/bandeja')
    await userEvent.click(screen.getByRole('button', { name: /^Buscar ahora/ }))
    await waitFor(() => expect(calls.some((c) => c.path === '/agent/launch')).toBe(true))
    // Primero abre la búsqueda (con las empresas) y el agente la sigue.
    expect(calls.find((c) => c.path === '/search/run')?.body).toEqual({ portal_ids: [1, 2], include_companies: true })
    const body = calls.find((c) => c.path === '/agent/launch')?.body as { action: string; search: Record<string, unknown> }
    expect(body.action).toBe('search-jobs')
    expect(body.search).toEqual({ platform_ids: [], search_run_id: 5 })
  })

  it('manda solo los portales elegidos, y sin «solo esta vez»', async () => {
    const calls = mockApi(
      routes([platform(1, 'InfoJobs'), platform(2, 'Tecnoempleo')], { 'POST /search/run': started, 'POST /agent/launch': { status: 202, body: launched } }),
    )
    renderApp('/buscar')
    await userEvent.click(await screen.findByRole('checkbox', { name: /Tecnoempleo/ }))
    expect(strip()).toHaveTextContent('1 portal')
    expect(screen.queryByRole('button', { name: 'Buscar otra cosa solo esta vez' })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /^Buscar ahora/ }))
    await waitFor(() => expect(calls.some((c) => c.path === '/agent/launch')).toBe(true))
    expect(calls.find((c) => c.path === '/search/run')?.body).toEqual({ portal_ids: [1], include_companies: true })
    const body = calls.find((c) => c.path === '/agent/launch')?.body as { search: unknown }
    expect(body.search).toEqual({ platform_ids: [1], search_run_id: 5 })
  })

  it('no deja lanzar sin portales elegidos ni empresas, y no hay «Cambiar»', async () => {
    mockApi(routes([platform(1, 'InfoJobs')]))
    renderApp('/buscar')
    const box = await screen.findByRole('checkbox', { name: /InfoJobs/ })
    expect(within(strip()).queryByRole('button', { name: 'Cambiar' })).not.toBeInTheDocument()
    await userEvent.click(box)
    expect(screen.getByText('Elige al menos un portal.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^Buscar ahora/ })).toBeDisabled()
    await userEvent.click(box)
    expect(screen.getByRole('button', { name: /^Buscar ahora/ })).toBeEnabled()
    const portals = screen.getByRole('region', { name: /^Portales ·/ })
    expect(within(portals).getByRole('link', { name: 'Empresas con portal propio' })).toHaveAttribute('href', '/fuentes/empresas')
  })

  it('con el mismo clic revisa las empresas y, sin portales elegidos, solo ellas (fase 45)', async () => {
    const infojobs = platform(1, 'InfoJobs')
    const acme = { ...platform(9, 'Acme'), kind: 'greenhouse', kind_label: 'Greenhouse', browse: null }
    const calls = mockApi(
      routes([], {
        // «Buscar» pide las plataformas (`kind=agent_browse`) y todas las fuentes, para las empresas.
        'GET /sources': (_req: Request, url: URL) => ({
          sources: url.searchParams.get('kind') ? [infojobs] : [infojobs, acme],
          agent_browse: { max_result_pages: 5, delay_seconds: 5 },
        }),
        'POST /search/run': { run_id: 6, portals: 0, companies: 1, companies_skipped: 0, message: '' },
      }),
    )
    renderApp('/buscar')
    await screen.findByRole('checkbox', { name: /InfoJobs/ })
    expect(await within(strip()).findByText(/1 portal · 1 empresa/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('checkbox', { name: /InfoJobs/ }))
    expect(strip()).toHaveTextContent('Sin portales elegidos: solo revisará la empresa.')
    await userEvent.click(within(strip()).getByRole('button', { name: /^Buscar ahora/ }))
    await waitFor(() => expect(calls.some((c) => c.path === '/search/run')).toBe(true))
    expect(calls.find((c) => c.path === '/search/run')?.body).toEqual({ portal_ids: [], include_companies: true })
    expect(calls.some((c) => c.path === '/agent/launch')).toBe(false)
  })

  it('si tu agente no se abre, la búsqueda deja de esperarlo (fase 45)', async () => {
    const calls = mockApi(
      routes([platform(1, 'InfoJobs')], {
        'POST /search/run': started,
        'POST /agent/launch': { status: 409, body: { ok: false, error: { type: 'unavailable', message: 'Sin terminal.', details: [] } } },
        'POST /search/run/5/stop': { run: null },
      }),
    )
    renderApp('/buscar')
    await screen.findByRole('checkbox', { name: /InfoJobs/ })
    await userEvent.click(within(strip()).getByRole('button', { name: /^Buscar ahora/ }))
    await waitFor(() => expect(calls.some((c) => c.path === '/search/run/5/stop')).toBe(true))
    expect(calls.filter((c) => c.path === '/search/run')).toHaveLength(1)
  })

  it('una casilla encima de la lista selecciona o quita todos los portales', async () => {
    mockApi(routes([platform(1, 'InfoJobs'), platform(2, 'Tecnoempleo')]))
    renderApp('/buscar')
    const all = await screen.findByRole('checkbox', { name: 'Quitar selección' })
    expect(all).toBeChecked()
    await userEvent.click(all)
    expect(screen.getByRole('checkbox', { name: /InfoJobs/ })).not.toBeChecked()
    expect(screen.getByRole('checkbox', { name: /Tecnoempleo/ })).not.toBeChecked()
    expect(screen.getByText('Elige al menos un portal.')).toBeInTheDocument()
    // Con uno solo, la casilla queda a medias.
    await userEvent.click(screen.getByRole('checkbox', { name: /InfoJobs/ }))
    const some = screen.getByRole('checkbox', { name: 'Seleccionar todos' })
    expect(some).not.toBeChecked()
    expect((some as HTMLInputElement).indeterminate).toBe(true)
    await userEvent.click(some)
    expect(screen.getByRole('checkbox', { name: /Tecnoempleo/ })).toBeChecked()
    // «Gestionar portales» ya no está junto a la selección: va en «Dónde buscar».
    expect(screen.queryByRole('link', { name: 'Gestionar portales' })).not.toBeInTheDocument()
  })

  it('avisa de lo que hay que preparar y resume la búsqueda', async () => {
    const urls = ['https://glassdoor.es/a', 'https://glassdoor.es/b']
    mockApi(
      routes([
        platform(1, 'Glassdoor', { browse: { allow_agent_browsing: true, search_urls: urls, priority: 1, access: 'login', max_offers: 15, notes: '' } }),
        platform(2, 'Tecnoempleo', { browse: { allow_agent_browsing: true, search_urls: ['https://tecnoempleo.com/a'], priority: 2, access: 'free', max_offers: 10, notes: '' } }),
      ]),
    )
    renderApp('/buscar')
    const list = await screen.findByRole('list', { name: 'Portales en los que buscar' })
    expect(strip()).toHaveTextContent('hasta 25 ofertas nuevas en portales')
    expect(within(list).getByText('2 búsquedas guardadas')).toBeInTheDocument()
    expect(within(list).getByText('1 búsqueda guardada')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Qué ofertas cuentan' })).toBeInTheDocument()
    // Ningún texto nombra un agente concreto ni pide conectar el navegador: lo dice tu agente si falta.
    expect(screen.queryByText(/navegador conectado/)).not.toBeInTheDocument()
    // La ayuda del botón de tu agente sí dice con cuál se abre (fase 24.4): no cuenta.
    const page = document.body.cloneNode(true) as HTMLElement
    page.querySelectorAll('[data-slot="agent-button"]').forEach((button) => button.remove())
    expect(page.textContent).not.toMatch(/Claude|Codex|Chrome/)
    expect(within(list).getByText('Pide sesión')).toBeInTheDocument()
    expect(screen.getByText('Inicia sesión en Glassdoor')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('checkbox', { name: /Glassdoor/ }))
    expect(screen.queryByText('Inicia sesión en Glassdoor')).not.toBeInTheDocument()
  })

  it('cambia a la vez las ofertas por portal de los elegidos', async () => {
    const calls = mockApi(
      routes([platform(1, 'InfoJobs'), platform(2, 'Tecnoempleo'), platform(3, 'Glassdoor')], {
        'POST /sources/browse/max-offers': { sources: [], default_max_offers: 20 },
      }),
    )
    renderApp('/buscar')
    await screen.findByRole('list', { name: 'Portales en los que buscar' })
    const control = screen.getByRole('combobox', { name: /ofertas por portal/i })
    expect(control).toHaveTextContent('10')
    expect(control).toHaveAccessibleName('Hasta 10 ofertas por portal')
    // Glassdoor fuera: solo cambian los elegidos.
    await userEvent.click(screen.getByRole('checkbox', { name: /Glassdoor/ }))
    await userEvent.click(control)
    await userEvent.click(await screen.findByRole('option', { name: '20' }))
    await waitFor(() => expect(calls.some((c) => c.path === '/sources/browse/max-offers')).toBe(true))
    expect(calls.find((c) => c.path === '/sources/browse/max-offers')?.body).toEqual({ source_ids: [1, 2], max_offers: 20 })
  })

  it('si cada portal tiene su límite, lo dice y elegir uno los iguala', async () => {
    const browse = (max_offers: number) => ({ allow_agent_browsing: true, search_urls: [], priority: 1, access: 'free', max_offers, notes: '' })
    const calls = mockApi(
      routes([platform(1, 'InfoJobs', { browse: browse(5) }), platform(2, 'Tecnoempleo', { browse: browse(40) })], {
        'POST /sources/browse/max-offers': { sources: [], default_max_offers: 15 },
      }),
    )
    renderApp('/buscar')
    await screen.findByRole('list', { name: 'Portales en los que buscar' })
    const control = screen.getByRole('combobox', { name: /ofertas por portal/i })
    expect(control).toHaveTextContent('varía')
    expect(screen.getByText('Cada portal tiene el suyo (de 5 a 40): elige un número para igualarlos.')).toBeInTheDocument()
    await userEvent.click(control)
    await userEvent.click(await screen.findByRole('option', { name: '15' }))
    await waitFor(() => expect(calls.find((c) => c.path === '/sources/browse/max-offers')?.body).toEqual({ source_ids: [1, 2], max_offers: 15 }))
  })

  it('sin navegador, consulta las fuentes con API una a una', async () => {
    const result = (id: number, created: number) => ({ source_id: id, name: 'x', kind: 'lever', run_id: 1, skipped: null, found: 3, after_filters: 3, created, existing: 0, duplicates: 0, job_ids: [], errors: [], message: '' })
    const calls = mockApi(
      routes(
        [
          platform(7, 'Acme', { kind: 'lever', browse: null }),
          platform(8, 'Globex', { kind: 'greenhouse', browse: null }),
          platform(9, 'Sin claves', { kind: 'adzuna', browse: null, keys_missing: true }),
        ],
        { 'POST /sources/7/run': result(7, 2), 'POST /sources/8/run': result(8, 1) },
      ),
    )
    renderApp('/buscar')
    await userEvent.click(await screen.findByRole('button', { name: 'Consultar ahora' }))
    expect(await screen.findByText('3 ofertas nuevas')).toBeInTheDocument()
    expect(calls.filter((c) => c.method === 'POST').map((c) => c.path)).toEqual(['/sources/7/run', '/sources/8/run'])
  })

  it('sin portales, lleva a elegirlos y la franja sigue a mano', async () => {
    mockApi(routes([]))
    renderApp('/buscar')
    expect(await screen.findByRole('heading', { name: 'Aún no hay portales en los que buscar' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Ir a «Dónde buscar»' })).toHaveAttribute('href', '/fuentes/plataformas')
    expect(within(strip()).getByText('Aún no hay portales en los que buscar')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^Buscar ahora/ })).not.toBeInTheDocument()
  })
})

describe('Buscar ofertas: tus puestos y lugares en la franja', () => {
  const preferences = {
    roles: ['Data Engineer', 'Data Analyst'],
    seniority_target: [],
    remote_modes: [],
    locations: { preferred: ['Vigo'], allowed: ['Madrid'] },
    languages_for_work: ['es'],
    cv: { photo_policy: { default: true } },
  }
  const editable = (prefs: unknown, hash: string) => ({
    exists: true,
    file_hash: hash,
    profile: { personal: { name: 'Demo' }, preferences: prefs },
    issues: [],
    profile_version_id: 3,
    undo_available: 0,
    policy_discard_title_keywords: [],
    policy_years_tolerance: 1,
  })
  const savedSection = (hash: string) => ({
    section: 'preferences',
    dry_run: false,
    changed: true,
    diff: '',
    file_hash: hash,
    profile_version_id: 4,
    version_created: true,
    rescore_queued: true,
    generated_ids: [],
    warnings: [],
  })

  /** Un perfil que cambia al guardar, como el de verdad: cada guardado, un `file_hash` nuevo. */
  function withProfile() {
    let current = editable(preferences, 'h1')
    let saves = 1
    const calls = mockApi(
      routes([platform(1, 'InfoJobs')], {
        'GET /profile/editable': () => current,
        'GET /profile/role-suggestions': [
          { title: 'BI Engineer', count: 3 },
          { title: 'Analytics Developer', count: 1 },
        ],
        'PUT /profile/sections/preferences': (request: Request) =>
          request
            .clone()
            .json()
            .then((body: { content: unknown }) => {
              saves += 1
              current = editable(body.content, `h${saves}`)
              return savedSection(`h${saves}`)
            }),
      }),
    )
    return () => calls.filter((c) => c.method === 'PUT') as unknown as { body: { file_hash: string; content: typeof preferences } }[]
  }

  it('enseña tus puestos y lugares como etiquetas y quita uno con «Deshacer»', async () => {
    const puts = withProfile()
    renderApp('/buscar')
    const roles = await within(await findStrip()).findByRole('group', { name: 'Puestos' })
    expect(within(roles).getByText('Data Engineer')).toBeInTheDocument()
    const places = within(strip()).getByRole('group', { name: 'Dónde' })
    expect(within(places).getByText('Vigo')).toBeInTheDocument()
    expect(within(places).getByText('solo híbrido o remoto')).toBeInTheDocument()
    expect(strip()).toHaveTextContent('Se guarda en tu perfil, para esta y las próximas búsquedas.')

    await userEvent.click(within(roles).getByRole('button', { name: 'Quitar Data Analyst' }))
    expect(await within(strip()).findByText('Quitado «Data Analyst»: guardado en tu perfil.')).toBeInTheDocument()
    expect(puts()[0].body.file_hash).toBe('h1')
    expect(puts()[0].body.content.roles).toEqual(['Data Engineer'])
    // El resto de tus preferencias va tal cual.
    expect(puts()[0].body.content.locations).toEqual(preferences.locations)
    await waitFor(() => expect(within(roles).queryByText('Data Analyst')).not.toBeInTheDocument())

    const undo = await within(strip()).findByRole('button', { name: 'Deshacer' })
    await waitFor(() => expect(undo).toBeEnabled())
    await userEvent.click(undo)
    await waitFor(() => expect(puts()).toHaveLength(2))
    expect(puts()[1].body.file_hash).toBe('h2')
    expect(puts()[1].body.content.roles).toEqual(['Data Engineer', 'Data Analyst'])
    expect(await within(roles).findByText('Data Analyst')).toBeInTheDocument()
  })

  it('añade un puesto de las sugerencias o el que escribes, con el teclado', async () => {
    const puts = withProfile()
    renderApp('/buscar')
    const roles = await within(await findStrip()).findByRole('group', { name: 'Puestos' })
    const add = () => within(roles).getByRole('button', { name: 'Añadir puesto' })
    await userEvent.click(add())
    expect(within(roles).getByRole('combobox', { name: 'Añadir puesto' })).toHaveFocus()
    const list = await within(roles).findByRole('listbox', { name: 'De ofertas que has aprobado' })
    expect(within(list).getByRole('option', { name: /BI Engineer/ })).toHaveTextContent('3 aprobadas')
    // Flecha abajo y arriba recorren la lista; Intro elige.
    await userEvent.keyboard('{ArrowDown}{ArrowUp}{Enter}')
    await waitFor(() => expect(puts()).toHaveLength(1))
    expect(puts()[0].body.content.roles).toEqual(['Data Engineer', 'Data Analyst', 'BI Engineer'])
    expect(await within(strip()).findByText('Añadido «BI Engineer»: guardado en tu perfil.')).toBeInTheDocument()

    // Lo que escribes va primero; sin tildes ni mayúsculas, filtra las sugerencias.
    await waitFor(() => expect(add()).toBeEnabled())
    await userEvent.click(add())
    await userEvent.keyboard('analytics')
    expect(within(roles).getAllByRole('option').map((o) => o.textContent)).toEqual(['Añadir «analytics»', 'Analytics Developer1 aprobada'])
    await userEvent.keyboard('{Enter}')
    await waitFor(() => expect(puts()).toHaveLength(2))
    expect(puts()[1].body.content.roles.at(-1)).toBe('analytics')

    // Esc cierra sin guardar y devuelve el foco al botón.
    await waitFor(() => expect(add()).toBeEnabled())
    await userEvent.click(add())
    await userEvent.keyboard('Algo{Escape}')
    await waitFor(() => expect(add()).toHaveFocus())
    expect(puts()).toHaveLength(2)
  })

  it('añade un lugar en cualquier modalidad', async () => {
    const puts = withProfile()
    renderApp('/buscar')
    const places = await within(await findStrip()).findByRole('group', { name: 'Dónde' })
    await userEvent.click(within(places).getByRole('button', { name: 'Añadir lugar' }))
    await userEvent.keyboard('A Coruña{Enter}')
    await waitFor(() => expect(puts()).toHaveLength(1))
    expect(puts()[0].body.content.locations).toEqual({ preferred: ['Vigo', 'A Coruña'], allowed: ['Madrid'] })
  })

  it('un guardado que no cambia el fichero no deja la franja bloqueada', async () => {
    mockApi(
      routes([platform(1, 'InfoJobs')], {
        'GET /profile/editable': editable(preferences, 'h1'),
        'GET /profile/role-suggestions': [],
        'PUT /profile/sections/preferences': { ...savedSection('h1'), changed: false },
      }),
    )
    renderApp('/buscar')
    const roles = await within(await findStrip()).findByRole('group', { name: 'Puestos' })
    await userEvent.click(within(roles).getByRole('button', { name: 'Quitar Data Analyst' }))
    expect(await within(strip()).findByText('Quitado «Data Analyst»: guardado en tu perfil.')).toBeInTheDocument()
    await waitFor(() => expect(within(roles).getByRole('button', { name: 'Añadir puesto' })).toHaveAttribute('aria-disabled', 'false'))
  })

  it('si no se puede guardar, lo dice y deja lo que había', async () => {
    mockApi(
      routes([platform(1, 'InfoJobs')], {
        'GET /profile/editable': editable(preferences, 'h1'),
        'GET /profile/role-suggestions': [],
        'PUT /profile/sections/preferences': {
          status: 409,
          body: { ok: false, error: { type: 'conflict', message: 'Tu perfil ha cambiado: recarga la página.', details: [] } },
        },
      }),
    )
    renderApp('/buscar')
    const roles = await within(await findStrip()).findByRole('group', { name: 'Puestos' })
    await userEvent.click(within(roles).getByRole('button', { name: 'Quitar Data Analyst' }))
    expect(await within(strip()).findByRole('alert')).toHaveTextContent('Tu perfil ha cambiado')
    expect(within(roles).getByText('Data Analyst')).toBeInTheDocument()
  })

  it('marca la modalidad y el nivel con chips que se guardan al momento', async () => {
    const puts = withProfile()
    renderApp('/buscar')
    const modes = await within(await findStrip()).findByRole('group', { name: 'Modalidad' })
    const remote = within(modes).getByRole('checkbox', { name: 'Remoto' })
    expect(remote).not.toBeChecked()
    await userEvent.click(remote)
    await waitFor(() => expect(puts()).toHaveLength(1))
    expect(puts()[0].body.content.remote_modes).toEqual(['remote'])
    expect(await within(strip()).findByText('Añadido «Remoto»: guardado en tu perfil.')).toBeInTheDocument()
    await waitFor(() => expect(within(modes).getByRole('checkbox', { name: 'Remoto' })).toBeChecked())

    const levels = within(strip()).getByRole('group', { name: 'Nivel' })
    await waitFor(() => expect(within(levels).getByRole('checkbox', { name: 'Senior' })).toBeEnabled())
    await userEvent.click(within(levels).getByRole('checkbox', { name: 'Senior' }))
    await waitFor(() => expect(puts()).toHaveLength(2))
    // Cada cambio parte del perfil que acaba de guardarse.
    expect(puts()[1].body.file_hash).toBe('h2')
    expect(puts()[1].body.content).toMatchObject({ remote_modes: ['remote'], seniority_target: ['senior'] })
  })

  it('cada lugar se pulsa para elegir qué aceptas en él', async () => {
    const puts = withProfile()
    renderApp('/buscar')
    const places = await within(await findStrip()).findByRole('group', { name: 'Dónde' })
    await userEvent.click(within(places).getByRole('button', { name: 'Qué aceptas en Vigo' }))
    await userEvent.click(await screen.findByRole('menuitemradio', { name: 'Descartar' }))
    await waitFor(() => expect(puts()).toHaveLength(1))
    expect(puts()[0].body.content.locations).toEqual({ preferred: [], allowed: ['Madrid'], excluded: ['Vigo'] })
    expect(await within(strip()).findByText('Cambiado «Vigo: descartar»: guardado en tu perfil.')).toBeInTheDocument()
    // Lo descartado se sigue viendo, con su nota.
    expect(await within(places).findByText('descartar')).toBeInTheDocument()
  })
})

describe('Buscar ofertas: «Más ajustes»', () => {
  const preferences = {
    roles: ['Data Engineer'],
    seniority_target: [],
    remote_modes: [],
    locations: { preferred: ['Vigo'] },
    languages_for_work: ['es'],
    cv: { photo_policy: { default: true } },
    exclude_signals: ['fixed_term'],
    discard_title_keywords: ['Prácticas'],
  }
  const editable = (prefs: unknown, hash: string) => ({
    exists: true,
    file_hash: hash,
    profile: { personal: { name: 'Demo' }, preferences: prefs },
    issues: [],
    profile_version_id: 3,
    undo_available: 0,
    policy_discard_title_keywords: ['sales'],
    policy_years_tolerance: 1,
  })

  /** Como el servidor: cada guardado (de la sección o del sueldo), un `file_hash` nuevo. */
  function withProfile(salary: number | null = 30000) {
    let current = editable(preferences, 'h1')
    let floor = salary
    let saves = 1
    const next = () => {
      saves += 1
      return `h${saves}`
    }
    const calls = mockApi(
      routes([platform(1, 'InfoJobs')], {
        'GET /profile/editable': () => current,
        'GET /profile/role-suggestions': [],
        'GET /profile/salary-floor': () => ({ salary_floor_eur: floor, file_hash: current.file_hash }),
        'PUT /profile/sections/preferences': (request: Request) =>
          request
            .clone()
            .json()
            .then((body: { content: unknown }) => {
              const hash = next()
              current = editable(body.content, hash)
              return { section: 'preferences', dry_run: false, changed: true, diff: '', file_hash: hash, profile_version_id: 4, version_created: true, rescore_queued: true, generated_ids: [], warnings: [] }
            }),
        'PUT /profile/salary-floor': (request: Request) =>
          request
            .clone()
            .json()
            .then((body: { salary_floor_eur: number | null }) => {
              const hash = next()
              floor = body.salary_floor_eur
              current = { ...current, file_hash: hash }
              return { changed: true, file_hash: hash, profile_version_id: 5, rescore_queued: true }
            }),
      }),
    )
    return () => calls.filter((c) => c.method === 'PUT') as unknown as { path: string; body: Record<string, unknown> & { file_hash: string } }[]
  }
  /** El panel que despliega el botón (plegado, sigue en la página: se busca por `aria-controls`). */
  const more = () => {
    const button = within(strip()).getByRole('button', { name: /Más ajustes/ })
    return document.getElementById(button.getAttribute('aria-controls')!)!
  }
  const findMore = async () => {
    await findStrip()
    await waitFor(() => expect(within(strip()).getByRole('button', { name: /Más ajustes/ })).toBeInTheDocument())
    return more()
  }

  it('el botón cuenta los grupos con algo puesto y despliega los ajustes en la franja', async () => {
    withProfile()
    renderApp('/buscar')
    const button = await within(await findStrip()).findByRole('button', { name: /Más ajustes/ })
    // Sueldo, idiomas, contrato (sin temporal) y una palabra que descarta: los cuatro grupos.
    await waitFor(() => expect(button).toHaveAccessibleName(/4 grupos con ajustes/))
    expect(button).toHaveAttribute('aria-expanded', 'false')
    expect(more()).not.toBeVisible()
    await userEvent.click(button)
    expect(button).toHaveAttribute('aria-expanded', 'true')
    expect(more()).toBeVisible()
    expect(within(more()).getByRole('heading', { name: 'Contrato y jornada' })).toBeInTheDocument()
    // «Temporal» de `exclude_signals` sale sin marcar; el resto, marcado.
    expect(within(more()).getByRole('checkbox', { name: 'Indefinido' })).toBeChecked()
    expect(within(more()).getByRole('checkbox', { name: 'Temporal' })).not.toBeChecked()
    // La explicación de las palabras va en su globo, con las de la configuración de la app.
    await userEvent.hover(within(more()).getByRole('button', { name: 'Qué palabras descartan' }))
    expect((await screen.findAllByText(/También descartan las de la configuración de la app: sales/)).length).toBeGreaterThan(0)
    expect(screen.getByRole('spinbutton', { name: 'Sueldo mínimo' })).toHaveValue(30000)
  })

  it('en /buscar/ajustes llega ya desplegado', async () => {
    withProfile()
    renderApp('/buscar/ajustes')
    await findMore()
    await waitFor(() => expect(more()).toBeVisible())
    expect(within(strip()).getByRole('button', { name: /Más ajustes/ })).toHaveAttribute('aria-expanded', 'true')
  })

  it('plegar y desplegar «Más ajustes» cambia la dirección sin mover ni volver a montar la página', async () => {
    withProfile()
    const scrollTo = vi.spyOn(window, 'scrollTo').mockImplementation(() => {})
    try {
      renderApp('/buscar')
      const before = await findStrip()
      scrollTo.mockClear()
      const button = await within(before).findByRole('button', { name: /Más ajustes/ })
      await userEvent.click(button)
      await waitFor(() => expect(button).toHaveAttribute('aria-expanded', 'true'))
      await userEvent.click(button)
      await waitFor(() => expect(button).toHaveAttribute('aria-expanded', 'false'))
      // El mismo nodo: la franja no se ha vuelto a montar (y no ha perdido lo que tuvieras a medias).
      expect(strip()).toBe(before)
      expect(scrollTo).not.toHaveBeenCalled()
    } finally {
      scrollTo.mockRestore()
    }
  })

  it('guarda de una vez lo de tu perfil y el sueldo, y se puede deshacer', async () => {
    const puts = withProfile()
    renderApp('/buscar/ajustes')
    await findMore()
    await waitFor(() => expect(screen.getByRole('spinbutton', { name: 'Sueldo mínimo' })).toHaveValue(30000))
    const save = within(more()).getByRole('button', { name: 'Guardar cambios' })
    expect(save).toBeDisabled()
    await userEvent.type(within(more()).getByRole('spinbutton', { name: 'Desde' }), '2')
    await userEvent.click(within(more()).getByRole('checkbox', { name: 'Jornada completa' }))
    await userEvent.click(within(more()).getByRole('checkbox', { name: 'Ofertas que no dicen qué empresa contrata' }))
    const salary = within(more()).getByRole('spinbutton', { name: 'Sueldo mínimo' })
    await userEvent.clear(salary)
    await userEvent.type(salary, '35000')
    expect(within(more()).getByText('Al guardar se recalcula el encaje de tus ofertas abiertas.')).toBeInTheDocument()
    await userEvent.click(save)

    await waitFor(() => expect(puts()).toHaveLength(2))
    expect(puts()[0].path).toBe('/profile/sections/preferences')
    expect(puts()[0].body.file_hash).toBe('h1')
    expect(puts()[0].body.content).toMatchObject({
      min_years_required: 2,
      employment_types: ['full_time'],
      contract_types: ['permanent', 'freelance'],
      exclude_signals: ['employer_hidden'],
      roles: ['Data Engineer'], // lo de la franja, tal cual
    })
    // El sueldo va después, con el `file_hash` que dejó lo anterior.
    expect(puts()[1]).toMatchObject({ path: '/profile/salary-floor', body: { file_hash: 'h2', salary_floor_eur: 35000 } })
    expect(await within(more()).findByText('Guardado en tu perfil.')).toBeInTheDocument()

    await waitFor(() => expect(within(more()).getByRole('button', { name: 'Deshacer' })).toBeEnabled())
    await userEvent.click(within(more()).getByRole('button', { name: 'Deshacer' }))
    await waitFor(() => expect(puts()).toHaveLength(4))
    expect(puts()[2].body.file_hash).toBe('h3')
    expect(puts()[2].body.content).toMatchObject({ min_years_required: null, employment_types: [] })
    expect(puts()[3].body).toEqual({ file_hash: 'h4', salary_floor_eur: 30000 })
    expect(await within(more()).findByText('Deshecho: tus ajustes vuelven a estar como antes.')).toBeInTheDocument()
  })

  it('el «Deshacer» de la franja solo devuelve lo que cambió en ella, no lo guardado después en «Más ajustes»', async () => {
    const puts = withProfile()
    renderApp('/buscar/ajustes')
    await findMore()
    const modes = within(strip()).getByRole('group', { name: 'Modalidad' })
    await userEvent.click(within(modes).getByRole('checkbox', { name: 'Remoto' }))
    await waitFor(() => expect(puts()).toHaveLength(1))
    const from = within(more()).getByRole('spinbutton', { name: 'Desde' })
    await waitFor(() => expect(from).toBeEnabled())
    await userEvent.type(from, '2')
    await userEvent.click(within(more()).getByRole('button', { name: 'Guardar cambios' }))
    await waitFor(() => expect(puts()).toHaveLength(2))
    // El primer «Deshacer» es el de la franja (el de «Más ajustes» va después).
    const undo = () => within(strip()).getAllByRole('button', { name: 'Deshacer' })[0]
    await waitFor(() => expect(undo()).toBeEnabled())
    await userEvent.click(undo())
    await waitFor(() => expect(puts()).toHaveLength(3))
    expect(puts()[2].body.content).toMatchObject({ remote_modes: [], min_years_required: 2 })
  })

  it('«Restablecer» lo deja todo vacío y «Descartar cambios» vuelve a lo guardado', async () => {
    const puts = withProfile()
    renderApp('/buscar/ajustes')
    await findMore()
    await waitFor(() => expect(screen.getByRole('spinbutton', { name: 'Sueldo mínimo' })).toHaveValue(30000))
    await userEvent.click(within(more()).getByRole('button', { name: 'Restablecer' }))
    expect(within(more()).getByRole('spinbutton', { name: 'Sueldo mínimo' })).toHaveValue(null)
    expect(within(more()).getByRole('checkbox', { name: 'Indefinido' })).not.toBeChecked()
    expect(within(more()).queryByRole('list', { name: 'Palabras en el título' })).not.toBeInTheDocument()
    await userEvent.click(within(more()).getByRole('button', { name: 'Descartar cambios' }))
    expect(within(more()).getByRole('spinbutton', { name: 'Sueldo mínimo' })).toHaveValue(30000)
    expect(within(more()).getByRole('checkbox', { name: 'Indefinido' })).toBeChecked()

    await userEvent.click(within(more()).getByRole('button', { name: 'Restablecer' }))
    await userEvent.click(within(more()).getByRole('button', { name: 'Guardar cambios' }))
    await waitFor(() => expect(puts()).toHaveLength(2))
    expect(puts()[0].body.content).toMatchObject({ contract_types: [], languages_for_work: [], discard_title_keywords: [], exclude_signals: [] })
    expect(puts()[1].body).toEqual({ file_hash: 'h2', salary_floor_eur: null })
  })

  it('no guarda un sueldo que no es un número entero positivo, y un conflicto ofrece «Recargar»', async () => {
    const calls = mockApi(
      routes([platform(1, 'InfoJobs')], {
        'GET /profile/editable': editable(preferences, 'h1'),
        'GET /profile/role-suggestions': [],
        'GET /profile/salary-floor': { salary_floor_eur: 30000, file_hash: 'h1' },
        'PUT /profile/salary-floor': {
          status: 409,
          body: { ok: false, error: { type: 'conflict', message: 'El fichero ha cambiado.', details: [] } },
        },
      }),
    )
    renderApp('/buscar/ajustes')
    await findMore()
    const salary = await within(more()).findByRole('spinbutton', { name: 'Sueldo mínimo' })
    await waitFor(() => expect(salary).toHaveValue(30000))
    await userEvent.clear(salary)
    await userEvent.type(salary, '-3')
    expect(within(more()).getByText(/número entero de euros mayor que 0/)).toBeInTheDocument()
    expect(within(more()).getByRole('button', { name: 'Guardar cambios' })).toBeDisabled()
    await userEvent.clear(salary)
    await userEvent.type(salary, '35000')
    await userEvent.click(within(more()).getByRole('button', { name: 'Guardar cambios' }))
    expect(await within(more()).findByRole('alert')).toHaveTextContent('Tu perfil ha cambiado')
    // Solo el sueldo cambió: no se toca la sección.
    expect(calls.some((c) => c.path === '/profile/sections/preferences')).toBe(false)
    const reads = () => calls.filter((c) => c.path === '/profile/editable').length
    const before = reads()
    await userEvent.click(within(more()).getByRole('button', { name: 'Recargar' }))
    await waitFor(() => expect(reads()).toBeGreaterThan(before))
    expect(within(more()).queryByRole('alert')).not.toBeInTheDocument()
  })

  it('los idiomas se escriben por su nombre y se guardan como código', async () => {
    const puts = withProfile()
    renderApp('/buscar/ajustes')
    await findMore()
    const tags = await within(more()).findByRole('list', { name: 'Idiomas de trabajo' })
    expect(within(tags).getByText('español')).toBeInTheDocument()
    const input = within(more()).getByRole('combobox', { name: 'Idiomas de trabajo' })
    await userEvent.type(input, 'klingon{Enter}')
    expect(within(more()).getByText('«klingon» no es un idioma de la lista.')).toBeInTheDocument()
    await userEvent.clear(input)
    await userEvent.type(input, 'Francés{Enter}')
    await userEvent.click(within(more()).getByRole('button', { name: 'Guardar cambios' }))
    await waitFor(() => expect(puts()).toHaveLength(1))
    expect(puts()[0].body.content).toMatchObject({ languages_for_work: ['es', 'fr'] })
  })
})
