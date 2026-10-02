import { render } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router'
import { vi } from 'vitest'
import type {
  AlertJob,
  CvView,
  JobCv,
  JobRow,
  JobView,
  MatchView,
  RenderResult,
  Schemas,
  StatusReport,
  TemplateInfo,
  TemplateList,
  TriageItem,
  TriageQueue,
} from '@/api/client'
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
/** JSON si lo es; si no (una subida con `FormData`), el texto tal cual. */
function parseBody(text: string): unknown {
  if (!text) return undefined
  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}

export function mockApi(routes: Record<string, Handler | unknown>): Call[] {
  const calls: Call[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: Request) => {
      const url = new URL(input.url)
      const key = `${input.method} ${url.pathname}`
      const text = await input.clone().text()
      calls.push({ method: input.method, path: url.pathname, search: url.searchParams, body: parseBody(text) })
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

export function status(pendingExtraction = 0, pendingTriage = 0, pendingDetail = 0): StatusReport {
  return {
    total: pendingExtraction + pendingTriage + pendingDetail,
    pending_tasks: 0,
    by_stage: {
      pending_detail: pendingDetail,
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
    score: null,
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

export function matchView(changes: Partial<MatchView> = {}): MatchView {
  const now = new Date().toISOString()
  return {
    job_id: 1,
    match_id: 1,
    profile_version_id: 1,
    extraction_id: 1,
    score: 78,
    triage_threshold: 55,
    below_threshold: false,
    hard_filters: { passed: true, failures: [] },
    breakdown: {
      components: [
        { name: 'must_have_coverage', value: 0.8, weight: 0.45, effective_weight: 0.6429, points: 51.43 },
        { name: 'semantic_similarity', value: null, weight: 0.3, effective_weight: 0, points: 0 },
        { name: 'preferences_fit', value: 0.95, weight: 0.15, effective_weight: 0.2143, points: 20.36 },
        { name: 'nice_to_have_coverage', value: 0.5, weight: 0.1, effective_weight: 0.1429, points: 7.14 },
      ],
      must_have: {
        ratio: 0.8,
        covered: [
          { skill: 'Python', profile_skill: 'Python', level: 'F', weight: 1 },
          { skill: 'dbt', profile_skill: 'dbt', level: 'basic', weight: 0.2 },
        ],
        missing: ['Kafka'],
      },
      nice_to_have: { ratio: null, covered: [], missing: [] },
      semantic: null,
      preferences: { value: 0.95, role: 1, role_match: 'Data Engineer', remote_mode: 0.85, location: 1 },
      notes: ['Similitud semántica desactivada (JH_EMBEDDINGS=off).'],
    },
    assessment: null,
    assessment_stale: false,
    created_at: now,
    ...changes,
  }
}

export function triageItem(id: number, score: number, changes: Partial<TriageItem> = {}): TriageItem {
  return {
    job: jobRow({ id, title: `Oferta ${id}`, company: `Empresa ${id}`, score }),
    extraction: EXTRACTION,
    match: matchView({ job_id: id, match_id: id, score, below_threshold: score < 55 }),
    ...changes,
  }
}

export function triageQueue(items: TriageItem[], changes: Partial<TriageQueue> = {}): TriageQueue {
  return { items, total: items.length, triage_threshold: 55, profile_missing: false, ...changes }
}

// --- CV ------------------------------------------------------------------------------------------

const SECTIONS: TemplateInfo['sections'] = [
  'summary',
  'experience',
  'projects',
  'education',
  'certifications',
  'extra_sections',
  'skills',
  'languages',
]

export function templateInfo(changes: Partial<TemplateInfo> = {}): TemplateInfo {
  return {
    id: 'ats-simple',
    name: 'ATS sencilla',
    engine: 'docx',
    origin: 'builtin',
    description: 'Una columna, sin foto ni tablas.',
    tags: ['ats'],
    ats_friendly: true,
    photo_supported: false,
    photo_shape: 'circle',
    columns: 1,
    page_size: 'A4',
    max_pages: 1,
    capacity: { summary_chars: 450, experience_bullets: 9, skill_groups: 4 },
    sections: SECTIONS,
    accent_colors: null,
    fonts: ['Calibri'],
    languages: ['es', 'en'],
    has_preview: true,
    from_user_cv: false,
    has_source_preview: false,
    ...changes,
  }
}

export const CLASICA_FOTO = templateInfo({
  id: 'clasica-foto',
  name: 'Clásica con foto',
  ats_friendly: false,
  photo_supported: true,
  accent_colors: { default: '#1F4E79', choices: ['#1F4E79', '#2E5E4E', '#7A2E39', '#3F3F46'] },
})

export function templateList(changes: Partial<TemplateList> = {}): TemplateList {
  return { templates: [templateInfo(), CLASICA_FOTO], invalid: [], fallback_template: 'ats-simple', ...changes }
}

type RenderChanges = Partial<Omit<RenderResult, 'options'>> & { options?: Partial<RenderResult['options']> }

export function renderResult(id: number, changes: RenderChanges = {}): RenderResult {
  const { options, ...rest } = changes
  return {
    render_id: id,
    job_id: 1,
    document_id: 1,
    template_id: 'clasica-foto',
    template_hash: 'abc',
    options: {
      template_id: 'clasica-foto',
      template_source: 'default_template',
      rule_index: null,
      photo: true,
      accent_color: '#1F4E79',
      max_pages: 1,
      hidden_sections: [],
      page_size: 'A4',
      offer: { ats: null, countries: ['ES'], domain: null, language: 'es' },
      warnings: [],
      ...options,
    },
    docx_path: `cvs/1/1/${id}/CV-Lucia-Varela-Otero.docx`,
    pdf_path: `cvs/1/1/${id}/CV-Lucia-Varela-Otero.pdf`,
    pages: 1,
    max_pages: 1,
    keyword_coverage: { present: ['Python', 'SQL'], missing: ['dbt'] },
    warnings: [],
    selected: false,
    template_changed: false,
    created_at: new Date().toISOString(),
    ...rest,
  }
}

export function jobCv(renders: RenderResult[], changes: Partial<CvView> = {}): JobCv {
  return {
    job_id: 1,
    stage: 'cv_ready',
    can_render: true,
    cv: {
      job_id: 1,
      document_id: 1,
      profile_version_id: 1,
      created_at: new Date().toISOString(),
      content: {
        language: 'es',
        subtitle: 'Data Engineer',
        summary: 'Resumen ficticio.',
        experience: [{ experience_id: 'exp-1', bullets: [{ text: 'Logro ficticio.', evidence: ['exp-1/a1'] }] }],
        projects: [],
        skills: [],
        education_ids: [],
        certification_ids: [],
        extra_sections: [],
        languages: [],
        include_regional_language: false,
        keywords_targeted: [],
      },
      evidence: { 'exp-1/a1': 'Logro ficticio.' },
      verification: { passed: true, issues: [] },
      renders,
      ...changes,
    },
  }
}

// --- Alertas por correo ----------------------------------------------------------------------------

export function alertJob(id: number, changes: Partial<AlertJob> = {}): AlertJob {
  const now = new Date().toISOString()
  return {
    job_id: id,
    title: `Alerta ${id}`,
    company: `Empresa ${id}`,
    location: 'Vigo, Galicia, España',
    platform: 'linkedin',
    platform_label: 'LinkedIn',
    url: `https://www.linkedin.com/jobs/view/40000000${id}/`,
    first_seen_at: now,
    expires_at: now,
    prefilter_passed: true,
    prefilter_reason: null,
    risk_flags: [],
    ...changes,
  }
}
