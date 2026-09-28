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
    renderApp('/')

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
  })

  it('filtra por la etapa de la URL y busca con retardo', async () => {
    const calls = mockApi({ 'GET /status': status(0, 1), 'GET /jobs': page() })
    renderApp('/?stage=pending_triage')

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

  it('muestra un estado vacío que invita a dar de alta', async () => {
    mockApi({ 'GET /status': status(), 'GET /jobs': page([]) })
    renderApp('/')
    expect(await screen.findByText('Tu bandeja está vacía')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Añadir la primera/ })).toHaveAttribute('href', '/nueva')
  })

  it('explica cómo arrancar la API si no responde', async () => {
    mockApi({})
    globalThis.fetch = () => Promise.reject(new TypeError('Failed to fetch'))
    renderApp('/')
    expect(await screen.findByText('La API no responde')).toBeInTheDocument()
    expect(screen.getByText('uv run jh serve')).toBeInTheDocument()
  })
})

describe('Cabecera', () => {
  it('muestra los recuentos por etapa y el recordatorio de extracción', async () => {
    mockApi({ 'GET /status': status(3, 2), 'GET /jobs': page() })
    renderApp('/')

    const nav = await screen.findByRole('navigation', { name: 'Ofertas por etapa' })
    await waitFor(() => expect(within(nav).getByRole('link', { name: /Por extraer\s*3/ })).toBeInTheDocument())
    expect(within(nav).getByRole('link', { name: /Todas\s*5/ })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('status')).toHaveTextContent(
      'Hay 3 ofertas por extraer. Ejecuta el skill procesar-ofertas en tu agente.',
    )
  })

  it('no muestra el recordatorio si no hay nada por extraer', async () => {
    mockApi({ 'GET /status': status(0, 2), 'GET /jobs': page() })
    renderApp('/')
    await screen.findByRole('link', { name: /Por revisar\s*2/ })
    expect(screen.queryByText(/por extraer\./)).not.toBeInTheDocument()
  })

  it('cambia entre tema del sistema, claro y oscuro', async () => {
    mockApi({ 'GET /status': status(), 'GET /jobs': page() })
    renderApp('/')
    const toggle = screen.getByRole('button', { name: 'Tema: el del sistema' })
    await userEvent.click(toggle)
    expect(screen.getByRole('button', { name: 'Tema: claro' })).toBeInTheDocument()
    expect(document.documentElement).not.toHaveClass('dark')
    await userEvent.click(screen.getByRole('button', { name: 'Tema: claro' }))
    expect(document.documentElement).toHaveClass('dark')
  })
})
