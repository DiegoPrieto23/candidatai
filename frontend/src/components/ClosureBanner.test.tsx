import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { jobRow, jobView, mockApi, renderApp, status } from '@/test/utils'

const SUSPECT = {
  job_id: 7,
  title: 'Data Engineer',
  company: 'Acme Datos',
  url: 'https://es.indeed.com/viewjob?jk=1',
  stage: 'cv_ready',
  reason: 'closed_text',
  detail: 'la página dice «este empleo ha caducado en indeed» (comprobado en el navegador)',
  since: '2026-11-20T08:00:00Z',
}
const OTHER = { ...SUSPECT, job_id: 8, title: 'BI Analyst', reason: 'stale', detail: 'vista hace 45 días (más de 30)' }
const JOBS = { items: [jobRow()], total: 1, limit: 50, offset: 0 }

describe('Ofertas que pueden estar cerradas (Bandeja)', () => {
  it('lista las sospechosas, las descarta todas como cerradas y comprueba ahora', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /jobs': JOBS,
      'GET /jobs/closure-suspects': { items: [SUSPECT, OTHER], unverified_important: 1 },
      'POST /jobs/check-open': { stale: 2, queued: 5, message: '' },
      'POST /jobs/7/events': { event_id: 1, stage: 'closed' },
      'POST /jobs/8/events': { event_id: 2, stage: 'closed' },
    })
    renderApp('/bandeja')
    const banner = await screen.findByRole('region', { name: 'Ofertas que pueden estar cerradas' })
    expect(within(banner).getByText('2 ofertas pueden estar cerradas o caducadas')).toBeInTheDocument()
    expect(within(banner).getByText(/Hay una aprobada o con CV/)).toBeInTheDocument()
    expect(within(banner).getByRole('button', { name: /Revisar ofertas caducadas/ })).toBeInTheDocument()

    await userEvent.click(within(banner).getByRole('button', { name: 'Ver las 2' }))
    expect(within(banner).getByRole('link', { name: 'Data Engineer' })).toHaveAttribute('href', '/jobs/7')
    expect(within(banner).getByText(/^La página dice «este empleo ha caducado en indeed»/)).toBeInTheDocument()

    await userEvent.click(within(banner).getByRole('button', { name: 'Comprobar ahora' }))
    expect(await within(banner).findByText(/Comprobaciones en cola: 5/)).toBeInTheDocument()

    await userEvent.click(within(banner).getByRole('button', { name: 'Descartar las 2' }))
    await userEvent.click(within(banner).getByRole('button', { name: 'Sí, descartar' }))
    await waitFor(() => expect(calls.some((c) => c.path === '/jobs/8/events')).toBe(true))
    for (const id of [7, 8]) {
      expect(calls.find((c) => c.path === `/jobs/${id}/events`)?.body).toEqual({ type: 'discarded', reason: 'closed' })
    }
  })

  it('sin sospechosas deja solo los botones', async () => {
    mockApi({
      'GET /status': status(),
      'GET /jobs': JOBS,
      'GET /jobs/closure-suspects': { items: [], unverified_important: 0 },
    })
    renderApp('/bandeja')
    const banner = await screen.findByRole('region', { name: 'Ofertas que pueden estar cerradas' })
    expect(within(banner).getByText('¿Siguen abiertas?')).toBeInTheDocument()
    expect(within(banner).queryByRole('button', { name: /Descartar/ })).not.toBeInTheDocument()
  })

  it('la ficha dice que no se pudo comprobar y enlaza al anuncio', async () => {
    mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView({
        stage: 'pending_triage',
        url: 'https://es.indeed.com/viewjob?jk=2',
        signals: {
          liveness: {
            checked_at: '2026-11-26T08:00:00Z',
            status: 'unknown',
            detail: 'la página bloquea el acceso (HTTP 403)',
            http_status: 403,
          },
        },
      }),
    })
    renderApp('/jobs/1')
    const note = await screen.findByRole('region', { name: 'No se ha podido comprobar si sigue abierta' })
    expect(within(note).getByText(/^La página bloquea el acceso \(HTTP 403\)/)).toBeInTheDocument()
    expect(within(note).getByRole('link', { name: /Ver el anuncio/ })).toHaveAttribute('href', 'https://es.indeed.com/viewjob?jk=2')
  })
})
