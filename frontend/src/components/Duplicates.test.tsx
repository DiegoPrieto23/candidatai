import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { mockApi, renderApp, status } from '@/test/utils'

const item = (job_id: number, title: string, keep_reason: string | null = null) => ({
  job_id,
  title,
  company: 'Acme Datos',
  url: `https://example.com/jobs/${job_id}`,
  first_seen_at: '2026-10-01T08:00:00Z',
  original_id: 42,
  original_title: 'Analytics Engineer II',
  original_stage: 'approved',
  keep_reason,
})

const LIST = {
  items: [item(86, 'Analytics Engineer II, Full Stack'), item(94, 'Analytics Engineer (Revenue)'), item(13, 'Analytics Engineer', 'own_work')],
  erasable: 2,
  kept: 1,
}

describe('Duplicadas de antes en la Bandeja', () => {
  it('avisa, enseña la vista previa y borra solo las que se pueden borrar', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /jobs': { items: [], total: 0, limit: 50, offset: 0 },
      'GET /jobs/duplicates': LIST,
      'POST /jobs/duplicates/erase': {
        status: 200,
        body: { ok: true, deleted_jobs: 2, kept: 0, moved_sightings: 2, backup: 'backups/candidatai-1.db', message: '' },
      },
    })
    renderApp('/bandeja')
    const banner = await screen.findByRole('region', { name: 'Hay 2 ofertas duplicadas' })
    await userEvent.click(within(banner).getByRole('button', { name: 'Ver y borrar' }))

    const dialog = await screen.findByRole('dialog', { name: '¿Borrar 2 ofertas duplicadas?' })
    const erasable = within(dialog).getByRole('list', { name: 'Duplicadas que se borran' })
    expect(within(erasable).getByText('Analytics Engineer II, Full Stack')).toBeInTheDocument()
    expect(within(erasable).getAllByRole('link', { name: 'Analytics Engineer II' })[0]).toHaveAttribute('href', '/jobs/42')
    const kept = within(dialog).getByRole('list', { name: 'Se queda 1' })
    expect(within(kept).getByText(/tiene algo propio/)).toBeInTheDocument()

    await userEvent.click(within(dialog).getByRole('button', { name: 'Borrar 2 duplicadas' }))
    await waitFor(() => expect(calls.some((c) => c.path === '/jobs/duplicates/erase')).toBe(true))
    expect(calls.find((c) => c.path === '/jobs/duplicates/erase')?.body).toEqual({ job_ids: [86, 94] })
    expect(await screen.findByText(/2 ofertas duplicadas borradas/)).toHaveTextContent('backups/candidatai-1.db')
  })

  it('sin duplicadas que borrar no dice nada', async () => {
    mockApi({
      'GET /status': status(),
      'GET /jobs': { items: [], total: 0, limit: 50, offset: 0 },
      'GET /jobs/duplicates': { items: [item(13, 'Analytics Engineer', 'no_longer_duplicate')], erasable: 0, kept: 1 },
    })
    renderApp('/bandeja')
    await screen.findByRole('heading', { level: 1 })
    await waitFor(() => expect(screen.queryByText(/duplicad/)).not.toBeInTheDocument())
  })
})
