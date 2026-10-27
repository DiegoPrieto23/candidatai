import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import { resetWatches, WATCH_MINUTES, watchFor } from '@/lib/readyWatch'
import {
  jobCv,
  jobView,
  milestone,
  mockApi,
  processView,
  renderApp,
  renderResult,
  status,
  templateList,
} from '@/test/utils'

const launcher = { available: true, agent: 'claude', reason: null, actions: [] }
const launched = { ok: true, agent: 'claude', prompt: 'Usa el skill…', message: 'ok', job_id: 1 }
const later = () => new Date(Date.now() + 1000).toISOString()
// La ficha vuelve a pedir el CV o la guía cada 5 s: se espera algo más.
const POLL = { timeout: 8000 }

beforeEach(() => resetWatches())

describe('Aviso de «listo» tras abrir el agente', () => {
  it('avisa cuando el agente deja el CV y lo abre con un clic', async () => {
    let cv = { job_id: 1, stage: 'approved', can_render: true, cv: null } as ReturnType<typeof jobCv> | object
    const calls = mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView({ stage: 'approved' }),
      'GET /jobs/1/cv': () => cv,
      'GET /templates': templateList(),
      'GET /agent': launcher,
      'POST /agent/launch': launched,
    })
    renderApp('/jobs/1?tab=application')
    const section = await screen.findByRole('region', { name: 'CV' })
    await userEvent.click(await within(section).findByRole('button', { name: 'Generar CV' }))
    expect(await within(section).findByText(/Te aviso aquí en cuanto esté/)).toBeInTheDocument()
    expect(screen.queryByText('Tu CV está listo')).not.toBeInTheDocument()

    // Un render anterior al clic no cuenta; uno nuevo, sí.
    cv = jobCv([renderResult(1, { selected: true, created_at: later() })])
    const notice = (await screen.findByText('Tu CV está listo', {}, POLL)).closest('[role="status"]') as HTMLElement
    expect(within(notice).getByText('Data Engineer · Brétema Analytics')).toBeInTheDocument()
    expect(within(notice).getByRole('link', { name: 'Abrir PDF' })).toHaveAttribute(
      'href',
      'http://127.0.0.1:8000/renders/1/pdf',
    )
    expect(calls.filter((c) => c.path === '/jobs/1/cv').length).toBeGreaterThan(1)
    await userEvent.click(within(notice).getByRole('button', { name: 'Cerrar aviso' }))
    expect(screen.queryByText('Tu CV está listo')).not.toBeInTheDocument()
  }, 15_000)

  it('avisa cuando está la guía de la entrevista', async () => {
    const future = new Date(Date.now() + 2 * 86_400_000).toISOString()
    let guide: ReturnType<typeof milestone>['guide'] = null
    mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView({ stage: 'in_process' }),
      'GET /jobs/1/process': () =>
        processView({ stage: 'in_process', milestones: [milestone(5, { starts_at: future, guide })] }),
      'GET /agent': launcher,
      'POST /agent/launch': launched,
    })
    renderApp('/jobs/1?tab=process')
    const section = await screen.findByRole('region', { name: 'Proceso' })
    await userEvent.click(await within(section).findByRole('button', { name: 'Preparar' }))
    await within(section).findByText(/Te aviso aquí en cuanto esté/)

    guide = { file: '1-5-acme-guia.pdf', language: 'es', title: 'Data Engineer', saved_at: later(), agent_name: null }
    const notice = (await screen.findByText('Tu guía de la entrevista está lista', {}, POLL)).closest(
      '[role="status"]',
    ) as HTMLElement
    expect(within(notice).getByRole('link', { name: 'Abrir PDF' })).toHaveAttribute(
      'href',
      'http://127.0.0.1:8000/milestones/5/guide.pdf',
    )
    // La ficha se ha puesto al día sola: el enlace a la guía ya está.
    await waitFor(() => expect(within(section).getByRole('link', { name: 'Guía de preparación (PDF)' })).toBeInTheDocument())
  }, 15_000)

  it('deja de vigilar al pasar el tiempo sin nada nuevo', () => {
    watchFor('generate-cv', 1)
    const stored = JSON.parse(sessionStorage.getItem('cai.readyWatches') ?? '[]') as { until: number }[]
    expect(stored).toHaveLength(1)
    expect(stored[0].until - Date.now()).toBeLessThanOrEqual(WATCH_MINUTES * 60_000)
    watchFor('assess-fit', 1) // no deja documento: no se vigila
    expect(JSON.parse(sessionStorage.getItem('cai.readyWatches') ?? '[]')).toHaveLength(1)
  })
})
