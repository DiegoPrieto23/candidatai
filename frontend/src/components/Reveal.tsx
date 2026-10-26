import { useId, useState, type ReactNode } from 'react'
import { CaretDownIcon } from '@phosphor-icons/react'
import { cn } from '@/lib/utils'

/**
 * Lo secundario de una sección (opciones de diseño, versiones anteriores, el detalle de un dosier),
 * plegado tras un botón discreto. Lo de dentro no se monta hasta abrirlo; después solo se oculta,
 * para no perder lo que se esté escribiendo. `defaultOpen`: abierto de entrada (p. ej. con avisos).
 */
export function Reveal({
  label,
  children,
  className,
  defaultOpen = false,
}: {
  label: string
  children: ReactNode
  className?: string
  defaultOpen?: boolean
}) {
  const [open, setOpen] = useState(defaultOpen)
  const [mounted, setMounted] = useState(defaultOpen)
  const id = useId()
  // El espacio entre lo de dentro es el que pide quien lo usa (`space-y-*` de `className`).
  const spacing = className?.split(/\s+/).filter((c) => c.startsWith('space-y-')).join(' ') || 'space-y-4'
  return (
    <div className={cn('space-y-4', className)}>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => {
          setOpen(!open)
          setMounted(true)
        }}
        className="inline-flex items-center gap-1.5 rounded-sm text-sm font-medium text-muted-foreground outline-none hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50"
      >
        {label}
        <CaretDownIcon className={cn('size-3.5 transition-transform', open && 'rotate-180')} />
      </button>
      {mounted && (
        <div id={id} hidden={!open} className={spacing}>
          {children}
        </div>
      )}
    </div>
  )
}
