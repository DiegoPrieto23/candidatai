import { useEffect, useId, useRef, useState } from 'react'
import { Link } from 'react-router'
import { useTranslation } from 'react-i18next'
import { ArrowRightIcon, CircleNotchIcon } from '@phosphor-icons/react'
import type { AssistantView } from '@/api/client'
import {
  useAgentLauncher,
  useAskAssistant,
  useAssistantRequests,
  useCancelAssistantRequest,
  usePendingPrompts,
} from '@/api/queries'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { errorMessage } from '@/lib/errors'
import { HELP_SCREENS } from '@/lib/helpSearch'
import { cn } from '@/lib/utils'

/** El mismo tope que aplica el servidor (y que la corrección de un CV). */
const ASSISTANT_MAX_CHARS = 2000

const ACTIVE: AssistantView['status'][] = ['queued', 'running']
/** Ejemplos para la primera vez: una pulsación los escribe en la caja, sin enviarlos. */
const SUGGESTIONS = ['pending', 'reviewFirst', 'noReply', 'howItGoes'] as const
const linkClass =
  'inline-flex items-center gap-1 rounded-sm text-sm font-medium text-primary underline-offset-4 outline-none hover:underline focus-visible:ring-[3px] focus-visible:ring-ring/50'

function RequestCard({ request, asking, onGo }: { request: AssistantView; asking: boolean; onGo: () => void }) {
  const { t, i18n } = useTranslation('help')
  const cancel = useCancelAssistantRequest()
  const active = ACTIVE.includes(request.status)
  const open = active || request.status === 'waiting'
  const lastStep = request.progress.at(-1)?.text
  const when = new Intl.DateTimeFormat(i18n.language, { dateStyle: 'short', timeStyle: 'short' }).format(
    new Date(request.created_at),
  )

  return (
    <li className="border-b py-3 last:border-b-0">
      <p className="text-xs text-muted-foreground">{t('assistant.asked', { when })}</p>
      <p className="mt-0.5 text-sm font-medium text-pretty whitespace-pre-wrap">{request.text}</p>

      <div className="mt-2 text-sm text-pretty text-muted-foreground" aria-live="polite">
        {open && (
          <p className="flex items-center gap-1.5">
            {active && <CircleNotchIcon className="size-3.5 shrink-0 animate-spin" weight="bold" aria-hidden />}
            <span>
              {asking && active ? t('assistant.status.asking') : t(`assistant.status.${request.status}` as never)}
              {active && !asking && lastStep ? ` · ${lastStep}` : ''}
            </span>
          </p>
        )}
        {request.status === 'cancelled' && <p>{t('assistant.status.cancelled')}</p>}
        {request.status === 'failed' && (
          <p className="text-destructive">
            {t('assistant.status.failed')}
            {request.error ? ` ${request.error}` : ''}
          </p>
        )}
        {request.answer && <p className="whitespace-pre-wrap text-foreground">{request.answer}</p>}
        {request.status === 'done' && !request.answer && <p>{t('assistant.noAnswer')}</p>}
        {request.questions.length > 0 && (
          <ul className="mt-1 list-disc pl-4">
            {request.questions.map((question) => (
              <li key={question}>{question}</li>
            ))}
          </ul>
        )}
      </div>

      {request.links.length > 0 && (
        <ul className="mt-2 grid gap-1">
          {request.links.map((link, index) => {
            const to = link.job_id ? `/jobs/${link.job_id}` : link.screen ? HELP_SCREENS[link.screen] : undefined
            if (!to) return null
            const label = link.job_id
              ? (link.label ?? t('assistant.jobLink', { id: link.job_id }))
              : t('goTo', { screen: t(`screens.${link.screen}` as never) })
            return (
              <li key={`${to}-${index}`}>
                <Link to={to} onClick={onGo} className={linkClass}>
                  {label}
                  <ArrowRightIcon className="size-3.5" weight="bold" aria-hidden />
                </Link>
              </li>
            )
          })}
        </ul>
      )}

      {open && (
        <Button
          variant="ghost"
          size="sm"
          className="mt-1.5 -ml-2 h-7 px-2 text-xs"
          disabled={cancel.isPending}
          onClick={() => cancel.mutate(request.id)}
        >
          {t('assistant.cancel')}
        </Button>
      )}
      {cancel.isError && <p className="mt-1 text-xs text-destructive">{errorMessage(cancel.error)}</p>}
    </li>
  )
}

/**
 * «Asistente»: lo que escribes se guarda en la app y se lo pasa a tu agente, ahora en
 * segundo plano o como encargo para tu próxima sesión. La app no llama a ningún modelo. Debajo,
 * las últimas peticiones con su progreso, su respuesta y enlaces a lo que ha cambiado.
 */
export function AssistantTab({ onGo }: { onGo: () => void }) {
  const { t } = useTranslation('help')
  const [text, setText] = useState('')
  const field = useRef<HTMLTextAreaElement>(null)
  const hintId = useId()
  const launcher = useAgentLauncher()
  const requests = useAssistantRequests()
  const prompts = usePendingPrompts()
  const ask = useAskAssistant()

  useEffect(() => {
    field.current?.focus()
  }, [])

  const action = launcher.data?.actions.find((item) => item.id === 'assistant')
  const noAgent = launcher.data?.no_agent_installed ?? false
  const background = action?.background_agent
  const canRunNow = background?.available ?? false
  const asking = (prompts.data?.prompts ?? []).some((prompt) => prompt.kind === 'question')
  const trimmed = text.trim()
  const ready = trimmed.length > 0 && !ask.isPending

  const send = (mode: 'background' | 'session') => {
    if (!ready) return
    ask.mutate({ text: trimmed, mode }, { onSuccess: () => setText('') })
  }

  if (noAgent) {
    return (
      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4 text-sm text-pretty">
        <p className="font-medium">{t('assistant.noAgentTitle')}</p>
        <p className="mt-1 text-muted-foreground">{t('assistant.noAgentBody')}</p>
        <Link to={HELP_SCREENS.agent!} onClick={onGo} className={cn(linkClass, 'mt-2')}>
          {t('goTo', { screen: t('screens.agent') })}
          <ArrowRightIcon className="size-3.5" weight="bold" aria-hidden />
        </Link>
      </div>
    )
  }

  const list = requests.data?.requests ?? []
  return (
    <>
      <form className="border-b px-4 py-3" onSubmit={(event) => event.preventDefault()}>
        <Textarea
          ref={field}
          value={text}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => {
            if (event.key !== 'Enter' || !(event.ctrlKey || event.metaKey)) return
            event.preventDefault()
            send(canRunNow ? 'background' : 'session')
          }}
          maxLength={ASSISTANT_MAX_CHARS}
          rows={3}
          aria-label={t('assistant.label')}
          aria-describedby={hintId}
          placeholder={t('assistant.placeholder')}
          className="resize-none"
        />
        <p id={hintId} className="mt-1.5 text-xs text-pretty text-muted-foreground">
          {t('assistant.hint')}
          {text.length > ASSISTANT_MAX_CHARS - 200 && ` ${t('assistant.left', { count: ASSISTANT_MAX_CHARS - text.length })}`}
        </p>
        <div className="mt-2 flex flex-wrap gap-2">
          <Button type="button" size="sm" disabled={!ready || !canRunNow} onClick={() => send('background')}>
            {t('assistant.sendNow')}
          </Button>
          <Button type="button" size="sm" variant="outline" disabled={!ready} onClick={() => send('session')}>
            {t('assistant.sendLater')}
          </Button>
        </div>
        {launcher.data && !canRunNow && (
          <p className="mt-1.5 text-xs text-pretty text-muted-foreground">{t('assistant.noBackground')}</p>
        )}
        {ask.isError && (
          <p role="alert" className="mt-1.5 text-xs text-destructive">
            {errorMessage(ask.error)}
          </p>
        )}
      </form>
      <div className="min-h-0 flex-1 overflow-y-auto px-4">
        {list.length === 0 ? (
          <section aria-label={t('assistant.suggestionsLabel')} className="py-3">
            <p className="text-sm text-pretty text-muted-foreground">{t('assistant.empty')}</p>
            <ul className="mt-2.5 flex flex-col items-start gap-1.5">
              {SUGGESTIONS.map((key) => {
                const suggestion = t(`assistant.suggestions.${key}`)
                return (
                  <li key={key}>
                    <button
                      type="button"
                      onClick={() => {
                        // Solo la escribe: enviarla sigue siendo cosa tuya.
                        setText(suggestion)
                        field.current?.focus()
                      }}
                      className="rounded-full border bg-background px-3 py-1 text-left text-sm text-pretty outline-none hover:border-primary/40 hover:bg-accent focus-visible:ring-[3px] focus-visible:ring-ring/50"
                    >
                      {suggestion}
                    </button>
                  </li>
                )
              })}
            </ul>
          </section>
        ) : (
          <section aria-label={t('assistant.history')}>
            <ul>
              {list.map((request) => (
                <RequestCard key={request.id} request={request} asking={asking} onGo={onGo} />
              ))}
            </ul>
          </section>
        )}
      </div>
    </>
  )
}
