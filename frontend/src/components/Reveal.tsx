import { useState, type ReactNode } from 'react'
import { CaretDownIcon } from '@phosphor-icons/react'
import { cn } from '@/lib/utils'

/**
 * Lo secundario de una sección (opciones de diseño, versiones anteriores, el detalle de un dosier),
 * plegado tras un botón discreto. Lo de dentro no se monta hasta abrirlo.
 */
export function Reveal({
  label,
  children,
  className,
}: {
  label: string
  children: ReactNode
  className?: string
}) {
  const [open, setOpen] = useState(false)
  return (
    <div className={cn('space-y-4', className)}>
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        className="inline-flex items-center gap-1.5 rounded-sm text-sm font-medium text-muted-foreground outline-none hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50"
      >
        {label}
        <CaretDownIcon className={cn('size-3.5 transition-transform', open && 'rotate-180')} />
      </button>
      {open && children}
    </div>
  )
}
