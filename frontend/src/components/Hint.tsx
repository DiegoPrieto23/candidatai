import type { ReactElement, ReactNode } from 'react'
import { InfoIcon } from '@phosphor-icons/react'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'

/**
 * Globo de ayuda (fase 27.1): sale al pasar el ratón y al enfocar con el teclado. Con `children`,
 * ese elemento es el disparador (tiene que aceptar ref y eventos: un `<span>` o un `<button>`, nunca
 * un `<button disabled>`, que no dispara eventos). Sin `children`, pone un icono ⓘ enfocable con
 * `label` como nombre accesible, para explicar un campo junto a su etiqueta.
 */
export function Hint({
  text,
  label,
  children,
  side = 'top',
  className,
}: {
  text: ReactNode
  label?: string
  children?: ReactElement
  side?: 'top' | 'right' | 'bottom' | 'left'
  className?: string
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        {children ?? (
          <button
            type="button"
            aria-label={label}
            className="inline-flex rounded-full text-muted-foreground outline-none hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50"
          >
            <InfoIcon className="size-3.5" weight="bold" aria-hidden />
          </button>
        )}
      </TooltipTrigger>
      <TooltipContent side={side} className={cn('max-w-xs text-left text-pretty', className)}>
        {text}
      </TooltipContent>
    </Tooltip>
  )
}
