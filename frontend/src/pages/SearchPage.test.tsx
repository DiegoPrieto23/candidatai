import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
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

/** La franja de arriba: qué buscas, dónde y cuántas, y el botón. */
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
        { 'POST /agent/launch': { status: 202, body: launched } },
      ),
    )
    renderApp('/buscar')
    const list = await screen.findByRole('list', { name: 'Portales en los que buscar' })
    expect(within(list).getByRole('checkbox', { name: /InfoJobs/ })).toBeChecked()
    expect(within(list).getByText('4 nuevas')).toBeInTheDocument()
    expect(within(list).getByText('de 9', { exact: false })).toBeInTheDocument()
    expect(strip()).toHaveTextContent('2 portales · hasta 20 ofertas')
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
    await waitFor(() => expect(calls.some((c) => c.method === 'POST')).toBe(true))
    const body = calls.find((c) => c.method === 'POST')?.body as { action: string; search: Record<string, unknown> }
    expect(body.action).toBe('search-jobs')
    expect(body.search).toEqual({ platform_ids: [] })
  })

  it('manda los portales elegidos y la búsqueda puntual', async () => {
    const calls = mockApi(
      routes([platform(1, 'InfoJobs'), platform(2, 'Tecnoempleo')], { 'POST /agent/launch': { status: 202, body: launched } }),
    )
    renderApp('/buscar')
    await userEvent.click(await screen.findByRole('checkbox', { name: /Tecnoempleo/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Buscar otra cosa solo esta vez' }))
    expect(strip()).toHaveTextContent('Solo esta vez · tu perfil no cambia')
    await userEvent.type(screen.getByLabelText('Puesto'), 'Data Engineer')
    await userEvent.type(screen.getByLabelText('Dónde'), 'Madrid')
    await userEvent.click(screen.getByRole('button', { name: /^Buscar ahora/ }))
    await waitFor(() => expect(calls.some((c) => c.method === 'POST')).toBe(true))
    const body = calls.find((c) => c.method === 'POST')?.body as { search: unknown }
    expect(body.search).toEqual({ platform_ids: [1], role: 'Data Engineer', location: 'Madrid' })
  })

  it('no deja lanzar sin portales ni con caracteres que no se admiten', async () => {
    mockApi(routes([platform(1, 'InfoJobs')]))
    renderApp('/buscar')
    const box = await screen.findByRole('checkbox', { name: /InfoJobs/ })
    await userEvent.click(box)
    expect(screen.getByText('Elige al menos un portal.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^Buscar ahora/ })).toBeDisabled()
    await userEvent.click(box)
    await userEvent.click(screen.getByRole('button', { name: 'Buscar otra cosa solo esta vez' }))
    await userEvent.type(screen.getByLabelText('Puesto'), 'x"; rm')
    expect(within(strip()).getByRole('alert')).toHaveTextContent(/solo letras/i)
    expect(screen.getByRole('button', { name: /^Buscar ahora/ })).toBeDisabled()
    // Al volver a tu búsqueda, lo de esta vez deja de contar.
    await userEvent.click(screen.getByRole('button', { name: 'Volver a tu búsqueda' }))
    expect(screen.queryByLabelText('Puesto')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^Buscar ahora/ })).toBeEnabled()
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
    expect(strip()).toHaveTextContent('2 portales · hasta 25 ofertas')
    expect(within(list).getByText('2 búsquedas guardadas')).toBeInTheDocument()
    expect(within(list).getByText('1 búsqueda guardada')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Qué ofertas cuentan' })).toBeInTheDocument()
    // Ningún texto nombra un agente concreto ni pide conectar el navegador: lo dice tu agente si falta.
    expect(screen.queryByText(/navegador conectado/)).not.toBeInTheDocument()
    expect(document.body.textContent).not.toMatch(/Claude|Codex|Chrome/)
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
    const control = await screen.findByRole('combobox', { name: /ofertas por portal/i })
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
    const control = await screen.findByRole('combobox', { name: /ofertas por portal/i })
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

  it('sin portales, lleva a elegirlos', async () => {
    mockApi(routes([]))
    renderApp('/buscar')
    expect(await screen.findByText('Aún no hay portales en los que buscar')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Ir a «Dónde buscar»' })).toHaveAttribute('href', '/fuentes/plataformas')
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
})
