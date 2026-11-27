import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { JobCost } from '@/api/client'
import { jobView, mockApi, renderApp, status } from '@/test/utils'

function cost(changes: Partial<JobCost> = {}): JobCost {
  return {
    job_id: 1,
    runs: [
      {
        run_id: 3,
        action: 'process-jobs',
        label: 'Valorar las ofertas nuevas',
        agent: 'claude',
        model: null,
        finished_at: '2026-10-12T10:00:00Z',
        share: 0.5,
        shared_with: 2,
        usage: { input_tokens: 500, output_tokens: 100, cost_usd: 0.05 },
      },
      {
        run_id: 4,
        action: 'generate-cv',
        label: 'Generar CV',
        agent: 'opencode',
        model: 'ollama/qwen3:8b',
        finished_at: '2026-10-13T10:00:00Z',
        share: 1,
        shared_with: 1,
        usage: { input_tokens: 2000, output_tokens: 400 },
      },
    ],
    total: {
      runs: 2,
      with_usage: 2,
      input_tokens: 2500,
      output_tokens: 500,
      cached_tokens: 0,
      turns: 0,
      duration_ms: 0,
      cost_usd: 0.05,
      avg_tokens: 1500,
      avg_duration_ms: null,
      avg_cost_usd: 0.05,
    },
    terminal_note: '…',
    ...changes,
  }
}

describe('Coste del agente en la ficha (fase 25.4)', () => {
  it('suma lo gastado en la oferta y dice qué ejecuciones se reparten', async () => {
    mockApi({ 'GET /status': status(), 'GET /jobs/1': jobView(), 'GET /jobs/1/costs': cost() })
    renderApp('/jobs/1?tab=history')
    const panel = await screen.findByRole('region', { name: 'Coste del agente' })
    expect(panel).toHaveTextContent(/3.?000 tokens · 0[.,]0500 USD en 2 ejecuciones en segundo plano/)
    const runs = within(panel).getByRole('list', { name: 'Ejecuciones' })
    expect(runs).toHaveTextContent(/Valorar las ofertas nuevas · claude · .* · repartida entre 2 ofertas/)
    expect(runs).toHaveTextContent(/Generar CV · opencode · ollama\/qwen3:8b/)
    expect(within(panel).getByText(/No cuenta lo que se hace en una terminal/)).toBeInTheDocument()
  })

  it('cada ejecución abre su conversación, donde se le puede seguir escribiendo (fase 48.1c)', async () => {
    const run = {
      id: 4,
      action: 'generate-cv',
      label: 'Generar CV',
      job_id: 1,
      milestone_id: null,
      agent: 'claude',
      model: null,
      status: 'done',
      prompt: '…',
      allowed_tools: [],
      progress: [],
      result: 'Listo.',
      questions: [],
      error: null,
      usage: null,
      cancel_requested: false,
      can_resume: true,
      asks_permissions: true,
      created_at: '2026-10-13T09:58:00Z',
      started_at: '2026-10-13T09:58:00Z',
      finished_at: '2026-10-13T10:00:00Z',
    }
    const events = {
      run_id: 4,
      status: 'done',
      last_seq: 1,
      prompts: [],
      reply: 'resume',
      events: [{ seq: 1, at: '2026-10-13T09:58:01Z', kind: 'text', tool: null, text: 'CV terminado.', ok: null, sub: false }],
    }
    mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView(),
      'GET /jobs/1/costs': cost(),
      'GET /agent/runs/4': run,
      'GET /agent/runs/4/events': events,
      'GET /agent/agents': { agents: [] },
    })
    renderApp('/jobs/1?tab=history')
    const panel = await screen.findByRole('region', { name: 'Coste del agente' })
    const [, second] = within(panel).getAllByRole('button', { name: 'Ver conversación' })
    await userEvent.click(second)
    const side = await screen.findByRole('complementary', { name: 'CV generado' })
    expect(within(side).getByText('CV terminado.')).toBeInTheDocument()
    expect(within(side).getByRole('textbox', { name: 'Mensaje para el agente' })).toBeInTheDocument()
  })

  it('sin ejecuciones no se enseña', async () => {
    mockApi({ 'GET /status': status(), 'GET /jobs/1': jobView(), 'GET /jobs/1/costs': cost({ runs: [] }) })
    renderApp('/jobs/1?tab=history')
    await screen.findByRole('heading', { level: 1 })
    expect(screen.queryByRole('region', { name: 'Coste del agente' })).not.toBeInTheDocument()
  })
})
