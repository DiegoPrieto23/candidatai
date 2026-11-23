import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { board, boardCard, jobRow, jobView, matchView, mockApi, renderApp, status } from '@/test/utils'

const erased = (count: number) => ({
  ok: true,
  deleted_jobs: count,
  backup: 'backups/candidatai-20261120-101500-000000.db',
  message: 'Hecho.',
})

const inbox = { items: [jobRow()], total: 1, next_cursor: null }

describe('Borrar datos', () => {
  it('«Borrar oferta» está arriba, junto a «Ver original», y avisa de que no es descartar', async () => {
    mockApi({ 'GET /status': status(), 'GET /jobs/1': jobView(), 'GET /jobs/1/match': matchView() })
    renderApp('/jobs/1')
    const button = await screen.findByRole('button', { name: 'Borrar oferta' })
    const header = screen.getByRole('link', { name: /Ver original/ }).parentElement!
    expect(header).toContainElement(button)

    await userEvent.hover(button)
    expect(await screen.findByRole('tooltip')).toHaveTextContent(/Borrar no es descartar/)
  })

  it('borrar una oferta pide continuar tras el aviso y escribir la empresa', async () => {
    const view = jobView()
    const calls = mockApi({
      'GET /status': status(),
      'GET /jobs/1': view,
      'GET /jobs/1/match': matchView(),
      'POST /jobs/1/erase': erased(1),
      'GET /board': board([boardCard(2, 'applied')]),
      'GET /upcoming': { days: 7, items: [] },
    })
    renderApp('/jobs/1')

    await userEvent.click(await screen.findByRole('button', { name: 'Borrar oferta' }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText(/Borrar no es descartar/)).toBeInTheDocument()
    expect(within(dialog).getByText(/Antes se guarda una copia de seguridad/)).toBeInTheDocument()
    expect(within(dialog).queryByRole('textbox')).not.toBeInTheDocument()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Entendido, continuar' }))

    const erase = within(dialog).getByRole('button', { name: 'Borrar para siempre' })
    const input = within(dialog).getByLabelText(new RegExp(`escribir el nombre de la empresa: ${view.company}`))
    await userEvent.type(input, 'Otra')
    expect(erase).toBeDisabled()
    await userEvent.clear(input)
    await userEvent.type(input, view.company.toUpperCase())
    await userEvent.click(erase)

    await waitFor(() => expect(calls.some((c) => c.path === '/jobs/1/erase')).toBe(true))
    expect(calls.find((c) => c.path === '/jobs/1/erase')?.body).toEqual({ confirm: view.company.toUpperCase() })
    // Vuelve a Procesos y avisa de dónde quedó la copia.
    expect(await screen.findByText(/Oferta borrada\. Copia de seguridad previa: backups\//)).toBeInTheDocument()
  })

  it('«Vaciar todo», en la barra de la Bandeja, lleva dos avisos y escribir BORRAR', async () => {
    const calls = mockApi({ 'GET /status': status(3), 'GET /jobs': inbox, 'POST /data/erase': erased(3) })
    renderApp('/bandeja')

    // En la misma barra que las pestañas, detrás de «Revisión rápida».
    const tabs = await screen.findByRole('navigation', { name: 'Vistas de la bandeja' })
    const button = await screen.findByRole('button', { name: 'Vaciar todo' })
    expect(tabs.parentElement).toContainElement(button)
    expect(tabs).not.toContainElement(button)

    await userEvent.click(button)
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByRole('heading')).toHaveTextContent('¿Vaciar todas las ofertas y candidaturas?')
    expect(within(dialog).getByText(/Se quedan el perfil/)).toBeInTheDocument()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Sí, continuar' }))
    expect(within(dialog).getByRole('heading')).toHaveTextContent('Última comprobación')
    expect(within(dialog).queryByRole('textbox')).not.toBeInTheDocument()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Sí, continuar' }))

    const erase = within(dialog).getByRole('button', { name: 'Vaciar para siempre' })
    const input = within(dialog).getByLabelText('Para confirmar, escribir BORRAR')
    await userEvent.type(input, 'borrar')
    expect(erase).toBeDisabled() // en mayúsculas, como se pide
    await userEvent.clear(input)
    await userEvent.type(input, 'BORRAR')
    await userEvent.click(erase)

    await waitFor(() => expect(calls.find((c) => c.path === '/data/erase')?.body).toEqual({ confirm: 'BORRAR' }))
    expect(await within(dialog).findByText(/Hecho: 3 ofertas borradas/)).toBeInTheDocument()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Entendido' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('cancelar no borra nada, y sin ofertas no hay nada que vaciar', async () => {
    const calls = mockApi({ 'GET /status': status(1), 'GET /jobs': inbox })
    renderApp('/bandeja')
    await userEvent.click(await screen.findByRole('button', { name: 'Vaciar todo' }))
    await userEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Cancelar' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(calls.some((c) => c.method === 'POST')).toBe(false)
  })

  it('sin ofertas, «Vaciar todo» está desactivado', async () => {
    mockApi({ 'GET /status': status(), 'GET /jobs': { items: [], total: 0, next_cursor: null } })
    renderApp('/bandeja')
    expect(await screen.findByRole('button', { name: 'Vaciar todo' })).toBeDisabled()
  })
})
