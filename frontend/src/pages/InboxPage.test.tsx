import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { jobRow, mockApi, renderApp, status } from '@/test/utils'

const page = (items = [jobRow()]) => ({ items, total: items.length, limit: 50, offset: 0 })

describe('Bandeja', () => {
  it('lista las ofertas con empresa, modalidad y etapa', async () => {
    mockApi({
      'GET /status': status(1, 1),
      'GET /jobs': page([
        jobRow(),
        jobRow({ id: 2, title: 'BI Developer', company: 'Faro Logística', stage: 'pending_extraction', remote_mode: null, risk_flags: ['injection_phrase'] }),
      ]),
    })
    renderApp('/bandeja')

    const table = await screen.findByRole('table')
    const rows = within(table).getAllByRole('row')
    expect(rows).toHaveLength(3) // cabecera + 2
    expect(within(rows[1]).getByText('Data Engineer')).toBeInTheDocument()
    expect(within(rows[1]).getByText('Híbrido')).toBeInTheDocument()
    expect(within(rows[1]).getByText('Por revisar')).toBeInTheDocument()
    expect(within(rows[1]).getByText('hoy')).toBeInTheDocument()
    expect(within(rows[2]).getByText('Sin extraer')).toBeInTheDocument()
    expect(within(rows[2]).getByLabelText('Posible contenido dirigido a una IA')).toBeInTheDocument()
    expect(within(rows[1]).getByRole('link', { name: 'Data Engineer' })).toHaveAttribute('href', '/jobs/1')
    expect(within(rows[1]).getByText('Sin score')).toBeInTheDocument()
  })

  it('enseña el score del último match', async () => {
    mockApi({ 'GET /status': status(0, 1), 'GET /jobs': page([jobRow({ score: 81 })]) })
    renderApp('/bandeja')
    const table = await screen.findByRole('table')
    expect(within(table).getByLabelText('Score 81 de 100')).toBeInTheDocument()
  })

  it('filtra por la etapa de la URL y busca con retardo', async () => {
    const calls = mockApi({ 'GET /status': status(0, 1), 'GET /jobs': page() })
    renderApp('/bandeja?stage=pending_triage')

    expect(await screen.findByRole('heading', { level: 1, name: 'Por revisar' })).toBeInTheDocument()
    const first = calls.find((c) => c.path === '/jobs')!
    expect(first.search.get('stage')).toBe('pending_triage')

    await userEvent.type(screen.getByRole('searchbox'), 'bretema')
    await waitFor(() =>
      expect(calls.some((c) => c.path === '/jobs' && c.search.get('q') === 'bretema')).toBe(true),
    )
    // No una consulta por tecla.
    expect(calls.filter((c) => c.path === '/jobs' && c.search.get('q')?.startsWith('b')).length).toBeLessThan(3)
  })

  it('enseña el salario y ordena por salario, encaje y fecha desde la cabecera', async () => {
    const calls = mockApi({
      'GET /status': status(0, 1),
      'GET /jobs': page([
        jobRow({ salary: { min: 40000, max: 50000, currency: 'EUR', period: 'year' } }),
        jobRow({ id: 2, title: 'BI Developer' }),
      ]),
    })
    renderApp('/bandeja?stage=approved')

    const table = await screen.findByRole('table')
    const rows = within(table).getAllByRole('row')
    expect(within(rows[1]).getByText(/40\.000\s€ - 50\.000\s€ \/ año/)).toBeInTheDocument()
    expect(within(rows[2]).getByText('No lo indica')).toBeInTheDocument()
    const lastJobsCall = () => calls.filter((c) => c.path === '/jobs').at(-1)!
    expect(lastJobsCall().search.get('sort')).toBe('date') // por defecto: las más recientes
    expect(lastJobsCall().search.get('dir')).toBe('desc')

    await userEvent.click(within(table).getByRole('button', { name: 'Salario' }))
    await waitFor(() => expect(lastJobsCall().search.get('sort')).toBe('salary'))
    expect(lastJobsCall().search.get('dir')).toBe('desc')
    expect(lastJobsCall().search.get('stage')).toBe('approved')
    expect(within(table).getByRole('columnheader', { name: 'Salario' })).toHaveAttribute('aria-sort', 'descending')

    await userEvent.click(within(table).getByRole('button', { name: 'Salario' }))
    await waitFor(() => expect(lastJobsCall().search.get('dir')).toBe('asc'))

    await userEvent.click(within(table).getByRole('button', { name: 'Encaje' }))
    await waitFor(() => expect(lastJobsCall().search.get('sort')).toBe('score'))
    expect(lastJobsCall().search.get('dir')).toBe('desc')
  })

  it('muestra un estado vacío que invita a dar de alta', async () => {
    mockApi({ 'GET /status': status(), 'GET /jobs': page([]) })
    renderApp('/bandeja')
    expect(await screen.findByText('Tu bandeja está vacía')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Añadir la primera/ })).toHaveAttribute('href', '/nueva')
  })

  it('explica cómo arrancar la API si no responde', async () => {
    mockApi({})
    globalThis.fetch = () => Promise.reject(new TypeError('Failed to fetch'))
    renderApp('/bandeja')
    expect(await screen.findByText('CandidatAI no responde')).toBeInTheDocument()
    expect(screen.getByText('cai start')).toBeInTheDocument()
  })
})

describe('Cabecera', () => {
  it('las etapas son filtros de la Bandeja, con su recuento', async () => {
    const calls = mockApi({ 'GET /status': status(3, 2), 'GET /jobs': page() })
    renderApp('/bandeja')

    const filters = await screen.findByRole('navigation', { name: 'Filtrar por etapa' })
    await waitFor(() => expect(within(filters).getByRole('button', { name: /Por extraer\s*3/ })).toBeInTheDocument())
    expect(within(filters).getByRole('button', { name: /Todas\s*5/ })).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(within(filters).getByRole('button', { name: /Por revisar\s*2/ }))
    await waitFor(() => expect(calls.some((c) => c.path === '/jobs' && c.search.get('stage') === 'pending_triage')).toBe(true))
    // De 25 en 25.
    expect(calls.find((c) => c.path === '/jobs')?.search.get('limit')).toBe('25')
    // Sin avisos fijos arriba: lo que espera se cuenta en Inicio y en la barra lateral.
    expect(screen.queryByText(/por extraer\./)).not.toBeInTheDocument()
  })

  it('cambia entre tema del sistema, claro y oscuro', async () => {
    mockApi({ 'GET /status': status(), 'GET /jobs': page() })
    renderApp('/bandeja')
    const toggle = screen.getByRole('button', { name: 'Tema: el del sistema' })
    await userEvent.click(toggle)
    expect(screen.getByRole('button', { name: 'Tema: claro' })).toBeInTheDocument()
    expect(document.documentElement).not.toHaveClass('dark')
    await userEvent.click(screen.getByRole('button', { name: 'Tema: claro' }))
    expect(document.documentElement).toHaveClass('dark')
  })
})

describe('Descartar desde la Bandeja (fase 27.6)', () => {
  const summaries = () =>
    page([
      jobRow({ id: 1, title: 'Analytics Engineer', stage: 'pending_detail', remote_mode: null, url: 'https://portal.example/1' }),
      jobRow({ id: 2, title: 'BI Developer', stage: 'pending_detail', remote_mode: null }),
    ])
  const ok = { ok: true, event_id: 9, stage: 'closed' }

  it('solo enseña «Descartar» en «Por completar» y «Por extraer»', async () => {
    mockApi({ 'GET /status': status(0, 1), 'GET /jobs': page() })
    renderApp('/bandeja?stage=pending_triage')
    const table = await screen.findByRole('table')
    expect(within(table).queryByRole('button', { name: /^Descartar/ })).not.toBeInTheDocument()
    expect(within(table).queryByRole('checkbox')).not.toBeInTheDocument()
  })

  it('descarta en un clic con «No me interesa», sin abrir la ficha, y «Deshacer» la devuelve', async () => {
    const calls = mockApi({
      'GET /status': status(0, 1),
      'GET /jobs': summaries(),
      'POST /jobs/1/events': ok,
    })
    renderApp('/bandeja?stage=pending_detail')
    const table = await screen.findByRole('table')
    expect(within(table).getByRole('link', { name: 'Abrir Analytics Engineer en su portal' })).toHaveAttribute(
      'href',
      'https://portal.example/1',
    )

    await userEvent.click(within(table).getByRole('button', { name: 'Descartar Analytics Engineer' }))
    expect(within(table).queryByText('Analytics Engineer')).not.toBeInTheDocument()
    expect(within(table).getByText('BI Developer')).toBeInTheDocument()
    const notice = await screen.findByText(/Descartada:/)
    expect(notice).toHaveTextContent('Descartada: Analytics Engineer · No me interesa (título o empresa)')
    expect(screen.getByRole('heading', { level: 1, name: 'Por completar' })).toBeInTheDocument() // sigue en la Bandeja
    const posts = calls.filter((c) => c.method === 'POST')
    expect(posts.map((c) => c.body)).toEqual([{ type: 'discarded', reason: 'not_interested' }])

    await userEvent.click(screen.getByRole('button', { name: 'Deshacer' }))
    await waitFor(() => expect(within(table).getByText('Analytics Engineer')).toBeInTheDocument())
    expect(calls.filter((c) => c.method === 'POST').at(-1)!.body).toEqual({ type: 'reopened' })
  })

  it('si la API falla, la fila vuelve y avisa', async () => {
    mockApi({
      'GET /status': status(1, 0),
      'GET /jobs': page([jobRow({ id: 1, title: 'Analytics Engineer', stage: 'pending_extraction' })]),
      'POST /jobs/1/events': { status: 409, body: { ok: false, error: { type: 'invalid_transition', message: 'Ya está cerrada.', details: [] } } },
    })
    renderApp('/bandeja?stage=pending_extraction')
    const table = await screen.findByRole('table')
    expect(within(table).queryByRole('link', { name: /en su portal/ })).not.toBeInTheDocument() // solo en «Por completar»
    await userEvent.click(within(table).getByRole('button', { name: 'Descartar Analytics Engineer' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Ya está cerrada.')
    expect(within(table).getByText('Analytics Engineer')).toBeInTheDocument()
  })

  it('el ▾ abre el diálogo para dar otro motivo', async () => {
    const calls = mockApi({ 'GET /status': status(0, 1), 'GET /jobs': summaries(), 'POST /jobs/2/events': ok })
    renderApp('/bandeja?stage=pending_detail')
    const table = await screen.findByRole('table')
    await userEvent.click(within(table).getByRole('button', { name: 'Descartar BI Developer con otro motivo' }))
    await userEvent.click(await screen.findByRole('menuitem', { name: 'Descartar con otro motivo…' }))
    const dialog = await screen.findByRole('dialog')
    await userEvent.click(within(dialog).getByRole('radio', { name: /Ubicación/ }))
    await userEvent.click(within(dialog).getByRole('button', { name: 'Descartar' }))
    await waitFor(() =>
      expect(calls.find((c) => c.method === 'POST')!.body).toEqual({ type: 'discarded', reason: 'location' }),
    )
  })

  it('descarta varias seleccionadas de golpe y las deshace todas', async () => {
    const calls = mockApi({
      'GET /status': status(0, 2),
      'GET /jobs': summaries(),
      'POST /jobs/1/events': ok,
      'POST /jobs/2/events': ok,
    })
    renderApp('/bandeja?stage=pending_detail')
    const table = await screen.findByRole('table')
    await userEvent.click(within(table).getByRole('checkbox', { name: 'Seleccionar todas' }))
    await userEvent.click(screen.getByRole('button', { name: 'Descartar 2' }))
    expect(await screen.findByText(/Descartadas 2 ofertas/)).toBeInTheDocument()
    expect(within(table).getAllByRole('row')).toHaveLength(1) // solo la cabecera
    expect(calls.filter((c) => c.method === 'POST').map((c) => c.path)).toEqual(['/jobs/1/events', '/jobs/2/events'])

    await userEvent.click(screen.getByRole('button', { name: 'Deshacer' }))
    await waitFor(() => expect(within(table).getAllByRole('row')).toHaveLength(3))
  })
})

describe('Descartes seguidos', () => {
  it('se acumulan en el mismo aviso y «Deshacer» los devuelve todos', async () => {
    const ok = { ok: true, event_id: 9, stage: 'closed' }
    mockApi({
      'GET /status': status(1, 0),
      'GET /jobs': page([
        jobRow({ id: 1, title: 'Analytics Engineer', stage: 'pending_extraction' }),
        jobRow({ id: 2, title: 'BI Developer', stage: 'pending_extraction' }),
      ]),
      'POST /jobs/1/events': ok,
      'POST /jobs/2/events': ok,
    })
    renderApp('/bandeja?stage=pending_extraction')
    const table = await screen.findByRole('table')
    await userEvent.click(within(table).getByRole('button', { name: 'Descartar Analytics Engineer' }))
    await screen.findByText(/Descartada:/)
    await userEvent.click(within(table).getByRole('button', { name: 'Descartar BI Developer' }))
    expect(await screen.findByText(/Descartadas 2 ofertas/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Deshacer' }))
    await waitFor(() => expect(within(table).getAllByRole('row')).toHaveLength(3))
    expect(screen.queryByText(/Descartad/)).not.toBeInTheDocument()
  })
})

describe('«Cerrada» con su fecha de cierre', () => {
  it('enseña la columna «Cerrada» y ordena por ella', async () => {
    const closedAt = new Date().toISOString()
    const calls = mockApi({
      'GET /status': status(0, 1),
      'GET /jobs': page([jobRow({ stage: 'closed', closed_at: closedAt, closed_by: 'duplicate_detected' })]),
    })
    renderApp('/bandeja?stage=closed')
    const table = await screen.findByRole('table')
    expect(within(table).getByRole('columnheader', { name: 'Alta' })).toBeInTheDocument()
    const time = within(table).getAllByText('hoy')[1]
    expect(time.getAttribute('title')).toMatch(/· Duplicado detectado/)
    const lastJobsCall = () => calls.filter((c) => c.path === '/jobs').at(-1)!
    expect(lastJobsCall().search.get('sort')).toBe('date') // no cambia el orden por defecto

    await userEvent.click(within(table).getByRole('button', { name: 'Cerrada' }))
    await waitFor(() => expect(lastJobsCall().search.get('sort')).toBe('closed'))
    expect(lastJobsCall().search.get('dir')).toBe('desc')
  })

  it('fuera de «Cerrada» no hay columna y un sort=closed se ignora', async () => {
    const calls = mockApi({ 'GET /status': status(0, 1), 'GET /jobs': page() })
    renderApp('/bandeja?stage=approved&sort=closed')
    const table = await screen.findByRole('table')
    expect(within(table).queryByRole('columnheader', { name: 'Cerrada' })).not.toBeInTheDocument()
    expect(calls.find((c) => c.path === '/jobs')!.search.get('sort')).toBe('date')
  })
})
