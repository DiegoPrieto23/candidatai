import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { AlertJob } from '@/api/client'
import { alertJob, mockApi, renderApp, status } from '@/test/utils'

/** API simulada con estado: descartar saca la oferta; reabrir la devuelve. */
function mockAlerts(initial: AlertJob[], extra: Record<string, unknown> = {}) {
  let jobs = [...initial]
  const routes: Record<string, unknown> = {
    'GET /status': () => status(0, 0, jobs.length),
    'GET /alerts': () => ({
      jobs,
      total: jobs.length,
      passed: jobs.filter((j) => j.prefilter_passed).length,
      filters_applied: true,
    }),
    ...extra,
  }
  for (const job of initial) {
    routes[`POST /jobs/${job.job_id}/events`] = async (request: Request) => {
      const body = (await request.clone().json()) as { type: string }
      if (body.type === 'reopened') jobs = initial.filter((j) => j === job || jobs.includes(j))
      else jobs = jobs.filter((j) => j.job_id !== job.job_id)
      return { ok: true, event_id: 9, stage: body.type === 'reopened' ? 'pending_detail' : 'closed' }
    }
  }
  return mockApi(routes)
}

function selected() {
  return screen.getByRole('option', { selected: true })
}

afterEach(() => vi.restoreAllMocks())

describe('Alertas', () => {
  it('separa las que no pasan el prefiltro y enseña el motivo', async () => {
    mockAlerts([
      alertJob(1),
      alertJob(2, { prefilter_passed: false, prefilter_reason: 'El título indica seniority senior.' }),
    ])
    renderApp('/alertas')

    const good = await screen.findByRole('listbox', { name: 'Encajan con tus preferencias' })
    expect(within(good).getByText('Alerta 1')).toBeInTheDocument()
    const bad = screen.getByRole('listbox', { name: 'No pasan el prefiltro' })
    expect(within(bad).getByText('El título indica seniority senior.')).toBeInTheDocument()
    expect(screen.getByText('No pasan el prefiltro (1)')).toBeInTheDocument()
    const open = within(good).getByRole('link', { name: /Abrir/ })
    expect(open).toHaveAttribute('href', 'https://www.linkedin.com/jobs/view/400000001/')
    expect(open).toHaveAttribute('target', '_blank')
    expect(open).toHaveAttribute('rel', 'noopener noreferrer')
    // El recuento de la cabecera.
    const nav = screen.getByRole('link', { name: /^Alertas/ })
    expect(await within(nav).findByText('2')).toBeInTheDocument()
    expect(nav).toHaveTextContent('por completar')
  })

  it('se mueve con J/K, abre con O en otra pestaña y descarta con D', async () => {
    const opened = vi.spyOn(window, 'open').mockReturnValue(null)
    const calls = mockAlerts([alertJob(1), alertJob(2), alertJob(3)])
    renderApp('/alertas')
    await screen.findByText('Alerta 1')

    await userEvent.keyboard('j')
    expect(within(selected()).getByText('Alerta 2')).toBeInTheDocument()
    await userEvent.keyboard('o')
    expect(opened).toHaveBeenCalledWith(
      'https://www.linkedin.com/jobs/view/400000002/',
      '_blank',
      'noopener,noreferrer',
    )

    await userEvent.keyboard('d')
    const dialog = await screen.findByRole('dialog')
    expect(dialog).toHaveTextContent('Alerta 2')
    await userEvent.keyboard('3{Enter}')
    expect(await screen.findByText(/Descartada/)).toHaveTextContent('Descartada Alerta 2 · Ubicación o modalidad')
    expect(within(selected()).getByText('Alerta 3')).toBeInTheDocument()
    expect(calls.filter((c) => c.method === 'POST').map((c) => c.body)).toEqual([
      { type: 'discarded', reason: 'location' },
    ])

    await userEvent.click(screen.getByRole('button', { name: 'Deshacer' }))
    expect(await screen.findByText('Alerta 2')).toBeInTheDocument()
  })

  it('revisa el correo a demanda y enseña el resultado', async () => {
    const calls = mockAlerts([], {
      'POST /alerts/poll': {
        source_id: 1,
        run_id: 1,
        messages: 1,
        found: 3,
        created: 3,
        summaries: 3,
        existing: 0,
        job_ids: [1, 2, 3],
        errors: [],
        message: 'Alertas por correo: 1 correo nuevo, 3 ofertas, 3 nuevas (3 como resumen).',
      },
    })
    renderApp('/alertas')
    expect(await screen.findByText('Sin alertas pendientes')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Revisar correo ahora' }))
    expect(await screen.findByText(/1 correo nuevo, 3 ofertas/)).toBeInTheDocument()
    expect(calls.some((c) => c.method === 'POST' && c.path === '/alerts/poll')).toBe(true)
  })
})
