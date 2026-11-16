import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { CalendarItem } from '@/api/client'
import { addMonths, monthGrid, shift, viewRange } from '@/lib/calendar'
import { board, boardCard, mockApi, renderApp, status } from '@/test/utils'

function item(changes: Partial<CalendarItem> = {}): CalendarItem {
  return {
    kind: 'interview',
    job_id: 3,
    job_title: 'Data Engineer',
    company: 'Brétema Analytics',
    stage: 'in_process',
    milestone_id: 7,
    title: 'Entrevista técnica',
    // 10:30 en Madrid (horario de verano).
    starts_at: '2026-10-07T08:30:00Z',
    ends_at: '2026-10-07T09:30:00Z',
    all_day: false,
    location: 'https://meet.example.com/abc',
    status: 'scheduled',
    ...changes,
  }
}

const ITEMS = [
  item(),
  item({
    kind: 'application_deadline',
    job_id: 5,
    company: 'Néboa Data',
    milestone_id: null,
    title: 'Plazo de la oferta',
    starts_at: '2026-10-08T22:00:00Z',
    ends_at: null,
    all_day: true,
    location: null,
    stage: 'approved',
  }),
  item({ milestone_id: 8, title: 'Primera llamada', starts_at: '2026-10-01T07:00:00Z', ends_at: null, status: 'done' }),
]

function routes() {
  return {
    'GET /status': status(),
    'GET /calendar': (_: Request, url: URL) => ({
      start: url.searchParams.get('start'),
      end: url.searchParams.get('end'),
      items: ITEMS.filter((i) => i.starts_at.slice(0, 10) >= url.searchParams.get('start')! || i.all_day),
    }),
  }
}

describe('Calendario: fechas', () => {
  it('la cuadrícula del mes va de lunes a domingo y los meses cortos no se saltan', () => {
    const grid = monthGrid('2026-10-15')
    expect(grid[0]).toBe('2026-09-28')
    expect(grid.at(-1)).toBe('2026-11-01')
    expect(grid).toHaveLength(35)
    expect(addMonths('2026-01-31', 1)).toBe('2026-02-28')
    expect(viewRange('week', '2026-10-25')).toEqual({ start: '2026-10-19', end: '2026-10-25' })
    expect(shift('agenda', '2026-10-01', 1)).toBe('2026-10-31')
  })
})

describe('Calendario', () => {
  it('muestra el mes con los hitos y abre el detalle con el enlace a la oferta', async () => {
    const calls = mockApi(routes())
    renderApp('/calendario?view=month&date=2026-10-05')
    expect(await screen.findByRole('heading', { name: /octubre de 2026/ })).toBeInTheDocument()
    const day = await screen.findByRole('listitem', { name: 'miércoles, 7 de octubre' })
    await userEvent.click(await within(day).findByRole('button', { name: /10:30 Entrevista técnica · Brétema Analytics/ }))
    const call = calls.find((c) => c.path === '/calendar')
    expect(call?.search.get('start')).toBe('2026-09-28')
    expect(call?.search.get('end')).toBe('2026-11-01')

    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText('Programado')).toBeInTheDocument()
    expect(within(dialog).getByRole('link', { name: 'Ver la oferta' })).toHaveAttribute('href', '/jobs/3')
    expect(within(dialog).getByRole('link', { name: 'https://meet.example.com/abc' })).toBeInTheDocument()
    expect(within(dialog).getByRole('link', { name: /Añadir a mi calendario/ })).toHaveAttribute(
      'href',
      expect.stringContaining('/milestones/7/ics'),
    )
  })

  it('el plazo de la oferta sale traducido y como día entero', async () => {
    mockApi(routes())
    renderApp('/calendario?view=month&date=2026-10-05')
    const day = await screen.findByRole('listitem', { name: 'viernes, 9 de octubre' })
    expect(await within(day).findByRole('button', { name: 'Plazo de la oferta · Néboa Data' })).toBeInTheDocument()
  })

  it('cambia a la semana y avanza, pidiendo a la API cada rango', async () => {
    const calls = mockApi(routes())
    renderApp('/calendario?view=month&date=2026-10-07')
    await userEvent.click(await screen.findByRole('button', { name: 'Semana' }))
    expect(await screen.findByRole('button', { name: /Entrevista técnica/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Semana' })).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(screen.getByRole('button', { name: 'Siguiente' }))
    await waitFor(() =>
      expect(calls.filter((c) => c.path === '/calendar').map((c) => c.search.get('start'))).toEqual([
        '2026-09-28',
        '2026-10-05',
        '2026-10-12',
      ]),
    )
  })

  it('la agenda lista los días con hitos y el día entero', async () => {
    mockApi(routes())
    renderApp('/calendario?view=agenda&date=2026-10-01')
    expect(await screen.findByRole('heading', { name: 'miércoles, 7 de octubre' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'jueves, 1 de octubre' })).toBeInTheDocument()
    expect(screen.getByText('Todo el día')).toBeInTheDocument()
  })

  it('sin hitos, la agenda lo dice', async () => {
    mockApi({ 'GET /status': status(), 'GET /calendar': { start: '2027-01-01', end: '2027-01-30', items: [] } })
    renderApp('/calendario?view=agenda&date=2027-01-01')
    expect(await screen.findByText('Nada en los 30 días a partir de esta fecha.')).toBeInTheDocument()
  })
})

describe('Calendario: añadir un hito', () => {
  it('el «+» de un día abre el alta con esa fecha y guarda el hito en la oferta elegida', async () => {
    const calls = mockApi({
      ...routes(),
      'GET /board': board([boardCard(3, 'in_process'), boardCard(4, 'closed')]),
      'POST /jobs/3/milestones': { id: 21 },
    })
    renderApp('/calendario?view=month&date=2026-10-05')
    const day = await screen.findByRole('listitem', { name: 'jueves, 15 de octubre' })
    await userEvent.click(within(day).getByRole('button', { name: 'Añadir un hito el jueves, 15 de octubre' }))
    const dialog = await screen.findByRole('dialog')
    await userEvent.click(await within(dialog).findByRole('button', { name: 'Oferta' }))
    const list = await screen.findByRole('listbox', { name: 'Oferta' })
    // Solo los procesos abiertos; con pocos, sin caja de búsqueda.
    expect(within(list).queryByText('Empresa 4')).not.toBeInTheDocument()
    expect(screen.queryByRole('combobox', { name: 'Busca por empresa o puesto' })).not.toBeInTheDocument()
    await userEvent.click(within(list).getByRole('option', { name: /Empresa 3/ }))
    expect(within(dialog).getByRole('button', { name: 'Oferta' })).toHaveTextContent('Empresa 3 · Oferta 3')
    await userEvent.type(within(dialog).getByLabelText('Título (opcional)'), 'Técnica')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Guardar hito' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'POST')).toBe(true))
    const post = calls.find((c) => c.method === 'POST')!
    expect(post.path).toBe('/jobs/3/milestones')
    // 14:00 en Madrid el 15 de octubre (horario de verano).
    expect(post.body).toMatchObject({ kind: 'interview', title: 'Técnica', starts_at: '2026-10-15T14:00:00+02:00', all_day: false })
  })

  it('con muchas ofertas, se busca por empresa o puesto sin tildes ni mayúsculas', async () => {
    const cards = Array.from({ length: 9 }, (_, i) => boardCard(10 + i, 'applied'))
    cards.push(boardCard(30, 'in_process', { company: 'Brétema Analytics', title: 'Data Engineer' }))
    mockApi({ ...routes(), 'GET /board': board(cards) })
    renderApp('/calendario?view=month&date=2026-10-05')
    const day = await screen.findByRole('listitem', { name: 'jueves, 15 de octubre' })
    await userEvent.click(within(day).getByRole('button', { name: 'Añadir un hito el jueves, 15 de octubre' }))
    const dialog = await screen.findByRole('dialog')
    await userEvent.click(await within(dialog).findByRole('button', { name: 'Oferta' }))
    const search = await screen.findByRole('combobox', { name: 'Busca por empresa o puesto' })
    await waitFor(() => expect(search).toHaveFocus())
    await userEvent.type(search, 'BRETEMA data')
    const list = screen.getByRole('listbox', { name: 'Oferta' })
    expect(within(list).getAllByRole('option')).toHaveLength(1)
    await userEvent.keyboard('{Enter}')
    expect(within(dialog).getByRole('button', { name: 'Oferta' })).toHaveTextContent('Brétema Analytics · Data Engineer')
    expect(await within(dialog).findByRole('button', { name: 'Guardar hito' })).toBeInTheDocument()
  })

  it('distingue hoy, fines de semana y días de otro mes', async () => {
    mockApi(routes())
    renderApp('/calendario?view=month&date=2026-10-05')
    const outside = await screen.findByRole('listitem', { name: 'lunes, 28 de septiembre' })
    expect(outside.className).toMatch(/repeating-linear-gradient/)
    const weekend = screen.getByRole('listitem', { name: 'sábado, 10 de octubre' })
    expect(weekend.className).toMatch(/bg-muted/)
  })
})
