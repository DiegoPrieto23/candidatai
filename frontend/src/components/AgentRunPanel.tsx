import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Link } from 'react-router'
import { useTranslation } from 'react-i18next'
import { ArrowUpIcon, CaretRightIcon, CheckIcon, CircleNotchIcon, ProhibitIcon, WarningIcon } from '@phosphor-icons/react'
import type { AgentTaskView } from '@/api/client'
import {
  useAgentRunEvents,
  useAgentsOverview,
  useOpenAgentRun,
  useSendAgentMessage,
  type AgentRunEvent,
} from '@/api/queries'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'
import { errorMessage } from '@/lib/errors'
import { Elapsed, StepBar } from '@/components/agentTaskParts'
import { PromptCard } from '@/components/PromptCard'
import { PROMPT_TOOLS, mergeByTime, pairTools, resultLink, terminalLines, toolLabel } from '@/lib/agentTasks'

/** Lo que el panel necesita de una ejecución: desde su aviso o desde el historial de la ficha. */
export type PanelTarget = Pick<
  AgentTaskView,
  'action' | 'job_id' | 'subject' | 'agent' | 'started_at' | 'finished_at' | 'steps' | 'asks_permissions' | 'status' | 'outcome'
> & { run_id: number }

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

function EventRow({ event, target, first }: { event: AgentRunEvent; target: PanelTarget; first: boolean }) {
  const { t } = useTranslation('nav', { keyPrefix: 'tasks' })
  if (event.kind === 'system') {
    return (
      <li className="flex items-center gap-2 text-xs text-muted-foreground before:h-px before:flex-1 before:bg-border after:h-px after:flex-1 after:bg-border">
        {first ? t('panel.started') : t('panel.resumed')}
      </li>
    )
  }
  if (event.kind === 'user') {
    return (
      <li className="max-w-[85%] self-end rounded-lg rounded-br-sm bg-primary px-3 py-2 text-sm whitespace-pre-wrap break-words text-primary-foreground">
        {event.text}
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
    const to = event.ok ? resultLink(target) : null
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
  return null
}

/**
 * Escribirle al agente (fase 48.1c). Mientras trabaja, se le pasa con su siguiente herramienta;
 * al terminar, retoma la misma conversación. Si su agente no sabe retomarla sin ventana, se ofrece
 * abrirla en una ventana.
 */
function Compose({ runId, reply }: { runId: number; reply: 'live' | 'resume' | 'window' | 'none' }) {
  const { t } = useTranslation('nav', { keyPrefix: 'tasks.panel.compose' })
  const send = useSendAgentMessage(runId)
  const open = useOpenAgentRun()
  const [text, setText] = useState('')
  if (reply === 'none') return null
  if (reply === 'window') {
    return (
      <div className="space-y-2 border-t px-4 py-3">
        <p className="text-xs text-muted-foreground">{t('windowOnly')}</p>
        <Button size="sm" variant="outline" disabled={open.isPending} onClick={() => open.mutate(runId)}>
          {t('openWindow')}
        </Button>
        {open.isError && (
          <p role="alert" className="text-xs text-destructive">
            {errorMessage(open.error)}
          </p>
        )}
      </div>
    )
  }
  const submit = () => {
    const clean = text.trim()
    if (!clean) return
    send.mutate(clean, { onSuccess: () => setText('') })
  }
  return (
    <form
      className="space-y-1.5 border-t px-3 py-2.5"
      onSubmit={(event) => {
        event.preventDefault()
        submit()
      }}
    >
      <div className="flex items-end gap-1.5 rounded-lg border bg-background p-1.5 pl-2.5 focus-within:border-ring">
        <Textarea
          aria-label={t('label')}
          placeholder={reply === 'live' ? t('placeholderLive') : t('placeholderResume')}
          value={text}
          maxLength={2000}
          rows={1}
          className="min-h-0 flex-1 resize-none border-0 bg-transparent p-1 shadow-none focus-visible:ring-0"
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => {
            // Intro envía; Mayús+Intro, salto de línea.
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault()
              submit()
            }
          }}
        />
        <Button type="submit" size="icon" className="size-8 shrink-0" aria-label={t('send')} disabled={send.isPending || !text.trim()}>
          <ArrowUpIcon weight="bold" />
        </Button>
      </div>
      <p className="px-1 text-xs text-muted-foreground">{reply === 'live' ? t('hintLive') : t('hintResume')}</p>
      {send.isError && (
        <p role="alert" className="px-1 text-xs text-destructive">
          {errorMessage(send.error)}
        </p>
      )}
    </form>
  )
}

const STATUS_KEYS = ['queued', 'running', 'done', 'needs_user', 'failed', 'cancelled', 'timeout'] as const

/**
 * El panel lateral con la conversación de una ejecución sin ventana (fase 48.1a): los pasos, cada
 * herramienta que usa el agente y lo que escribe, sus preguntas y permisos (48.1b), lo que se le
 * escribe y la pestaña «Terminal» (48.1c). No es modal: la página se sigue usando y, en pantallas
 * anchas, se aparta para dejarle sitio.
 */
export function AgentRunPanel({
  target,
  onClose,
  stop,
}: {
  target: PanelTarget
  onClose: () => void
  /** El botón «Detener» del aviso, con su confirmación (sin aviso, no hay). */
  stop?: React.ReactNode
}) {
  const { t } = useTranslation('nav', { keyPrefix: 'tasks' })
  const titleId = useId()
  const [tab, setTab] = useState<'chat' | 'terminal'>('chat')
  const runId = target.run_id
  const events = useAgentRunEvents(runId)
  const agents = useAgentsOverview()
  const body = useRef<HTMLDivElement>(null)
  const heading = useRef<HTMLHeadingElement>(null)
  const stick = useRef(true)

  const list = events.data?.events ?? []
  const status = events.data?.status
  const live = status === 'queued' || status === 'running'
  // Las preguntas y los permisos, en su sitio de la conversación (por la hora). Las llamadas con que
  // el agente los hace no se pintan: la tarjeta ya lo dice.
  const items = pairTools(list).filter((item) => item.kind !== 'tool' || !PROMPT_TOOLS.has(item.start.tool ?? ''))
  const merged = mergeByTime(items, events.data?.prompts ?? [])
  const firstSystem = list.find((event) => event.kind === 'system')?.seq

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
  }, [list.length, tab])

  const agentName =
    agents.data?.agents.find((a) => a.name === target.agent)?.info.display_name ?? target.agent ?? ''
  const statusText = status && (STATUS_KEYS as readonly string[]).includes(status) ? t(`panel.status.${status}` as never) : ''
  const finishedOk = !live && (target.outcome === 'done' || status === 'done')
  const name = t(`actions.${target.action}.${finishedOk ? 'done' : 'running'}` as never)
  const tabs = [
    { id: 'chat', label: t('panel.conversation') },
    { id: 'terminal', label: t('panel.terminal') },
  ] as const

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
            {target.subject && <p className="truncate text-sm text-muted-foreground">{target.subject}</p>}
            <p className="tabular mt-0.5 text-xs text-muted-foreground">
              {[agentName, t('panel.noWindow'), statusText].filter(Boolean).join(' · ')}
              {' · '}
              <Elapsed from={target.started_at} until={live ? null : target.finished_at} />
            </p>
          </div>
          {stop}
          <Button variant="ghost" size="icon" className="size-8" aria-label={t('panel.collapse')} onClick={onClose}>
            <CaretRightIcon />
          </Button>
        </div>
        {target.steps.length > 0 && <StepBar steps={target.steps} labelled />}
        <div role="tablist" aria-label={t('panel.views')} className="flex gap-1">
          {tabs.map((item) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={tab === item.id}
              onClick={() => setTab(item.id)}
              className={cn(
                'rounded-md px-2.5 py-1 text-xs font-medium text-muted-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring',
                tab === item.id && 'bg-accent text-accent-foreground',
              )}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>
      <div
        ref={body}
        role="tabpanel"
        aria-label={tab === 'chat' ? t('panel.conversation') : t('panel.terminal')}
        onScroll={(event) => {
          const box = event.currentTarget
          stick.current = box.scrollHeight - box.scrollTop - box.clientHeight < 40
        }}
        className={cn(
          'min-h-0 flex-1 overflow-y-auto',
          tab === 'terminal' && 'bg-zinc-950 font-mono text-xs text-zinc-200 dark:bg-black',
        )}
      >
        {tab === 'chat' ? (
          <ol aria-live="polite" aria-label={t('panel.conversation')} className="flex flex-col gap-2.5 px-4 py-4">
            {events.isPending && <li className="text-sm text-muted-foreground">{t('panel.loading')}</li>}
            {!events.isPending && items.length === 0 && (
              <li className="text-sm text-muted-foreground">{live ? t('panel.waiting') : t('panel.empty')}</li>
            )}
            {merged.map((entry) =>
              entry.kind === 'prompt' ? (
                <PromptCard key={`p${entry.prompt.id}`} prompt={entry.prompt} />
              ) : entry.item.kind === 'tool' ? (
                <ToolRow key={entry.item.start.seq} start={entry.item.start} result={entry.item.result} live={live} />
              ) : (
                <EventRow
                  key={entry.item.event.seq}
                  event={entry.item.event}
                  target={target}
                  first={entry.item.event.seq === firstSystem}
                />
              ),
            )}
          </ol>
        ) : (
          // La misma conversación, tal cual y en orden, como en una consola. Solo lectura.
          <pre aria-label={t('panel.terminal')} className="px-3 py-3 whitespace-pre-wrap break-words">
            {terminalLines(t, list).map((line, index) => (
              <span key={index} className={cn('block', line.tone === 'dim' && 'text-zinc-400', line.tone === 'accent' && 'text-teal-300', line.tone === 'warn' && 'text-amber-300', line.tone === 'error' && 'text-red-400')}>
                {line.text}
              </span>
            ))}
          </pre>
        )}
      </div>
      {!target.asks_permissions && (
        <p className="border-t px-4 py-2 text-xs text-muted-foreground">{t('panel.noPermissions')}</p>
      )}
      {events.data && <Compose runId={runId} reply={events.data.reply} />}
    </aside>,
    document.body,
  )
}
