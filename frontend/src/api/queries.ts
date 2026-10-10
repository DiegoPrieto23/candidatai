import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError, api, unwrap, type CvRenderOptions, type Schemas, type Stage } from './client'
import type { operations } from './schema'

export const PAGE_SIZE = 50

export const keys = {
  status: ['status'] as const,
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
  apply: (id: number) => ['apply', id] as const,
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

/** Encola rellenar el formulario (o, en LinkedIn, solo abrirlo). No envía nada. */
export function usePrepareApplication(jobId: number) {
  return useApplyMutation(jobId, () =>
    unwrap(api.POST('/jobs/{job_id}/apply/prepare', { params: { path: { job_id: jobId } } })),
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
