import type { ReactNode } from 'react'
import { CheckIcon } from '@phosphor-icons/react'
import { cn } from '@/lib/utils'

/**
 * Opciones que se marcan y desmarcan como chips (selección múltiple). Cada chip es una casilla de
 * verdad, oculta: el lector de pantalla y el teclado la tratan como tal. Quien la usa pone el nombre
 * del grupo (`labelledBy` o `label`).
 */
export function ChipChoices<V extends string>({
  value,
  options,
  onChange,
  disabled,
  label,
  labelledBy,
  describedBy,
}: {
  value: readonly V[]
  options: readonly { value: V; label: string }[]
  /** El valor nuevo, en el orden de `options`. */
  onChange: (value: V[], changed: { value: V; label: string; checked: boolean }) => void
  disabled?: boolean
  label?: string
  labelledBy?: string
  describedBy?: string
}) {
  return (
    <div role="group" aria-label={label} aria-labelledby={labelledBy} aria-describedby={describedBy} className="flex flex-wrap items-center gap-1.5">
      {options.map((option) => {
        const checked = value.includes(option.value)
        return (
          <label
            key={option.value}
            className={cn(
              'inline-flex cursor-pointer items-center gap-1.5 rounded-full border px-3 py-0.5 text-sm whitespace-nowrap transition-colors select-none',
              'has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring has-[:disabled]:cursor-default has-[:disabled]:opacity-60',
              checked
                ? 'border-primary/45 bg-accent font-medium text-accent-foreground'
                : 'border-input bg-card text-foreground hover:border-ring',
            )}
          >
            <input
              type="checkbox"
              className="sr-only"
              checked={checked}
              disabled={disabled}
              onChange={(e) => {
                const next = options.filter((o) => (o.value === option.value ? e.target.checked : value.includes(o.value))).map((o) => o.value)
                onChange(next, { ...option, checked: e.target.checked })
              }}
            />
            {checked && <CheckIcon className="-ml-0.5 size-3.5" weight="bold" aria-hidden />}
            {option.label}
          </label>
        )
      })}
    </div>
  )
}

/** Una fila de la franja con su nombre a la izquierda (como las de etiquetas). */
export function StripRow({ id, icon, label, children }: { id: string; icon: ReactNode; label: string; children: ReactNode }) {
  return (
    <div className="grid gap-x-4 gap-y-2 px-5 py-3 sm:grid-cols-[7rem_minmax(0,1fr)]">
      <span id={id} className="flex items-center gap-2 pt-1 text-sm text-muted-foreground">
        {icon}
        {label}
      </span>
      <div className="flex min-h-8 min-w-0 flex-wrap items-center">{children}</div>
    </div>
  )
}
