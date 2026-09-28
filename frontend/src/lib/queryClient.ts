import { QueryClient } from '@tanstack/react-query'
import { ApiError } from '@/api/client'

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 10_000,
        // Un 404 o un error de validación no se arreglan reintentando.
        retry: (count, error) => count < 2 && !(error instanceof ApiError && error.status >= 400),
      },
    },
  })
}
