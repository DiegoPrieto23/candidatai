import { useEffect, useState } from 'react'
import { ArrowSquareOutIcon, ArrowsClockwiseIcon, CaretDownIcon, LinkBreakIcon, XIcon } from '@phosphor-icons/react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { useCheckOpenJobs, useClosureSuspects, useJobEvent } from '@/api/queries'
import { AgentButton } from '@/components/AgentButton'
import { BusyLabel } from '@/components/StableLabel'
import { Button } from '@/components/ui/button'
import { errorMessage } from '@/lib/errors'
import { formatDate } from '@/lib/labels'
import { cn } from '@/lib/utils'

/** Lo que tarda el worker en vaciar la cola, más o menos: mientras, la lista se recarga sola. */
const WATCH_MS = 3 * 60 * 1000

/**
 * En la Bandeja: las ofertas abiertas antes de enviar que pueden estar cerradas o caducadas (las
 * marca la comprobación diaria, la antigüedad o el agente). Nunca se cierran solas: se descartan
 * todas de una vez o se abren una a una. Además, «Comprobar ahora» (el worker) y «Revisar ofertas
 * caducadas» (el agente, en el navegador del usuario, para las aprobadas y con CV).
 */
export function ClosureBanner() {
  const { t } = useTranslation('signals', { keyPrefix: 'closureBanner' })
  const [watching, setWatching] = useState(false)
  const { data } = useClosureSuspects(watching)
  const check = useCheckOpenJobs()
  const event = useJobEvent()
  const [open, setOpen] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [discarding, setDiscarding] = useState(false)
  const [discardError, setDiscardError] = useState<string | null>(null)

  useEffect(() => {
    if (!watching) return
    const timer = window.setTimeout(() => setWatching(false), WATCH_MS)
    return () => window.clearTimeout(timer)
  }, [watching])

  if (!data) return null
  const items = data.items
  const count = items.length

  const discardAll = async () => {
    setDiscarding(true)
    setDiscardError(null)
    // De una en una: SQLite no agradece escrituras a la vez.
    for (const item of items) {
      try {
        await event.mutateAsync({ jobId: item.job_id, body: { type: 'discarded', reason: 'closed' } })
      } catch (err) {
        setDiscardError(errorMessage(err))
      }
    }
    setDiscarding(false)
    setConfirming(false)
  }

  return (
    <section
      aria-label={t('label')}
      className={cn(
        'rounded-xl border px-4 py-3 text-sm',
        count > 0 ? 'border-warning-border bg-warning text-warning-foreground' : 'bg-card',
      )}
    >
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <div className="min-w-0 flex-1">
          <h2 className="flex items-center gap-2 font-semibold">
            <LinkBreakIcon className="size-[18px] shrink-0" weight="duotone" />
            {count > 0 ? t('title', { count }) : t('titleNone')}
          </h2>
          <p className={cn('mt-0.5 text-xs', count > 0 ? 'opacity-80' : 'text-muted-foreground')}>
            {t('intro')}
            {data.unverified_important > 0 && ` ${t('unverified', { count: data.unverified_important })}`}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            className="bg-background/70"
            disabled={check.isPending}
            onClick={() => check.mutate(undefined, { onSuccess: () => setWatching(true) })}
          >
            <ArrowsClockwiseIcon className={cn(check.isPending && 'animate-spin')} />
            <BusyLabel busy={check.isPending} busyText={t('checking')} text={t('checkNow')} />
          </Button>
          <AgentButton action="review-expired">{t('review')}</AgentButton>
        </div>
      </div>

      {check.data && (
        <p role="status" className="mt-2 text-xs">
          {t('queued', { stale: check.data.stale, queued: check.data.queued })}
        </p>
      )}
      {check.error && (
        <p role="alert" className="mt-2 text-xs text-destructive">
          {errorMessage(check.error)}
        </p>
      )}

      {count > 0 && (
        <>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <Button size="xs" variant="ghost" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
              <CaretDownIcon className={cn('transition-transform', open && 'rotate-180')} />
              {open ? t('hide') : t('show', { count })}
            </Button>
            {confirming ? (
              <>
                <span>{t('confirm', { count })}</span>
                <Button size="xs" disabled={discarding} onClick={() => void discardAll()}>
                  <BusyLabel busy={discarding} busyText={t('discarding')} text={t('confirmYes')} />
                </Button>
                <Button size="xs" variant="ghost" disabled={discarding} onClick={() => setConfirming(false)}>
                  {t('cancel')}
                </Button>
              </>
            ) : (
              <Button size="xs" variant="outline" className="bg-background/70" onClick={() => setConfirming(true)}>
                <XIcon weight="bold" />
                {t('discardAll', { count })}
              </Button>
            )}
          </div>
          {discardError && (
            <p role="alert" className="mt-2 text-xs text-destructive">
              {discardError}
            </p>
          )}
          {open && (
            <ul className="mt-2 divide-y divide-warning-border/60">
              {items.map((item) => (
                <li key={item.job_id} className="py-2">
                  <Link to={`/jobs/${item.job_id}`} className="font-medium underline-offset-4 hover:underline">
                    {item.title}
                  </Link>
                  <span className="opacity-80"> · {item.company}</span>
                  <p className="text-xs opacity-80">
                    {t('line', {
                      detail: item.detail.charAt(0).toUpperCase() + item.detail.slice(1),
                      since: formatDate(item.since),
                    })}{' '}
                    {item.url && (
                      <a
                        href={item.url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 underline underline-offset-4"
                      >
                        {t('view')}
                        <ArrowSquareOutIcon className="size-3.5" aria-hidden />
                      </a>
                    )}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  )
}
