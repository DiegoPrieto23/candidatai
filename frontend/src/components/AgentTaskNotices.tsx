import { useCallback, useEffect, useId, useRef, useState } from 'react'
import { Link } from 'react-router'
import { useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { ChatsCircleIcon, CheckCircleIcon, CircleNotchIcon, MinusIcon, WarningIcon, XIcon } from '@phosphor-icons/react'
import type { AgentTaskView } from '@/api/client'
import {
  keys,
  useAgentTasks,
  useCancelAgentRun,
  useDismissAgentTask,
  useOpenAgentRun,
  type AgentAction,
} from '@/api/queries'
import { AgentRunPanel } from '@/components/AgentRunPanel'
import { Elapsed, StepBar } from '@/components/agentTaskParts'
import { resultLink, stepText, toolLabel } from '@/lib/agentTasks'
import { Button } from '@/components/ui/button'
import { errorMessage } from '@/lib/errors'
import { notifyIfHidden } from '@/lib/notify'
import { WATCHED_ACTIONS } from '@/lib/readyWatch'
import { cn } from '@/lib/utils'

function Progress({ done, total }: { done: number; total: number }) {
  return (
    <span aria-hidden className="mt-2 block h-1 overflow-hidden rounded-sm bg-foreground/10">
      <span className="block h-full bg-primary transition-[width] duration-300" style={{ width: `${Math.round((done / total) * 100)}%` }} />
    </span>
  )
}

/** «Detener» con una confirmación corta en el sitio (nada de diálogos del navegador). */
function StopControl({ task, className }: { task: AgentTaskView; className?: string }) {
  const { t } = useTranslation('nav', { keyPrefix: 'tasks' })
  const cancel = useCancelAgentRun()
  const [confirming, setConfirming] = useState(false)
  const confirmId = useId()
  const stopButton = useRef<HTMLButtonElement>(null)
  if (task.status !== 'running' || task.run_id == null || task.stopping) return null
  const runId = task.run_id
  if (!confirming) {
    return (
      <div className={className}>
        <Button
          ref={stopButton}
          size="sm"
          variant="outline"
          onClick={() => {
            cancel.reset()
            setConfirming(true)
          }}
        >
          {t('stop')}
        </Button>
      </div>
    )
  }
  const keepGoing = () => {
    setConfirming(false)
    // El foco vuelve a «Detener», que reaparece al cerrar la confirmación.
    requestAnimationFrame(() => stopButton.current?.focus())
  }
  return (
    <div role="group" aria-labelledby={confirmId} className={cn('space-y-2', className)}>
      <p id={confirmId} className="text-xs">
        {t('stopConfirm')}
      </p>
      {cancel.isError && (
        <p role="alert" className="text-xs text-destructive">
          {t('stopFailed')}
        </p>
      )}
      <div className="flex gap-2">
        <Button
          size="sm"
          variant="destructive"
          disabled={cancel.isPending}
          onClick={() => cancel.mutate(runId, { onSuccess: () => setConfirming(false) })}
        >
          {t('stopYes')}
        </Button>
        {/* El botón seguro recibe el foco al abrirse la confirmación. */}
        <Button size="sm" variant="outline" autoFocus onClick={keepGoing}>
          {t('stopNo')}
        </Button>
      </div>
    </div>
  )
}

/** «Abrir en una ventana» de una ejecución sin ventana que falló o se quedó con una pregunta. */
function OpenInWindow({ runId }: { runId: number }) {
  const { t } = useTranslation('nav', { keyPrefix: 'tasks' })
  const open = useOpenAgentRun()
  return (
    <>
      <Button size="sm" variant="outline" disabled={open.isPending} onClick={() => open.mutate(runId)}>
        {t('openWindow')}
      </Button>
      {open.isError && (
        <p role="alert" className="basis-full text-xs text-destructive">
          {errorMessage(open.error)}
        </p>
      )}
    </>
  )
}

function TaskNotice({
  task,
  panelOpen,
  onConversation,
}: {
  task: AgentTaskView
  panelOpen: boolean
  onConversation: () => void
}) {
  const { t } = useTranslation('nav', { keyPrefix: 'tasks' })
  const dismiss = useDismissAgentTask()
  const client = useQueryClient()
  const [minimized, setMinimized] = useState<string | null>(null)

  const running = task.status === 'running'
  const good = task.status === 'finished' && task.outcome === 'done'
  // Fase 47.4: la detuvo el usuario; no es que el agente haya parado por su cuenta.
  const ending = task.status === 'finished' && task.stopped_by_user ? 'cancelled' : (task.outcome ?? 'stopped')
  const name = (kind: 'running' | 'done') => t(`actions.${task.action}.${kind}` as never)
  const title =
    running && task.stopping
      ? t('stopping')
      : running || task.status === 'stale'
        ? name('running')
        : good
          ? name('done')
          : t(`${ending}.title` as never, { action: name('running') })
  const state = `${task.status}:${task.outcome}`

  // Lo que el agente va guardando se ve sin recargar: la bandeja, los recuentos, la ficha.
  const progress = `${task.status}:${task.done}`
  const previous = useRef(progress)
  useEffect(() => {
    if (progress === previous.current) return
    previous.current = progress
    void client.invalidateQueries({ predicate: (q) => q.queryKey[0] !== keys.agent[0] })
  }, [progress, client])

  // Solo se avisa de lo que has visto en marcha, no de un aviso antiguo al abrir la app.
  const wasRunning = useRef(running)
  useEffect(() => {
    if (running) {
      wasRunning.current = true
    } else if (wasRunning.current && task.status === 'finished') {
      wasRunning.current = false
      notifyIfHidden(title, task.subject ?? t('notification'))
    }
  }, [running, task.status, task.subject, title, t])

  // El CV y la guía tienen su propio aviso («Tu CV está listo»), con el PDF a un clic. Con el panel
  // abierto se queda: lo que pasó se sigue leyendo ahí.
  const handedOver = good && WATCHED_ACTIONS[task.action as AgentAction] !== undefined && !panelOpen
  const { mutate: close } = dismiss
  useEffect(() => {
    if (handedOver) close(task.id)
  }, [handedOver, close, task.id])
  if (handedOver) return null

  const icon = running ? (
    <CircleNotchIcon className="size-4 shrink-0 animate-spin text-primary" weight="bold" aria-hidden />
  ) : good ? (
    <CheckCircleIcon className="size-4 shrink-0 text-primary" weight="fill" aria-hidden />
  ) : (
    <WarningIcon className="size-4 shrink-0 text-warning-foreground" weight="fill" aria-hidden />
  )
  const counted = task.total > 0
  const stepped = task.steps.length > 0
  const step = stepText(t, task.steps)

  if (minimized === state) {
    return (
      <button
        type="button"
        onClick={() => setMinimized(null)}
        aria-label={t('expand', { title })}
        className="pointer-events-auto inline-flex items-center gap-2 rounded-lg border bg-card px-3 py-2 text-sm font-medium shadow-lg outline-none transition-colors hover:bg-foreground/[0.03] focus-visible:ring-2 focus-visible:ring-ring"
      >
        {icon}
        {title}
        {running && (counted || step) && (
          <span className="tabular text-xs font-normal text-muted-foreground">
            {counted ? `${task.done}/${task.total}` : step}
          </span>
        )}
      </button>
    )
  }

  // Sin ventana, el aviso dice qué hace ahora: el paso o, sin pasos, la última herramienta.
  const now = task.last_tool ? toolLabel(t, task.last_tool) : null
  let body: string
  if (running && task.stopping) body = t('stoppingBody')
  else if (running && task.background) body = (stepped ? step : now) ?? t('runningBackground')
  else if (running) body = t('runningTerminal')
  else if (task.status === 'stale') body = t('stale')
  else if (good) body = counted ? t('doneCount', { count: task.done }) : t('doneBody')
  else body = t(`${ending}.body` as never)

  const inTerminal = running && task.run_id == null
  const conversation = task.run_id != null
  const failedRun = task.run_id != null && task.status === 'finished' && (task.outcome === 'failed' || task.outcome === 'needs_user')
  const to = good ? resultLink(task) : null
  return (
    <div
      role="status"
      className="pointer-events-auto flex w-80 max-w-[calc(100vw-2rem)] items-start gap-3 rounded-lg border bg-card p-3 text-sm shadow-lg animate-in fade-in slide-in-from-bottom-1 duration-200"
    >
      <span className="mt-0.5">{icon}</span>
      <div className="min-w-0 flex-1">
        <p className="font-medium">{title}</p>
        {task.subject && <p className="truncate text-muted-foreground">{task.subject}</p>}
        <p className={cn('text-muted-foreground', task.subject && 'mt-1 text-xs')}>{body}</p>
        {running && counted && (
          <>
            <Progress done={task.done} total={task.total} />
            <p className="tabular mt-1.5 text-xs text-muted-foreground">{t('counts', { done: task.done, total: task.total })}</p>
          </>
        )}
        {(running || good) && !counted && stepped && (
          <div className="mt-2">
            <StepBar steps={task.steps} />
          </div>
        )}
        {task.background && (running || task.status === 'finished') && (
          <p className="mt-1.5 text-xs text-muted-foreground">
            <Elapsed from={task.started_at} until={task.finished_at} />
          </p>
        )}
        {(to || conversation || failedRun) && (
          <div className="mt-2.5 flex flex-wrap gap-2">
            {to && (
              <Button asChild size="sm" variant="outline" onClick={() => dismiss.mutate(task.id)}>
                <Link to={to}>{t('see')}</Link>
              </Button>
            )}
            {conversation && (
              <Button size="sm" variant="outline" aria-expanded={panelOpen} onClick={onConversation}>
                <ChatsCircleIcon />
                {t('conversation')}
              </Button>
            )}
            {failedRun && task.run_id != null && <OpenInWindow runId={task.run_id} />}
          </div>
        )}
        {/* Con el panel abierto, «Detener» está en su cabecera. */}
        {!panelOpen && <StopControl task={task} className="mt-2.5" />}
        {inTerminal && (
          <div className="mt-2.5 space-y-2">
            <p className="text-xs text-muted-foreground">{t('terminalStop')}</p>
            <Button size="sm" variant="outline" disabled={dismiss.isPending} onClick={() => dismiss.mutate(task.id)}>
              {t('markDone')}
            </Button>
          </div>
        )}
      </div>
      <div className="-mt-1 -mr-1 flex shrink-0">
        <Button variant="ghost" size="icon" className="size-7" aria-label={t('minimize')} onClick={() => setMinimized(state)}>
          <MinusIcon />
        </Button>
        <Button variant="ghost" size="icon" className="size-7" aria-label={t('close')} disabled={dismiss.isPending} onClick={() => dismiss.mutate(task.id)}>
          <XIcon />
        </Button>
      </div>
    </div>
  )
}

/**
 * «Leyendo ofertas…», «Generando el CV…» mientras tu agente trabaja en lo que lanzó un botón, en
 * cualquier página. Cambia cuando guarda el resultado o dice que no ha podido y se queda hasta que
 * lo cierras: puede acabar cuando no estás mirando. Cerrarlo no para al agente. Sin ventana (fase
 * 48.1a), dice el paso en curso y abre el panel con la conversación.
 */
export function AgentTaskNotices() {
  const tasks = useAgentTasks().data?.tasks ?? []
  const [panelTask, setPanelTask] = useState<number | null>(null)
  const shown = tasks.find((task) => task.id === panelTask && task.run_id != null)
  const closePanel = useCallback(() => setPanelTask(null), [])
  return (
    <>
      {tasks.map((task) => (
        <TaskNotice
          key={task.id}
          task={task}
          panelOpen={shown?.id === task.id}
          onConversation={() => setPanelTask(shown?.id === task.id ? null : task.id)}
        />
      ))}
      {shown && <AgentRunPanel task={shown} onClose={closePanel} stop={<StopControl task={shown} />} />}
    </>
  )
}
