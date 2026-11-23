import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { jobRow, jobView, mockApi, renderApp, status } from '@/test/utils'

const SEEN = '2026-11-10T08:00:00Z'
const NOTICE = {
  job_id: 7,
  title: 'BI Analyst',
  company: 'Acme Datos',
  closed_at: '2026-09-01T08:00:00Z',
  closed_by: 'discarded',
  seen_at: SEEN,
  url: 'https://example.com/jobs/77',
}

describe('Ofertas que vuelven a publicarse (fase 45)', () => {
  it('la bandeja marca las reabiertas y avisa de las que cerraste tú', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /jobs': { items: [jobRow({ reopening_of: 3 })], total: 1, limit: 50, offset: 0 },
      'GET /jobs/republished': { items: [NOTICE] },
      'POST /jobs/7/republished/dismiss': { items: [] },
      'POST /jobs/7/events': { event_id: 9, stage: 'pending_triage' },
    })
    renderApp('/bandeja')
    expect((await screen.findAllByText('Reabierta')).length).toBeGreaterThan(0)

    const banner = await screen.findByRole('region', { name: 'Ha vuelto a publicarse' })
    expect(within(banner).getByText('Una oferta cerrada ha vuelto a publicarse')).toBeInTheDocument()
    expect(within(banner).getByRole('link', { name: 'BI Analyst' })).toHaveAttribute('href', '/jobs/7')
    expect(within(banner).getByText(/Descartada · publicada otra vez el/)).toBeInTheDocument()
    expect(within(banner).getByRole('link', { name: /Ver la publicación/ })).toHaveAttribute('href', NOTICE.url)

    await userEvent.click(within(banner).getByRole('button', { name: 'Reabrir' }))
    await waitFor(() => expect(calls.some((c) => c.path === '/jobs/7/events')).toBe(true))
    expect(calls.find((c) => c.path === '/jobs/7/events')?.body).toEqual({ type: 'reopened' })

    await userEvent.click(within(banner).getByRole('button', { name: 'Ignorar' }))
    await waitFor(() => expect(calls.some((c) => c.path === '/jobs/7/republished/dismiss')).toBe(true))
  })

  it('la ficha de una reapertura dice de qué oferta viene y cómo acabó', async () => {
    mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView({
        stage: 'pending_triage',
        reopening_of: 3,
        reopening: {
          job_id: 3,
          first_seen_at: '2026-03-12T08:00:00Z',
          closed_at: '2026-04-20T08:00:00Z',
          closed_by: 'rejected',
          stage_before_close: 'in_process',
          discard_reason: null,
        },
      }),
    })
    renderApp('/jobs/1')
    const note = await screen.findByText(/Reapertura/)
    expect(note.closest('p')).toHaveTextContent(/de la oferta del 12 mar 2026 \(rechazo durante el proceso\)/)
    expect(screen.getByRole('link', { name: /oferta del/ })).toHaveAttribute('href', '/jobs/3')
  })

  it('la ficha de una que cerraste y vuelve propone reabrirla', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView({
        stage: 'closed',
        signals: { republished_after_close: { seen_at: SEEN, url: null } },
      }),
      'POST /jobs/1/republished/dismiss': { items: [] },
    })
    renderApp('/jobs/1')
    const notice = await screen.findByRole('region', { name: 'Ha vuelto a publicarse' })
    expect(within(notice).getByText(/Se cerró a mano y ha vuelto a publicarse/)).toBeInTheDocument()
    await userEvent.click(within(notice).getByRole('button', { name: 'Ignorar' }))
    await waitFor(() => expect(calls.some((c) => c.path === '/jobs/1/republished/dismiss')).toBe(true))
  })
})
