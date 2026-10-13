import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { AgentRequestView, AgentRunView } from '@/api/client'
import { mockApi, renderApp, status } from '@/test/utils'

const launcher = {
  available: true,
  agent: 'claude',
  reason: null,
  background: { available: true, agent: 'claude', reason: null },
  actions: [],
}

function run(changes: Partial<AgentRunView> = {}): AgentRunView {
  return {
    id: 1,
    action: 'process-jobs',
    label: 'Procesar ofertas',
    job_id: null,
    milestone_id: null,
    agent: 'claude',
    status: 'done',
    prompt: 'Usa el skill process-jobs…',
    allowed_tools: ['get_status', 'list_jobs', 'get_job', 'save_extraction'],
    progress: [
      { at: '2026-10-12T10:00:00Z', kind: 'tool', text: 'list_jobs' },
      { at: '2026-10-12T10:00:01Z', kind: 'tool', text: 'Subagente «extractor»' },
    ],
    result: 'Procesadas 2 ofertas.',
    questions: [],
    error: null,
    usage: null,
    cancel_requested: false,
    can_resume: true,
    created_at: '2026-10-12T10:00:00Z',
    started_at: '2026-10-12T10:00:00Z',
    finished_at: '2026-10-12T10:01:30Z',
    ...changes,
  }
}

function request(changes: Partial<AgentRequestView> = {}): AgentRequestView {
  return {
    id: 7,
    action: 'generate-cv',
    label: 'Generar CV',
    job_id: 42,
    milestone_id: null,
    prompt: 'Usa el skill generate-cv de CandidatAI para la oferta 42.',
    status: 'pending',
    summary: null,
    agent_name: null,
    created_at: '2026-10-12T09:00:00Z',
    completed_at: null,
    ...changes,
  }
}

describe('Página «Agente» (fase 19)', () => {
  it('enseña las ejecuciones con su estado, progreso y preguntas', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /agent': launcher,
      'GET /agent/runs': {
        active: 1,
        runs: [
          run({ id: 3, status: 'running', finished_at: null, result: null, can_resume: false }),
          run({
            id: 2,
            action: 'generate-cv',
            label: 'Generar CV',
            job_id: 42,
            status: 'needs_user',
            questions: ['La oferta parece cerrada, ¿redacto igualmente?'],
          }),
          run(),
        ],
      },
      'GET /agent/requests': { pending: 0, requests: [] },
      'POST /agent/runs/3/cancel': run({ id: 3, status: 'running', cancel_requested: true }),
      'POST /agent/runs/2/open': {
        ok: true,
        agent: 'claude',
        prompt: '…',
        message: 'Se ha abierto claude con la misma sesión.',
      },
    })
    renderApp('/agente')
    expect(await screen.findByRole('heading', { name: 'Agente' })).toBeInTheDocument()
    const cards = await screen.findAllByRole('listitem', {}, { timeout: 3000 })
    expect(screen.getByText('En curso')).toBeInTheDocument()
    expect(screen.getByText('Necesita tu respuesta')).toBeInTheDocument()
    expect(screen.getByText('La oferta parece cerrada, ¿redacto igualmente?')).toBeInTheDocument()
    expect(screen.getAllByText(/Solo con:/)[0]).toHaveTextContent('get_status, list_jobs, get_job, save_extraction')
    expect(screen.getAllByText('Subagente «extractor»').length).toBeGreaterThan(0)
    expect(screen.getByRole('link', { name: 'oferta 42' })).toHaveAttribute('href', '/jobs/42')
    expect(cards.length).toBeGreaterThan(0)

    await userEvent.click(screen.getByRole('button', { name: 'Cancelar' }))
    await userEvent.click(screen.getByRole('button', { name: 'Contestar en terminal' }))
    expect(await screen.findByText('Se ha abierto claude con la misma sesión.')).toBeInTheDocument()
    const posts = calls.filter((c) => c.method === 'POST')
    expect(posts.map((c) => c.path)).toEqual(['/agent/runs/3/cancel', '/agent/runs/2/open'])
    // Cuerpo JSON: `require_ui` lo exige (sin él, la API responde 403).
    expect(posts.map((c) => c.body)).toEqual([{}, {}])
  })

  it('lista los encargos pendientes y los quita', async () => {
    const calls = mockApi({
      'GET /status': { ...status(), agent_requests: 1 },
      'GET /agent': launcher,
      'GET /agent/runs': { active: 0, runs: [] },
      'GET /agent/requests': {
        pending: 1,
        requests: [
          request(),
          request({
            id: 5,
            action: 'process-jobs',
            label: 'Procesar ofertas',
            job_id: null,
            status: 'done',
            summary: 'Procesadas 3.',
            agent_name: 'claude-code',
          }),
        ],
      },
      'POST /agent/requests/7/cancel': request({ status: 'cancelled' }),
    })
    renderApp('/agente')
    const pending = await screen.findByRole('list', { name: 'Encargos pendientes' })
    expect(within(pending).getByText('Usa el skill generate-cv de CandidatAI para la oferta 42.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Atender encargos' })).toBeInTheDocument()
    expect(screen.getByText(/Aún no has lanzado nada en segundo plano/)).toBeInTheDocument()
    await userEvent.click(within(pending).getByRole('button', { name: 'Quitar' }))
    expect(calls.find((c) => c.method === 'POST' && c.path === '/agent/requests/7/cancel')?.body).toEqual({})
  })

  it('avisa si hay algo en cola y ninguna en curso (¿worker parado?)', async () => {
    mockApi({
      'GET /status': status(),
      'GET /agent': {
        ...launcher,
        background: { available: false, agent: null, reason: 'Tu agente (codex) no tiene `launch.headless`.' },
      },
      'GET /agent/runs': {
        active: 1,
        runs: [
          run({
            status: 'queued',
            created_at: '2020-01-01T00:00:00Z',
            started_at: null,
            finished_at: null,
            result: null,
            progress: [],
          }),
        ],
      },
      'GET /agent/requests': { pending: 0, requests: [] },
    })
    renderApp('/agente')
    expect(await screen.findByText(/ninguna en curso/)).toHaveTextContent('¿está cai worker en marcha?')
    expect(await screen.findByText(/no tiene `launch.headless`/)).toBeInTheDocument()
  })
})
