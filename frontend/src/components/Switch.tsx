import { cn } from '@/lib/utils'

/** Interruptor accesible (`role="switch"`): Plataformas y buzones de Alertas. */
export function Switch({
  checked,
  disabled,
  label,
  onChange,
}: {
  checked: boolean
  disabled?: boolean
  label: string
  onChange: (checked: boolean) => void
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        'relative inline-flex h-5 w-9 shrink-0 items-center rounded-full border transition-colors',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50',
        checked ? 'border-primary bg-primary' : 'border-input bg-muted',
      )}
    >
      <span
        className={cn(
          'inline-block size-3.5 rounded-full transition-transform',
          checked ? 'translate-x-[1.125rem] bg-primary-foreground' : 'translate-x-0.5 bg-muted-foreground',
        )}
      />
    </button>
  )
}
