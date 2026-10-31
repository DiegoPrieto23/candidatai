/**
 * Elementos plegables de las listas de «Mi perfil»: cada empresa, proyecto, formación,
 * certificación, sección o historia arranca plegada (solo su cabecera) y se despliega pulsándola.
 * El borrador vive en `useBlockEditor`, así que plegar no pierde cambios.
 */
import type { ReactNode } from 'react'
import { CaretRightIcon } from '@phosphor-icons/react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'

/** Una tarjeta plegable con borde de color: icono, título, resumen de una línea y sus controles. */
export function FoldItem({
  label,
  title,
  summary,
  icon,
  controls,
  open,
  onOpenChange,
  children,
}: {
  label: string
  title: string
  summary?: string
  icon: ReactNode
  controls: ReactNode
  open: boolean
  onOpenChange: (open: boolean) => void
  children: ReactNode
}) {
  return (
    <Collapsible open={open} onOpenChange={onOpenChange} asChild>
      <article aria-label={label} className="grid rounded-none border border-l-4 border-l-primary/70 bg-background/60 shadow-xs">
        <div className="flex items-center justify-between gap-2 bg-primary/[0.06] pr-2">
          <h3 className="min-w-0 flex-1">
            <CollapsibleTrigger className="group flex w-full min-w-0 items-center gap-2 rounded-none px-4 py-2.5 text-left outline-none hover:bg-primary/[0.05] focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:ring-inset">
              <CaretRightIcon
                className="size-4 shrink-0 text-muted-foreground transition-transform group-data-[state=open]:rotate-90"
                weight="bold"
                aria-hidden
              />
              <span className="shrink-0 text-primary [&_svg]:size-[18px]" aria-hidden>
                {icon}
              </span>
              <span className="grid min-w-0">
                <span className="truncate font-semibold">{title}</span>
                {summary && <span className="truncate text-xs font-normal text-muted-foreground">{summary}</span>}
              </span>
            </CollapsibleTrigger>
          </h3>
          {controls}
        </div>
        <CollapsibleContent className="grid gap-4 border-t p-4">{children}</CollapsibleContent>
      </article>
    </Collapsible>
  )
}

/** «Desplegar todo» o «Plegar todo», según estén ya todos abiertos. */
export function FoldAllButton({ allOpen, onClick }: { allOpen: boolean; onClick: () => void }) {
  const { t } = useTranslation('profileEditor')
  return (
    <Button type="button" size="sm" variant="ghost" onClick={onClick}>
      {allOpen ? t('fold.collapseAll') : t('fold.expandAll')}
    </Button>
  )
}
