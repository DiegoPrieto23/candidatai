import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { Link } from 'react-router'
import { useTranslation } from 'react-i18next'
import { ArrowRightIcon, ArrowUpIcon, CircleNotchIcon, SparkleIcon } from '@phosphor-icons/react'
import type { AssistantView } from '@/api/client'
import {
  useAgentLauncher,
  useAskAssistant,
  useAssistantConversation,
  useAssistantConversations,
  useCancelAssistantRequest,
  usePendingPrompts,
} from '@/api/queries'
import { Hint } from '@/components/Hint'
import { Button } from '@/components/ui/button'
import { errorMessage } from '@/lib/errors'
import { HELP_SCREENS } from '@/lib/helpSearch'
import { dateFormatter } from '@/lib/labels'
import { APP_TIME_ZONE, toLocalDateInput } from '@/lib/time'
import { cn } from '@/lib/utils'

/** El mismo tope que aplica el servidor (y que la corrección de un CV). */
const ASSISTANT_MAX_CHARS = 2000

const ACTIVE: AssistantView['status'][] = ['queued', 'running', 'terminal']
/** Ejemplos para la primera vez: una pulsación los escribe en la caja, sin enviarlos. */
const SUGGESTIONS = ['pending', 'reviewFirst', 'noReply', 'howItGoes'] as const
const linkClass =
  'inline-flex items-center gap-1 rounded-sm text-sm font-medium text-primary underline-offset-4 outline-none hover:underline focus-visible:ring-[3px] focus-visible:ring-ring/50'

const DAY = { timeZone: APP_TIME_ZONE, day: 'numeric', month: 'short' } as const
const DAY_YEAR = { ...DAY, year: 'numeric' } as const
const WHEN = { timeZone: APP_TIME_ZONE, dateStyle: 'medium', timeStyle: 'short' } as const

/** El separador de un día: «Hoy», «Ayer» o la fecha (con año si no es el actual). */
function useDayLabel() {
  const { t } = useTranslation('help')
  return (day: string, iso: string) => {
    const today = toLocalDateInput(new Date())
    if (day === today) return t('assistant.today')
    // Ayer, con días del calendario (sin restar 24 h, que falla el día del cambio de hora).
    const yesterday = new Date(`${today}T12:00:00Z`)
    yesterday.setUTCDate(yesterday.getUTCDate() - 1)
    if (day === yesterday.toISOString().slice(0, 10)) return t('assistant.yesterday')
    const sameYear = day.slice(0, 4) === today.slice(0, 4)
    return dateFormatter(sameYear ? DAY : DAY_YEAR).format(new Date(iso))
  }
}

/** Un turno: tu pregunta en una burbuja a la derecha y la respuesta del asistente a la izquierda. */
function Turn({ request, asking, onGo }: { request: AssistantView; asking: boolean; onGo: () => void }) {
  const { t } = useTranslation('help')
  const cancel = useCancelAssistantRequest()
  const active = ACTIVE.includes(request.status)
  const open = active || request.status === 'waiting'
  const lastStep = request.progress.at(-1)?.text
  const when = dateFormatter(WHEN).format(new Date(request.created_at))
  const links = request.links.flatMap((link) => {
    const to = link.job_id ? `/jobs/${link.job_id}` : link.screen ? HELP_SCREENS[link.screen] : undefined
    if (!to) return []
    const label = link.job_id
      ? (link.label ?? t('assistant.jobLink', { id: link.job_id }))
      : t('goTo', { screen: t(`screens.${link.screen}` as never) })
    return [{ to, label }]
  })

  return (
    <>
      <li aria-label={t('assistant.you')} className="flex justify-end">
        <span className="sr-only">{t('assistant.you')}: </span>
        <p
          title={when}
          className="max-w-[85%] rounded-2xl rounded-br-md bg-primary/12 px-3 py-2 text-sm text-pretty whitespace-pre-wrap text-foreground"
        >
          {request.text}
        </p>
      </li>
      <li aria-label={t('assistantTitle')} className="flex gap-2.5">
        <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-primary/12 text-primary">
          <SparkleIcon className="size-3.5" weight="fill" aria-hidden />
        </span>
        <div className="min-w-0 flex-1 text-sm text-pretty">
          <span className="sr-only">{t('assistantTitle')}: </span>
          {request.answer && <p className="whitespace-pre-wrap">{request.answer}</p>}
          {request.status === 'done' && !request.answer && (
            <p className="text-muted-foreground">{t('assistant.noAnswer')}</p>
          )}
          {request.questions.length > 0 && (
            <ul className="mt-1 list-disc pl-4 text-muted-foreground">
              {request.questions.map((question) => (
                <li key={question}>{question}</li>
              ))}
            </ul>
          )}
          {links.length > 0 && (
            <ul className="mt-2 grid gap-1">
              {links.map((link, index) => (
                <li key={`${link.to}-${index}`}>
                  <Link to={link.to} onClick={onGo} className={linkClass}>
                    {link.label}
                    <ArrowRightIcon className="size-3.5" weight="bold" aria-hidden />
                  </Link>
                </li>
              ))}
            </ul>
          )}

          {/* El estado, en una línea pequeña bajo la respuesta. */}
          {open && (
            <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
              {active && <CircleNotchIcon className="size-3.5 shrink-0 animate-spin" weight="bold" aria-hidden />}
              <span>
                {asking && active ? t('assistant.status.asking') : t(`assistant.status.${request.status}` as never)}
                {active && !asking && lastStep ? ` · ${lastStep}` : ''}
              </span>
              <Button
                variant="ghost"
                size="sm"
                className="ml-auto h-6 px-2 text-xs"
                disabled={cancel.isPending}
                onClick={() => cancel.mutate(request.id)}
              >
                {t('assistant.cancel')}
              </Button>
            </p>
          )}
          {request.status === 'cancelled' && (
            <p className="text-xs text-muted-foreground">{t('assistant.status.cancelled')}</p>
          )}
          {request.status === 'failed' && (
            <p className="text-xs text-destructive">
              {t('assistant.status.failed')}
              {request.error ? ` ${request.error}` : ''}
            </p>
          )}
          {cancel.isError && <p className="mt-1 text-xs text-destructive">{errorMessage(cancel.error)}</p>}
        </div>
      </li>
    </>
  )
}

/**
 * «Asistente», como un chat: lo que escribes se guarda en la app y se lo pasa a tu agente, en
 * segundo plano si puede trabajar así desde la app; si no, en una terminal a la vista; y si tampoco,
 * como encargo para tu próxima sesión.
 * La app no llama a ningún modelo. Arriba, los mensajes de la conversación abierta, por días; abajo,
 * la caja. `conversationId` en `null`: una conversación nueva, que se crea al enviar.
 */
export function AssistantTab({
  conversationId,
  onConversation,
  onAutoOpen,
  onGo,
}: {
  conversationId: number | null
  onConversation: (id: number | null) => void
  /** Lo que la app elige al abrir (lo ignora si ya has elegido tú). */
  onAutoOpen: (id: number | null) => void
  onGo: () => void
}) {
  const { t } = useTranslation('help')
  const [text, setText] = useState('')
  const field = useRef<HTMLTextAreaElement>(null)
  const scroller = useRef<HTMLDivElement>(null)
  const launcher = useAgentLauncher()
  const conversations = useAssistantConversations()
  const conversation = useAssistantConversation(conversationId)
  const prompts = usePendingPrompts()
  const ask = useAskAssistant()
  const dayLabel = useDayLabel()

  // Al abrir: una conversación nueva, salvo que haya una con tu agente trabajando, que se abre. Con
  // datos recién pedidos, no con los de la caché, que pueden ser de hace minutos.
  useEffect(() => {
    if (!conversations.isFetchedAfterMount || !conversations.data) return
    onAutoOpen(conversations.data.conversations.find((item) => item.active)?.id ?? null)
  }, [conversations.isFetchedAfterMount, conversations.data, onAutoOpen])

  // La conversación abierta ahora (para no saltar a otra si cambias mientras se envía).
  const shown = useRef(conversationId)
  useEffect(() => {
    shown.current = conversationId
  }, [conversationId])

  useEffect(() => {
    field.current?.focus()
  }, [conversationId])

  const action = launcher.data?.actions.find((item) => item.id === 'assistant')
  const noAgent = launcher.data?.no_agent_installed ?? false
  const canRunNow = action?.background_agent?.available ?? false
  // Sin segundo plano, si tu agente se puede abrir en una terminal, se abre a la vista y la respuesta
  // llega igual aquí; si tampoco, queda como encargo para tu próxima sesión.
  const canOpenTerminal = Boolean(action?.agent?.agent && !action.agent.blocked)
  const asking = (prompts.data?.prompts ?? []).some((prompt) => prompt.kind === 'question')
  const trimmed = text.trim()
  // Si se envía antes de saber si hay segundo plano, el texto espera a saberlo (`queued`).
  const [queued, setQueued] = useState<string | null>(null)
  const ready = trimmed.length > 0 && !ask.isPending && queued === null

  // La más antigua arriba, como en un chat. En una conversación nueva, nada.
  const list = conversationId === null ? [] : (conversation.data?.requests ?? [])
  const last = list.at(-1)

  // Un mensaje nuevo baja hasta él; si cambia la respuesta del último, solo si ya estabas abajo
  // (para no quitarte de donde lees).
  const seen = useRef({ count: -1, atBottom: true })
  useLayoutEffect(() => {
    const box = scroller.current
    if (!box) return
    if (list.length !== seen.current.count || seen.current.atBottom) box.scrollTop = box.scrollHeight
    seen.current.count = list.length
  }, [list.length, last?.id, last?.status, last?.answer, last?.progress.length])

  // Sin segundo plano ni terminal, la misma flecha lo deja como encargo y el hilo lo dice. Si no se
  // pudo saber (falla la consulta del agente), también: un encargo funciona con cualquier agente.
  const known = launcher.data !== undefined || launcher.isError
  const mode = canRunNow ? 'background' : canOpenTerminal ? 'terminal' : 'session'
  // Con `mutateAsync`, la conversación nueva queda abierta aunque cambies de pestaña mientras se
  // envía; si has pasado a otra conversación, no se salta de vuelta.
  const submit = (body: string) => {
    const from = conversationId
    ask
      .mutateAsync({ text: body, mode, conversation_id: from })
      .then((view) => {
        if (shown.current !== from) return
        setText('')
        onConversation(view.conversation_id)
        field.current?.focus()
      })
      .catch(() => {}) // el error lo enseña `ask.error`
  }
  const send = () => {
    if (!ready) return
    if (known) submit(trimmed)
    else setQueued(trimmed)
  }

  useEffect(() => {
    if (queued === null || !known) return
    setQueued(null)
    submit(queued)
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `submit` cambia en cada render
  }, [queued, known])

  if (noAgent) {
    return (
      <div
        role="region"
        aria-label={t('assistant.conversationLabel')}
        tabIndex={0}
        className="min-h-0 flex-1 overflow-y-auto px-4 py-4 text-sm text-pretty outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:ring-inset"
      >
        <p className="font-medium">{t('assistant.noAgentTitle')}</p>
        <p className="mt-1 text-muted-foreground">{t('assistant.noAgentBody')}</p>
        <Link to={HELP_SCREENS.agent!} onClick={onGo} className={cn(linkClass, 'mt-2')}>
          {t('goTo', { screen: t('screens.agent') })}
          <ArrowRightIcon className="size-3.5" weight="bold" aria-hidden />
        </Link>
      </div>
    )
  }

  const nearLimit = text.length > ASSISTANT_MAX_CHARS - 200
  const days = new Map<string, AssistantView[]>()
  for (const request of list) {
    const day = toLocalDateInput(request.created_at)
    days.set(day, [...(days.get(day) ?? []), request])
  }

  return (
    <>
      <div
        ref={scroller}
        onScroll={(event) => {
          const box = event.currentTarget
          seen.current.atBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 40
        }}
        // Enfocable, para leer una conversación larga también con el teclado.
        role="region"
        aria-label={t('assistant.conversationLabel')}
        tabIndex={0}
        className="min-h-0 flex-1 overflow-y-auto bg-muted/50 px-4 py-3 outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:ring-inset dark:bg-muted/30"
      >
        {conversationId !== null && conversation.isError ? (
          <p role="alert" className="text-sm text-destructive">
            {errorMessage(conversation.error)}
          </p>
        ) : list.length === 0 && conversationId !== null ? null : list.length === 0 ? (
          <section aria-label={t('assistant.suggestionsLabel')}>
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
            <p className="mt-3 text-xs text-pretty text-muted-foreground">{t('assistant.protected')}</p>
          </section>
        ) : (
          <section role="log" aria-live="polite" aria-label={t('assistant.history')} className="grid gap-4">
            {[...days.entries()].map(([day, turns]) => (
              <div key={day} className="grid gap-3">
                <p className="flex items-center gap-2 text-xs text-muted-foreground before:h-px before:flex-1 before:bg-border after:h-px after:flex-1 after:bg-border">
                  {dayLabel(day, turns[0]!.created_at)}
                </p>
                <ol className="grid gap-3">
                  {turns.map((request) => (
                    <Turn key={request.id} request={request} asking={asking} onGo={onGo} />
                  ))}
                </ol>
              </div>
            ))}
          </section>
        )}
      </div>

      <form
        className="shrink-0 border-t bg-card p-3"
        onSubmit={(event) => {
          event.preventDefault()
          send()
        }}
      >
        <div className="flex items-end gap-2 rounded-2xl border border-input bg-background py-1.5 pr-1.5 pl-3 transition-[color,box-shadow] focus-within:border-ring focus-within:ring-[3px] focus-within:ring-ring/50 dark:bg-input/30">
          <textarea
            ref={field}
            value={text}
            onChange={(event) => setText(event.target.value)}
            onKeyDown={(event) => {
              // Intro envía y Mayús+Intro salta de línea; mientras se compone (IME), Intro no envía.
              if (event.key !== 'Enter' || event.shiftKey || event.nativeEvent.isComposing) return
              event.preventDefault()
              send()
            }}
            maxLength={ASSISTANT_MAX_CHARS}
            readOnly={queued !== null}
            aria-busy={queued !== null || ask.isPending}
            rows={1}
            aria-label={t('assistant.label')}
            placeholder={t('assistant.placeholder')}
            className="field-sizing-content max-h-36 min-h-8 flex-1 resize-none bg-transparent py-1 text-base outline-none placeholder:text-muted-foreground md:text-sm"
          />
          <Button
            type="submit"
            size="icon"
            aria-label={t('assistant.send')}
            disabled={!ready}
            className="size-8 shrink-0 rounded-full"
          >
            <ArrowUpIcon className="size-4" weight="bold" aria-hidden />
          </Button>
        </div>
        {(list.length > 0 || nearLimit) && (
          <div className="mt-1.5 flex items-center gap-2 px-1 text-xs text-muted-foreground">
            {list.length > 0 && <Hint text={t('assistant.protected')} label={t('assistant.protectedLabel')} side="top" />}
            {nearLimit && (
              <span className="ml-auto">{t('assistant.left', { count: ASSISTANT_MAX_CHARS - text.length })}</span>
            )}
          </div>
        )}
        {ask.isError && (
          <p role="alert" className="mt-1 px-1 text-xs text-destructive">
            {errorMessage(ask.error)}
          </p>
        )}
      </form>
    </>
  )
}
