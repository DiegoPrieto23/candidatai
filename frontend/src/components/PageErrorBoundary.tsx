import { Component, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { WarningCircleIcon } from '@phosphor-icons/react'
import { Button } from '@/components/ui/button'

const RELOADED_KEY = 'cai-chunk-reload'

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

function PageLoadFailed() {
  const { t } = useTranslation('nav')
  return (
    <div role="alert" className="flex flex-col items-start gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-5 sm:flex-row sm:items-center">
      <WarningCircleIcon className="size-6 shrink-0 text-destructive" weight="duotone" />
      <div className="min-w-0 flex-1">
        <p className="font-medium">{t('pageError.title')}</p>
        <p className="mt-0.5 text-sm text-muted-foreground">{t('pageError.body')}</p>
      </div>
      <Button variant="outline" size="sm" onClick={() => window.location.reload()}>
        {t('pageError.reload')}
      </Button>
    </div>
  )
}

type Props = { children: ReactNode; /** La ruta: al cambiar, se vuelve a intentar. */ path: string }

/**
 * Si una página no se puede pintar (no llega su código o falla al montarse), el aviso sale en su
 * hueco y la barra lateral sigue funcionando; al ir a otra página se vuelve a intentar.
 */
export class PageErrorBoundary extends Component<Props, { failed: boolean; path: string }> {
  state = { failed: false, path: this.props.path }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  static getDerivedStateFromProps(props: Props, state: { path: string }) {
    return props.path === state.path ? null : { failed: false, path: props.path }
  }

  componentDidCatch(error: unknown) {
    if (isChunkLoadError(error)) reloadOnce()
  }

  render() {
    return this.state.failed ? <PageLoadFailed /> : this.props.children
  }
}
