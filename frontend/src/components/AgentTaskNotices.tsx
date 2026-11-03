import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'
import { useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { CheckCircleIcon, CircleNotchIcon, MinusIcon, WarningIcon, XIcon } from '@phosphor-icons/react'
import type { AgentTaskView } from '@/api/client'
import { keys, useAgentTasks, useDismissAgentTask, type AgentAction } from '@/api/queries'
import { Button } from '@/components/ui/button'
import { notifyIfHidden } from '@/lib/notify'
import { WATCHED_ACTIONS } from '@/lib/readyWatch'
import { cn } from '@/lib/utils'

/** Dónde se ve el resultado. Lo que es de una oferta va a su ficha, en la pestaña que toca. */
function resultLink(task: AgentTaskView): string | null {
  const action = task.action as AgentAction
  if (action === 'process-jobs') return '/bandeja'
  if (action === 'assess-fit') return '/bandeja/revision'
  if (action === 'review-replies') return '/respuestas'
  if (task.job_id === null) return null
  if (action === 'research-company') return `/jobs/${task.job_id}?tab=company`
  if (action === 'draft-message' || action === 'draft-follow-up') return `/jobs/${task.job_id}?tab=process`
  return `/jobs/${task.job_id}`
}

function Progress({ done, total }: { done: number; total: number }) {
  return (
    <span aria-hidden className="mt-2 block h-1 overflow-hidden rounded-sm bg-foreground/10">
      <span className="block h-full bg-primary transition-[width] duration-300" style={{ width: `${Math.round((done / total) * 100)}%` }} />
    </span>
  )
}

function TaskNotice({ task }: { task: AgentTaskView }) {
  const { t } = useTranslation('nav', { keyPrefix: 'tasks' })
  const dismiss = useDismissAgentTask()
  const client = useQueryClient()
  const [minimized, setMinimized] = useState<string | null>(null)

  const running = task.status === 'running'
  const good = task.status === 'finished' && task.outcome === 'done'
  const name = (kind: 'running' | 'done') => t(`actions.${task.action}.${kind}` as never)
  const title = running || task.status === 'stale' ? name('running') : good ? name('done') : t(`${task.outcome ?? 'stopped'}.title` as never, { action: name('running') })
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

  // El CV y la guía tienen su propio aviso («Tu CV está listo»), con el PDF a un clic.
  const handedOver = good && WATCHED_ACTIONS[task.action as AgentAction] !== undefined
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
        {running && counted && (
          <span className="tabular text-xs font-normal text-muted-foreground">
            {task.done}/{task.total}
          </span>
        )}
      </button>
    )
  }

  let body: string
  if (running) body = task.background ? t('runningBackground') : t('runningTerminal')
  else if (task.status === 'stale') body = t('stale')
  else if (good) body = counted ? t('doneCount', { count: task.done }) : t('doneBody')
  else body = t(`${task.outcome ?? 'stopped'}.body` as never)

  const to = good ? resultLink(task) : task.background && !running ? '/agente' : null
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
        {to && (
          <div className="mt-2.5">
            <Button asChild size="sm" variant="outline" onClick={() => dismiss.mutate(task.id)}>
              <Link to={to}>{good ? t('see') : t('seeAgent')}</Link>
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
 * lo cierras: puede acabar cuando no estás mirando. Cerrarlo no para al agente.
 */
export function AgentTaskNotices() {
  const tasks = useAgentTasks().data?.tasks ?? []
  return (
    <>
      {tasks.map((task) => (
        <TaskNotice key={task.id} task={task} />
      ))}
    </>
  )
}
