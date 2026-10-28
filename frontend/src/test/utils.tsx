import { render } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router'
import { vi } from 'vitest'
import type {
  AlertJob,
  Board,
  BoardCard,
  CvView,
  JobCv,
  JobRow,
  JobView,
  MatchView,
  MilestoneOut,
  ProcessView,
  RenderResult,
  Schemas,
  StatusReport,
  TemplateInfo,
  TemplateList,
  TriageItem,
  TriageQueue,
  JobPackage,
  JobCoverLetter,
  LetterRenderResult,
  AssistedApplication,
  AttemptView,
} from '@/api/client'
import { AppRoutes } from '@/App'
import { TooltipProvider } from '@/components/ui/tooltip'
import { preloadAllPages } from '@/lib/pages'

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

/**
 * POST que hace el usuario. La ficha de una aprobada comprueba sola si sigue abierta (fase 16):
 * esa llamada no cuenta.
 */
export function isUserPost(call: Call): boolean {
  return call.method === 'POST' && !call.path.endsWith('/check-open')
}

// Las páginas, ya descargadas: `renderApp` las pinta sin esperar a su chunk, como la app tras la
// primera visita.
await preloadAllPages()

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
    agent_requests: 0,
    demo_mode: false,
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
    signals: {},
    duplicate_of: null,
    first_seen_at: new Date().toISOString(),
    remote_mode: 'hybrid',
    salary: null,
    score: null,
    known_contacts: 0,
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
    signals: [],
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
      notes: ['Similitud semántica desactivada (CAI_EMBEDDINGS=off).'],
    },
    assessment: null,
    assessment_stale: false,
    assessment_score: null,
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
  return { items, total: items.length, triage_threshold: 55, assess_min_score: 45, profile_missing: false, ...changes }
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
  accent_colors: { default: '#1F4E79', choices: ['#1F4E79', '#2E5E4E', '#7A2E39', '#3F3F46'], free: false },
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

// --- Seguimiento (fase 10) -----------------------------------------------------------------------

export function processView(changes: Partial<ProcessView> = {}): ProcessView {
  return {
    job_id: 1,
    stage: 'applied',
    applied_at: null,
    channel: null,
    followup: null,
    milestones: [],
    contacts: [],
    notes: [],
    documents: { cv_render_id: null, cv_sent: false, answers_document_id: null, cover_letter_document_id: null },
    offer_received: false,
    ...changes,
  }
}

export function milestone(id: number, changes: Partial<MilestoneOut> = {}): MilestoneOut {
  const now = new Date().toISOString()
  return {
    id,
    job_id: 1,
    kind: 'interview',
    title: 'Entrevista',
    starts_at: '2026-10-07T08:30:00Z',
    ends_at: null,
    all_day: false,
    location: null,
    notes: null,
    status: 'scheduled',
    event_id: 10,
    created_at: now,
    updated_at: now,
    ...changes,
  }
}

export function boardCard(id: number, stage: BoardCard['stage'], changes: Partial<BoardCard> = {}): BoardCard {
  return {
    job_id: id,
    title: `Oferta ${id}`,
    company: `Empresa ${id}`,
    stage,
    score: 70,
    applied_at: null,
    last_event_at: new Date().toISOString(),
    next_milestone: null,
    followup_due: false,
    days_waiting: null,
    closed_by: null,
    reopen_to: null,
    ...changes,
  }
}

/** Los movimientos que devuelve la API (derivados de las transiciones del backend). */
export const BOARD_MOVES: Board['moves'] = [
  { event: 'discarded', from_stages: ['approved', 'cv_ready'], to: 'closed' },
  { event: 'applied', from_stages: ['cv_ready'], to: 'applied' },
  { event: 'applied_manually', from_stages: ['approved', 'cv_ready'], to: 'applied' },
  { event: 'reply_received', from_stages: ['applied'], to: 'in_process' },
  { event: 'interview_scheduled', from_stages: ['applied'], to: 'in_process' },
  { event: 'interview_done', from_stages: ['applied'], to: 'in_process' },
  { event: 'test_assigned', from_stages: ['applied'], to: 'in_process' },
  { event: 'offer_received', from_stages: ['applied'], to: 'in_process' },
  { event: 'rejected', from_stages: ['approved', 'cv_ready', 'applied', 'in_process'], to: 'closed' },
  { event: 'withdrawn', from_stages: ['approved', 'cv_ready', 'applied', 'in_process'], to: 'closed' },
  { event: 'expired', from_stages: ['approved', 'cv_ready', 'applied', 'in_process'], to: 'closed' },
  { event: 'accepted', from_stages: ['in_process'], to: 'closed' },
  { event: 'reopened', from_stages: ['closed'], to: null },
]

export function board(cards: BoardCard[]): Board {
  const stages: BoardCard['stage'][] = ['approved', 'cv_ready', 'applied', 'in_process', 'closed']
  return {
    columns: stages.map((stage) => {
      const inColumn = cards.filter((c) => c.stage === stage)
      return { stage, cards: inColumn, total: inColumn.length }
    }),
    moves: BOARD_MOVES,
    days_without_reply: 10,
  }
}

export const SCREENING: JobPackage['answers'] = {
  document_id: 7,
  profile_version_id: 1,
  language: 'es',
  edited_by_user: false,
  created_at: '2026-10-03T10:00:00Z',
  answers: [
    {
      question: '¿Has migrado procesos ETL a Python?',
      answer: 'Sí: migré las cargas de SSIS a Python.',
      evidence: ['exp-norteconsulting/a1'],
      needs_user_input: false,
    },
    { question: 'Expectativa salarial', answer: '', evidence: [], needs_user_input: true },
  ],
  evidence: { 'exp-norteconsulting/a1': 'Migré las cargas nocturnas de SSIS a Python' },
}

export function jobPackage(changes: Partial<JobPackage> = {}): JobPackage {
  return {
    job_id: 1,
    stage: 'cv_ready',
    can_edit: true,
    cv: {
      render_id: 3,
      document_id: 2,
      template_id: 'ats-simple',
      pages: 1,
      pdf_url: '/renders/3/pdf',
      sent: false,
      verified: true,
    },
    answers: SCREENING,
    cover_letter: null,
    ...changes,
  }
}

// --- Carta de presentación (fase 08c) ------------------------------------------------------------

export function letterRender(id: number, changes: Partial<LetterRenderResult> = {}): LetterRenderResult {
  return {
    render_id: id,
    job_id: 1,
    document_id: 9,
    template_id: 'clasica-foto',
    template_hash: 'h',
    options: {
      template_id: 'clasica-foto',
      template_source: 'cv',
      base_template_id: 'clasica-foto',
      cv_render_id: 3,
      letter_fallback: false,
      photo: true,
      accent_color: '#1F4E79',
      page_size: 'A4',
      max_pages: 1,
      offer: { ats: null, countries: ['ES'], domain: null, language: 'es' },
      warnings: [],
    },
    docx_path: `cvs/1/9/${id}/Carta-Lucia-Varela-Otero.docx`,
    pdf_path: `cvs/1/9/${id}/Carta-Lucia-Varela-Otero.pdf`,
    pages: 1,
    warnings: [],
    selected: id === 1,
    created_at: '2026-10-03T10:00:00Z',
    ...changes,
  }
}

export const LETTER_CONTENT = {
  language: 'es' as const,
  recipient: 'Equipo de datos de Acme',
  greeting: 'Hola, equipo de Acme:',
  paragraphs: [
    { text: 'Os escribo por el puesto de Data Engineer.', evidence: ['extraction'] },
    { text: 'Migré las cargas de SSIS a Python (-35 %).', evidence: ['exp-norteconsulting/a1'] },
  ],
  sign_off: 'Un saludo,',
  keywords_targeted: ['Python'],
}

export function jobCoverLetter(
  changes: Partial<JobCoverLetter> = {},
  letter: Partial<NonNullable<JobCoverLetter['info']['letter']>> | null = {},
): JobCoverLetter {
  return {
    info: {
      job_id: 1,
      stage: 'cv_ready',
      brief: { instructions: 'Menciona que uso su producto desde 2023.', max_words: 150, updated_at: '2026-10-03T09:00:00Z' },
      preferences: {
        max_words: 170,
        tone: 'cercano y directo',
        sign_off: { es: 'Un saludo,', en: 'Kind regards,' },
        instructions: 'Busco equipos que cuiden la calidad del dato.',
        avoid: ['mencionar el salario'],
        default_format: 'text',
      },
      max_words: 150,
      letter:
        letter === null
          ? null
          : {
              document_id: 9,
              profile_version_id: 1,
              created_at: '2026-10-03T10:00:00Z',
              edited_by_user: false,
              content: LETTER_CONTENT,
              evidence: { extraction: 'La oferta (su extracción)' },
              word_count: 15,
              instructions_used: { brief: null, preferences: null, max_words: 150 },
              verification: { passed: true, issues: [] },
              renders: [letterRender(1)],
              ...letter,
            },
    },
    can_edit: true,
    plain_text: 'Hola, equipo de Acme:\r\n\r\nOs escribo por el puesto de Data Engineer.\r\n',
    cv_template_id: 'clasica-foto',
    templates: [
      { id: 'carta-simple', name: 'Carta sencilla', engine: 'docx', origin: 'builtin', letter_only: true, photo_supported: false, accent_colors: { default: '#1F4E79', choices: ['#1F4E79', '#2E5E4E'], free: true } },
      { id: 'clasica-foto', name: 'Clásica con foto', engine: 'docx', origin: 'builtin', letter_only: false, photo_supported: true, accent_colors: { default: '#1F4E79', choices: ['#1F4E79', '#2E5E4E', '#7A2E39', '#3F3F46'], free: false } },
    ],
    ...changes,
  }
}

// --- Candidatura asistida (fase 11) --------------------------------------------------------------

export function attemptView(changes: Partial<AttemptView> = {}): AttemptView {
  return {
    id: 5,
    job_id: 1,
    company: 'Acme Analytics',
    platform: 'greenhouse',
    mode: 'fill',
    url: 'https://boards.greenhouse.io/acme/jobs/1',
    domain: 'boards.greenhouse.io',
    status: 'ready',
    fields: [
      {
        marker: '0',
        label: 'Email',
        control: 'text',
        kind: 'email',
        required: true,
        status: 'filled',
        source: 'Perfil: correo',
        value: 'lucia.varela@example.com',
        note: null,
      },
      {
        marker: '1',
        label: 'Gender',
        control: 'select',
        kind: 'sensitive',
        required: false,
        status: 'sensitive',
        source: null,
        value: null,
        note: 'Dato sensible: nunca se rellena solo. Decides tú.',
      },
      {
        marker: '2',
        label: 'Acepto la política de privacidad',
        control: 'checkbox',
        kind: 'consent',
        required: true,
        status: 'consent',
        source: null,
        value: null,
        note: 'Se marcará al confirmar el envío.',
      },
    ],
    warnings: [
      { code: 'submit_button', message: 'Al confirmar se pulsará «Submit application».', detail: 'Submit application' },
    ],
    missing_required: 0,
    consents: [
      {
        marker: '2',
        label: 'Acepto la política de privacidad',
        control: 'checkbox',
        kind: 'consent',
        required: true,
        status: 'consent',
        source: null,
        value: null,
        note: null,
      },
    ],
    can_submit: true,
    can_rescan: true,
    can_fill_page: false,
    submit_button: 'Submit application',
    pending_task: null,
    has_screenshot: true,
    has_confirmation: false,
    error: null,
    created_at: '2026-10-05T10:00:00Z',
    updated_at: '2026-10-05T10:01:00.123456Z',
    ...changes,
  }
}

export function assistedApplication(changes: Partial<AssistedApplication> = {}): AssistedApplication {
  return {
    job_id: 1,
    company: 'Acme Analytics',
    attempt: null,
    mode: 'fill',
    domain: 'boards.greenhouse.io',
    url: 'https://boards.greenhouse.io/acme/jobs/1',
    portal: null,
    in_docker: false,
    can_prepare: true,
    reason: null,
    ...changes,
  }
}
