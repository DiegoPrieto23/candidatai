import { render } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router'
import { vi } from 'vitest'
import type { JobRow, JobView, Schemas, StatusReport } from '@/api/client'
import { AppRoutes } from '@/App'
import { TooltipProvider } from '@/components/ui/tooltip'

type Handler = (request: Request, url: URL) => unknown | Promise<unknown>

export interface Call {
  method: string
  path: string
  search: URLSearchParams
  body: unknown
}

/**
 * Simula la API: `routes` va de «MÉTODO /ruta» a la respuesta (JSON). Una respuesta
 * `{status, body}` devuelve ese código. Devuelve la lista de llamadas para comprobarlas.
 */
export function mockApi(routes: Record<string, Handler | unknown>): Call[] {
  const calls: Call[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: Request) => {
      const url = new URL(input.url)
      const key = `${input.method} ${url.pathname}`
      const text = await input.clone().text()
      calls.push({ method: input.method, path: url.pathname, search: url.searchParams, body: text ? JSON.parse(text) : undefined })
      if (!(key in routes)) {
        return Response.json({ ok: false, error: { type: 'not_found', message: `Sin simular: ${key}`, details: [] } }, { status: 404 })
      }
      const route = routes[key]
      const result = typeof route === 'function' ? await (route as Handler)(input, url) : route
      if (result && typeof result === 'object' && 'status' in result && 'body' in result) {
        const { status, body } = result as { status: number; body: unknown }
        return Response.json(body, { status })
      }
      return Response.json(result, { status: input.method === 'POST' ? 201 : 200 })
    }),
  )
  return calls
}

export function renderApp(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <TooltipProvider>
        <MemoryRouter initialEntries={[path]}>
          <AppRoutes />
        </MemoryRouter>
      </TooltipProvider>
    </QueryClientProvider>,
  )
}

// --- Datos de prueba (ficticios, como los de demo/) ---------------------------------------------

export function status(pendingExtraction = 0, pendingTriage = 0): StatusReport {
  return {
    total: pendingExtraction + pendingTriage,
    pending_tasks: 0,
    by_stage: {
      pending_extraction: pendingExtraction,
      pending_triage: pendingTriage,
      approved: 0,
      cv_ready: 0,
      applied: 0,
      in_process: 0,
      closed: 0,
    },
  }
}

export function jobRow(changes: Partial<JobRow> = {}): JobRow {
  return {
    id: 1,
    title: 'Data Engineer',
    company: 'Brétema Analytics',
    location: 'Santiago de Compostela',
    url: 'https://example.com/jobs/1',
    stage: 'pending_triage',
    risk_flags: [],
    duplicate_of: null,
    first_seen_at: new Date().toISOString(),
    remote_mode: 'hybrid',
    ...changes,
  }
}

export const EXTRACTION: Schemas['JobExtraction'] = {
  title_normalized: 'Data Engineer',
  seniority: 'mid',
  years_experience_min: 3,
  employment_type: 'full_time',
  remote_mode: 'hybrid',
  locations: ['Santiago de Compostela'],
  languages_required: [{ language: 'Inglés', level: 'B2' }],
  salary: { min: 38000, max: 46000, currency: 'EUR', period: 'year' },
  must_have_skills: ['Python', 'SQL', 'dbt'],
  nice_to_have_skills: ['Terraform'],
  responsibilities: ['Mantener pipelines ELT'],
  domain: 'Distribución',
  posting_language: 'es',
  application_deadline: null,
  red_flags: [],
  injection_suspected: false,
  injection_excerpt: null,
}

export function jobView(changes: Partial<JobView> = {}): JobView {
  const now = new Date().toISOString()
  return {
    ...jobRow(),
    posted_at: null,
    raw_text: 'Texto original de la oferta ficticia.',
    extraction: { extraction_id: 1, created_at: now, data: EXTRACTION },
    events: [
      { id: 1, type: 'found', actor: 'system', agent_name: null, payload: {}, occurred_at: now, recorded_at: now },
      { id: 2, type: 'extracted', actor: 'agent', agent_name: 'claude-code', payload: { extraction_id: 1 }, occurred_at: now, recorded_at: now },
    ],
    injection: null,
    ...changes,
  }
}
