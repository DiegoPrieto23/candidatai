import { Component, useEffect, useState, type ReactNode } from 'react'
import { Trans, useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { WarningCircleIcon } from '@phosphor-icons/react'
import { API_URL } from '@/api/client'
import { Button } from '@/components/ui/button'

const RELOADED_KEY = 'cai-chunk-reload'
const ISSUES_URL = 'https://github.com/DiegoPrieto23/candidatai/issues'

/** El navegador no pudo descargar el código de una página (`import()` de un chunk). */
function isChunkLoadError(error: unknown): boolean {
  return (
    error instanceof Error &&
    /dynamically imported module|Importing a module script failed|error loading dynamically/i.test(error.message)
  )
}

/**
 * Tras actualizar la app con la pestaña abierta, los chunks de la versión anterior ya no existen:
 * la primera vez se recarga sola (con `index.html` nuevo, que apunta a los nuevos). Si vuelve a
 * fallar enseguida, es otra cosa (la app parada): no se recarga en bucle.
 */
function reloadOnce(): boolean {
  try {
    const last = Number(sessionStorage.getItem(RELOADED_KEY) ?? 0)
    if (Date.now() - last < 10_000) return false
    sessionStorage.setItem(RELOADED_KEY, String(Date.now()))
  } catch {
    return false // sin almacenamiento no se puede evitar el bucle: mejor el aviso
  }
  window.location.reload()
  return true
}

/** ¿Contesta la app? Sin esto, el aviso no sabría si culpar a la app parada o a la página. */
function useApiAnswers(): boolean | null {
  const [answers, setAnswers] = useState<boolean | null>(null)
  useEffect(() => {
    const controller = new AbortController()
    fetch(`${API_URL}/status`, { cache: 'no-store', signal: controller.signal })
      .then((response) => setAnswers(response.ok))
      .catch(() => !controller.signal.aborted && setAnswers(false))
    return () => controller.abort()
  }, [])
  return answers
}

function Notice({ title, children, action }: { title: string; children: ReactNode; action: ReactNode }) {
  return (
    <div role="alert" className="flex flex-col items-start gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-5 sm:flex-row sm:items-center">
      <WarningCircleIcon className="size-6 shrink-0 text-destructive" weight="duotone" />
      <div className="min-w-0 flex-1">
        <p className="font-medium">{title}</p>
        <div className="mt-0.5 text-sm text-muted-foreground">{children}</div>
      </div>
      {action}
    </div>
  )
}

/** La app no contesta: está parada o se ha cerrado su ventana. Lo único útil es abrirla y recargar. */
function AppDown() {
  const { t } = useTranslation('nav', { keyPrefix: 'pageError' })
  return (
    <Notice
      title={t('down.title')}
      action={
        <Button variant="outline" size="sm" onClick={() => window.location.reload()}>
          {t('reload')}
        </Button>
      }
    >
      {t('down.body')}
    </Notice>
  )
}

/**
 * La página ha fallado al pintarse, con la app en marcha: recargar no lo arregla, así que no se
 * culpa a una actualización. Se ofrece volver a Inicio y se dice dónde está el detalle para avisar.
 */
function PageBroken() {
  const { t } = useTranslation('nav', { keyPrefix: 'pageError' })
  return (
    <Notice
      title={t('broken.title')}
      action={
        <Button asChild variant="outline" size="sm">
          <Link to="/">{t('broken.home')}</Link>
        </Button>
      }
    >
      <p>{t('broken.body')}</p>
      <p className="mt-1">
        <Trans
          t={t}
          i18nKey="broken.report"
          components={{
            kbd: <kbd className="rounded border bg-background px-1 font-mono text-xs" />,
            issues: <a href={ISSUES_URL} target="_blank" rel="noreferrer" className="font-medium text-primary underline-offset-4 hover:underline" />,
          }}
        />
      </p>
    </Notice>
  )
}

/** No llegó el código de la página: si la app no contesta, es eso; si contesta, la página falla. */
function ChunkFailed() {
  const answers = useApiAnswers()
  if (answers === null) return null // un instante, mientras se comprueba
  return answers ? <PageBroken /> : <AppDown />
}

type Failure = 'chunk' | 'render' | null
type Props = { children: ReactNode; /** La ruta: al cambiar, se vuelve a intentar. */ path: string }

/**
 * Si una página no se puede pintar (no llega su código o falla al montarse), el aviso sale en su
 * hueco y la barra lateral sigue funcionando; al ir a otra página se vuelve a intentar.
 */
export class PageErrorBoundary extends Component<Props, { failed: Failure; path: string }> {
  state: { failed: Failure; path: string } = { failed: null, path: this.props.path }

  static getDerivedStateFromError(error: unknown) {
    return { failed: isChunkLoadError(error) ? 'chunk' : 'render' }
  }

  static getDerivedStateFromProps(props: Props, state: { path: string }) {
    return props.path === state.path ? null : { failed: null, path: props.path }
  }

  componentDidCatch(error: unknown) {
    if (isChunkLoadError(error)) reloadOnce()
  }

  render() {
    if (this.state.failed === 'chunk') return <ChunkFailed />
    if (this.state.failed === 'render') return <PageBroken />
    return this.props.children
  }
}
