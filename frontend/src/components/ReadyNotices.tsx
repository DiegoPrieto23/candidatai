import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { useQueryClient } from '@tanstack/react-query'
import { ArrowSquareOutIcon, CheckCircleIcon, XIcon } from '@phosphor-icons/react'
import { useTranslation } from 'react-i18next'
import { fileUrls, type JobCv, type ProcessView } from '@/api/client'
import { keys, useJob, useJobCv, useJobProcess } from '@/api/queries'
import { Button } from '@/components/ui/button'
import { POLL_MS, stopWatching, useWatches, type Watch, type WatchKind } from '@/lib/readyWatch'

interface Ready {
  id: string
  kind: WatchKind
  jobId: number
  url: string
}

const after = (iso: string, since: string) => Date.parse(iso) > Date.parse(since)

/** El PDF del CV guardado después de pulsar el botón: el elegido o, si no, el último. */
function readyCv(data: JobCv | undefined, since: string): string | null {
  const fresh = (data?.cv?.renders ?? []).filter((r) => r.pdf_path && after(r.created_at, since))
  const render = fresh.find((r) => r.selected) ?? fresh.at(-1)
  return render ? fileUrls.renderPdf(render.render_id) : null
}

function readyGuide(data: ProcessView | undefined, watch: Watch): string | null {
  const guide = data?.milestones.find((m) => m.id === watch.milestoneId)?.guide
  return guide && watch.milestoneId && after(guide.saved_at, watch.since)
    ? fileUrls.interviewGuide(watch.milestoneId)
    : null
}

/** Vuelve a pedir el CV o la ficha cada `POLL_MS` (también con la pestaña en segundo plano) y avisa
 * en cuanto hay algo nuevo. Al compartir la consulta con la ficha, la ficha se pone al día sola. */
function Watcher({ watch, onReady }: { watch: Watch; onReady: (ready: Ready) => void }) {
  const cv = useJobCv(watch.jobId, watch.kind === 'cv', POLL_MS)
  const process = useJobProcess(watch.jobId, watch.kind === 'guide', POLL_MS)
  const url = watch.kind === 'cv' ? readyCv(cv.data, watch.since) : readyGuide(process.data, watch)

  useEffect(() => {
    if (url) {
      stopWatching(watch.id)
      onReady({ id: `${watch.id}:${watch.since}`, kind: watch.kind, jobId: watch.jobId, url })
      return
    }
    const left = watch.until - Date.now()
    const timer = window.setTimeout(() => stopWatching(watch.id), Math.max(0, left))
    return () => window.clearTimeout(timer)
  }, [url, watch, onReady])
  return null
}

/** Notificación del sistema si la pestaña no está a la vista (y el permiso ya está dado). */
function notify(title: string, body: string) {
  if (typeof window === 'undefined' || !('Notification' in window)) return
  if (Notification.permission !== 'granted' || document.visibilityState === 'visible') return
  try {
    const n = new Notification(title, { body })
    n.onclick = () => {
      window.focus()
      n.close()
    }
  } catch {
    // Algunos navegadores no dejan crearlas fuera de un service worker: queda el aviso de la página.
  }
}

function Notice({ ready, onClose }: { ready: Ready; onClose: () => void }) {
  const { t } = useTranslation('agentButton', { keyPrefix: 'ready' })
  const job = useJob(ready.jobId)
  const title = job.data ? `${job.data.title} · ${job.data.company}` : t('job', { id: ready.jobId })
  return (
    <div
      role="status"
      className="pointer-events-auto flex w-80 max-w-[calc(100vw-2rem)] items-start gap-3 rounded-lg border bg-card p-3 text-sm shadow-lg"
    >
      <CheckCircleIcon className="mt-0.5 size-5 shrink-0 text-emerald-700 dark:text-emerald-400" weight="duotone" aria-hidden />
      <div className="min-w-0 flex-1 space-y-2">
        <div>
          <p className="font-medium">{t(ready.kind)}</p>
          <p className="truncate text-muted-foreground">{title}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button asChild size="sm">
            <a href={ready.url} target="_blank" rel="noreferrer" onClick={onClose}>
              <ArrowSquareOutIcon />
              {t('open')}
            </a>
          </Button>
          <Button asChild size="sm" variant="outline">
            <Link to={`/jobs/${ready.jobId}${ready.kind === 'guide' ? '?tab=process' : ''}`} onClick={onClose}>
              {t('show')}
            </Link>
          </Button>
        </div>
      </div>
      <Button variant="ghost" size="icon" className="-mt-1 -mr-1 size-7" aria-label={t('close')} onClick={onClose}>
        <XIcon />
      </Button>
    </div>
  )
}

/**
 * Avisos de «Tu CV está listo» y «Tu guía está lista» tras pulsar «Generar CV» o «Preparar»:
 * abajo a la derecha, con el PDF a un clic. El navegador no deja abrir una pestaña sin un clic
 * tuyo, así que no se abre sola.
 */
export function ReadyNotices() {
  const { t } = useTranslation('agentButton', { keyPrefix: 'ready' })
  const client = useQueryClient()
  const watches = useWatches()
  const [ready, setReady] = useState<Ready[]>([])

  const [onReady] = useState(() => (item: Ready) => {
    setReady((items) => (items.some((i) => i.id === item.id) ? items : [...items, item]))
    // La etapa (p. ej. «CV listo») y los recuentos también cambian.
    void client.invalidateQueries({ queryKey: keys.job(item.jobId) })
    void client.invalidateQueries({ queryKey: keys.status })
    notify(t(item.kind), t('notification'))
  })

  return (
    <>
      {watches.map((w) => (
        <Watcher key={`${w.id}:${w.since}`} watch={w} onReady={onReady} />
      ))}
      {ready.length > 0 && (
        <div className="pointer-events-none fixed right-4 bottom-4 z-40 flex flex-col items-end gap-2">
          {ready.map((item) => (
            <Notice key={item.id} ready={item} onClose={() => setReady((items) => items.filter((i) => i !== item))} />
          ))}
        </div>
      )}
    </>
  )
}
