import { Suspense, useEffect, useLayoutEffect, useRef } from 'react'
import { Link, Outlet, useLocation, useNavigationType } from 'react-router'
import { useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { CircleNotchIcon, FlaskIcon, PlusIcon } from '@phosphor-icons/react'
import { keys, useAgentRuns, useStatus } from '@/api/queries'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import { PageErrorBoundary } from '@/components/PageErrorBoundary'
import { AgentTaskNotices } from '@/components/AgentTaskNotices'
import { ReadyNotices } from '@/components/ReadyNotices'
import { SearchRunNotice } from '@/components/SearchRunNotice'
import { UserPrompts } from '@/components/UserPrompts'
import { Brand, MobileNav, Sidebar } from '@/components/Sidebar'

/**
 * En segundo plano (fase 19): aviso mientras tu agente trabaja sin ventana. Cuando termina una
 * ejecución, refresca todo: el agente ha podido extraer ofertas, valorarlas o generar un CV.
 */
function BackgroundRunReminder() {
  const { t } = useTranslation('nav')
  const { data } = useAgentRuns()
  const { pathname } = useLocation()
  const client = useQueryClient()
  // La última que terminó (no un recuento: la lista solo trae las 20 más recientes).
  const lastFinished = (data?.runs ?? []).reduce(
    (last, r) => (r.finished_at && r.finished_at > last ? r.finished_at : last),
    '',
  )
  const previous = useRef<string | null>(null)
  useEffect(() => {
    if (previous.current !== null && lastFinished > previous.current) {
      void client.invalidateQueries({
        predicate: (q) => q.queryKey[0] !== keys.agent[0],
      })
    }
    previous.current = lastFinished
  }, [lastFinished, client])

  const current = data?.runs.find((r) => r.status === 'running') ?? data?.runs.find((r) => r.status === 'queued')
  if (!current || pathname === '/agente') return null
  return (
    <div
      role="status"
      className="flex items-center gap-3 rounded-xl border px-4 py-2.5 text-sm text-muted-foreground animate-in fade-in"
    >
      <CircleNotchIcon
        className={cn('size-4 shrink-0', current.status === 'running' && 'animate-spin')}
        weight="bold"
      />
      <p>
        {current.status === 'running' ? t('reminders.running') : t('reminders.queued')}: «{current.label}».{' '}
        <Link to="/agente" className="underline underline-offset-4">
          {t('reminders.seeProgress')}
        </Link>
      </p>
    </div>
  )
}

// Modo demo (fase 12.1): la carpeta de datos la creó `cai demo seed`. Fijo en todas las páginas.
function DemoBanner() {
  const { t } = useTranslation('nav')
  const { data } = useStatus()
  if (!data?.demo_mode) return null
  return (
    <div
      role="note"
      aria-label={t('demo.label')}
      className="border-b border-warning-border bg-warning text-warning-foreground"
    >
      <p className="flex max-w-6xl items-center gap-2 px-4 py-1.5 text-xs sm:px-8">
        <FlaskIcon className="size-4 shrink-0" weight="duotone" />
        <span>
          <span className="font-semibold">{t('demo.title')}</span> {t('demo.body')}
        </span>
      </p>
    </div>
  )
}

/** Mientras llega el chunk de una página: el hueco de su título, su entradilla y su contenido. */
function PageFallback() {
  const { t } = useTranslation('nav')
  return (
    <div role="status" aria-label={t('loadingPage')} className="grid gap-3">
      <Skeleton className="h-8 w-56" />
      <Skeleton className="h-4 w-full max-w-md" />
      <Skeleton className="mt-3 h-64 w-full rounded-xl" />
    </div>
  )
}

const MAIN_ID = 'contenido'

/**
 * El primer Tab de cada página: salta el menú y deja el foco en el contenido. Oculto hasta que lo
 * enfocas. Sin cambiar la URL, que el `#` no es una ruta de la app.
 */
function SkipLink() {
  const { t } = useTranslation('nav')
  return (
    <a
      href={`#${MAIN_ID}`}
      onClick={(e) => {
        e.preventDefault()
        document.getElementById(MAIN_ID)?.focus()
      }}
      className="sr-only rounded-md bg-background text-sm font-medium shadow-md outline-none focus:not-sr-only focus:fixed focus:px-3 focus:py-2 focus:top-3 focus:left-3 focus:z-50 focus-visible:ring-2 focus-visible:ring-ring"
    >
      {t('skipToContent')}
    </a>
  )
}

/**
 * Al ir a otra página se empieza por arriba: `BrowserRouter` deja el scroll de la anterior. Atrás y
 * Adelante, no, que ahí el navegador recuerda dónde estabas; ni lo que solo cambia la consulta (un
 * filtro de la Bandeja). En `useLayoutEffect`, antes de pintar y antes de los `useEffect` de la página
 * que llevan a un bloque concreto, que tienen la última palabra.
 */
function useScrollToTop(pathname: string) {
  const navigation = useNavigationType()
  const previous = useRef(pathname)
  useLayoutEffect(() => {
    if (previous.current === pathname) return
    previous.current = pathname
    if (navigation !== 'POP') window.scrollTo(0, 0)
  }, [pathname, navigation])
}

export function AppShell() {
  const { t } = useTranslation('nav')
  const { pathname } = useLocation()
  useScrollToTop(pathname)
  return (
    <div className="flex min-h-[100dvh]">
      <SkipLink />
      <Sidebar />
      <div className="min-w-0 flex-1">
        {/* En escritorio la navegación y «Nueva oferta» van en la barra lateral: arriba, solo el aviso de demo. */}
        <header className="sticky top-0 z-20 border-b bg-background/80 backdrop-blur-md empty:hidden supports-[backdrop-filter]:bg-background/65 lg:static lg:border-b-0 lg:bg-transparent lg:backdrop-blur-none">
          <DemoBanner />
          <div className="flex max-w-6xl items-center gap-3 px-4 py-2 sm:px-8 lg:hidden">
            <MobileNav />
            <Brand />
            <Button asChild size="sm" className="ml-auto shrink-0 active:translate-y-px">
              <Link to="/nueva">
                <PlusIcon weight="bold" />
                <span className="sr-only sm:not-sr-only">{t('header.newJob')}</span>
              </Link>
            </Button>
          </div>
        </header>
        {/* Destino de «Saltar al contenido»: sin anillo, que enmarcaría la página entera. */}
        <main id={MAIN_ID} tabIndex={-1} className="max-w-6xl px-4 pb-24 pt-6 outline-none sm:px-8 sm:pt-8">
          <div className="mb-6 empty:hidden">
            <BackgroundRunReminder />
          </div>
          <PageErrorBoundary path={pathname}>
            <Suspense fallback={<PageFallback />}>
              <Outlet />
            </Suspense>
          </PageErrorBoundary>
        </main>
      </div>
      {/* Abajo a la derecha, uno encima de otro: se ven al hacer scroll y no mueven la página. */}
      <div className="pointer-events-none fixed right-4 bottom-4 z-40 flex flex-col items-end gap-2">
        <UserPrompts />
        <SearchRunNotice />
        <AgentTaskNotices />
        <ReadyNotices />
      </div>
    </div>
  )
}
