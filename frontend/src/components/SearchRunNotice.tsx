import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'
import { useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { CheckCircleIcon, CircleNotchIcon, MinusIcon, WarningIcon, XIcon } from '@phosphor-icons/react'
import { keys, useDismissSearchRun, useSearchRun } from '@/api/queries'
import { Button } from '@/components/ui/button'
import { notifyIfHidden } from '@/lib/notify'
import { cn } from '@/lib/utils'

/** Un tramo por portal: se ve de un vistazo cuánto queda sin leer ninguna cifra. */
function PortalProgress({ done, total }: { done: number; total: number }) {
  return (
    <span aria-hidden className="mt-2 flex gap-1">
      {Array.from({ length: total }, (_, index) => (
        <span key={index} className={cn('h-1 flex-1 rounded-sm', index < done ? 'bg-primary' : 'bg-foreground/10')} />
      ))}
    </span>
  )
}

/**
 * «Buscando ofertas…» mientras tu agente recorre los portales en su ventana, en cualquier página de
 * la app. Cambia cuando el agente dice que ha terminado o que no ha podido, y se queda hasta que lo
 * cierras: la búsqueda puede acabar cuando no estás mirando. Minimizado se queda en una pastilla, y
 * vuelve a abrirse solo cuando cambia de estado, para que no se te pase que ha terminado.
 */
export function SearchRunNotice() {
  const { t } = useTranslation('nav', { keyPrefix: 'searchRun' })
  const client = useQueryClient()
  const run = useSearchRun().data?.run ?? null
  const dismiss = useDismissSearchRun()
  const [minimized, setMinimized] = useState<string | null>(null)

  // Lo que llega mientras buscas se ve sin recargar: la bandeja, los recuentos, «última búsqueda».
  const progress = run ? `${run.id}:${run.status}:${run.portals_done}:${run.created}` : null
  const previous = useRef<string | null>(null)
  useEffect(() => {
    if (previous.current !== null && progress !== null && progress !== previous.current) {
      void client.invalidateQueries({ predicate: (q) => q.queryKey[0] !== keys.agent[0] })
    }
    previous.current = progress
  }, [progress, client])

  const finishedTitle = run?.status === 'finished' ? t(`${run.outcome ?? 'done'}.title`) : null
  const notified = useRef<number | null>(null)
  useEffect(() => {
    if (!run || !finishedTitle || notified.current === run.id) return
    // Al abrir la app con un aviso antiguo no hay nada nuevo que notificar: solo si lo viste buscando.
    if (previous.current?.startsWith(`${run.id}:running`)) notifyIfHidden(finishedTitle, t('notification'))
    notified.current = run.id
  }, [run, finishedTitle, t])

  if (!run) return null

  const counts = t('counts', { done: run.portals_done, total: run.portals_total, count: run.created })
  const problems = run.problems > 0 ? t('problems', { count: run.problems }) : null
  const running = run.status === 'running'
  const good = run.status === 'finished' && run.outcome === 'done'

  const state = `${run.id}:${run.status}`
  const icon = running ? (
    <CircleNotchIcon className="size-4 shrink-0 animate-spin text-primary" weight="bold" aria-hidden />
  ) : good ? (
    <CheckCircleIcon className="size-4 shrink-0 text-primary" weight="fill" aria-hidden />
  ) : (
    <WarningIcon className="size-4 shrink-0 text-warning-foreground" weight="fill" aria-hidden />
  )

  let title: string
  let body: string
  if (running) {
    title = t('running.title')
    body = t('running.body')
  } else if (run.status === 'stale') {
    title = t('stale.title')
    body = t('stale.body')
  } else if (run.outcome === 'no_browser') {
    title = t('no_browser.title')
    body = t('no_browser.body')
  } else if (run.outcome === 'stopped') {
    title = t('stopped.title')
    body = t('stopped.body')
  } else {
    title = t('done.title')
    body = t('done.body', { count: run.created, found: run.found })
  }

  if (minimized === state) {
    return (
      <button
        type="button"
        onClick={() => setMinimized(null)}
        aria-label={t('expand', { title })}
        className="pointer-events-auto inline-flex items-center gap-2 rounded-lg border bg-card px-3 py-2 text-sm font-medium shadow-lg outline-none transition-colors hover:bg-foreground/[0.03] focus-visible:ring-2 focus-visible:ring-ring"
      >
        {icon}
        {title}
        {running && (
          <span className="tabular text-xs font-normal text-muted-foreground">
            {run.portals_done}/{run.portals_total}
          </span>
        )}
      </button>
    )
  }

  return (
    <div
      role="status"
      className="pointer-events-auto flex w-80 max-w-[calc(100vw-2rem)] items-start gap-3 rounded-lg border bg-card p-3 text-sm shadow-lg animate-in fade-in slide-in-from-bottom-1 duration-200"
    >
      <span className="mt-0.5">{icon}</span>
      <div className="min-w-0 flex-1">
        <p className="font-medium">{title}</p>
        <p className="mt-0.5 text-muted-foreground">{body}</p>
        {(running || run.status === 'stale') && (
          <>
            <PortalProgress done={run.portals_done} total={run.portals_total} />
            <p className="tabular mt-1.5 text-xs text-muted-foreground">{counts}</p>
          </>
        )}
        {!running && problems && <p className="mt-1 text-xs text-warning-foreground">{problems}</p>}
        <div className="mt-2.5 flex flex-wrap gap-2 empty:hidden">
          {run.status === 'finished' && run.created > 0 && (
            <Button asChild size="sm" variant="outline" onClick={() => dismiss.mutate(run.id)}>
              <Link to="/bandeja">{t('seeInbox')}</Link>
            </Button>
          )}
        </div>
      </div>
      <div className="-mt-1 -mr-1 flex shrink-0">
        <Button variant="ghost" size="icon" className="size-7" aria-label={t('minimize')} onClick={() => setMinimized(state)}>
          <MinusIcon />
        </Button>
        <Button variant="ghost" size="icon" className="size-7" aria-label={t('close')} disabled={dismiss.isPending} onClick={() => dismiss.mutate(run.id)}>
          <XIcon />
        </Button>
      </div>
    </div>
  )
}
