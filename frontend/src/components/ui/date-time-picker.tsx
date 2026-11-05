/**
 * Selectores de fecha y hora propios, en lugar de los `<input type="date|datetime-local|time">` del
 * navegador (cuyo desplegable cambia de un navegador a otro y no sigue el diseño de la app).
 *
 * Los valores son cadenas sin zona, como las de esos inputs: `YYYY-MM-DD`, `YYYY-MM-DDTHH:mm` y
 * `HH:mm`. Así se siguen convirtiendo con `lib/time.ts` (hora de Madrid) y no cambia nada fuera.
 * Las fechas se calculan sobre esas cadenas, sin pasar por la zona del navegador.
 */

import * as React from 'react'
import { useTranslation } from 'react-i18next'
import { Popover } from 'radix-ui'
import { CalendarBlankIcon, CaretLeftIcon, CaretRightIcon, ClockIcon } from '@phosphor-icons/react'
import { Button } from '@/components/ui/button'
import { dateFormatter } from '@/lib/labels'
import { toLocalDateInput, toLocalInput } from '@/lib/time'
import { cn } from '@/lib/utils'

/** La hora que se pone cuando no se sabe una concreta: las dos de la tarde. */
export const DEFAULT_TIME = '14:00'

// --- Cálculo de fechas (sobre `YYYY-MM-DD`) ------------------------------------------------------

interface Ymd {
  y: number
  m: number // 1-12
  d: number
}

const pad = (n: number) => String(n).padStart(2, '0')

function parseDate(value: string): Ymd | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value)
  if (!match) return null
  const [y, m, d] = [Number(match[1]), Number(match[2]), Number(match[3])]
  const check = new Date(Date.UTC(y, m - 1, d))
  return check.getUTCFullYear() === y && check.getUTCMonth() === m - 1 && check.getUTCDate() === d ? { y, m, d } : null
}

const key = (p: Ymd) => `${p.y}-${pad(p.m)}-${pad(p.d)}`

const fromUtc = (date: Date): Ymd => ({ y: date.getUTCFullYear(), m: date.getUTCMonth() + 1, d: date.getUTCDate() })

const addDays = (p: Ymd, days: number): Ymd => fromUtc(new Date(Date.UTC(p.y, p.m - 1, p.d + days)))

/** Suma meses sin salirse de mes: el 31 de enero + 1 mes es el 28 (o 29) de febrero. */
function addMonths(p: Ymd, months: number): Ymd {
  const first = new Date(Date.UTC(p.y, p.m - 1 + months, 1))
  const last = new Date(Date.UTC(first.getUTCFullYear(), first.getUTCMonth() + 1, 0)).getUTCDate()
  return { y: first.getUTCFullYear(), m: first.getUTCMonth() + 1, d: Math.min(p.d, last) }
}

/** Las 6 semanas (42 días) que enseña un mes, empezando en lunes. */
function monthGrid(view: Ymd): Ymd[] {
  const first = new Date(Date.UTC(view.y, view.m - 1, 1))
  const offset = (first.getUTCDay() + 6) % 7
  return Array.from({ length: 42 }, (_, i) => addDays({ y: view.y, m: view.m, d: 1 }, i - offset))
}

const utc = (p: Ymd) => new Date(Date.UTC(p.y, p.m - 1, p.d))

const MONTH_TITLE = { timeZone: 'UTC', month: 'long', year: 'numeric' } as const
const WEEKDAY = { timeZone: 'UTC', weekday: 'short' } as const
const DAY_LONG = { timeZone: 'UTC', weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' } as const
const DAY_SHORT = { timeZone: 'UTC', weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' } as const

const capitalize = (text: string) => text.charAt(0).toUpperCase() + text.slice(1)

// Un lunes cualquiera: de ahí salen los nombres de los días de la semana en el idioma activo.
const MONDAY: Ymd = { y: 2024, m: 1, d: 1 }

// --- Calendario ----------------------------------------------------------------------------------

function Calendar({
  selected,
  today,
  onSelect,
}: {
  selected: string
  today: string
  onSelect: (day: string) => void
}) {
  const { t } = useTranslation()
  const selectedYmd = parseDate(selected)
  const start = selectedYmd ?? parseDate(today) ?? { y: 2026, m: 1, d: 1 }
  const [focus, setFocus] = React.useState<Ymd>(start)
  const [view, setView] = React.useState<Ymd>({ ...start, d: 1 })
  const grid = React.useRef<HTMLDivElement>(null)
  const refocus = React.useRef(false)

  // Si la fecha cambia desde fuera (con «Hoy» o «Ahora»), el calendario la sigue.
  React.useEffect(() => {
    if (!selectedYmd) return
    setFocus(selectedYmd)
    setView({ ...selectedYmd, d: 1 })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected])

  React.useEffect(() => {
    if (!refocus.current) return
    refocus.current = false
    grid.current?.querySelector<HTMLElement>(`[data-day="${key(focus)}"]`)?.focus()
  }, [focus])

  function go(next: Ymd) {
    refocus.current = true
    setFocus(next)
    setView({ ...next, d: 1 })
  }

  function onKeyDown(event: React.KeyboardEvent) {
    // Se parte del día que tiene el foco (con un clic puede no ser el del estado).
    const from = parseDate((event.target as HTMLElement).dataset.day ?? '') ?? focus
    const moves: Record<string, Ymd> = {
      ArrowLeft: addDays(from, -1),
      ArrowRight: addDays(from, 1),
      ArrowUp: addDays(from, -7),
      ArrowDown: addDays(from, 7),
      PageUp: addMonths(from, event.shiftKey ? -12 : -1),
      PageDown: addMonths(from, event.shiftKey ? 12 : 1),
    }
    const next = moves[event.key]
    if (!next) return
    event.preventDefault()
    go(next)
  }

  const cells = monthGrid(view)
  // El día al que se llega con Tab: el del foco si está en este mes; si no (tras pasar de mes), el 1.
  const tabbable = focus.y === view.y && focus.m === view.m ? key(focus) : key({ ...view, d: 1 })
  const weekdays = Array.from({ length: 7 }, (_, i) => dateFormatter(WEEKDAY).format(utc(addDays(MONDAY, i))))
  const title = capitalize(dateFormatter(MONTH_TITLE).format(utc(view)))

  return (
    <div className="grid gap-2">
      <div className="flex items-center justify-between gap-2">
        <span aria-live="polite" className="pl-1 text-sm font-semibold">
          {title}
        </span>
        <div className="flex gap-0.5">
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            aria-label={t('picker.prevMonth')}
            onClick={() => setView(addMonths(view, -1))}
          >
            <CaretLeftIcon />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            aria-label={t('picker.nextMonth')}
            onClick={() => setView(addMonths(view, 1))}
          >
            <CaretRightIcon />
          </Button>
        </div>
      </div>
      <div className="grid grid-cols-7 text-center text-xs text-muted-foreground" aria-hidden="true">
        {weekdays.map((day, i) => (
          <span key={i} className="flex h-7 items-center justify-center">
            {day}
          </span>
        ))}
      </div>
      <div ref={grid} role="group" aria-label={title} className="grid grid-cols-7 gap-y-0.5" onKeyDown={onKeyDown}>
        {cells.map((cell) => {
          const id = key(cell)
          const outside = cell.m !== view.m
          const isSelected = id === selected.slice(0, 10)
          const focusable = id === tabbable
          return (
            <button
              key={id}
              type="button"
              data-day={id}
              tabIndex={focusable ? 0 : -1}
              aria-label={dateFormatter(DAY_LONG).format(utc(cell))}
              aria-pressed={isSelected}
              aria-current={id === today ? 'date' : undefined}
              onClick={() => onSelect(id)}
              className={cn(
                'flex size-9 items-center justify-center justify-self-center rounded-md text-sm tabular-nums outline-none transition-colors',
                'hover:bg-foreground/[0.07] focus-visible:ring-[3px] focus-visible:ring-ring/50',
                outside && 'text-muted-foreground/50',
                id === today && !isSelected && 'font-semibold text-primary ring-1 ring-inset ring-primary/50',
                isSelected && 'bg-primary font-medium text-primary-foreground hover:bg-primary/90',
              )}
            >
              {cell.d}
            </button>
          )
        })}
      </div>
    </div>
  )
}

// --- Hora ----------------------------------------------------------------------------------------

function splitTime(value: string): [string, string] {
  const match = /^(\d{2}):(\d{2})/.exec(value)
  return match ? [match[1] ?? '', match[2] ?? ''] : ['', '']
}

const inRange = (text: string, max: number) => text !== '' && Number(text) <= max

/**
 * Hora en dos casillas (`HH` y `mm`) que se escriben con el teclado; con ↑ y ↓ suben y bajan (la hora
 * de uno en uno, los minutos de cinco en cinco). Vacía vale `''`.
 */
export function TimeInput({
  id,
  value,
  onChange,
  disabled,
  className,
}: {
  id?: string
  value: string
  onChange: (value: string) => void
  disabled?: boolean
  className?: string
}) {
  const { t } = useTranslation()
  const [draft, setDraft] = React.useState(() => splitTime(value))
  // Si el valor cambia desde fuera se reescriben las casillas; si es el que acabas de teclear, no.
  React.useEffect(() => {
    setDraft((prev) => {
      const typed = inRange(prev[0], 23) && inRange(prev[1], 59) ? `${pad(Number(prev[0]))}:${pad(Number(prev[1]))}` : null
      return typed === value ? prev : splitTime(value)
    })
  }, [value])

  function commit(hour: string, minute: string) {
    if (inRange(hour, 23) && inRange(minute, 59)) onChange(`${pad(Number(hour))}:${pad(Number(minute))}`)
  }

  function edit(index: 0 | 1, raw: string) {
    const text = raw.replace(/\D/g, '').slice(0, 2)
    const next: [string, string] = index === 0 ? [text, draft[1]] : [draft[0], text]
    setDraft(next)
    // Con un solo dígito se espera: «3» puede ser el principio de «30».
    if (text.length === 2) commit(...next)
  }

  function step(index: 0 | 1, direction: 1 | -1) {
    const max = index === 0 ? 23 : 59
    const unit = index === 0 ? 1 : 5
    const current = Number(draft[index] || 0)
    const moved = index === 0 ? current + direction * unit : (Math.floor(current / unit) + direction) * unit
    const next = (((moved % (max + 1)) + max + 1) % (max + 1)).toString()
    const pair: [string, string] = index === 0 ? [next, draft[1] || '0'] : [draft[0] || '0', next]
    setDraft([pad(Number(pair[0])), pad(Number(pair[1]))])
    commit(...pair)
  }

  function settle() {
    const [hour, minute] = draft
    if (hour === '' && minute === '') return onChange('')
    const filled: [string, string] = [hour || '0', minute || '0']
    setDraft([pad(Number(filled[0])), pad(Number(filled[1]))])
    commit(...filled)
  }

  const box =
    'h-9 w-11 rounded-md border border-input bg-transparent text-center text-sm tabular-nums outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-input/30'

  function field(index: 0 | 1, label: string, fieldId?: string) {
    return (
      <input
        id={fieldId}
        type="text"
        inputMode="numeric"
        autoComplete="off"
        placeholder="––"
        aria-label={label}
        disabled={disabled}
        value={draft[index]}
        className={box}
        onChange={(e) => edit(index, e.target.value)}
        // Al entrar se selecciona lo escrito: lo que teclees lo sustituye en vez de añadirse.
        onFocus={(e) => e.target.select()}
        onMouseUp={(e) => e.preventDefault()}
        onKeyDown={(e) => {
          if (e.key !== 'ArrowUp' && e.key !== 'ArrowDown') return
          e.preventDefault()
          step(index, e.key === 'ArrowUp' ? 1 : -1)
        }}
      />
    )
  }

  return (
    <span
      role="group"
      aria-label={t('picker.time')}
      className={cn('inline-flex items-center gap-1', className)}
      // Se completa (minutos a 00, casillas vacías = sin hora) al salir de las dos casillas, no al pasar de una a otra.
      onBlur={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget)) settle()
      }}
    >
      {field(0, t('picker.hour'), id)}
      <span aria-hidden="true" className="font-medium text-muted-foreground">
        :
      </span>
      {field(1, t('picker.minute'))}
    </span>
  )
}

// --- Selector (botón + desplegable) ---------------------------------------------------------------

interface PickerProps {
  id?: string
  /** `YYYY-MM-DD` o, en `DateTimePicker`, `YYYY-MM-DDTHH:mm`. Vacío, sin elegir. */
  value: string
  onChange: (value: string) => void
  /** Con `required` no sale «Borrar» y el formulario no se envía sin valor. */
  required?: boolean
  disabled?: boolean
  className?: string
  /** Hora que se pone al elegir un día sin hora (solo `DateTimePicker`). */
  defaultTime?: string
  'aria-invalid'?: boolean
  'aria-describedby'?: string
}

function Picker({
  mode,
  id,
  value,
  onChange,
  required,
  disabled,
  className,
  defaultTime = DEFAULT_TIME,
  ...aria
}: PickerProps & { mode: 'date' | 'datetime' }) {
  const { t } = useTranslation()
  const [open, setOpen] = React.useState(false)
  const body = React.useRef<HTMLDivElement>(null)
  const withTime = mode === 'datetime'
  const today = toLocalDateInput(new Date())
  const datePart = value.slice(0, 10)
  const timePart = value.slice(11, 16)
  const parsed = parseDate(datePart)

  const shown = parsed
    ? dateFormatter(DAY_SHORT).format(utc(parsed)) + (withTime && timePart ? ` · ${timePart}` : '')
    : null

  function pickDay(day: string) {
    if (!withTime) {
      onChange(day)
      setOpen(false)
      return
    }
    onChange(`${day}T${timePart || defaultTime}`)
  }

  function setTime(time: string) {
    if (time) onChange(`${parsed ? datePart : today}T${time}`)
  }

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>
        <button
          type="button"
          id={id}
          disabled={disabled}
          data-slot="date-time-picker"
          data-empty={shown ? undefined : ''}
          className={cn(
            'flex h-9 w-full min-w-0 items-center justify-between gap-2 rounded-md border border-input bg-transparent px-3 py-1 text-left text-base transition-[color,box-shadow] outline-none md:text-sm dark:bg-input/30',
            'focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50',
            'aria-invalid:border-destructive aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40',
            'disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50',
            'data-[state=open]:border-ring data-[state=open]:ring-[3px] data-[state=open]:ring-ring/50',
            className,
          )}
          {...aria}
        >
          <span className={cn('truncate', !shown && 'text-muted-foreground')}>
            {shown ?? t(withTime ? 'picker.chooseDateTime' : 'picker.chooseDate')}
          </span>
          <CalendarBlankIcon aria-hidden="true" className="size-4 shrink-0 text-muted-foreground" />
        </button>
      </Popover.Trigger>
      {required && (
        // Sin él, `required` no avisaría al enviar el formulario con un botón: es el aviso nativo del navegador.
        <input
          tabIndex={-1}
          aria-hidden="true"
          required
          value={value}
          onChange={() => {}}
          className="pointer-events-none absolute size-px opacity-0"
        />
      )}
      <Popover.Portal>
        <Popover.Content
          align="start"
          sideOffset={6}
          collisionPadding={12}
          aria-label={t(withTime ? 'picker.chooseDateTime' : 'picker.chooseDate')}
          onOpenAutoFocus={(event) => {
            event.preventDefault()
            body.current?.querySelector<HTMLElement>('[data-day][tabindex="0"]')?.focus()
          }}
          className="z-[70] w-[19.5rem] max-w-[calc(100vw-1.5rem)] rounded-xl border bg-popover p-3 text-popover-foreground shadow-lg outline-none data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95"
        >
          <div ref={body} className="grid gap-3">
            <Calendar selected={datePart} today={today} onSelect={pickDay} />

            {withTime && (
              <div className="flex items-center justify-between gap-3 border-t pt-3">
                <span className="flex items-center gap-2 text-sm text-muted-foreground">
                  <ClockIcon aria-hidden="true" className="size-4" />
                  {t('picker.time')}
                </span>
                <TimeInput value={timePart} onChange={setTime} />
              </div>
            )}
            {withTime && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="-mt-1 justify-start text-muted-foreground"
                onClick={() => setTime(DEFAULT_TIME)}
              >
                {t('picker.anytime', { time: DEFAULT_TIME })}
              </Button>
            )}

            <div className="flex items-center justify-between gap-2 border-t pt-2">
              <div className="flex gap-1">
                {!required && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      onChange('')
                      setOpen(false)
                    }}
                  >
                    {t('picker.clear')}
                  </Button>
                )}
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    if (withTime) onChange(toLocalInput(new Date()))
                    else {
                      onChange(today)
                      setOpen(false)
                    }
                  }}
                >
                  {t(withTime ? 'picker.now' : 'picker.today')}
                </Button>
              </div>
              {withTime && (
                <Button type="button" size="sm" onClick={() => setOpen(false)}>
                  {t('picker.done')}
                </Button>
              )}
            </div>
          </div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  )
}

/** Un día (`YYYY-MM-DD`): al elegirlo se cierra. */
export function DatePicker(props: PickerProps) {
  return <Picker mode="date" {...props} />
}

/** Un día y una hora (`YYYY-MM-DDTHH:mm`), en hora de Madrid como el resto de la app. */
export function DateTimePicker(props: PickerProps) {
  return <Picker mode="datetime" {...props} />
}
