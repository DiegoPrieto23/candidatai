import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { SourceRunResult, SourceTestResult, SourceView } from '@/api/client'
import { mockApi, renderApp, status } from '@/test/utils'

function source(overrides: Partial<SourceView> = {}): SourceView {
  return {
    id: 1,
    kind: 'greenhouse',
    kind_label: 'Greenhouse',
    name: 'Acme Datos',
    active: true,
    config: { slug: 'acmedatos', region: 'global', title_keywords: [] },
    keys_missing: false,
    last_run_at: '2026-10-02T05:30:00Z',
    last_run: {
      id: 3,
      actor: 'system',
      started_at: '2026-10-02T05:30:00Z',
      finished_at: '2026-10-02T05:30:02Z',
      found: 12,
      after_filters: 3,
      created: 2,
      existing: 0, skipped_known: 0, filtered_out: 0, left_by_limit: 0, reopened: 0,
      errors: [],
    },
    ...overrides,
  }
}

const preview: SourceTestResult = {
  kind: 'greenhouse',
  name: 'Brétema',
  found: 12,
  after_filters: 1,
  filters_applied: true,
  message: '12 ofertas encontradas, 1 tras filtros',
  errors: [],
  jobs: [
    { external_id: '1', title: 'Data Engineer', company: 'Brétema', location: 'Vigo', url: 'https://example.com/1', passed: true, reason: null },
    { external_id: '2', title: 'Account Executive', company: 'Brétema', location: 'Madrid', url: 'https://example.com/2', passed: false, reason: 'El título no encaja con tus puestos.' },
  ],
}

const URL = 'https://careers.bretema.example/vigo/'
const resolved: SourceTestResult = {
  ...preview,
  resolution: {
    url: URL,
    how: 'page',
    kind: 'greenhouse',
    kind_label: 'Greenhouse',
    slug: 'bretema',
    region: 'global',
    locations: ['Vigo'],
    website: 'https://bretema.example',
    issues: [],
  },
}

describe('Empresas objetivo', () => {
  it('lista las fuentes con su última ejecución y oculta las manuales', async () => {
    mockApi({
      'GET /status': status(),
      'GET /sources': {
        sources: [
          source({ config: { slug: 'acmedatos', region: 'global', title_keywords: [], locations: ['Madrid'] } }),
          source({ id: 2, kind: 'manual_text', kind_label: 'Alta manual por texto', name: 'Manual', config: {} }),
          source({ id: 3, kind: 'adzuna', kind_label: 'Adzuna', name: 'Datos Vigo', config: { query: 'data' }, keys_missing: true, last_run: null, active: false }),
        ],
      },
    })
    renderApp('/empresas')

    expect(await screen.findByRole('heading', { name: 'Acme Datos' })).toBeInTheDocument()
    // Solo lo nuevo que encaja contigo: nada de «encontradas» ni «tras filtros».
    expect(screen.getByText(/2 ofertas nuevas para ti/)).toBeInTheDocument()
    expect(screen.queryByText(/tras filtros|encontradas/)).not.toBeInTheDocument()
    expect(screen.getByText('Solo Madrid')).toBeInTheDocument()
    expect(screen.queryByText('Manual')).not.toBeInTheDocument()
    expect(screen.getByText('Faltan sus claves de acceso')).toBeInTheDocument()
    expect(screen.getByText('Pausada')).toBeInTheDocument()
    expect(screen.getByText('Aún no se ha revisado')).toBeInTheDocument()
    // Lo de dentro del ATS no se enseña; la búsqueda de un portal, sí.
    expect(screen.queryByText('acmedatos')).not.toBeInTheDocument()
    expect(screen.getByText('«data»')).toBeInTheDocument()
    // Con empresas, el alta va tras su botón.
    expect(screen.queryByRole('form', { name: 'Añadir fuente' })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Añadir empresa' }))
    expect(screen.getByRole('form', { name: 'Añadir fuente' })).toBeInTheDocument()
  })

  it('prueba una empresa con su nombre y su dirección y luego la añade', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /sources': { sources: [] },
      'POST /sources/test': resolved,
      'POST /sources': source({ id: 5, name: 'Brétema' }),
    })
    renderApp('/empresas')
    // Sin ninguna, lo explica y el formulario sale abierto de entrada.
    expect(await screen.findByText('Aún no sigues ninguna empresa')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Añadir empresa' })).not.toBeInTheDocument()
    const form = screen.getByRole('form', { name: 'Añadir fuente' })
    // Solo dos campos: nada de ATS ni de slug a la vista.
    expect(within(form).queryByLabelText('Nombre en la dirección')).not.toBeInTheDocument()
    expect(within(form).queryByLabelText('Web de empleo que usa')).not.toBeInTheDocument()
    await userEvent.type(within(form).getByLabelText('Empresa'), 'Brétema')
    await userEvent.type(within(form).getByLabelText('Dirección de su web de empleo'), URL)
    await userEvent.click(within(form).getByRole('button', { name: 'Probar' }))

    expect(await within(form).findByText('Encontrada: usa Greenhouse · 1 oferta para ti')).toBeInTheDocument()
    expect(within(form).getByText('Solo Vigo')).toBeInTheDocument()
    expect(within(form).getByText(/Greenhouse · bretema, enlazado desde su web/)).toBeInTheDocument()
    expect(within(form).getByRole('link', { name: 'Data Engineer' })).toHaveAttribute('href', 'https://example.com/1')
    // Lo que no encaja no se enseña, ni siquiera plegado.
    expect(within(form).queryByText('Account Executive')).not.toBeInTheDocument()
    expect(within(form).queryByText(/filtradas/)).not.toBeInTheDocument()

    await userEvent.click(within(form).getByRole('button', { name: 'Añadir' }))
    expect(await within(form).findByText(/«Brétema» añadida/)).toBeInTheDocument()
    const posted = calls.filter((c) => c.method === 'POST').map((c) => c.body)
    expect(posted[0]).toMatchObject({ name: 'Brétema', url: URL })
    expect(posted[0]).not.toHaveProperty('kind')
    // Al añadir, lo detectado: no vuelve a buscar su web de empleo.
    expect(posted[1]).toMatchObject({ kind: 'greenhouse', name: 'Brétema', slug: 'bretema', url: URL, locations: ['Vigo'] })
  })

  it('«Más opciones» trae lo detectado para corregirlo', async () => {
    mockApi({ 'GET /status': status(), 'GET /sources': { sources: [] }, 'POST /sources/test': resolved })
    renderApp('/empresas')
    const form = await screen.findByRole('form', { name: 'Añadir fuente' })
    await userEvent.type(within(form).getByLabelText('Empresa'), 'Brétema')
    await userEvent.type(within(form).getByLabelText('Dirección de su web de empleo'), URL)
    await userEvent.click(within(form).getByRole('button', { name: 'Probar' }))
    await within(form).findByText('Solo Vigo')
    await userEvent.click(within(form).getByRole('button', { name: 'Más opciones' }))
    expect(within(form).getByLabelText('Nombre en la dirección')).toHaveValue('bretema')
    expect(within(form).getByRole('combobox', { name: 'Web de empleo que usa' })).toHaveTextContent('Greenhouse')
  })

  it('una web sin sistema conocido se añade a los portales', async () => {
    mockApi({
      'GET /status': status(),
      'GET /sources': { sources: [] },
      'POST /sources/test': {
        ...preview,
        kind: 'agent_browse',
        found: 0,
        after_filters: 0,
        jobs: [],
        resolution: { ...resolved.resolution!, how: 'none', kind: null, kind_label: null, slug: null, locations: [] },
      },
      'POST /sources': source({ id: 7, kind: 'agent_browse', kind_label: 'Búsqueda con navegador', name: 'Brétema' }),
    })
    renderApp('/empresas')
    const form = await screen.findByRole('form', { name: 'Añadir fuente' })
    await userEvent.type(within(form).getByLabelText('Empresa'), 'Brétema')
    await userEvent.type(within(form).getByLabelText('Dirección de su web de empleo'), URL)
    await userEvent.click(within(form).getByRole('button', { name: 'Probar' }))
    expect(await within(form).findByText(/No reconocemos el sistema de empleo/)).toBeInTheDocument()
    await userEvent.click(within(form).getByRole('button', { name: 'Añadir' }))
    expect(await within(form).findByText(/añadida a tus portales/)).toBeInTheDocument()
  })

  it('sin ofertas que encajen, lo dice', async () => {
    mockApi({
      'GET /status': status(),
      'GET /sources': { sources: [] },
      'POST /sources/test': { ...preview, after_filters: 0, jobs: [preview.jobs[1]!] },
    })
    renderApp('/empresas')
    const form = await screen.findByRole('form', { name: 'Añadir fuente' })
    await userEvent.type(within(form).getByLabelText('Empresa'), 'Brétema')
    await userEvent.type(within(form).getByLabelText('Dirección de su web de empleo'), URL)
    await userEvent.click(within(form).getByRole('button', { name: 'Probar' }))
    expect(await screen.findByText('0 ofertas para ti')).toBeInTheDocument()
    expect(screen.getByText('Ninguna oferta encaja ahora con tu búsqueda; se revisa cada día.')).toBeInTheDocument()
    expect(screen.queryByText('Account Executive')).not.toBeInTheDocument()
  })

  it('cambia los lugares de una empresa desde su tarjeta', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /sources': { sources: [source()] },
      'POST /sources/1/locations': { status: 200, body: source() },
    })
    renderApp('/empresas')
    await userEvent.click(await screen.findByRole('button', { name: 'Más acciones de Acme Datos' }))
    await userEvent.click(await screen.findByRole('menuitem', { name: 'Limitar a unos lugares' }))
    await userEvent.type(screen.getByRole('textbox', { name: 'Lugares de Acme Datos' }), 'Madrid, Vigo')
    await userEvent.click(screen.getByRole('button', { name: 'Guardar' }))
    expect(calls.find((c) => c.path === '/sources/1/locations')?.body).toEqual({ locations: ['Madrid', 'Vigo'] })
  })

  it('pide búsqueda en vez de dirección para un portal', async () => {
    mockApi({ 'GET /status': status(), 'GET /sources': { sources: [] } })
    renderApp('/empresas')
    const form = await screen.findByRole('form', { name: 'Añadir fuente' })
    await userEvent.click(within(form).getByRole('button', { name: 'Más opciones' }))
    await userEvent.click(within(form).getByRole('combobox', { name: 'Web de empleo que usa' }))
    await userEvent.click(await screen.findByRole('option', { name: 'Adzuna (búsqueda)' }))
    expect(within(form).getByLabelText('Palabras de búsqueda')).toBeInTheDocument()
    expect(within(form).queryByLabelText('Dirección de su web de empleo')).not.toBeInTheDocument()
    expect(within(form).queryByLabelText('Nombre en la dirección')).not.toBeInTheDocument()
    expect(within(form).getByLabelText('Ubicación (opcional)')).toBeInTheDocument()
  })

  it('marca el campo con error al añadir', async () => {
    mockApi({
      'GET /status': status(),
      'GET /sources': { sources: [] },
      'POST /sources': {
        status: 422,
        body: { ok: false, error: { type: 'validation_error', message: 'Entrada no válida (1 error): url.', details: [{ field: 'url', received: 'ftp://x', reason: 'Dirección no válida.' }] } },
      },
    })
    renderApp('/empresas')
    const form = await screen.findByRole('form', { name: 'Añadir fuente' })
    await userEvent.type(within(form).getByLabelText('Empresa'), 'X')
    await userEvent.type(within(form).getByLabelText('Dirección de su web de empleo'), 'ftp://x')
    await userEvent.click(within(form).getByRole('button', { name: 'Añadir' }))
    expect(await within(form).findByText('Dirección no válida.')).toBeInTheDocument()
  })

  it('cada empresa tiene un interruptor y un menú, sin «Probar»', async () => {
    mockApi({ 'GET /status': status(), 'GET /sources': { sources: [source(), source({ id: 2, name: 'Brétema', active: false })] } })
    renderApp('/empresas')
    const list = (await screen.findByRole('heading', { name: 'Acme Datos' })).closest('ul')!
    const rows = within(list).getAllByRole('listitem')
    expect(rows).toHaveLength(2)
    expect(within(rows[0]!).getByRole('switch', { name: 'Revisar Acme Datos cada día' })).toHaveAttribute('aria-checked', 'true')
    expect(within(rows[1]!).getByRole('switch', { name: 'Revisar Brétema cada día' })).toHaveAttribute('aria-checked', 'false')
    expect(within(rows[1]!).getByText('Pausada')).toBeInTheDocument()
    for (const row of rows) {
      expect(within(row).getAllByRole('button').map((b) => b.getAttribute('aria-label'))).toEqual([
        expect.stringMatching(/^Más acciones de /),
      ])
      expect(within(row).queryByRole('button', { name: 'Probar' })).not.toBeInTheDocument()
    }
    // Pausada, «Buscar ahora» no se puede pulsar.
    await userEvent.click(within(rows[1]!).getByRole('button', { name: 'Más acciones de Brétema' }))
    expect(await screen.findByRole('menuitem', { name: 'Buscar ahora' })).toHaveAttribute('aria-disabled', 'true')
  })

  it('el menú abre el campo con el foco dentro, y pasar de la web a los lugares empieza de cero', async () => {
    mockApi({
      'GET /status': status(),
      'GET /sources': { sources: [source({ website: 'https://careers.acmedatos.example', config: { slug: 'acmedatos', locations: ['Madrid'] } })] },
    })
    renderApp('/empresas')
    await userEvent.click(await screen.findByRole('button', { name: 'Más acciones de Acme Datos' }))
    await userEvent.click(await screen.findByRole('menuitem', { name: 'Cambiar web' }))
    const web = screen.getByRole('textbox', { name: 'Web de Acme Datos' })
    await waitFor(() => expect(web).toHaveFocus())
    expect(web).toHaveValue('careers.acmedatos.example')

    await userEvent.click(screen.getByRole('button', { name: 'Más acciones de Acme Datos' }))
    await userEvent.click(await screen.findByRole('menuitem', { name: 'Cambiar lugares' }))
    const places = screen.getByRole('textbox', { name: 'Lugares de Acme Datos' })
    await waitFor(() => expect(places).toHaveFocus())
    expect(places).toHaveValue('Madrid')
    expect(screen.queryByRole('textbox', { name: 'Web de Acme Datos' })).not.toBeInTheDocument()
  })

  it('ejecuta una fuente ahora y la pausa', async () => {
    const run: SourceRunResult = {
      source_id: 1,
      name: 'Acme Datos',
      kind: 'greenhouse',
      run_id: 4,
      skipped: null,
      found: 12,
      after_filters: 3,
      created: 2,
      existing: 1,
      duplicates: 0,
      job_ids: [7, 8],
      errors: [],
      message: 'Greenhouse · Acme Datos: 12 ofertas encontradas, 3 tras filtros, 2 nuevas, 1 ya estaba',
    }
    const calls = mockApi({
      'GET /status': status(),
      'GET /sources': { sources: [source()] },
      'POST /sources/1/run': { status: 200, body: run },
      'POST /sources/1/active': { status: 200, body: source({ active: false }) },
    })
    renderApp('/empresas')
    await userEvent.click(await screen.findByRole('button', { name: 'Más acciones de Acme Datos' }))
    await userEvent.click(await screen.findByRole('menuitem', { name: 'Buscar ahora' }))
    expect(calls.some((c) => c.path === '/sources/1/run')).toBe(true)
    expect(await screen.findByText('2 ofertas nuevas para ti.')).toBeInTheDocument()
    expect(screen.queryByText(/tras filtros/)).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Verlas' })).toHaveAttribute('href', '/bandeja?stage=pending_extraction')

    await userEvent.click(screen.getByRole('switch', { name: 'Revisar Acme Datos cada día' }))
    expect(calls.find((c) => c.path === '/sources/1/active')?.body).toEqual({ active: false })
  })

  it('enseña el logo de la web de la empresa y deja cambiarla', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /sources': { sources: [source({ website: 'https://careers.acmedatos.example' })] },
      'POST /sources/1/website': { status: 200, body: source({ website: 'https://acmedatos.example' }) },
    })
    const { container } = renderApp('/empresas')
    expect(await screen.findByRole('link', { name: /careers\.acmedatos\.example/ })).toHaveAttribute(
      'href',
      'https://careers.acmedatos.example',
    )
    // El icono lo sirve la app: tu navegador no visita la web de la empresa.
    expect(container.querySelector('img')).toHaveAttribute(
      'src',
      'http://127.0.0.1:8000/sources/1/icon?v=careers.acmedatos.example',
    )

    await userEvent.click(screen.getByRole('button', { name: 'Más acciones de Acme Datos' }))
    await userEvent.click(await screen.findByRole('menuitem', { name: 'Cambiar web' }))
    const input = screen.getByRole('textbox', { name: 'Web de Acme Datos' })
    await userEvent.clear(input)
    await userEvent.type(input, 'acmedatos.example')
    await userEvent.click(screen.getByRole('button', { name: 'Guardar' }))
    expect(calls.find((c) => c.path === '/sources/1/website')?.body).toEqual({ website: 'acmedatos.example' })
  })

  it('sin web, pone la inicial y ofrece añadirla', async () => {
    mockApi({ 'GET /status': status(), 'GET /sources': { sources: [source({ website: null })] } })
    renderApp('/empresas')
    expect(await screen.findByText('A')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Más acciones de Acme Datos' }))
    expect(await screen.findByRole('menuitem', { name: 'Añadir su web (para el logo)' })).toBeInTheDocument()
  })

  it('en «Más opciones», los ATS con su ejemplo de slug y su idioma en Personio', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /sources': { sources: [] },
      'POST /sources': source({ id: 6, kind: 'personio', kind_label: 'Personio', name: 'Brétema' }),
    })
    renderApp('/empresas')
    const form = await screen.findByRole('form', { name: 'Añadir fuente' })
    await userEvent.click(within(form).getByRole('button', { name: 'Más opciones' }))
    await userEvent.click(within(form).getByRole('combobox', { name: 'Web de empleo que usa' }))
    for (const name of ['Detectarla sola', 'Teamtailor', 'Workable', 'SmartRecruiters', 'Recruitee', 'Manfred (búsqueda)', 'freehire (búsqueda)']) {
      expect(await screen.findByRole('option', { name })).toBeInTheDocument()
    }
    await userEvent.click(screen.getByRole('option', { name: 'Personio' }))
    expect(within(form).getByText('<nombre>.jobs.personio.de')).toBeInTheDocument()
    expect(within(form).getByRole('link', { name: 'Cómo encontrarlo' })).toHaveAttribute(
      'href',
      expect.stringContaining('docs/FUENTES_OFERTAS.md'),
    )
    await userEvent.type(within(form).getByLabelText('Empresa'), 'Brétema')
    await userEvent.type(within(form).getByLabelText('Nombre en la dirección'), 'bretema')
    await userEvent.type(within(form).getByLabelText('Idioma de la descripción (opcional)'), 'EN')
    await userEvent.click(within(form).getByRole('button', { name: 'Añadir' }))
    expect(await within(form).findByText(/«Brétema» añadida/)).toBeInTheDocument()
    expect(calls.find((c) => c.method === 'POST')?.body).toMatchObject({
      kind: 'personio',
      slug: 'bretema',
      language: 'en',
      url: null,
    })
  })

  it('busca en freehire por país y solo en remoto', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /sources': { sources: [] },
      'POST /sources/test': { ...preview, kind: 'freehire', name: 'Datos remoto' },
    })
    renderApp('/empresas')
    const form = await screen.findByRole('form', { name: 'Añadir fuente' })
    await userEvent.click(within(form).getByRole('button', { name: 'Más opciones' }))
    await userEvent.click(within(form).getByRole('combobox', { name: 'Web de empleo que usa' }))
    await userEvent.click(await screen.findByRole('option', { name: 'freehire (búsqueda)' }))
    expect(within(form).queryByLabelText('Nombre en la dirección')).not.toBeInTheDocument()
    expect(within(form).getByText('Sin claves. Busca en el título de las ofertas.')).toBeInTheDocument()
    await userEvent.type(within(form).getByLabelText('Nombre de la búsqueda'), 'Datos remoto')
    await userEvent.type(within(form).getByLabelText('Palabras de búsqueda'), 'data engineer')
    const country = within(form).getByLabelText('País')
    await userEvent.clear(country)
    await userEvent.type(country, 'PT')
    await userEvent.click(within(form).getByLabelText('Solo ofertas en remoto'))
    await userEvent.click(within(form).getByRole('button', { name: 'Probar' }))
    expect(await within(form).findByText('1 oferta para ti')).toBeInTheDocument()
    expect(calls.find((c) => c.method === 'POST')?.body).toMatchObject({
      kind: 'freehire',
      query: 'data engineer',
      country: 'pt',
      remote_only: true,
      slug: null,
    })
  })
})
