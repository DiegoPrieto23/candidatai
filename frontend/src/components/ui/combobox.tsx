/**
 * Selector con búsqueda, del estilo del selector de fecha (mismo `Popover`, bordes y sombras), en
 * lugar de un `<select>` nativo cuando la lista puede ser larga.
 *
 * Al abrirlo, una caja de texto filtra mientras escribes, sin distinguir mayúsculas ni tildes, por
 * la etiqueta y la descripción de cada opción. Con pocas opciones no hace falta buscar: la caja no
 * aparece y se recorre la lista directamente. Teclado: flechas, Inicio y Fin para moverse, Intro
 * para elegir y Esc para cerrar; el foco vuelve al botón al cerrar.
 */

import * as React from 'react'
import { Popover } from 'radix-ui'
import { CaretUpDownIcon, CheckIcon, MagnifyingGlassIcon } from '@phosphor-icons/react'
import { matchesQuery } from '@/lib/text'
import { cn } from '@/lib/utils'

export interface ComboboxOption {
  value: string
  /** Primera línea, en negrita (p. ej. la empresa). */
  label: string
  /** Segunda línea (p. ej. el puesto). También se busca en ella. */
  description?: string
  /** Dato pequeño a la derecha (p. ej. la etapa). No se busca en él. */
  meta?: string
}

/** Con este número de opciones o menos, la lista se recorre sin caja de búsqueda. */
const SEARCH_THRESHOLD = 7

export function Combobox({
  id,
  value,
  onChange,
  options,
  label,
  placeholder,
  searchLabel,
  noMatch,
  className,
  ...aria
}: {
  id?: string
  value: string | null
  onChange: (value: string) => void
  options: ComboboxOption[]
  /** Nombre accesible de la lista (el mismo que la etiqueta del campo). */
  label: string
  /** Lo que enseña el botón sin nada elegido. */
  placeholder: string
  /** Marcador y nombre accesible de la caja de búsqueda. */
  searchLabel: string
  /** La línea sin resultados, con lo que se ha escrito. */
  noMatch: (query: string) => string
  className?: string
  'aria-label'?: string
  'aria-labelledby'?: string
  'aria-invalid'?: boolean
}) {
  const [open, setOpen] = React.useState(false)
  const [query, setQuery] = React.useState('')
  const [active, setActive] = React.useState(0)
  const listId = React.useId()
  const optionId = (index: number) => `${listId}-option-${index}`
  const list = React.useRef<HTMLDivElement>(null)
  const input = React.useRef<HTMLInputElement>(null)

  const searchable = options.length > SEARCH_THRESHOLD
  // Se busca en la etiqueta y la descripción; la etapa (`meta`) no cuenta.
  const shown = searchable
    ? options.filter((option) => matchesQuery(`${option.label} ${option.description ?? ''}`, query))
    : options
  const selected = options.find((option) => option.value === value) ?? null

  function changeOpen(next: boolean) {
    setOpen(next)
    if (!next) return
    setQuery('')
    setActive(Math.max(0, options.findIndex((option) => option.value === value)))
  }

  // Si la lista cambia con el selector abierto (se acorta), la opción activa no se sale de ella.
  const current = Math.min(active, shown.length - 1)
  const activeId = current >= 0 ? optionId(current) : undefined

  const reveal = (index: number) => document.getElementById(optionId(index))?.scrollIntoView?.({ block: 'nearest' })

  // La opción activa siempre a la vista al moverse con el teclado (al abrir, en `onOpenAutoFocus`).
  React.useEffect(() => {
    if (open) reveal(current)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [current, open])

  function choose(option: ComboboxOption) {
    onChange(option.value)
    setOpen(false)
  }

  function onKeyDown(event: React.KeyboardEvent) {
    const last = shown.length - 1
    const moves: Record<string, number> = {
      ArrowDown: Math.min(current + 1, last),
      ArrowUp: Math.max(current - 1, 0),
      Home: 0,
      End: last,
    }
    if (event.key in moves) {
      // En la caja de búsqueda, Inicio y Fin mueven el cursor del texto, no la opción.
      if (searchable && (event.key === 'Home' || event.key === 'End')) return
      event.preventDefault()
      setActive(Math.max(0, moves[event.key]))
      return
    }
    // En la lista sin búsqueda, la barra espaciadora también elige, como en un `<select>`.
    if (event.key === 'Enter' || (!searchable && event.key === ' ')) {
      event.preventDefault()
      const option = shown[current]
      if (option) choose(option)
    }
  }

  return (
    <Popover.Root open={open} onOpenChange={changeOpen}>
      <Popover.Trigger asChild>
        <button
          type="button"
          id={id}
          data-slot="combobox"
          aria-haspopup="listbox"
          className={cn(
            'flex h-9 w-full min-w-0 items-center justify-between gap-2 rounded-md border border-input bg-transparent px-3 py-1 text-left text-base transition-[color,box-shadow] outline-none md:text-sm dark:bg-input/30',
            'focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50',
            'aria-invalid:border-destructive aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40',
            'data-[state=open]:border-ring data-[state=open]:ring-[3px] data-[state=open]:ring-ring/50',
            className,
          )}
          onKeyDown={(event) => {
            if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
              event.preventDefault()
              changeOpen(true)
            }
          }}
          {...aria}
        >
          <span className={cn('truncate', !selected && 'text-muted-foreground')}>
            {selected ? (
              <>
                <span className="font-medium">{selected.label}</span>
                {selected.description && <span className="text-muted-foreground"> · {selected.description}</span>}
              </>
            ) : (
              placeholder
            )}
          </span>
          <CaretUpDownIcon aria-hidden="true" className="size-4 shrink-0 text-muted-foreground" />
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          align="start"
          sideOffset={6}
          collisionPadding={12}
          onOpenAutoFocus={(event) => {
            event.preventDefault()
            ;(searchable ? input.current : list.current)?.focus()
            reveal(current)
          }}
          aria-label={label}
          className="z-[70] w-[var(--radix-popover-trigger-width)] min-w-[16rem] max-w-[calc(100vw-1.5rem)] overflow-hidden rounded-xl border bg-popover text-popover-foreground shadow-lg outline-none data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95"
        >
          {searchable && (
            <div className="flex items-center gap-2 border-b px-3">
              <MagnifyingGlassIcon aria-hidden="true" className="size-4 shrink-0 text-muted-foreground" />
              <input
                ref={input}
                type="text"
                autoComplete="off"
                spellCheck={false}
                role="combobox"
                aria-expanded="true"
                aria-controls={listId}
                aria-autocomplete="list"
                aria-activedescendant={activeId}
                aria-label={searchLabel}
                placeholder={searchLabel}
                value={query}
                onChange={(event) => {
                  setQuery(event.target.value)
                  setActive(0)
                }}
                onKeyDown={onKeyDown}
                className="h-10 w-full min-w-0 bg-transparent text-base outline-none placeholder:text-muted-foreground md:text-sm"
              />
            </div>
          )}
          <div
            ref={list}
            id={listId}
            role="listbox"
            aria-label={label}
            aria-activedescendant={searchable ? undefined : activeId}
            tabIndex={searchable ? -1 : 0}
            onKeyDown={searchable ? undefined : onKeyDown}
            className="max-h-72 overflow-y-auto p-1 outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:ring-inset"
          >
            {shown.map((option, index) => {
              const isSelected = option.value === value
              return (
                <div
                  key={option.value}
                  id={optionId(index)}
                  role="option"
                  aria-selected={isSelected}
                  data-active={index === current ? '' : undefined}
                  onMouseMove={() => setActive(index)}
                  // Sin robar el foco a la caja de búsqueda: el clic elige y cierra.
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => choose(option)}
                  className="flex cursor-pointer items-start gap-2 rounded-lg px-2 py-1.5 text-sm data-[active]:bg-accent data-[active]:text-accent-foreground"
                >
                  <CheckIcon
                    aria-hidden="true"
                    weight="bold"
                    className={cn('mt-0.5 size-4 shrink-0 text-primary', !isSelected && 'invisible')}
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-semibold">{option.label}</span>
                    {option.description && (
                      <span className="block truncate text-muted-foreground">{option.description}</span>
                    )}
                  </span>
                  {option.meta && <span className="mt-0.5 shrink-0 text-xs text-muted-foreground">{option.meta}</span>}
                </div>
              )
            })}
          </div>
          {/* Fuera de la lista: un `listbox` solo admite opciones. */}
          {shown.length === 0 && (
            <p role="status" className="px-3 pb-3 text-center text-sm text-muted-foreground">
              {noMatch(query.trim())}
            </p>
          )}
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  )
}
