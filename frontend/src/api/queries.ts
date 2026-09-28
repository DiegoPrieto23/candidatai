import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, unwrap, type Schemas, type Stage } from './client'

export const PAGE_SIZE = 50

export const keys = {
  status: ['status'] as const,
  jobs: (params: JobsParams) => ['jobs', params] as const,
  allJobs: ['jobs'] as const,
  job: (id: number) => ['job', id] as const,
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
