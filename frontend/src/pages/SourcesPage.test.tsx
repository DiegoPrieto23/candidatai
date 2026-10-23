import { screen, within } from '@testing-library/react'
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
      errors: [],
    },
    ...overrides,
  }
}

const preview: SourceTestResult = {
  kind: 'greenhouse',
  name: 'Brétema',
  found: 12,
  after_filters: 3,
  filters_applied: true,
  message: '12 ofertas encontradas, 3 tras filtros',
  errors: [],
  jobs: [
    { external_id: '1', title: 'Data Engineer', company: 'Brétema', location: 'Vigo', url: 'https://example.com/1', passed: true, reason: null },
    { external_id: '2', title: 'Account Executive', company: 'Brétema', location: 'Madrid', url: 'https://example.com/2', passed: false, reason: 'El título no encaja con tus puestos.' },
  ],
}

describe('Empresas objetivo', () => {
  it('lista las fuentes con su última ejecución y oculta las manuales', async () => {
    mockApi({
      'GET /status': status(),
      'GET /sources': {
        sources: [
          source(),
          source({ id: 2, kind: 'manual_text', kind_label: 'Alta manual por texto', name: 'Manual', config: {} }),
          source({ id: 3, kind: 'adzuna', kind_label: 'Adzuna', name: 'Datos Vigo', config: { query: 'data' }, keys_missing: true, last_run: null, active: false }),
        ],
      },
    })
    renderApp('/empresas')

    expect(await screen.findByRole('heading', { name: 'Acme Datos' })).toBeInTheDocument()
    expect(screen.getByText(/12 encontradas, 3 tras filtros,\s+2 nuevas/)).toBeInTheDocument()
    expect(screen.queryByText('Manual')).not.toBeInTheDocument()
    expect(screen.getByText('Sin claves en .env')).toBeInTheDocument()
    expect(screen.getByText('Pausada')).toBeInTheDocument()
    expect(screen.getByText('Aún no se ha ejecutado')).toBeInTheDocument()
  })

  it('prueba una empresa antes de guardarla y luego la añade', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /sources': { sources: [] },
      'POST /sources/test': preview,
      'POST /sources': source({ id: 5, name: 'Brétema' }),
    })
    renderApp('/empresas')
    expect(await screen.findByText('Aún no sigues ninguna empresa')).toBeInTheDocument()

    const form = screen.getByRole('form', { name: 'Añadir fuente' })
    await userEvent.type(within(form).getByLabelText('Empresa'), 'Brétema')
    await userEvent.type(within(form).getByLabelText('Slug del tablero'), 'bretema')
    await userEvent.click(within(form).getByRole('button', { name: 'Probar' }))

    expect(await within(form).findByText('12 ofertas encontradas, 3 tras filtros')).toBeInTheDocument()
    expect(within(form).getByRole('link', { name: 'Data Engineer' })).toHaveAttribute('href', 'https://example.com/1')
    expect(within(form).queryByText('Account Executive')).not.toBeInTheDocument()
    await userEvent.click(within(form).getByRole('button', { name: /Ver también las 9 filtradas/ }))
    expect(within(form).getByText('Account Executive')).toBeInTheDocument()

    await userEvent.click(within(form).getByRole('button', { name: 'Añadir' }))
    expect(await within(form).findByText(/«Brétema» añadida/)).toBeInTheDocument()
    const posted = calls.filter((c) => c.method === 'POST').map((c) => c.body)
    expect(posted[0]).toMatchObject({ kind: 'greenhouse', name: 'Brétema', slug: 'bretema', query: null })
    expect(posted[1]).toEqual(posted[0])
  })

  it('pide búsqueda en vez de slug para un portal', async () => {
    mockApi({ 'GET /status': status(), 'GET /sources': { sources: [] } })
    renderApp('/empresas')
    const form = await screen.findByRole('form', { name: 'Añadir fuente' })
    await userEvent.click(within(form).getByRole('combobox', { name: 'Origen' }))
    await userEvent.click(await screen.findByRole('option', { name: 'Adzuna (búsqueda)' }))
    expect(within(form).getByLabelText('Palabras de búsqueda')).toBeInTheDocument()
    expect(within(form).queryByLabelText('Slug del tablero')).not.toBeInTheDocument()
    expect(within(form).getByLabelText('Ubicación (opcional)')).toBeInTheDocument()
  })

  it('marca el campo con error al añadir', async () => {
    mockApi({
      'GET /status': status(),
      'GET /sources': { sources: [] },
      'POST /sources': {
        status: 422,
        body: { ok: false, error: { type: 'validation_error', message: 'Entrada no válida (1 error): slug.', details: [{ field: 'slug', received: 'a/b', reason: 'Slug no válido.' }] } },
      },
    })
    renderApp('/empresas')
    const form = await screen.findByRole('form', { name: 'Añadir fuente' })
    await userEvent.type(within(form).getByLabelText('Empresa'), 'X')
    await userEvent.type(within(form).getByLabelText('Slug del tablero'), 'a/b')
    await userEvent.click(within(form).getByRole('button', { name: 'Añadir' }))
    expect(await within(form).findByText('Slug no válido.')).toBeInTheDocument()
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
    await userEvent.click(await screen.findByRole('button', { name: /Ejecutar ahora/ }))
    expect(await screen.findByText(/2 nuevas, 1 ya estaba/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Verlas' })).toHaveAttribute('href', '/bandeja?stage=pending_extraction')

    await userEvent.click(screen.getByRole('button', { name: 'Pausar' }))
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
    expect(container.querySelector('img')).toHaveAttribute('src', 'https://careers.acmedatos.example/favicon.ico')

    await userEvent.click(screen.getByRole('button', { name: 'Cambiar web' }))
    const input = screen.getByRole('textbox', { name: 'Web de Acme Datos' })
    await userEvent.clear(input)
    await userEvent.type(input, 'acmedatos.example')
    await userEvent.click(screen.getByRole('button', { name: 'Guardar' }))
    expect(calls.find((c) => c.path === '/sources/1/website')?.body).toEqual({ website: 'acmedatos.example' })
  })

  it('sin web, pone la inicial y ofrece añadirla', async () => {
    mockApi({ 'GET /status': status(), 'GET /sources': { sources: [source({ website: null })] } })
    renderApp('/empresas')
    expect(await screen.findByRole('button', { name: 'Añadir su web para el logo' })).toBeInTheDocument()
    expect(screen.getByText('A')).toBeInTheDocument()
  })

  it('ofrece los ATS nuevos con su ejemplo de slug y su idioma en Personio', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /sources': { sources: [] },
      'POST /sources': source({ id: 6, kind: 'personio', kind_label: 'Personio', name: 'Brétema' }),
    })
    renderApp('/empresas')
    const form = await screen.findByRole('form', { name: 'Añadir fuente' })
    await userEvent.click(within(form).getByRole('combobox', { name: 'Origen' }))
    for (const name of ['Teamtailor', 'Workable', 'SmartRecruiters', 'Recruitee', 'Manfred (búsqueda)', 'freehire (búsqueda)']) {
      expect(await screen.findByRole('option', { name })).toBeInTheDocument()
    }
    await userEvent.click(screen.getByRole('option', { name: 'Personio' }))
    expect(within(form).getByText('<slug>.jobs.personio.de')).toBeInTheDocument()
    expect(within(form).getByRole('link', { name: 'Cómo encontrarlo' })).toHaveAttribute(
      'href',
      expect.stringContaining('docs/FUENTES_OFERTAS.md'),
    )
    await userEvent.type(within(form).getByLabelText('Empresa'), 'Brétema')
    await userEvent.type(within(form).getByLabelText('Slug del tablero'), 'bretema')
    await userEvent.type(within(form).getByLabelText('Idioma de la descripción (opcional)'), 'EN')
    await userEvent.click(within(form).getByRole('button', { name: 'Añadir' }))
    expect(await within(form).findByText(/«Brétema» añadida/)).toBeInTheDocument()
    expect(calls.find((c) => c.method === 'POST')?.body).toMatchObject({
      kind: 'personio',
      slug: 'bretema',
      language: 'en',
      query: null,
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
    await userEvent.click(within(form).getByRole('combobox', { name: 'Origen' }))
    await userEvent.click(await screen.findByRole('option', { name: 'freehire (búsqueda)' }))
    expect(within(form).queryByLabelText('Slug del tablero')).not.toBeInTheDocument()
    expect(within(form).getByText('Sin claves. Busca en el título de las ofertas.')).toBeInTheDocument()
    await userEvent.type(within(form).getByLabelText('Nombre de la búsqueda'), 'Datos remoto')
    await userEvent.type(within(form).getByLabelText('Palabras de búsqueda'), 'data engineer')
    const country = within(form).getByLabelText('País')
    await userEvent.clear(country)
    await userEvent.type(country, 'PT')
    await userEvent.click(within(form).getByLabelText('Solo ofertas en remoto'))
    await userEvent.click(within(form).getByRole('button', { name: 'Probar' }))
    expect(await within(form).findByText('12 ofertas encontradas, 3 tras filtros')).toBeInTheDocument()
    expect(calls.find((c) => c.method === 'POST')?.body).toMatchObject({
      kind: 'freehire',
      query: 'data engineer',
      country: 'pt',
      remote_only: true,
      slug: null,
    })
  })
})
