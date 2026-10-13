import { useTranslation } from 'react-i18next'
import type { Stage } from '@/api/client'
import { STAGE_LABEL } from '@/lib/labels'
import { cn } from '@/lib/utils'

// Un solo acento: la intensidad crece a medida que la oferta avanza por el embudo.
const TONE: Record<Stage, string> = {
  pending_detail: 'border-dotted border-input text-muted-foreground/80 bg-transparent',
  pending_extraction: 'border-dashed border-input text-muted-foreground bg-transparent',
  pending_triage: 'border-input text-foreground bg-background/60',
  approved: 'border-primary/25 bg-accent text-accent-foreground',
  cv_ready: 'border-primary/35 bg-accent text-accent-foreground',
  applied: 'border-transparent bg-primary/85 text-primary-foreground',
  in_process: 'border-transparent bg-primary text-primary-foreground',
  closed: 'border-transparent bg-muted text-muted-foreground line-through decoration-1',
}

export function StageBadge({ stage, className }: { stage: Stage | null; className?: string }) {
  const { t } = useTranslation()
  if (!stage) {
    return <span className={cn('text-xs text-muted-foreground', className)}>{t('noStage')}</span>
  }
  return (
    <span
      className={cn(
        'inline-flex h-6 items-center whitespace-nowrap rounded-full border px-2.5 text-xs font-medium',
        TONE[stage],
        className,
      )}
    >
      {STAGE_LABEL[stage]}
    </span>
  )
}
