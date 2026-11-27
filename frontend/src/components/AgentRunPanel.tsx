import { useEffect, useId, useLayoutEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { Link } from 'react-router'
import { useTranslation } from 'react-i18next'
import { CaretRightIcon, CheckIcon, CircleNotchIcon, ProhibitIcon, WarningIcon } from '@phosphor-icons/react'
import type { AgentTaskView } from '@/api/client'
import { useAgentRunEvents, useAgentsOverview, type AgentRunEvent } from '@/api/queries'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { Elapsed, StepBar } from '@/components/agentTaskParts'
import { PromptCard } from '@/components/PromptCard'
import { PROMPT_TOOLS, mergeByTime, pairTools, resultLink, toolLabel } from '@/lib/agentTasks'

function ToolRow({ start, result, live }: { start: AgentRunEvent; result: AgentRunEvent | null; live: boolean }) {
  const { t } = useTranslation('nav', { keyPrefix: 'tasks' })
  const denied = result?.ok === false && result.text === 'denied'
  const icon = !result ? (
    live ? (
      <CircleNotchIcon className="size-4 animate-spin text-primary" weight="bold" aria-hidden />
    ) : (
      <span className="size-4" aria-hidden />
    )
  ) : result.ok ? (
    <CheckIcon className="size-4 text-primary" weight="bold" aria-hidden />
  ) : denied ? (
    <ProhibitIcon className="size-4 text-muted-foreground" weight="bold" aria-hidden />
  ) : (
    <WarningIcon className="size-4 text-warning-foreground" weight="fill" aria-hidden />
  )
  return (
    <li className={cn('flex items-start gap-2.5 text-sm', start.sub && 'pl-5')}>
      <span className="mt-0.5 shrink-0">{icon}</span>
      <span className="min-w-0 flex-1">
        <span className="break-words">{toolLabel(t, start.tool, start.text)}</span>{' '}
        <code className="rounded bg-accent px-1.5 py-px font-mono text-xs text-accent-foreground">{start.tool}</code>
        {start.sub && <span className="ml-1.5 text-xs text-muted-foreground">{t('panel.bySubagent')}</span>}
        {result && !result.ok && (
          <span className="block text-xs text-muted-foreground">{denied ? t('panel.denied') : t('panel.toolFailed')}</span>
        )}
      </span>
    </li>
  )
}

function EventRow({ event, task }: { event: AgentRunEvent; task: AgentTaskView }) {
  const { t } = useTranslation('nav', { keyPrefix: 'tasks' })
  if (event.kind === 'system') {
    return (
      <li className="flex items-center gap-2 text-xs text-muted-foreground before:h-px before:flex-1 before:bg-border after:h-px after:flex-1 after:bg-border">
        {t('panel.started')}
      </li>
    )
  }
  if (event.kind === 'text') {
    // Texto del agente: contenido no confiable, solo como texto plano.
    return (
      <li className="max-w-[92%] self-start rounded-lg rounded-bl-sm bg-muted px-3 py-2 text-sm whitespace-pre-wrap break-words">
        {event.text}
      </li>
    )
  }
  if (event.kind === 'result') {
    const to = event.ok ? resultLink(task) : null
    return (
      <li className="rounded-lg border p-3 text-sm">
        <p className="flex items-center gap-2 font-medium">
          {event.ok ? (
            <CheckIcon className="size-4 text-primary" weight="bold" aria-hidden />
          ) : (
            <WarningIcon className="size-4 text-warning-foreground" weight="fill" aria-hidden />
          )}
          {event.ok ? t('panel.finished') : t('panel.finishedWithError')}
        </p>
        {event.text && <p className="mt-2 whitespace-pre-wrap break-words text-muted-foreground">{event.text}</p>}
        {to && (
          <Button asChild size="sm" className="mt-3">
            <Link to={to}>{t('see')}</Link>
          </Button>
        )}
      </li>
    )
  }
  if (event.kind === 'error') {
    return (
      <li role="alert" className="rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm">
        <p className="font-medium text-destructive">{t('panel.error')}</p>
        {event.text && <p className="mt-1 whitespace-pre-wrap break-words">{event.text}</p>}
      </li>
    )
  }
  return null // `user`, `question` y `permission`: llegan con las 48.1b y 48.1c
}

const STATUS_KEYS = ['queued', 'running', 'done', 'needs_user', 'failed', 'cancelled', 'timeout'] as const

/**
 * El panel lateral con la conversación de una ejecución sin ventana (fase 48.1a): los pasos, cada
 * herramienta que usa el agente y lo que escribe. No es modal: la página se sigue usando y, en
 * pantallas anchas, se aparta para dejarle sitio.
 */
export function AgentRunPanel({
  task,
  onClose,
  stop,
}: {
  task: AgentTaskView
  onClose: () => void
  /** El botón «Detener» del aviso, con su confirmación. */
  stop: React.ReactNode
}) {
  const { t } = useTranslation('nav', { keyPrefix: 'tasks' })
  const titleId = useId()
  const runId = task.run_id ?? null
  const events = useAgentRunEvents(runId)
  const agents = useAgentsOverview()
  const body = useRef<HTMLOListElement>(null)
  const heading = useRef<HTMLHeadingElement>(null)
  const stick = useRef(true)

  const list = events.data?.events ?? []
  const status = events.data?.status
  const live = status === 'queued' || status === 'running'
  // Las preguntas y los permisos, en su sitio de la conversación (por la hora). Las llamadas con que
  // el agente los hace no se pintan: la tarjeta ya lo dice.
  const items = pairTools(list).filter((item) => item.kind !== 'tool' || !PROMPT_TOOLS.has(item.start.tool ?? ''))
  const merged = mergeByTime(items, events.data?.prompts ?? [])

  // En pantallas anchas la página se aparta (CSS con `data-agent-panel`).
  useEffect(() => {
    document.documentElement.dataset.agentPanel = 'open'
    return () => {
      delete document.documentElement.dataset.agentPanel
    }
  }, [])
  useEffect(() => heading.current?.focus(), [])
  useEffect(() => {
    const close = (event: KeyboardEvent) => {
      // Si Escape ya cerró otra cosa (un menú, un diálogo), el panel se queda.
      if (event.key === 'Escape' && !event.defaultPrevented) onClose()
    }
    window.addEventListener('keydown', close)
    return () => window.removeEventListener('keydown', close)
  }, [onClose])
  // Lo nuevo se ve sin bajar a mano, salvo que se haya subido a leer algo anterior.
  useLayoutEffect(() => {
    const box = body.current
    if (box && stick.current) box.scrollTop = box.scrollHeight
  }, [list.length])

  const agentName =
    agents.data?.agents.find((a) => a.name === task.agent)?.info.display_name ?? task.agent ?? ''
  const statusText = status && (STATUS_KEYS as readonly string[]).includes(status) ? t(`panel.status.${status}` as never) : ''
  const finishedOk = task.status === 'finished' && task.outcome === 'done'
  const name = t(`actions.${task.action}.${finishedOk ? 'done' : 'running'}` as never)

  return createPortal(
    <aside
      aria-labelledby={titleId}
      className="fixed inset-y-0 right-0 z-50 flex w-[27.5rem] max-w-full flex-col border-l bg-card shadow-2xl animate-in slide-in-from-right duration-200"
    >
      <div className="flex flex-col gap-3 border-b px-4 pt-3.5 pb-3">
        <div className="flex items-start gap-2">
          <div className="min-w-0 flex-1">
            <h2 id={titleId} ref={heading} tabIndex={-1} className="text-base leading-tight font-semibold outline-none">
              {name}
            </h2>
            {task.subject && <p className="truncate text-sm text-muted-foreground">{task.subject}</p>}
            <p className="tabular mt-0.5 text-xs text-muted-foreground">
              {[agentName, t('panel.noWindow'), statusText].filter(Boolean).join(' · ')}
              {' · '}
              <Elapsed from={task.started_at} until={task.finished_at} />
            </p>
          </div>
          {stop}
          <Button variant="ghost" size="icon" className="size-8" aria-label={t('panel.collapse')} onClick={onClose}>
            <CaretRightIcon />
          </Button>
        </div>
        {task.steps.length > 0 && <StepBar steps={task.steps} labelled />}
        <p className="text-xs font-medium text-muted-foreground">{t('panel.conversation')}</p>
      </div>
      <ol
        ref={body}
        aria-live="polite"
        aria-label={t('panel.conversation')}
        onScroll={(event) => {
          const box = event.currentTarget
          stick.current = box.scrollHeight - box.scrollTop - box.clientHeight < 40
        }}
        className="flex min-h-0 flex-1 flex-col gap-2.5 overflow-y-auto px-4 py-4"
      >
        {events.isPending && runId != null && <li className="text-sm text-muted-foreground">{t('panel.loading')}</li>}
        {!events.isPending && items.length === 0 && (
          <li className="text-sm text-muted-foreground">{live ? t('panel.waiting') : t('panel.empty')}</li>
        )}
        {merged.map((entry) =>
          entry.kind === 'prompt' ? (
            <PromptCard key={`p${entry.prompt.id}`} prompt={entry.prompt} />
          ) : entry.item.kind === 'tool' ? (
            <ToolRow key={entry.item.start.seq} start={entry.item.start} result={entry.item.result} live={live} />
          ) : (
            <EventRow key={entry.item.event.seq} event={entry.item.event} task={task} />
          ),
        )}
      </ol>
      {!task.asks_permissions && (
        <p className="border-t px-4 py-2.5 text-xs text-muted-foreground">{t('panel.noPermissions')}</p>
      )}
    </aside>,
    document.body,
  )
}
