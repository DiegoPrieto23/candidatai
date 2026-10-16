import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError, api, unwrap, type CvRenderOptions, type ReferralStatus, type Schemas, type Stage } from './client'
import type { operations } from './schema'

export const PAGE_SIZE = 50

export const keys = {
  status: ['status'] as const,
  prompts: ['prompts'] as const,
  jobs: (params: JobsParams) => ['jobs', params] as const,
  allJobs: ['jobs'] as const,
  job: (id: number) => ['job', id] as const,
  match: (id: number) => ['match', id] as const,
  triage: ['triage'] as const,
  cv: (id: number) => ['cv', id] as const,
  templates: ['templates'] as const,
  uploads: ['uploads'] as const,
  defaultTemplate: ['templates', 'default'] as const,
  sources: ['sources'] as const,
  alerts: ['alerts'] as const,
  board: ['board'] as const,
  followups: ['followups'] as const,
  upcoming: (days: number) => ['upcoming', days] as const,
  allUpcoming: ['upcoming'] as const,
  process: (id: number) => ['process', id] as const,
  /** Bajo `cv`: lo que invalida el CV (render, selección) invalida también el paquete. */
  package: (id: number) => ['cv', id, 'package'] as const,
  /** También bajo `cv`: la carta va a juego con el render seleccionado del CV. */
  letter: (id: number) => ['cv', id, 'letter'] as const,
  funnel: (since: string | null) => ['funnel', since] as const,
  // Bajo 'funnel': lo que invalida el embudo (referencias…) invalida también la calibración.
  calibration: (since: string | null) => ['funnel', 'calibration', since] as const,
  context: ['context'] as const,
  apply: (id: number) => ['apply', id] as const,
  agent: ['agent'] as const,
  agentRuns: ['agent', 'runs'] as const,
  agentAgents: ['agent', 'agents'] as const,
  agentRequests: ['agent', 'requests'] as const,
  skillGaps: (days: number) => ['skill-gaps', days] as const,
  allSkillGaps: ['skill-gaps'] as const,
  replies: (params: RepliesParams) => ['replies', params] as const,
  allReplies: ['replies'] as const,
  reply: (id: number) => ['reply', id] as const,
  drafts: (jobId: number) => ['drafts', jobId] as const,
  network: ['network'] as const,
  jobNetwork: (jobId: number) => ['network', 'job', jobId] as const,
  research: (jobId: number) => ['research', jobId] as const,
  // Bajo 'received-offers': guardar una invalida también la comparación.
  receivedOffers: ['received-offers'] as const,
  receivedOffer: (jobId: number) => ['received-offers', jobId] as const,
}

type JobsQuery = NonNullable<operations['list_jobs']['parameters']['query']>
export type JobSort = NonNullable<JobsQuery['sort']>
export type SortDirection = NonNullable<JobsQuery['dir']>

export interface JobsParams {
  stage?: Stage
  q?: string
  page: number
  sort?: JobSort
  dir?: SortDirection
}

export function useStatus() {
  return useQuery({
    queryKey: keys.status,
    queryFn: () => unwrap(api.GET('/status')),
    // El agente cambia el estado desde fuera (extrae ofertas): se refresca solo.
    refetchInterval: 30_000,
  })
}

export function useJobs(params: JobsParams) {
  return useQuery({
    queryKey: keys.jobs(params),
    queryFn: () =>
      unwrap(
        api.GET('/jobs', {
          params: {
            query: {
              stage: params.stage,
              q: params.q || undefined,
              limit: PAGE_SIZE,
              offset: (params.page - 1) * PAGE_SIZE,
              sort: params.sort,
              dir: params.dir,
            },
          },
        }),
      ),
    placeholderData: keepPreviousData,
  })
}

export function useJob(id: number) {
  return useQuery({
    queryKey: keys.job(id),
    queryFn: () => unwrap(api.GET('/jobs/{job_id}', { params: { path: { job_id: id } } })),
    enabled: Number.isInteger(id) && id > 0,
  })
}

function useInvalidateAll() {
  const client = useQueryClient()
  return () =>
    Promise.all([
      client.invalidateQueries({ queryKey: keys.status }),
      client.invalidateQueries({ queryKey: keys.allJobs }),
    ])
}

export function useAddFromUrl() {
  const invalidate = useInvalidateAll()
  return useMutation({
    mutationFn: (body: Schemas['AddFromUrlBody']) => unwrap(api.POST('/jobs/url', { body })),
    onSuccess: invalidate,
  })
}

export function useAddFromText() {
  const invalidate = useInvalidateAll()
  return useMutation({
    mutationFn: (body: Schemas['AddFromTextBody']) => unwrap(api.POST('/jobs/text', { body })),
    onSuccess: invalidate,
  })
}

export function useAddNote(jobId: number) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (note: string) =>
      unwrap(
        api.POST('/jobs/{job_id}/events', {
          params: { path: { job_id: jobId } },
          body: { type: 'note', note },
        }),
      ),
    onSuccess: () =>
      Promise.all([
        client.invalidateQueries({ queryKey: keys.job(jobId) }),
        client.invalidateQueries({ queryKey: keys.process(jobId) }),
      ]),
  })
}

export function useTriage() {
  return useQuery({
    queryKey: keys.triage,
    queryFn: () => unwrap(api.GET('/triage')),
  })
}

/** Match vigente de una oferta. `null` si aún no se puede calcular (sin extracción o sin perfil). */
export function useJobMatch(id: number, enabled = true) {
  return useQuery({
    queryKey: keys.match(id),
    queryFn: async () => {
      try {
        return await unwrap(api.GET('/jobs/{job_id}/match', { params: { path: { job_id: id } } }))
      } catch (error) {
        if (error instanceof ApiError && error.type === 'not_found') return null
        throw error
      }
    },
    enabled: enabled && Number.isInteger(id) && id > 0,
  })
}

export type UserEventBody = Schemas['AddUserEventBody']

/** Aprobar, descartar (con motivo) o reabrir. Refresca la cola, la ficha y los recuentos. */
export function useJobEvent() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ jobId, body }: { jobId: number; body: UserEventBody }) =>
      unwrap(api.POST('/jobs/{job_id}/events', { params: { path: { job_id: jobId } }, body })),
    onSuccess: (_result, { jobId }) =>
      Promise.all([
        client.invalidateQueries({ queryKey: keys.status }),
        client.invalidateQueries({ queryKey: keys.allJobs }),
        client.invalidateQueries({ queryKey: keys.triage }),
        client.invalidateQueries({ queryKey: keys.alerts }),
        client.invalidateQueries({ queryKey: keys.job(jobId) }),
        client.invalidateQueries({ queryKey: keys.match(jobId) }),
        ...invalidateTracking(client, jobId),
      ]),
  })
}

/** ¿Sigue abierta? (fase 16): comprueba la URL ahora (o devuelve la comprobación reciente). */
export function useCheckJobOpen() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ jobId, force = false }: { jobId: number; force?: boolean }) =>
      unwrap(api.POST('/jobs/{job_id}/check-open', { params: { path: { job_id: jobId } }, body: { force } })),
    // Una comprobación reciente devuelta tal cual no cambia nada: no hace falta recargar.
    onSuccess: (result, { jobId }) =>
      result.cached
        ? undefined
        : Promise.all([
            client.invalidateQueries({ queryKey: keys.job(jobId) }),
            client.invalidateQueries({ queryKey: keys.allJobs }),
          ]),
  })
}

/** «Sigue abierta»: quita el aviso de posible cierre (ese motivo ya no vuelve a avisar). */
export function useConfirmJobOpen() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (jobId: number) =>
      unwrap(api.POST('/jobs/{job_id}/still-open', { params: { path: { job_id: jobId } }, body: {} })),
    onSuccess: (_result, jobId) =>
      Promise.all([
        client.invalidateQueries({ queryKey: keys.job(jobId) }),
        client.invalidateQueries({ queryKey: keys.allJobs }),
      ]),
  })
}

/** CV vigente de la oferta (contenido, verificación y renders); `cv: null` si aún no tiene. */
export function useJobCv(jobId: number, enabled = true) {
  return useQuery({
    queryKey: keys.cv(jobId),
    queryFn: () => unwrap(api.GET('/jobs/{job_id}/cv', { params: { path: { job_id: jobId } } })),
    enabled: enabled && Number.isInteger(jobId) && jobId > 0,
  })
}

export function useTemplates() {
  return useQuery({
    queryKey: keys.templates,
    queryFn: () => unwrap(api.GET('/templates')),
    staleTime: 60_000,
  })
}

/** CVs subidos para convertirlos en plantilla y si ya se importaron. */
export function useUploads() {
  return useQuery({
    queryKey: keys.uploads,
    queryFn: () => unwrap(api.GET('/uploads')),
    // El agente importa el fichero desde fuera: se refresca solo para ver cuándo termina.
    refetchInterval: 15_000,
  })
}

export function useUploadCv() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (file: File) =>
      unwrap(
        api.POST('/uploads', {
          body: { file: file as unknown as string },
          bodySerializer: () => {
            const form = new FormData()
            form.append('file', file)
            return form
          },
        }),
      ),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.uploads }),
  })
}

export function useDeleteUpload() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (name: string) => unwrap(api.DELETE('/uploads/{name}', { params: { path: { name } } }).then(withNoContent)),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.uploads }),
  })
}

/** Un 204 no trae cuerpo: `unwrap` necesita algo en `data` para no tomarlo por error. */
function withNoContent<T extends { response: Response }>(result: T): T & { data: true } {
  return result.response.ok ? { ...result, data: true, error: undefined } : (result as T & { data: true })
}

export function useDefaultTemplate() {
  return useQuery({
    queryKey: keys.defaultTemplate,
    queryFn: () => unwrap(api.GET('/templates/default')),
  })
}

/** Fija la plantilla por defecto en tu perfil (conserva comentarios) e importa la versión nueva. */
export function useSetDefaultTemplate() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (templateId: string) =>
      unwrap(api.POST('/templates/{template_id}/default', { params: { path: { template_id: templateId } } })),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.defaultTemplate }),
  })
}

/** Renderiza el CV con otras opciones (sin agente). Puede pasar a «cv_ready»: refresca la ficha. */
export function useRenderCv(jobId: number) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ documentId, options }: { documentId: number; options: CvRenderOptions }) =>
      unwrap(
        api.POST('/documents/{document_id}/renders', {
          params: { path: { document_id: documentId } },
          body: options,
        }),
      ),
    onSuccess: () =>
      Promise.all([
        client.invalidateQueries({ queryKey: keys.cv(jobId) }),
        client.invalidateQueries({ queryKey: keys.job(jobId) }),
        client.invalidateQueries({ queryKey: keys.status }),
        client.invalidateQueries({ queryKey: keys.allJobs }),
      ]),
  })
}

/** Marca el render que se enviará. No cambia la etapa. */
export function useSelectRender(jobId: number) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (renderId: number) =>
      unwrap(api.POST('/renders/{render_id}/select', { params: { path: { render_id: renderId } } })),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.cv(jobId) }),
  })
}

// --- Fuentes: empresas objetivo y portales (fase 09) ---------------------------------------------

export function useSources() {
  return useQuery({
    queryKey: keys.sources,
    queryFn: () => unwrap(api.GET('/sources')),
    // El worker ejecuta las fuentes por su cuenta: se refresca solo.
    refetchInterval: 60_000,
  })
}

export function useAddSource() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: Schemas['SourceInput']) => unwrap(api.POST('/sources', { body })),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.sources }),
  })
}

/** Prueba una fuente sin guardar nada: la nueva del formulario o una guardada por su id. */
export function usePreviewSource() {
  return useMutation({
    mutationFn: (target: Schemas['SourceInput'] | number) =>
      typeof target === 'number'
        ? unwrap(api.POST('/sources/{source_id}/test', { params: { path: { source_id: target } } }))
        : unwrap(api.POST('/sources/test', { body: target })),
  })
}

export function useRunSource() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (sourceId: number) =>
      unwrap(api.POST('/sources/{source_id}/run', { params: { path: { source_id: sourceId } } })),
    onSuccess: () =>
      Promise.all([
        client.invalidateQueries({ queryKey: keys.sources }),
        client.invalidateQueries({ queryKey: keys.status }),
        client.invalidateQueries({ queryKey: keys.allJobs }),
      ]),
  })
}

/** Plataformas de la búsqueda con navegador del agente (fuentes `agent_browse`). */
export function usePlatforms() {
  return useQuery({
    queryKey: [...keys.sources, 'agent_browse'] as const,
    queryFn: () => unwrap(api.GET('/sources', { params: { query: { kind: 'agent_browse' } } })),
    // El agente anota sus recorridos por su cuenta: se refresca solo.
    refetchInterval: 60_000,
  })
}

/** Cambios del usuario en una plataforma. Activar LinkedIn exige `confirm_risk`. */
export function useUpdateBrowseSettings() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({
      sourceId,
      ...body
    }: { sourceId: number } & Partial<Schemas['BrowseSettingsBody']>) =>
      unwrap(
        api.POST('/sources/{source_id}/browse', {
          params: { path: { source_id: sourceId } },
          body: { confirm_risk: false, ...body },
        }),
      ),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.sources }),
  })
}

/** Búsqueda pública de LinkedIn sin sesión (fase 22). Bajo `sources`: añadir búsquedas la cambia. */
export function useLinkedInPublic() {
  return useQuery({
    queryKey: [...keys.sources, 'linkedin-public'] as const,
    queryFn: () => unwrap(api.GET('/sources/linkedin-public')),
    refetchInterval: 60_000, // el worker la ejecuta por su cuenta
  })
}

/** Encender exige `confirm_risk`; apagar, no. */
export function useUpdateLinkedInPublic() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: Partial<Schemas['LinkedInPublicSettingsBody']>) =>
      unwrap(api.POST('/sources/linkedin-public/settings', { body: { confirm_risk: false, ...body } })),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.sources }),
  })
}

/** «Buscar ahora»: tarda (≥ 10 s entre peticiones) y respeta el límite de una al día. */
export function useRunLinkedInPublic() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: () => unwrap(api.POST('/sources/linkedin-public/run', { body: {} })),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: keys.sources })
      client.invalidateQueries({ queryKey: keys.alerts })
      client.invalidateQueries({ queryKey: keys.status })
    },
  })
}

/** «Añadir plataforma»: una web donde el agente busca con tu navegador (LinkedIn, desactivada). */
export function useAddPlatform() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: Schemas['AgentBrowseSource']) => unwrap(api.POST('/sources/platforms', { body })),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.sources }),
  })
}

// --- Avisos al usuario (captcha, login…) ---------------------------------------------------------

/** Avisos que esperan tu respuesta. Se pregunta cada pocos segundos: el agente espera 5 minutos. */
export function usePendingPrompts() {
  return useQuery({
    queryKey: keys.prompts,
    queryFn: () => unwrap(api.GET('/prompts/pending')),
    refetchInterval: 4000,
    refetchIntervalInBackground: true,
  })
}

/** «Ya está» o «Saltar». */
export function useAnswerPrompt() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ promptId, outcome }: { promptId: number; outcome: 'done' | 'skipped' }) =>
      unwrap(api.POST('/prompts/{prompt_id}/answer', { params: { path: { prompt_id: promptId } }, body: { outcome } })),
    onSettled: () =>
      Promise.all([
        client.invalidateQueries({ queryKey: keys.prompts }),
        client.invalidateQueries({ queryKey: ['apply'] }),
      ]),
  })
}

export function useSetSourceActive() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ sourceId, active }: { sourceId: number; active: boolean }) =>
      unwrap(
        api.POST('/sources/{source_id}/active', {
          params: { path: { source_id: sourceId } },
          body: { active },
        }),
      ),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.sources }),
  })
}

// --- Alertas por correo: ofertas resumen (fase 09b) --------------------------------------------

export function useAlerts() {
  return useQuery({
    queryKey: keys.alerts,
    queryFn: () => unwrap(api.GET('/alerts')),
    // El worker lee el correo por su cuenta: se refresca solo.
    refetchInterval: 60_000,
  })
}

/** Lee ahora las alertas nuevas (IMAP en solo lectura y `data/inbox/`). */
export function usePollAlerts() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: () => unwrap(api.POST('/alerts/poll')),
    onSuccess: () =>
      Promise.all([
        client.invalidateQueries({ queryKey: keys.alerts }),
        client.invalidateQueries({ queryKey: keys.status }),
        client.invalidateQueries({ queryKey: keys.allJobs }),
      ]),
  })
}

// --- Seguimiento: kanban, ficha de proceso, hitos y contactos (fase 10) ------------------------

type Client = ReturnType<typeof useQueryClient>

/** Lo que cambia cuando se mueve un proceso: tablero, seguimientos, próximos y su ficha. */
function invalidateTracking(client: Client, jobId?: number) {
  return [
    client.invalidateQueries({ queryKey: keys.board }),
    client.invalidateQueries({ queryKey: keys.followups }),
    client.invalidateQueries({ queryKey: keys.allUpcoming }),
    ...(jobId
      ? [
          client.invalidateQueries({ queryKey: keys.process(jobId) }),
          client.invalidateQueries({ queryKey: keys.package(jobId) }),
        ]
      : []),
  ]
}

export function useBoard() {
  return useQuery({ queryKey: keys.board, queryFn: () => unwrap(api.GET('/board')) })
}

export function useFollowups() {
  return useQuery({
    queryKey: keys.followups,
    queryFn: () => unwrap(api.GET('/followups')),
    refetchInterval: 5 * 60_000,
  })
}

export function useUpcoming(days = 7) {
  return useQuery({
    queryKey: keys.upcoming(days),
    queryFn: () => unwrap(api.GET('/upcoming', { params: { query: { days } } })),
  })
}

export function useJobProcess(jobId: number, enabled = true) {
  return useQuery({
    queryKey: keys.process(jobId),
    queryFn: () =>
      unwrap(api.GET('/jobs/{job_id}/process', { params: { path: { job_id: jobId } } })),
    enabled: enabled && Number.isInteger(jobId) && jobId > 0,
  })
}

/** Tras un cambio en un proceso: recuentos, ficha de la oferta y seguimiento. */
function useInvalidateProcess() {
  const client = useQueryClient()
  return (jobId: number) =>
    Promise.all([
      client.invalidateQueries({ queryKey: keys.status }),
      client.invalidateQueries({ queryKey: keys.allJobs }),
      client.invalidateQueries({ queryKey: keys.job(jobId) }),
      ...invalidateTracking(client, jobId),
    ])
}

export type MilestoneCreate = Schemas['MilestoneCreate']
export type MilestoneFields = Schemas['MilestoneFields']
export type ContactFields = Schemas['ContactFields']

export function useCreateMilestone() {
  const invalidate = useInvalidateProcess()
  return useMutation({
    mutationFn: ({ jobId, body }: { jobId: number; body: MilestoneCreate }) =>
      unwrap(api.POST('/jobs/{job_id}/milestones', { params: { path: { job_id: jobId } }, body })),
    onSuccess: (_r, { jobId }) => invalidate(jobId),
  })
}

export function useUpdateMilestone(jobId: number) {
  const invalidate = useInvalidateProcess()
  return useMutation({
    mutationFn: ({ milestoneId, body }: { milestoneId: number; body: MilestoneFields }) =>
      unwrap(
        api.POST('/milestones/{milestone_id}', { params: { path: { milestone_id: milestoneId } }, body }),
      ),
    onSuccess: () => invalidate(jobId),
  })
}

export function useMilestoneStatus(jobId: number) {
  const invalidate = useInvalidateProcess()
  return useMutation({
    mutationFn: ({ milestoneId, body }: { milestoneId: number; body: Schemas['MilestoneStatusChange'] }) =>
      unwrap(
        api.POST('/milestones/{milestone_id}/status', {
          params: { path: { milestone_id: milestoneId } },
          body,
        }),
      ),
    onSuccess: () => invalidate(jobId),
  })
}

export function useSaveContact(jobId: number) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ contactId, body }: { contactId?: number; body: ContactFields }) =>
      contactId
        ? unwrap(api.POST('/contacts/{contact_id}', { params: { path: { contact_id: contactId } }, body }))
        : unwrap(api.POST('/jobs/{job_id}/contacts', { params: { path: { job_id: jobId } }, body })),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.process(jobId) }),
  })
}

export function useDeleteContact(jobId: number) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (contactId: number) =>
      unwrap(api.POST('/contacts/{contact_id}/delete', { params: { path: { contact_id: contactId } } })),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.process(jobId) }),
  })
}

export function useFunnelStats(since: string | null) {
  return useQuery({
    queryKey: keys.funnel(since),
    queryFn: () => unwrap(api.GET('/stats/funnel', { params: { query: { since } } })),
    placeholderData: keepPreviousData,
  })
}

/** «¿Acierta el score?» (fase 20): `since` es la fecha del primer envío. */
export function useCalibration(since: string | null) {
  return useQuery({
    queryKey: keys.calibration(since),
    queryFn: () => unwrap(api.GET('/stats/calibration', { params: { query: { since } } })),
    placeholderData: keepPreviousData,
  })
}

// --- Paquete de candidatura (fase 10.3) ----------------------------------------------------------

export type ScreeningAnswer = Schemas['ScreeningAnswer']

export function useJobPackage(jobId: number, enabled = true) {
  return useQuery({
    queryKey: keys.package(jobId),
    queryFn: () =>
      unwrap(api.GET('/jobs/{job_id}/package', { params: { path: { job_id: jobId } } })),
    enabled: enabled && Number.isInteger(jobId) && jobId > 0,
  })
}

/** Guarda la edición del usuario: un documento nuevo «Editadas por ti». No envía nada. */
export function useSaveAnswers(jobId: number) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (answers: ScreeningAnswer[]) =>
      unwrap(
        api.POST('/jobs/{job_id}/answers', { params: { path: { job_id: jobId } }, body: { answers } }),
      ),
    onSuccess: () =>
      Promise.all([
        client.invalidateQueries({ queryKey: keys.package(jobId) }),
        client.invalidateQueries({ queryKey: keys.process(jobId) }),
        client.invalidateQueries({ queryKey: keys.job(jobId) }),
      ]),
  })
}

// --- Carta de presentación (fase 08c) ------------------------------------------------------------

export type CoverLetterContent = Schemas['CoverLetterContent']
export type CoverLetterRenderOptions = Schemas['CoverLetterRenderOptions']
export type CoverLetterBriefInput = Schemas['CoverLetterBriefInput']

export function useJobCoverLetter(jobId: number, enabled = true) {
  return useQuery({
    queryKey: keys.letter(jobId),
    queryFn: () =>
      unwrap(api.GET('/jobs/{job_id}/cover-letter', { params: { path: { job_id: jobId } } })),
    enabled: enabled && Number.isInteger(jobId) && jobId > 0,
  })
}

/** Tras un cambio en la carta: ella, el paquete (ambos bajo `cv`), la ficha de proceso y el historial. */
function useInvalidateLetter(jobId: number) {
  const client = useQueryClient()
  return () =>
    Promise.all([
      client.invalidateQueries({ queryKey: keys.cv(jobId) }),
      client.invalidateQueries({ queryKey: keys.process(jobId) }),
      client.invalidateQueries({ queryKey: keys.job(jobId) }),
    ])
}

export function useSaveLetterBrief(jobId: number) {
  const invalidate = useInvalidateLetter(jobId)
  return useMutation({
    mutationFn: (body: CoverLetterBriefInput) =>
      unwrap(
        api.POST('/jobs/{job_id}/cover-letter/brief', { params: { path: { job_id: jobId } }, body }),
      ),
    onSuccess: () => invalidate(),
  })
}

export function useRenderLetter(jobId: number) {
  const invalidate = useInvalidateLetter(jobId)
  return useMutation({
    mutationFn: ({ documentId, options }: { documentId: number; options: CoverLetterRenderOptions }) =>
      unwrap(
        api.POST('/cover-letters/{document_id}/renders', {
          params: { path: { document_id: documentId } },
          body: options,
        }),
      ),
    onSuccess: () => invalidate(),
  })
}

/** Retoque a mano: una carta nueva «Editada por ti», sin verificación. No envía nada. */
export function useSaveUserLetter(jobId: number) {
  const invalidate = useInvalidateLetter(jobId)
  return useMutation({
    mutationFn: (body: CoverLetterContent) =>
      unwrap(api.POST('/jobs/{job_id}/cover-letter', { params: { path: { job_id: jobId } }, body })),
    onSuccess: () => invalidate(),
  })
}

// --- Candidatura asistida (fase 11) --------------------------------------------------------------

/** Mientras el worker trabaja en el intento, se vuelve a preguntar cada 2 s. */
const APPLY_BUSY = new Set(['queued', 'filling', 'submitting'])

export function useAssistedApplication(jobId: number, enabled = true) {
  return useQuery({
    queryKey: keys.apply(jobId),
    queryFn: () =>
      unwrap(api.GET('/jobs/{job_id}/apply', { params: { path: { job_id: jobId } } })),
    enabled: enabled && Number.isInteger(jobId) && jobId > 0,
    refetchInterval: (query) => {
      const attempt = query.state.data?.attempt
      return attempt && (APPLY_BUSY.has(attempt.status) || attempt.pending_task) ? 2000 : false
    },
  })
}

/** Tras cambiar la etapa (enviada), se refresca todo lo que la muestra. */
export function useRefreshAfterApply(jobId: number) {
  const client = useQueryClient()
  return () =>
    Promise.all([
      client.invalidateQueries({ queryKey: keys.job(jobId) }),
      client.invalidateQueries({ queryKey: keys.package(jobId) }),
      client.invalidateQueries({ queryKey: keys.process(jobId) }),
      client.invalidateQueries({ queryKey: keys.status }),
      client.invalidateQueries({ queryKey: keys.allJobs }),
      client.invalidateQueries({ queryKey: keys.board }),
    ])
}

function useApplyMutation<T>(jobId: number, call: (arg: T) => Promise<unknown>) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: call,
    // También tras un error (409 `stale`, `busy`…): el intento cambió y hay que verlo al día.
    onSettled: () => client.invalidateQueries({ queryKey: keys.apply(jobId) }),
  })
}

export function useOpenBrowser() {
  return useMutation({ mutationFn: () => unwrap(api.POST('/browser/open')) })
}

/**
 * Encola rellenar el formulario (o, en LinkedIn y en los portales de empleo, solo abrir la oferta).
 * Con `formUrl`, rellena esa URL: el formulario de la empresa. No envía nada.
 */
export function usePrepareApplication(jobId: number) {
  return useApplyMutation(jobId, (formUrl?: string) =>
    unwrap(
      api.POST('/jobs/{job_id}/apply/prepare', {
        params: { path: { job_id: jobId } },
        body: formUrl ? { form_url: formUrl } : undefined,
      }),
    ),
  )
}

/** «Rellenar esta página»: la pestaña que tienes delante en el navegador de CandidatAI. */
export function useFillApplicationPage(jobId: number) {
  return useApplyMutation(jobId, (attemptId: number) =>
    unwrap(api.POST('/apply/{attempt_id}/fill-page', { params: { path: { attempt_id: attemptId } } })),
  )
}

export function useRescanApplication(jobId: number) {
  return useApplyMutation(jobId, (attemptId: number) =>
    unwrap(api.POST('/apply/{attempt_id}/rescan', { params: { path: { attempt_id: attemptId } } })),
  )
}

export function useFocusApplication(jobId: number) {
  return useApplyMutation(jobId, (attemptId: number) =>
    unwrap(api.POST('/apply/{attempt_id}/focus', { params: { path: { attempt_id: attemptId } } })),
  )
}

/** Tu confirmación de envío: el nombre de la empresa y la versión del intento que revisaste. */
export function useSubmitApplication(jobId: number) {
  return useApplyMutation(
    jobId,
    ({ attemptId, company, reviewedAt }: { attemptId: number; company: string; reviewedAt: string }) =>
      unwrap(
        api.POST('/apply/{attempt_id}/submit', {
          params: { path: { attempt_id: attemptId } },
          body: { company_confirmation: company, reviewed_at: reviewedAt },
        }),
      ),
  )
}

export function useMarkApplicationSent(jobId: number) {
  const client = useQueryClient()
  const refresh = useRefreshAfterApply(jobId)
  return useMutation({
    mutationFn: () =>
      unwrap(api.POST('/jobs/{job_id}/apply/manual-done', { params: { path: { job_id: jobId } } })),
    onSuccess: () =>
      Promise.all([client.invalidateQueries({ queryKey: keys.apply(jobId) }), refresh()]),
  })
}

// --- Botones «en tu agente» (ADR-024) -----------------------------------------------------------

export type AgentAction = Schemas['LaunchBody']['action']

/** Qué agente abren los botones (o por qué no) y las órdenes que hay. Cambia poco: sin refresco. */
export function useAgentLauncher() {
  return useQuery({ queryKey: keys.agent, queryFn: () => unwrap(api.GET('/agent')), staleTime: Infinity })
}

/** Abre tu agente en una terminal con la orden escrita. No espera a que termine. `agent`: otro
 * agente solo para esta ejecución (fase 24.4). */
export function useLaunchAgent() {
  return useMutation({
    mutationFn: (body: LaunchTarget & { agent?: string }) => unwrap(api.POST('/agent/launch', { body })),
  })
}

// --- Elegir agente (fase 24.4) -----------------------------------------------------------------

/** Los agentes del manifiesto, tus preferencias y el agente efectivo de cada acción. */
export function useAgentsOverview() {
  return useQuery({ queryKey: keys.agentAgents, queryFn: () => unwrap(api.GET('/agent/agents')) })
}

/** Guarda las preferencias (sustituye todas). Cambia el agente de los botones: se refresca todo. */
export function useSaveAgentPreferences() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: Schemas['Preferences']) => unwrap(api.PUT('/agent/preferences', { body })),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.agent }),
  })
}

// --- En segundo plano y cola de encargos (fase 19) ---------------------------------------------

type LaunchTarget = { action: AgentAction; job_id?: number; milestone_id?: number }

/**
 * Las últimas ejecuciones en segundo plano. Mientras alguna está en cola o en curso se pregunta
 * cada 3 s (el worker guarda el progreso cada 2 s); si no, cada 20 s.
 */
export function useAgentRuns() {
  return useQuery({
    queryKey: keys.agentRuns,
    queryFn: () => unwrap(api.GET('/agent/runs', { params: { query: { limit: 20 } } })),
    refetchInterval: (query) => ((query.state.data?.active ?? 0) > 0 ? 3000 : 20000),
  })
}

/** «En segundo plano»: deja la ejecución en cola para el worker. */
export function useStartAgentRun() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: LaunchTarget) => unwrap(api.POST('/agent/runs', { body })),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.agentRuns }),
  })
}

export function useCancelAgentRun() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (runId: number) =>
      unwrap(api.POST('/agent/runs/{run_id}/cancel', { params: { path: { run_id: runId } }, body: {} })),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.agentRuns }),
  })
}

/** «Abrir en terminal»: sigue la sesión de una ejecución terminada. */
export function useOpenAgentRun() {
  return useMutation({
    mutationFn: (runId: number) =>
      unwrap(api.POST('/agent/runs/{run_id}/open', { params: { path: { run_id: runId } }, body: {} })),
  })
}

/** Los encargos para tu próxima sesión (todos: la página separa pendientes y hechos). */
export function useAgentRequests() {
  return useQuery({
    queryKey: keys.agentRequests,
    queryFn: () => unwrap(api.GET('/agent/requests', { params: { query: { limit: 50 } } })),
    // El agente los cierra desde fuera: se refresca solo.
    refetchInterval: 20000,
  })
}

/** «Dejar para mi próxima sesión». */
export function useCreateAgentRequest() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: LaunchTarget) => unwrap(api.POST('/agent/requests', { body })),
    onSuccess: () =>
      Promise.all([
        client.invalidateQueries({ queryKey: keys.agentRequests }),
        client.invalidateQueries({ queryKey: keys.status }),
      ]),
  })
}

export function useCancelAgentRequest() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (requestId: number) =>
      unwrap(api.POST('/agent/requests/{request_id}/cancel', { params: { path: { request_id: requestId } }, body: {} })),
    onSuccess: () =>
      Promise.all([
        client.invalidateQueries({ queryKey: keys.agentRequests }),
        client.invalidateQueries({ queryKey: keys.status }),
      ]),
  })
}

// --- Mi perfil: contexto y documentos (fase 13) ---------------------------------------------

export type FolderKind = Schemas['OpenFolderBody']['folder']

/** Estado de `data/contexto/` y `data/documentos/`. Se refresca al volver a la ventana. */
export function useContextStatus() {
  return useQuery({ queryKey: keys.context, queryFn: () => unwrap(api.GET('/context')) })
}

/** Abre la carpeta en el explorador; si no se puede, la respuesta trae la ruta para copiarla. */
export function useOpenFolder() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: { folder: FolderKind; job_id?: number }) =>
      unwrap(api.POST('/folders/open', { body })),
    // Abrir el contexto o los documentos crea lo que falte.
    onSuccess: () => client.invalidateQueries({ queryKey: keys.context }),
  })
}

// --- Huecos de skills (fase 14) ---------------------------------------------------------------

export type SkillGap = Schemas['SkillGap']
export type SkillMark = NonNullable<Schemas['MarkBody']['status']>

export function useSkillGaps(days: number) {
  return useQuery({
    queryKey: keys.skillGaps(days),
    queryFn: () => unwrap(api.GET('/skills/gaps', { params: { query: { days } } })),
    placeholderData: keepPreviousData,
  })
}

/** «Es lo mismo que…»: el alias cambia el score de las ofertas afectadas (lo recalcula el worker). */
export function useAddSkillAlias() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: { skill: string; profile_skill: string }) =>
      unwrap(api.POST('/skills/aliases', { body })),
    onSuccess: () =>
      Promise.all([
        client.invalidateQueries({ queryKey: keys.allSkillGaps }),
        client.invalidateQueries({ queryKey: keys.triage }),
        client.invalidateQueries({ queryKey: ['match'] }),
        client.invalidateQueries({ queryKey: keys.allJobs }),
      ]),
  })
}

/** «No la tengo», «La tengo» o quitar la marca (`null`). */
export function useSetSkillMark() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: { skill: string; status: SkillMark | null }) =>
      unwrap(api.POST('/skills/marks', { body })),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.allSkillGaps }),
  })
}

// --- Respuestas de las empresas (fase 15) ----------------------------------------------------

export type ReplyStatus = Schemas['ReplyInboxItem']['status']
export type ReplyDecision = Schemas['ReplyDecision']

export interface RepliesParams {
  status?: ReplyStatus
  jobId?: number
}

/** Bandeja «Respuestas» (o las de una oferta con `jobId`) y los recuentos por estado. */
export function useReplies(params: RepliesParams = {}) {
  return useQuery({
    queryKey: keys.replies(params),
    queryFn: () =>
      unwrap(api.GET('/replies', { params: { query: { status: params.status, job_id: params.jobId } } })),
    // El worker lee el correo y el agente guarda propuestas por su cuenta: se refresca solo.
    refetchInterval: 60_000,
  })
}

/** Una respuesta con el texto visible del correo. */
export function useReply(id: number | null) {
  return useQuery({
    queryKey: keys.reply(id ?? 0),
    queryFn: () => unwrap(api.GET('/replies/{reply_id}', { params: { path: { reply_id: id ?? 0 } } })),
    enabled: id !== null && id > 0,
  })
}

/** Lee ahora el correo (IMAP en solo lectura y `data/inbox/respuestas/`). */
export function usePollReplies() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: () => unwrap(api.POST('/replies/poll', { body: {} })),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.allReplies }),
  })
}

/** Acepta la propuesta (tal cual o cambiada): registra su evento y, si lo hay, su hito. */
export function useAcceptReply() {
  const client = useQueryClient()
  const invalidate = useInvalidateProcess()
  return useMutation({
    mutationFn: ({ replyId, body }: { replyId: number; body: ReplyDecision }) =>
      unwrap(api.POST('/replies/{reply_id}/accept', { params: { path: { reply_id: replyId } }, body })),
    onSuccess: (_r, { replyId, body }) =>
      Promise.all([
        client.invalidateQueries({ queryKey: keys.allReplies }),
        client.invalidateQueries({ queryKey: keys.reply(replyId) }),
        invalidate(body.job_id),
      ]),
  })
}

/** Ignora la respuesta: no registra nada. */
export function useIgnoreReply() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (replyId: number) =>
      unwrap(api.POST('/replies/{reply_id}/ignore', { params: { path: { reply_id: replyId } }, body: {} })),
    onSuccess: (_r, replyId) =>
      Promise.all([
        client.invalidateQueries({ queryKey: keys.allReplies }),
        client.invalidateQueries({ queryKey: keys.reply(replyId) }),
      ]),
  })
}

// --- Borradores de seguimiento y agradecimiento (fase 15) --------------------------------------

/** Borradores vigentes de la oferta y cuántos seguimientos llevas enviados. */
export function useJobDrafts(jobId: number, enabled = true) {
  return useQuery({
    queryKey: keys.drafts(jobId),
    queryFn: () => unwrap(api.GET('/jobs/{job_id}/drafts', { params: { path: { job_id: jobId } } })),
    enabled: enabled && Number.isInteger(jobId) && jobId > 0,
    // El agente los guarda desde fuera: se refresca solo.
    refetchInterval: 60_000,
  })
}

/** «Ya lo he enviado»: lo mandaste desde tu correo. Un seguimiento registra `followup_sent`. */
export function useMarkDraftSent(jobId: number) {
  const client = useQueryClient()
  const invalidate = useInvalidateProcess()
  return useMutation({
    mutationFn: (draftId: number) =>
      unwrap(api.POST('/drafts/{draft_id}/sent', { params: { path: { draft_id: draftId } }, body: {} })),
    onSuccess: () => Promise.all([client.invalidateQueries({ queryKey: keys.drafts(jobId) }), invalidate(jobId)]),
  })
}

export function useDiscardDraft(jobId: number) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (draftId: number) =>
      unwrap(api.POST('/drafts/{draft_id}/discard', { params: { path: { draft_id: draftId } }, body: {} })),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.drafts(jobId) }),
  })
}

// --- Red de LinkedIn (fase 18) ------------------------------------------------------------------

export function useNetworkStatus() {
  return useQuery({ queryKey: keys.network, queryFn: () => unwrap(api.GET('/network')) })
}

/** Importa `data/documentos/linkedin/Connections.csv` (sincroniza la red). */
export function useImportNetwork() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: () => unwrap(api.POST('/network/import', { body: {} })),
    onSuccess: () =>
      Promise.all([
        client.invalidateQueries({ queryKey: keys.network }),
        client.invalidateQueries({ queryKey: keys.allJobs }),
        client.invalidateQueries({ queryKey: keys.triage }),
      ]),
  })
}

export function useJobNetwork(jobId: number, enabled = true) {
  return useQuery({
    queryKey: keys.jobNetwork(jobId),
    queryFn: () => unwrap(api.GET('/jobs/{job_id}/network', { params: { path: { job_id: jobId } } })),
    enabled: enabled && Number.isInteger(jobId) && jobId > 0,
  })
}

/** «Añadir como contacto del proceso» con su papel. */
export function useAddContactFromNetwork(jobId: number) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: Schemas['AddFromNetwork']) =>
      unwrap(api.POST('/jobs/{job_id}/contacts/from-network', { params: { path: { job_id: jobId } }, body })),
    onSuccess: () =>
      Promise.all([
        client.invalidateQueries({ queryKey: keys.process(jobId) }),
        client.invalidateQueries({ queryKey: keys.jobNetwork(jobId) }),
      ]),
  })
}

/** «Referencia pedida / dada» en un contacto del proceso (o quitar la marca con `null`). */
export function useSetReferral(jobId: number) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ contactId, referral }: { contactId: number; referral: ReferralStatus | null }) =>
      unwrap(
        api.POST('/contacts/{contact_id}/referral', {
          params: { path: { contact_id: contactId } },
          body: { referral },
        }),
      ),
    onSuccess: () =>
      Promise.all([
        client.invalidateQueries({ queryKey: keys.process(jobId) }),
        client.invalidateQueries({ queryKey: ['funnel'] }),
      ]),
  })
}

// --- Dosier de empresa (fase 18) ----------------------------------------------------------------

export function useCompanyResearch(jobId: number, enabled = true) {
  return useQuery({
    queryKey: keys.research(jobId),
    queryFn: () =>
      unwrap(api.GET('/jobs/{job_id}/company-research', { params: { path: { job_id: jobId } } })),
    enabled: enabled && Number.isInteger(jobId) && jobId > 0,
    // Lo guarda el agente desde fuera: se refresca solo.
    refetchInterval: 60_000,
  })
}

/** Ficha (fase 21): la oferta recibida anotada por ti, o `null` si aún no hay. */
export function useReceivedOffer(jobId: number, enabled = true) {
  return useQuery({
    queryKey: keys.receivedOffer(jobId),
    queryFn: () =>
      unwrap(api.GET('/jobs/{job_id}/received-offer', { params: { path: { job_id: jobId } } })),
    enabled: enabled && Number.isInteger(jobId) && jobId > 0,
  })
}

function invalidateOffer(client: ReturnType<typeof useQueryClient>, jobId: number) {
  return Promise.all([
    client.invalidateQueries({ queryKey: keys.receivedOffers }),
    client.invalidateQueries({ queryKey: keys.job(jobId) }),
    client.invalidateQueries({ queryKey: keys.process(jobId) }),
    client.invalidateQueries({ queryKey: keys.board }),
  ])
}

/** Guarda la oferta recibida; si aún no había `offer_received`, la API lo registra. */
export function useSaveReceivedOffer(jobId: number) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: Schemas['ReceivedOfferFields']) =>
      unwrap(api.POST('/jobs/{job_id}/received-offer', { params: { path: { job_id: jobId } }, body })),
    onSuccess: () => invalidateOffer(client, jobId),
  })
}

export function useDeleteReceivedOffer(jobId: number) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: () =>
      unwrap(api.POST('/jobs/{job_id}/received-offer/delete', { params: { path: { job_id: jobId } } })),
    onSuccess: () => invalidateOffer(client, jobId),
  })
}

/** «Ofertas recibidas» en Procesos: lado a lado, con la diferencia con tu mínimo (solo la UI). */
export function useReceivedOffers() {
  return useQuery({
    queryKey: keys.receivedOffers,
    queryFn: () => unwrap(api.GET('/received-offers')),
  })
}
