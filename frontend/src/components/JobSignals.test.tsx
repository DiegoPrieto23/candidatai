import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { JobSignals, LivenessView } from '@/api/client'
import { jobRow, jobView, mockApi, renderApp, status, triageItem, triageQueue } from '@/test/utils'

const checkedAt = '2026-10-12T07:30:00Z'
const CLOSED: JobSignals = {
  possibly_closed: {
    since: checkedAt,
    checked_at: checkedAt,
    reason: 'http_404',
    detail: 'la página responde HTTP 404',
    http_status: 404,
  },
}
const REPOSTED: JobSignals = {
  reposted: { count: 3, dates: ['2026-08-20', '2026-09-10', '2026-10-01'], channel: 'infojobs', window_days: 90 },
}

function liveness(changes: Partial<LivenessView> = {}): LivenessView {
  return {
    job_id: 1,
    status: 'open',
    reason: null,
    detail: 'la página sigue publicada',
    checked_at: checkedAt,
    cached: false,
    possibly_closed: null,
    suppressed: false,
    message: 'Sigue abierta: la página sigue publicada.',
    ...changes,
  }
}

describe('Señales de la oferta', () => {
  it('la bandeja marca las republicadas y las que pueden estar cerradas', async () => {
    mockApi({
      'GET /status': status(),
      'GET /jobs': {
        items: [jobRow({ signals: { ...CLOSED, ...REPOSTED } })],
        total: 1,
        limit: 50,
        offset: 0,
      },
    })
    renderApp('/bandeja')
    expect((await screen.findAllByText('Republicada ×3')).length).toBeGreaterThan(0)
    expect(screen.getAllByText('¿Cerrada?').length).toBeGreaterThan(0)
  })

  it('el triaje enseña «Republicada ×N»', async () => {
    const item = triageItem(1, 80)
    mockApi({
      'GET /status': status(0, 1),
      'GET /triage': triageQueue([{ ...item, job: { ...item.job, signals: REPOSTED } }]),
    })
    renderApp('/triaje')
    expect(await screen.findByText('Republicada ×3')).toBeInTheDocument()
  })

  it('la ficha propone descartar con el motivo «Ya no está publicada», sin cerrarla sola', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView({ stage: 'pending_triage', signals: CLOSED }),
      'POST /jobs/1/events': { event_id: 9, stage: 'closed' },
    })
    renderApp('/jobs/1')
    const notice = await screen.findByRole('region', { name: 'Puede que esté cerrada' })
    expect(within(notice).getByText(/La página responde HTTP 404/)).toBeInTheDocument()
    expect(within(notice).getByText(/no la cierra: decide tú/)).toBeInTheDocument()
    expect(calls.some((c) => c.method === 'POST')).toBe(false)

    await userEvent.click(within(notice).getByRole('button', { name: 'Descartar' }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByRole('radio', { name: /Ya no está publicada/ })).toHaveAttribute('aria-checked', 'true')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Descartar' }))
    await waitFor(() => expect(calls.some((c) => c.path === '/jobs/1/events')).toBe(true))
    expect(calls.find((c) => c.path === '/jobs/1/events')?.body).toEqual({ type: 'discarded', reason: 'closed' })
  })

  it('«Sigue abierta» y «Comprobar otra vez» llaman a la API', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView({ stage: 'pending_triage', signals: CLOSED }),
      'POST /jobs/1/still-open': liveness({ suppressed: true }),
      'POST /jobs/1/check-open': liveness(),
    })
    renderApp('/jobs/1')
    const notice = await screen.findByRole('region', { name: 'Puede que esté cerrada' })
    await userEvent.click(within(notice).getByRole('button', { name: /Comprobar otra vez/ }))
    await waitFor(() => expect(calls.some((c) => c.path === '/jobs/1/check-open')).toBe(true))
    expect(calls.find((c) => c.path === '/jobs/1/check-open')?.body).toEqual({ force: true })
    expect(await within(notice).findByText(/Sigue abierta: la página sigue publicada/)).toBeInTheDocument()

    await userEvent.click(within(notice).getByRole('button', { name: 'Sigue abierta' }))
    await waitFor(() => expect(calls.some((c) => c.path === '/jobs/1/still-open')).toBe(true))
    expect(calls.find((c) => c.path === '/jobs/1/still-open')?.body).toEqual({})
  })

  it('una aprobada se comprueba al abrirla y el botón «Generar CV» avisa', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /agent': { available: true, agent: 'claude', reason: null, actions: [] },
      'GET /jobs/1': jobView({ stage: 'approved', signals: CLOSED }),
      'GET /jobs/1/cv': { job_id: 1, can_render: true, cv: null },
      'POST /jobs/1/check-open': liveness({ status: 'possibly_closed', cached: true }),
    })
    renderApp('/jobs/1')
    await waitFor(() => expect(calls.some((c) => c.path === '/jobs/1/check-open')).toBe(true))
    expect(calls.filter((c) => c.path === '/jobs/1/check-open')).toHaveLength(1)
    expect(calls.find((c) => c.path === '/jobs/1/check-open')?.body).toEqual({ force: false })
    expect(await screen.findByText(/Antes de gastar cuota: puede que esta oferta ya no esté publicada/)).toBeInTheDocument()
  })

  it('una pendiente de revisar no se comprueba sola y la republicación sale como nota', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView({ stage: 'pending_triage', signals: REPOSTED }),
    })
    renderApp('/jobs/1')
    expect(await screen.findByText(/Republicada ×3\./)).toBeInTheDocument()
    expect(screen.getByText(/en InfoJobs en 3 días distintos/)).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Puede que esté cerrada' })).not.toBeInTheDocument()
    expect(calls.some((c) => c.path === '/jobs/1/check-open')).toBe(false)
  })
})
