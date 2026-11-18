import { useId, useRef, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { CaretDownIcon, PlusIcon, XIcon } from '@phosphor-icons/react'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { matchesQuery } from '@/lib/text'
import { hasItem } from '@/lib/searchStrip'
import { cn } from '@/lib/utils'

export interface Tag {
  value: string
  /** Una nota pequeña tras el texto (p. ej. «solo híbrido o remoto»). */
  note?: string
  /** Tachada (un lugar que descartas). */
  struck?: boolean
  /** Lo que se elige al pulsar la etiqueta, en un menú (p. ej. qué aceptas en un lugar). */
  choice?: TagChoice
}

export interface TagChoice {
  /** El título del menú y el nombre del botón. */
  label: string
  value: string
  options: { value: string; label: string }[]
  onChange: (value: string) => void
}

export interface Suggestion {
  title: string
  count: number
}

/** Lo mismo que admite tu perfil en un puesto o un lugar. */
const MAX_CHARS = 80

/**
 * Una fila de la franja: su nombre a la izquierda y, a la derecha, las etiquetas (cada una con su ✕)
 * y «+ Añadir …» al final, que se convierte en una caja con sugerencias. Intro añade lo elegido o lo
 * escrito; Esc cierra. Lo que se añade o se quita lo guarda quien usa la fila (`onAdd`, `onRemove`).
 */
export function TagRow({
  label,
  icon,
  tags,
  empty,
  addLabel,
  placeholder,
  suggestions = [],
  suggestionsTitle,
  busy,
  onAdd,
  onRemove,
}: {
  label: string
  icon: ReactNode
  tags: Tag[]
  /** Lo que se lee sin ninguna etiqueta. */
  empty: string
  addLabel: string
  placeholder: string
  suggestions?: Suggestion[]
  suggestionsTitle?: string
  busy: boolean
  onAdd: (value: string) => void
  onRemove: (value: string) => void
}) {
  const { t } = useTranslation('search', { keyPrefix: 'strip' })
  const labelId = useId()
  const listId = useId()
  const [adding, setAdding] = useState(false)
  const [text, setText] = useState('')
  const [active, setActive] = useState(0)
  // La lista solo se ve con el foco en la caja (lo escrito se conserva al salir).
  const [focused, setFocused] = useState(true)
  const titleId = useId()
  const addButton = useRef<HTMLButtonElement>(null)

  const typed = text.trim()
  const values = tags.map((tag) => tag.value)
  const matching = suggestions.filter((s) => !hasItem(values, s.title) && matchesQuery(s.title, typed))
  // Lo escrito va primero, salvo que ya sea una de las sugerencias o ya lo tengas.
  const offerTyped = typed !== '' && !hasItem(values, typed) && !matching.some((s) => hasItem([s.title], typed))
  const options: { value: string; label: string; count?: number }[] = [
    ...(offerTyped ? [{ value: typed, label: t('addTyped', { text: typed }) }] : []),
    ...matching.map((s) => ({ value: s.title, label: s.title, count: s.count })),
  ]
  const current = Math.min(active, options.length - 1)
  const open = focused && options.length > 0
  const optionId = (i: number) => `${listId}-${i}`

  const close = (refocus: boolean) => {
    setAdding(false)
    setText('')
    setActive(0)
    setFocused(true)
    if (refocus) requestAnimationFrame(() => addButton.current?.focus())
  }

  const pick = (value: string) => {
    if (busy || !value || hasItem(values, value)) return
    onAdd(value)
    close(true)
  }

  return (
    <div role="group" aria-labelledby={labelId} className="grid gap-x-4 gap-y-2 px-5 py-3 sm:grid-cols-[7rem_minmax(0,1fr)]">
      <span id={labelId} className="flex items-center gap-2 pt-1 text-sm text-muted-foreground">
        {icon}
        {label}
      </span>
      <div className="flex min-h-8 flex-wrap items-center gap-1.5">
        {tags.length === 0 && !adding && <span className="text-sm text-muted-foreground">{empty}</span>}
        {tags.map((tag) => (
          <span
            key={tag.value}
            className={cn(
              'inline-flex max-w-full items-center gap-0.5 rounded-full border bg-muted py-0.5 pr-1 text-sm font-medium',
              tag.choice ? 'pl-1' : 'pl-3',
            )}
          >
            {tag.choice ? (
              <TagMenu tag={tag} choice={tag.choice} busy={busy} />
            ) : (
              <TagText tag={tag} />
            )}
            <button
              type="button"
              aria-disabled={busy}
              aria-label={t('remove', { item: tag.value })}
              onClick={() => {
                if (busy) return
                onRemove(tag.value)
                requestAnimationFrame(() => addButton.current?.focus())
              }}
              className="grid size-5 shrink-0 place-items-center rounded-full text-muted-foreground outline-none hover:bg-foreground/10 hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring aria-disabled:opacity-50"
            >
              <XIcon className="size-3" aria-hidden />
            </button>
          </span>
        ))}
        {adding ? (
          <span className="relative">
            <input
              autoFocus
              value={text}
              maxLength={MAX_CHARS}
              placeholder={placeholder}
              aria-label={addLabel}
              role="combobox"
              aria-autocomplete="list"
              aria-expanded={open}
              aria-controls={open ? listId : undefined}
              aria-activedescendant={open ? optionId(current) : undefined}
              onFocus={() => setFocused(true)}
              onChange={(e) => {
                setText(e.target.value)
                setActive(0)
              }}
              onKeyDown={(e) => {
                if (e.key === 'ArrowDown' && options.length > 0) {
                  e.preventDefault()
                  setActive((current + 1) % options.length)
                } else if (e.key === 'ArrowUp' && options.length > 0) {
                  e.preventDefault()
                  setActive((current - 1 + options.length) % options.length)
                } else if (e.key === 'Enter') {
                  e.preventDefault()
                  pick(options[current]?.value ?? typed)
                } else if (e.key === 'Escape') {
                  e.preventDefault()
                  close(true)
                }
              }}
              onBlur={() => {
                // Con algo escrito, la caja se queda a la vista para volver a ella (sin su lista); vacía, se cierra.
                if (!typed) close(false)
                else setFocused(false)
              }}
              className="h-7 w-56 rounded-full border border-ring bg-card px-3 text-sm outline-none ring-[3px] ring-ring/25"
            />
            {open && (
              <div className="absolute top-[calc(100%+6px)] left-0 z-20 w-72 rounded-lg border bg-popover p-1.5 text-popover-foreground shadow-lg">
                {matching.length > 0 && suggestionsTitle && (
                  <p id={titleId} className="px-2 pt-1 pb-1.5 text-xs text-muted-foreground">
                    {suggestionsTitle}
                  </p>
                )}
                <ul id={listId} role="listbox" {...(matching.length > 0 && suggestionsTitle ? { 'aria-labelledby': titleId } : { 'aria-label': addLabel })}>
                  {options.map((option, i) => (
                    <li
                      key={option.value}
                      id={optionId(i)}
                      role="option"
                      aria-selected={i === current}
                      // Sin perder el foco de la caja al pulsar.
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={() => pick(option.value)}
                      onMouseMove={() => setActive(i)}
                      className={cn('flex cursor-pointer items-baseline justify-between gap-3 rounded-md px-2 py-1.5 text-sm', i === current && 'bg-accent text-accent-foreground')}
                    >
                      <span className="min-w-0 truncate">{option.label}</span>
                      {option.count !== undefined && <span className="shrink-0 text-xs text-muted-foreground">{t('approved', { count: option.count })}</span>}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </span>
        ) : (
          <button
            ref={addButton}
            type="button"
            // Sin `disabled` mientras se guarda: así no pierde el foco que le devuelve la fila.
            aria-disabled={busy}
            onClick={() => {
              if (!busy) setAdding(true)
            }}
            className="inline-flex items-center gap-1 rounded-full border border-dashed border-input px-3 py-0.5 text-sm text-muted-foreground outline-none transition-colors hover:border-ring hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring aria-disabled:opacity-50"
          >
            <PlusIcon className="size-3" aria-hidden />
            {addLabel}
          </button>
        )}
      </div>
    </div>
  )
}

function TagText({ tag }: { tag: Tag }) {
  return (
    <>
      <span className={cn('truncate', tag.struck && 'text-muted-foreground line-through decoration-destructive/70')}>{tag.value}</span>
      {tag.note && <span className="ml-1 shrink-0 text-xs font-normal text-muted-foreground">{tag.note}</span>}
    </>
  )
}

/** Una etiqueta que se pulsa para elegir algo de ella (sin salir de la franja). */
function TagMenu({ tag, choice, busy }: { tag: Tag; choice: TagChoice; busy: boolean }) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label={choice.label}
        aria-disabled={busy}
        disabled={busy}
        className="inline-flex min-w-0 items-center gap-0.5 rounded-full py-px pr-1 pl-2 outline-none hover:bg-foreground/5 focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-100"
      >
        <TagText tag={tag} />
        <CaretDownIcon className="size-3 shrink-0 text-muted-foreground" aria-hidden />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="min-w-[13rem]">
        <DropdownMenuLabel className="text-xs font-normal text-muted-foreground">{choice.label}</DropdownMenuLabel>
        <DropdownMenuRadioGroup value={choice.value} onValueChange={choice.onChange}>
          {choice.options.map((option) => (
            <DropdownMenuRadioItem key={option.value} value={option.value}>
              {option.label}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
