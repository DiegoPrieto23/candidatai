import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError, api, unwrap, type CvRenderOptions, type Schemas, type Stage } from './client'

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
}

export interface JobsParams {
  stage?: Stage
  q?: string
  page: number
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
    onSuccess: () => client.invalidateQueries({ queryKey: keys.job(jobId) }),
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
