import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { useBoard, useCreateMilestone } from '@/api/queries'
import { MilestoneForm } from '@/components/MilestoneForm'
import { milestoneBody } from '@/lib/milestoneDraft'
import { ErrorState } from '@/components/States'
import { Combobox } from '@/components/ui/combobox'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { STAGE_LABEL } from '@/lib/labels'

/**
 * Alta de un hito desde el calendario: se elige la oferta (de los procesos abiertos, con búsqueda) y se rellena el
 * mismo formulario que en la ficha, con la fecha del día o de la hora pulsada.
 */
export function AddMilestoneDialog({ date, onClose }: { date: string | null; onClose: () => void }) {
  return (
    <Dialog open={date !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-xl">
        {date !== null && <AddMilestone date={date} onDone={onClose} />}
      </DialogContent>
    </Dialog>
  )
}

function AddMilestone({ date, onDone }: { date: string; onDone: () => void }) {
  const { t } = useTranslation('calendar', { keyPrefix: 'add' })
  const board = useBoard()
  const create = useCreateMilestone()
  const cards = (board.data?.columns ?? []).filter((c) => c.stage !== 'closed').flatMap((c) => c.cards)
  const [jobId, setJobId] = useState<number | null>(null)
  const card = cards.find((c) => c.job_id === jobId) ?? null

  return (
    <div className="grid gap-4">
      <DialogHeader>
        <DialogTitle>{t('title')}</DialogTitle>
        <DialogDescription>{t('description')}</DialogDescription>
      </DialogHeader>
      {board.isPending ? (
        <Skeleton className="h-9" />
      ) : board.isError ? (
        <ErrorState error={board.error} onRetry={() => board.refetch()} />
      ) : cards.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {t('none')}{' '}
          <Link to="/procesos" className="underline underline-offset-4" onClick={onDone}>
            {t('toBoard')}
          </Link>
        </p>
      ) : (
        <>
          <div className="space-y-1.5">
            <Label htmlFor="add-milestone-job">{t('job')}</Label>
            <Combobox
              id="add-milestone-job"
              label={t('job')}
              value={jobId === null ? null : String(jobId)}
              onChange={(value) => setJobId(Number(value))}
              options={cards.map((c) => ({
                value: String(c.job_id),
                label: c.company,
                description: c.title,
                meta: STAGE_LABEL[c.stage],
              }))}
              placeholder={t('pickJob')}
              searchLabel={t('searchJob')}
              noMatch={(query) => t('noMatch', { query })}
            />
          </div>
          {card && (
            <MilestoneForm
              stage={card.stage}
              initialDate={date}
              pending={create.isPending}
              error={create.error}
              onCancel={onDone}
              onSubmit={(draft, startsAt) =>
                create.mutate({ jobId: card.job_id, body: milestoneBody(draft, startsAt) }, { onSuccess: onDone })
              }
            />
          )}
        </>
      )}
    </div>
  )
}
