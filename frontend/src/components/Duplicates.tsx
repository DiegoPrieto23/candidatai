import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { CopyIcon, TrashIcon } from '@phosphor-icons/react'
import type { Schemas } from '@/api/client'
import { useDuplicateJobs, useEraseDuplicates } from '@/api/queries'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { BusyLabel } from '@/components/StableLabel'
import { errorMessage } from '@/lib/errors'

type Duplicate = Schemas['DuplicateView']

function DuplicateLine({ item }: { item: Duplicate }) {
  const { t } = useTranslation('erase', { keyPrefix: 'duplicates' })
  return (
    <li className="py-2">
      <span className="font-medium">{item.title}</span>
      <span className="text-muted-foreground"> · {item.company}</span>
      <p className="text-xs text-muted-foreground">
        {t('sameAs')}{' '}
        <Link to={`/jobs/${item.original_id}`} className="underline underline-offset-4 hover:text-foreground">
          {item.original_title}
        </Link>
        {item.keep_reason && <> · {t(`keep.${item.keep_reason}`)}</>}
      </p>
    </li>
  )
}

/**
 * En la Bandeja: las duplicadas que se guardaban antes (ya no se crean). Vista previa
 * con la lista y un borrado con confirmación corta; las que tienen algo propio se quedan.
 */
export function DuplicatesBanner() {
  const { t } = useTranslation('erase', { keyPrefix: 'duplicates' })
  const { data } = useDuplicateJobs()
  const erase = useEraseDuplicates()
  const [open, setOpen] = useState(false)
  const [done, setDone] = useState<string | null>(null)
  const items = data?.items ?? []
  const erasable = items.filter((item) => !item.keep_reason)
  const kept = items.filter((item) => item.keep_reason)

  if (done) {
    return (
      <div role="status" className="flex items-center gap-3 rounded-xl border bg-card px-4 py-2.5 text-sm">
        <CopyIcon className="size-[18px] shrink-0 text-muted-foreground" />
        <p className="min-w-0 flex-1">{done}</p>
        <Button size="xs" variant="ghost" onClick={() => setDone(null)}>
          {t('close')}
        </Button>
      </div>
    )
  }
  if (erasable.length === 0) return null

  const close = () => {
    setOpen(false)
    erase.reset()
  }
  const confirm = () =>
    erase.mutateAsync(erasable.map((item) => item.job_id)).then(
      (result) => {
        setOpen(false)
        setDone(t('done', { count: result.deleted_jobs, backup: result.backup ?? '' }))
      },
      () => undefined,
    )

  return (
    <section aria-label={t('bannerTitle', { count: erasable.length })} className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl border bg-card px-4 py-3 text-sm">
      <CopyIcon className="size-[18px] shrink-0 text-muted-foreground" weight="duotone" />
      <div className="min-w-0 flex-1">
        <h2 className="font-semibold">{t('bannerTitle', { count: erasable.length })}</h2>
        <p className="text-muted-foreground">{t('bannerText')}</p>
      </div>
      <Button size="sm" variant="outline" onClick={() => setOpen(true)}>
        {t('review')}
      </Button>
      <Dialog open={open} onOpenChange={(next) => !next && close()}>
        <DialogContent className="sm:max-w-xl">
          <DialogHeader>
            <DialogTitle>{t('title', { count: erasable.length })}</DialogTitle>
            <DialogDescription>{t('lead')}</DialogDescription>
          </DialogHeader>
          <ul aria-label={t('erasableList')} className="max-h-72 divide-y overflow-y-auto pr-1 text-sm">
            {erasable.map((item) => (
              <DuplicateLine key={item.job_id} item={item} />
            ))}
          </ul>
          {kept.length > 0 && (
            <div className="space-y-1 text-sm">
              <p className="font-medium">{t('keptTitle', { count: kept.length })}</p>
              <ul aria-label={t('keptTitle', { count: kept.length })} className="max-h-40 divide-y overflow-y-auto pr-1">
                {kept.map((item) => (
                  <DuplicateLine key={item.job_id} item={item} />
                ))}
              </ul>
            </div>
          )}
          <p className="text-xs text-muted-foreground">{t('backup')}</p>
          {erase.error != null && (
            <p role="alert" className="text-sm text-destructive">
              {errorMessage(erase.error)}
            </p>
          )}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={close}>
              {t('cancel')}
            </Button>
            <Button type="button" variant="destructive" disabled={erase.isPending} onClick={() => void confirm()}>
              <TrashIcon />
              <BusyLabel busy={erase.isPending} busyText={t('erasing')} text={t('erase', { count: erasable.length })} />
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  )
}
