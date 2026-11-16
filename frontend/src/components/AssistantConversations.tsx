import { useEffect, useId, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { CircleNotchIcon, PlusIcon, TrashIcon } from '@phosphor-icons/react'
import type { ConversationSummary } from '@/api/client'
import { useAssistantConversations, useDeleteAssistantConversation } from '@/api/queries'
import { Button } from '@/components/ui/button'
import { errorMessage } from '@/lib/errors'
import { toLocalDateInput } from '@/lib/time'
import { cn } from '@/lib/utils'

const GROUPS = ['today', 'yesterday', 'week', 'older'] as const
type Group = (typeof GROUPS)[number]

/** `YYYY-MM-DD` de hace `days` días, con días del calendario (sin restar horas). */
function daysAgo(today: string, days: number): string {
  const date = new Date(`${today}T12:00:00Z`)
  date.setUTCDate(date.getUTCDate() - days)
  return date.toISOString().slice(0, 10)
}

function groupOf(updatedAt: string, today: string): Group {
  const day = toLocalDateInput(updatedAt)
  if (day === today) return 'today'
  if (day === daysAgo(today, 1)) return 'yesterday'
  if (day >= daysAgo(today, 6)) return 'week'
  return 'older'
}

function Item({
  conversation,
  current,
  onOpen,
  onDeleting,
}: {
  conversation: ConversationSummary
  current: boolean
  onOpen: () => void
  onDeleting: () => void
}) {
  const { t } = useTranslation('help')
  const remove = useDeleteAssistantConversation()
  const [confirming, setConfirming] = useState(false)
  const trash = useRef<HTMLButtonElement>(null)
  const asked = useRef(false)

  // Al cancelar, el foco vuelve a la papelera de la fila (el botón que lo tenía desaparece).
  useEffect(() => {
    if (confirming) asked.current = true
    else if (asked.current) trash.current?.focus()
  }, [confirming])

  if (confirming) {
    return (
      <li
        className="rounded-md bg-background px-2 py-1.5 text-xs"
        onKeyDown={(event) => {
          // Esc cancela el borrado sin cerrar el panel.
          if (event.key !== 'Escape') return
          event.stopPropagation()
          setConfirming(false)
        }}
      >
        <p className="text-pretty">{t('assistant.conversations.confirm', { title: conversation.title })}</p>
        <div className="mt-1.5 flex gap-1">
          <Button
            size="sm"
            variant="destructive"
            className="h-6 px-2 text-xs"
            disabled={remove.isPending}
            onClick={() => {
              // Si es la abierta, el panel pasa antes a una nueva: así no se queda en una borrada.
              onDeleting()
              remove.mutate(conversation.id)
            }}
          >
            {t('assistant.conversations.delete')}
          </Button>
          {/* El foco, en lo que no borra. */}
          <Button size="sm" variant="ghost" className="h-6 px-2 text-xs" onClick={() => setConfirming(false)} autoFocus>
            {t('assistant.cancel')}
          </Button>
        </div>
        {remove.isError && <p className="mt-1 text-destructive">{errorMessage(remove.error)}</p>}
      </li>
    )
  }

  return (
    <li className="group relative min-w-0">
      <button
        type="button"
        aria-current={current ? 'true' : undefined}
        title={conversation.title}
        onClick={onOpen}
        className={cn(
          'flex w-full items-center gap-1.5 rounded-md py-1.5 pr-7 pl-2 text-left text-sm outline-none hover:bg-background focus-visible:ring-[3px] focus-visible:ring-ring/50',
          current && 'bg-primary/12 font-medium text-foreground hover:bg-primary/15 dark:bg-primary/20',
        )}
      >
        <span className="min-w-0 flex-1 truncate">{conversation.title}</span>
        {conversation.active && (
          <CircleNotchIcon
            className="size-3.5 shrink-0 animate-spin text-primary"
            weight="bold"
            aria-label={t('assistant.conversations.working')}
          />
        )}
      </button>
      <button
        ref={trash}
        type="button"
        aria-label={t('assistant.conversations.deleteLabel', { title: conversation.title })}
        onClick={() => setConfirming(true)}
        className="absolute top-1/2 right-1 flex size-6 -translate-y-1/2 items-center justify-center rounded-sm text-muted-foreground opacity-0 outline-none group-focus-within:opacity-100 group-hover:opacity-100 hover:text-destructive focus-visible:opacity-100 focus-visible:ring-[3px] focus-visible:ring-ring/50"
      >
        <TrashIcon className="size-3.5" aria-hidden />
      </button>
    </li>
  )
}

/**
 * El historial del Asistente, como la barra lateral de ChatGPT o Claude: «Nueva conversación» y las
 * conversaciones por fecha (Hoy, Ayer, Últimos 7 días, Antes), con el título cortado con «…».
 * Cada una se borra con una confirmación en su propia fila.
 */
export function AssistantConversations({
  id,
  currentId,
  onOpen,
  onNew,
}: {
  id?: string
  currentId: number | null
  onOpen: (id: number) => void
  onNew: () => void
}) {
  const { t } = useTranslation('help')
  const headingId = useId()
  const conversations = useAssistantConversations()
  const list = conversations.data?.conversations ?? []
  // El día de hoy, al abrir la barra (para agrupar por fechas).
  const [today] = useState(() => toLocalDateInput(new Date()))
  const groups = new Map<Group, ConversationSummary[]>()
  for (const conversation of list) {
    const group = groupOf(conversation.updated_at, today)
    groups.set(group, [...(groups.get(group) ?? []), conversation])
  }

  return (
    <nav
      id={id}
      aria-label={t('assistant.conversations.label')}
      className="flex w-60 shrink-0 flex-col border-r bg-muted/60 dark:bg-muted/40"
    >
      <div className="p-2">
        <Button variant="outline" size="sm" className="w-full justify-start gap-2 bg-background" onClick={onNew}>
          <PlusIcon weight="bold" aria-hidden />
          {t('assistant.conversations.new')}
        </Button>
      </div>
      <div className="min-h-0 flex-1 overflow-x-hidden overflow-y-auto px-2 pb-2">
        {conversations.isError ? (
          <p className="px-2 py-1 text-xs text-destructive">{errorMessage(conversations.error)}</p>
        ) : list.length === 0 && !conversations.isPending ? (
          <p className="px-2 py-1 text-xs text-pretty text-muted-foreground">{t('assistant.conversations.empty')}</p>
        ) : (
          GROUPS.filter((group) => groups.has(group)).map((group) => (
            <section key={group} aria-labelledby={`${headingId}-${group}`} className="mt-2 first:mt-0">
              <h3 id={`${headingId}-${group}`} className="px-2 pb-0.5 text-xs font-medium text-muted-foreground">
                {t(`assistant.conversations.groups.${group}`)}
              </h3>
              <ul className="flex flex-col gap-0.5">
                {groups.get(group)!.map((conversation) => (
                  <Item
                    key={conversation.id}
                    conversation={conversation}
                    current={conversation.id === currentId}
                    onOpen={() => onOpen(conversation.id)}
                    onDeleting={() => {
                      if (conversation.id === currentId) onNew()
                    }}
                  />
                ))}
              </ul>
            </section>
          ))
        )}
      </div>
    </nav>
  )
}
