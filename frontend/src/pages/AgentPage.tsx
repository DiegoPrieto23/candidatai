import { useState } from 'react'
import { Link } from 'react-router'
import {
  ChatCircleDotsIcon,
  CircleNotchIcon,
  ClockCountdownIcon,
  TerminalWindowIcon,
  XIcon,
} from '@phosphor-icons/react'
import type { AgentRequestView, AgentRunView } from '@/api/client'
import {
  useAgentLauncher,
  useAgentRequests,
  useAgentRuns,
  useCancelAgentRequest,
  useCancelAgentRun,
  useOpenAgentRun,
} from '@/api/queries'
import { AgentButton } from '@/components/AgentButton'
import { ErrorState } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { APP_TIME_ZONE, formatWhen } from '@/lib/time'
import { cn } from '@/lib/utils'

type RunStatus = AgentRunView['status']

const STATUS: Record<RunStatus, { label: string; className: string }> = {
  queued: { label: 'En cola', className: 'bg-foreground/[0.06] text-foreground/80' },
  running: { label: 'En curso', className: 'bg-primary/10 text-primary' },
  done: { label: 'Terminada', className: 'bg-foreground/[0.06] text-foreground/80' },
  needs_user: { label: 'Necesita tu respuesta', className: 'bg-warning text-warning-foreground' },
  failed: { label: 'Fallida', className: 'bg-destructive/10 text-destructive' },
  cancelled: { label: 'Cancelada', className: 'bg-foreground/[0.06] text-muted-foreground' },
  timeout: { label: 'Tiempo agotado', className: 'bg-destructive/10 text-destructive' },
}
// Si lleva esto en cola sin que nada corra, lo más probable es que el worker no esté arrancado.
const STUCK_MS = 30_000
const PROGRESS_PREVIEW = 8

function duration(run: AgentRunView): string | null {
  if (!run.started_at) return null
  const end = run.finished_at ? new Date(run.finished_at) : new Date()
  const seconds = Math.max(0, Math.round((end.getTime() - new Date(run.started_at).getTime()) / 1000))
  return seconds < 60 ? `${seconds} s` : `${Math.floor(seconds / 60)} min ${seconds % 60} s`
}

function StatusBadge({ status }: { status: RunStatus }) {
  const meta = STATUS[status]
  return (
    <span className={cn('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium', meta.className)}>
      {status === 'running' && <CircleNotchIcon className="size-3 animate-spin" weight="bold" />}
      {meta.label}
    </span>
  )
}

function Target({ jobId }: { jobId: number | null }) {
  if (!jobId) return null
  return (
    <Link to={`/jobs/${jobId}`} className="text-sm text-muted-foreground underline-offset-4 hover:underline">
      oferta {jobId}
    </Link>
  )
}

function RunCard({ run }: { run: AgentRunView }) {
  const cancel = useCancelAgentRun()
  const open = useOpenAgentRun()
  const [all, setAll] = useState(false)
  const active = run.status === 'queued' || run.status === 'running'
  const lines = all ? run.progress : run.progress.slice(-PROGRESS_PREVIEW)
  const took = duration(run)
  const error = cancel.error ?? open.error

  return (
    <li className="rounded-xl border bg-card p-4">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <h3 className="font-medium">{run.label}</h3>
        <Target jobId={run.job_id} />
        <StatusBadge status={run.status} />
        <span className="ml-auto text-xs text-muted-foreground tabular">
          {formatWhen(run.created_at)}
          {took && ` · ${took}`}
        </span>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        Solo con: <span className="font-mono">{run.allowed_tools.join(', ')}</span>
      </p>

      {run.questions.length > 0 && (
        <div className="mt-3 rounded-lg border border-warning-border bg-warning px-3 py-2.5 text-sm text-warning-foreground">
          <p className="flex items-center gap-2 font-medium">
            <ChatCircleDotsIcon className="size-4" weight="duotone" />
            Tu agente necesita que le contestes:
          </p>
          <ul className="mt-1.5 list-disc space-y-1 pl-6">
            {run.questions.map((q, i) => (
              <li key={i}>{q}</li>
            ))}
          </ul>
        </div>
      )}

      {run.error && (
        <p role="alert" className="mt-3 text-sm text-destructive">
          {run.error}
        </p>
      )}

      {run.result && (
        <details className="mt-3 group" open={run.status === 'done'}>
          <summary className="cursor-pointer text-xs font-medium tracking-wide text-muted-foreground uppercase">
            Resultado
          </summary>
          <pre className="mt-2 max-h-80 overflow-auto rounded-lg border bg-background p-3 font-sans text-sm leading-relaxed whitespace-pre-wrap">
            {run.result}
          </pre>
        </details>
      )}

      {lines.length > 0 && (
        <div className="mt-3">
          <h4 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">Progreso</h4>
          <ol className="mt-1.5 space-y-0.5 font-mono text-xs" aria-label={`Progreso de ${run.label}`}>
            {lines.map((line, i) => (
              <li
                key={i}
                className={cn(
                  'flex gap-2',
                  line.kind === 'error' && 'text-destructive',
                  line.kind === 'text' && 'font-sans text-foreground/80',
                  line.kind === 'tool' && 'text-foreground/70',
                  line.kind === 'info' && 'text-muted-foreground',
                )}
              >
                <span className="shrink-0 text-muted-foreground/70 tabular">
                  {new Date(line.at).toLocaleTimeString('es-ES', { timeZone: APP_TIME_ZONE })}
                </span>
                <span className="min-w-0 break-words">{line.text}</span>
              </li>
            ))}
          </ol>
          {run.progress.length > PROGRESS_PREVIEW && (
            <button
              type="button"
              onClick={() => setAll((v) => !v)}
              className="mt-1 text-xs text-muted-foreground underline underline-offset-4"
            >
              {all ? 'Ver solo lo último' : `Ver las ${run.progress.length} líneas`}
            </button>
          )}
        </div>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {active && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => cancel.mutate(run.id)}
            disabled={cancel.isPending || run.cancel_requested}
          >
            <XIcon />
            {run.cancel_requested ? 'Cancelando…' : 'Cancelar'}
          </Button>
        )}
        {!active && (
          <Button
            variant={run.status === 'needs_user' ? 'default' : 'outline'}
            size="sm"
            onClick={() => open.mutate(run.id)}
            disabled={open.isPending}
            title={run.can_resume ? 'Sigue la misma sesión en una terminal' : 'Abre la orden en una terminal'}
          >
            <TerminalWindowIcon weight="duotone" />
            {run.status === 'needs_user' ? 'Contestar en terminal' : 'Abrir en terminal'}
          </Button>
        )}
        {open.data && <span className="text-xs text-muted-foreground">{open.data.message}</span>}
        {error && <span className="text-xs text-destructive">{error.message}</span>}
      </div>
    </li>
  )
}

function Runs() {
  // `dataUpdatedAt`: la hora de la última consulta (se repite cada pocos segundos con algo en cola).
  const { data, dataUpdatedAt, isPending, isError, error, refetch } = useAgentRuns()
  const launcher = useAgentLauncher()
  const background = launcher.data?.background

  if (isPending) return <Skeleton className="h-40" />
  if (isError) return <ErrorState error={error} onRetry={() => void refetch()} />
  const running = data.runs.some((r) => r.status === 'running')
  const stuck =
    !running &&
    data.runs.some((r) => r.status === 'queued' && dataUpdatedAt - new Date(r.created_at).getTime() > STUCK_MS)
  return (
    <div className="space-y-3">
      {background && !background.available && (
        <p className="rounded-xl border bg-card px-4 py-3 text-sm text-muted-foreground">
          En segundo plano no está disponible: {background.reason}
        </p>
      )}
      {stuck && (
        <p
          role="status"
          className="rounded-xl border border-warning-border bg-warning px-4 py-3 text-sm text-warning-foreground"
        >
          Hay ejecuciones en cola desde hace rato y ninguna en curso. Las lanza el worker: ¿está{' '}
          <code className="font-mono">cai worker</code> en marcha?
        </p>
      )}
      {data.runs.length === 0 ? (
        <p className="rounded-xl border border-dashed px-4 py-6 text-center text-sm text-muted-foreground">
          Aún no has lanzado nada en segundo plano. En los botones de «Procesar ofertas», «Evaluar encaje» y «Generar
          CV», el desplegable ofrece «En segundo plano».
        </p>
      ) : (
        <ul className="space-y-3">
          {data.runs.map((run) => (
            <RunCard key={run.id} run={run} />
          ))}
        </ul>
      )}
    </div>
  )
}

function RequestRow({ request }: { request: AgentRequestView }) {
  const cancel = useCancelAgentRequest()
  const pending = request.status === 'pending'
  return (
    <li className="flex flex-wrap items-start gap-x-3 gap-y-1 rounded-lg border bg-card px-4 py-3">
      <div className="min-w-0 flex-1">
        <p className="flex flex-wrap items-center gap-x-3">
          <span className="font-medium">{request.label}</span>
          <Target jobId={request.job_id} />
          <span className="text-xs text-muted-foreground tabular">{formatWhen(request.created_at)}</span>
        </p>
        {pending ? (
          <p className="mt-0.5 text-sm text-muted-foreground">{request.prompt}</p>
        ) : (
          <p className="mt-0.5 text-sm text-muted-foreground">
            {request.status === 'done' ? (request.summary ?? 'Hecho.') : 'Cancelado.'}
            {request.agent_name && ` · ${request.agent_name}`}
          </p>
        )}
        {cancel.error && <p className="mt-1 text-xs text-destructive">{cancel.error.message}</p>}
      </div>
      {pending && (
        <Button variant="ghost" size="sm" onClick={() => cancel.mutate(request.id)} disabled={cancel.isPending}>
          <XIcon />
          Quitar
        </Button>
      )}
    </li>
  )
}

function Requests() {
  const { data, isPending, isError, error, refetch } = useAgentRequests()
  if (isPending) return <Skeleton className="h-24" />
  if (isError) return <ErrorState error={error} onRetry={() => void refetch()} />
  const pending = data.requests.filter((r) => r.status === 'pending').reverse()
  const closed = data.requests.filter((r) => r.status !== 'pending').slice(0, 10)
  return (
    <div className="space-y-4">
      {pending.length === 0 ? (
        <p className="rounded-xl border border-dashed px-4 py-6 text-center text-sm text-muted-foreground">
          No hay encargos. En cualquier botón del agente, el desplegable ofrece «Dejar para mi próxima sesión».
        </p>
      ) : (
        <>
          <ul className="space-y-2" aria-label="Encargos pendientes">
            {pending.map((r) => (
              <RequestRow key={r.id} request={r} />
            ))}
          </ul>
          <AgentButton action="handle-requests" variant="default">
            Atender encargos
          </AgentButton>
        </>
      )}
      {closed.length > 0 && (
        <details>
          <summary className="cursor-pointer text-xs font-medium tracking-wide text-muted-foreground uppercase">
            Cerrados recientemente
          </summary>
          <ul className="mt-2 space-y-2">
            {closed.map((r) => (
              <RequestRow key={r.id} request={r} />
            ))}
          </ul>
        </details>
      )}
    </div>
  )
}

export function AgentPage() {
  return (
    <div className="animate-in fade-in duration-300">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">Agente</h1>
        <p className="max-w-prose text-sm text-muted-foreground">
          Lo que tu agente hace en segundo plano y lo que le has dejado para tu próxima sesión. Sin coste de API: usa tu
          suscripción, de una ejecución en una.
        </p>
      </div>
      <div className="grid gap-8 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <section aria-labelledby="runs-title">
          <h2 id="runs-title" className="mb-3 flex items-center gap-2 text-lg font-semibold tracking-tight">
            <CircleNotchIcon className="size-5 text-muted-foreground" weight="duotone" />
            En segundo plano
          </h2>
          <Runs />
        </section>
        <section aria-labelledby="requests-title">
          <h2 id="requests-title" className="mb-3 flex items-center gap-2 text-lg font-semibold tracking-tight">
            <ClockCountdownIcon className="size-5 text-muted-foreground" weight="duotone" />
            Para tu próxima sesión
          </h2>
          <Requests />
        </section>
      </div>
    </div>
  )
}
