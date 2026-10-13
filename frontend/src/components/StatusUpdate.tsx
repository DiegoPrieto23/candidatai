import { useState, type ReactNode } from 'react'
import {
  CalendarCheckIcon,
  ChatCircleTextIcon,
  CheckCircleIcon,
  ClipboardTextIcon,
  ConfettiIcon,
  HourglassLowIcon,
  SignOutIcon,
  XCircleIcon,
} from '@phosphor-icons/react'
import { useTranslation } from 'react-i18next'
import type { BoardCard, EventType, JobView } from '@/api/client'
import { useBoard } from '@/api/queries'
import { MoveDialog } from '@/components/MoveDialog'
import { Button } from '@/components/ui/button'
import { errorMessage } from '@/lib/errors'
import { eventLabel, STAGE_LABEL } from '@/lib/labels'
import { moveOptions, type MoveOption } from '@/lib/moves'
import { cn } from '@/lib/utils'

/** Etapas en las que se registra lo que va pasando con la candidatura. */
const STATUS_STAGES = new Set(['applied', 'in_process'])

/** Texto e icono de cada paso, en el orden en que suelen pasar. Los cierres, al final. */
type Step = 'reply_received' | 'interview_scheduled' | 'interview_done' | 'test_assigned' | 'offer_received' | 'accepted' | 'rejected' | 'withdrawn' | 'expired'

const STEPS: { event: Step; icon: ReactNode; tone?: 'good' | 'bad' }[] = [
  { event: 'reply_received', icon: <ChatCircleTextIcon /> },
  { event: 'interview_scheduled', icon: <CalendarCheckIcon /> },
  { event: 'interview_done', icon: <CheckCircleIcon /> },
  { event: 'test_assigned', icon: <ClipboardTextIcon /> },
  { event: 'offer_received', icon: <ConfettiIcon />, tone: 'good' },
  { event: 'accepted', icon: <ConfettiIcon />, tone: 'good' },
  { event: 'rejected', icon: <XCircleIcon />, tone: 'bad' },
  { event: 'withdrawn', icon: <SignOutIcon /> },
  { event: 'expired', icon: <HourglassLowIcon /> },
]

/**
 * «¿Qué ha pasado?»: botones para registrar cada paso de una candidatura enviada (respuesta,
 * entrevista, rechazo…). Cada uno abre el mismo diálogo que el tablero de Procesos, registra su
 * evento con fecha y nota, y la oferta cambia de etapa sola.
 */
export function StatusUpdate({ job }: { job: JobView }) {
  const { t } = useTranslation('status')
  const visible = job.stage !== null && STATUS_STAGES.has(job.stage)
  const board = useBoard()
  const [chosen, setChosen] = useState<MoveOption[] | null>(null)
  if (!visible || !job.stage) return null
  const card = {
    job_id: job.id,
    title: job.title,
    company: job.company,
    stage: job.stage,
    reopen_to: null,
  } as unknown as BoardCard
  const options = board.data ? moveOptions(card, board.data.moves) : []
  const byEvent = new Map(options.map((o) => [o.event, o]))
  const steps = STEPS.filter((s) => byEvent.has(s.event))
  const known = new Set<EventType>(STEPS.map((s) => s.event))
  const others = options.filter((o) => !known.has(o.event))

  return (
    <section aria-label={t('label')} className="rounded-xl border border-primary/30 bg-primary/[0.03] p-5 sm:p-6">
      <h2 className="font-semibold">{t('title')}</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        {t('hint', { stage: STAGE_LABEL[job.stage] })}
      </p>
      {board.isError ? (
        <p role="alert" className="mt-3 text-sm text-destructive">
          {t('loadFailed', { error: errorMessage(board.error) })}
        </p>
      ) : (
        <div className="mt-4 flex flex-wrap gap-2">
          {steps.map((step) => (
            <Button
              key={step.event}
              type="button"
              size="sm"
              variant="outline"
              disabled={board.isPending}
              onClick={() => setChosen([byEvent.get(step.event)!])}
              className={cn(
                step.tone === 'good' && 'border-emerald-600/40 text-emerald-700 dark:text-emerald-400',
                step.tone === 'bad' && 'border-destructive/40 text-destructive',
              )}
            >
              {step.icon}
              {t(`steps.${step.event}`)}
            </Button>
          ))}
          {others.map((option) => (
            <Button key={option.event} type="button" size="sm" variant="outline" onClick={() => setChosen([option])}>
              {eventLabel(option.event)}
            </Button>
          ))}
        </div>
      )}
      <MoveDialog card={chosen ? card : null} options={chosen ?? []} onOpenChange={(open) => !open && setChosen(null)} />
    </section>
  )
}
