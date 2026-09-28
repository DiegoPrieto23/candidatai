import createClient from 'openapi-fetch'
import type { components, paths } from './schema'

export type Schemas = components['schemas']
export type Stage = Schemas['Stage']
export type JobRow = Schemas['JobRow']
export type JobView = Schemas['JobView']
export type EventOut = Schemas['EventOut']
export type StatusReport = Schemas['StatusReport']
export type AddJobResult = Schemas['AddJobResult']
export type ErrorDetail = Schemas['ErrorDetail']
export type MatchView = Schemas['MatchView']
export type TriageItem = Schemas['TriageItem']
export type TriageQueue = Schemas['TriageQueue']
export type DiscardReason = NonNullable<Schemas['AddUserEventBody']['reason']>

export const API_URL: string = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000'

export const api = createClient<paths>({
  baseUrl: API_URL,
  // Se resuelve en cada llamada (no al crear el cliente) para que los tests puedan simularlo.
  fetch: (request) => globalThis.fetch(request),
})

/** Error de la API con el formato común `{ok: false, error: {type, message, details}}`. */
export class ApiError extends Error {
  readonly type: string
  readonly status: number
  readonly details: ErrorDetail[]

  constructor(message: string, type: string, status: number, details: ErrorDetail[] = []) {
    super(message)
    this.name = 'ApiError'
    this.type = type
    this.status = status
    this.details = details
  }
}

const OFFLINE = new ApiError(
  'No hay conexión con la API. Arráncala con `uv run jh serve` en backend/.',
  'offline',
  0,
)

interface Result<T> {
  data?: T
  error?: unknown
  response: Response
}

function isErrorBody(value: unknown): value is Schemas['ErrorResponse'] {
  return typeof value === 'object' && value !== null && 'error' in value
}

/** Devuelve `data` o lanza `ApiError`. Envuelve la llamada para detectar la API caída. */
export async function unwrap<T>(call: Promise<Result<T>>): Promise<T> {
  let result: Result<T>
  try {
    result = await call
  } catch {
    throw OFFLINE
  }
  const { data, error, response } = result
  if (error !== undefined || data === undefined) {
    if (isErrorBody(error)) {
      const { message, type, details } = error.error
      throw new ApiError(message, type, response.status, details ?? [])
    }
    throw new ApiError(`Error inesperado de la API (${response.status}).`, 'unknown', response.status)
  }
  return data
}
