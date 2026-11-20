import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { CaretRightIcon, PlayIcon } from '@phosphor-icons/react'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { cn } from '@/lib/utils'

/**
 * La animación del botón del navegador (abrir una oferta, pulsar el botón, verla en la Bandeja), en
 * cada idioma, más su fotograma fijo. Sale de `docs/img/<idioma>/anim/`, la misma que usan las
 * guías. Si aún no está grabada, el glob viene vacío y no se enseña nada.
 */
const MEDIA = import.meta.glob<string>('../../../docs/img/*/anim/extension{,-still}.webp', {
  eager: true,
  query: '?url',
  import: 'default',
})

function media(language: string, still: boolean): string | undefined {
  const name = still ? 'extension-still' : 'extension'
  const find = (lang: string) =>
    Object.entries(MEDIA).find(([path]) => path.endsWith(`/img/${lang}/anim/${name}.webp`))?.[1]
  // Si aún no está grabada en ese idioma, la de otro: el gesto es el mismo.
  return find(language) ?? find('en') ?? find('es')
}

function prefersReducedMotion(): boolean {
  return Boolean(window.matchMedia?.('(prefers-reduced-motion: reduce)').matches)
}

/** Plegada o abierta desde fuera: el enlace va en otro sitio (`DemoToggle`) y aquí solo la animación. */
type Controlled = { open: boolean; id: string }

/** «Ver cómo se hace», plegado. Con menos movimiento, el fotograma fijo y un botón para reproducirla. */
export function DemoPlayer({ animated, still, controlled }: { animated: string; still?: string; controlled?: Controlled }) {
  const { t } = useTranslation('extension', { keyPrefix: 'demo' })
  const [playing, setPlaying] = useState(() => !prefersReducedMotion())
  const showStill = !playing && still

  return (
    <Collapsible className="group/demo" open={controlled?.open}>
      {!controlled && (
        <CollapsibleTrigger className="inline-flex items-center gap-1 text-sm font-medium text-primary underline-offset-4 hover:underline">
          <CaretRightIcon className="size-3.5 transition-transform group-data-[state=open]/demo:rotate-90" aria-hidden />
          {t('show')}
        </CollapsibleTrigger>
      )}
      <CollapsibleContent id={controlled?.id} className={controlled ? undefined : 'pt-3'}>
        <figure className="grid gap-2">
          <img
            src={showStill ? still : animated}
            alt={t('alt')}
            width={900}
            height={563}
            loading="lazy"
            className="h-auto w-full max-w-xl rounded-lg border bg-muted"
          />
          {showStill && (
            <div>
              <Button type="button" variant="outline" size="sm" onClick={() => setPlaying(true)}>
                <PlayIcon />
                {t('play')}
              </Button>
            </div>
          )}
        </figure>
      </CollapsibleContent>
    </Collapsible>
  )
}

function useLanguage(): string {
  const { i18n } = useTranslation()
  return i18n.language.split('-')[0] ?? 'en'
}

/** La demostración en el idioma de la UI; nada si aún no está grabada. Con `controlled`, sin su enlace. */
export function ExtensionDemo({ controlled }: { controlled?: Controlled } = {}) {
  const language = useLanguage()
  const animated = media(language, false)
  return animated ? <DemoPlayer animated={animated} still={media(language, true)} controlled={controlled} /> : null
}

/** El enlace «Ver cómo se hace» suelto, para ponerlo junto a un título; nada si no hay animación. */
export function DemoToggle({ open, onToggle, controls }: { open: boolean; onToggle: () => void; controls: string }) {
  const { t } = useTranslation('extension', { keyPrefix: 'demo' })
  if (!media(useLanguage(), false)) return null
  return (
    <button
      type="button"
      aria-expanded={open}
      aria-controls={controls}
      onClick={onToggle}
      className="inline-flex shrink-0 items-center gap-1 text-sm font-medium text-primary underline-offset-4 hover:underline"
    >
      <CaretRightIcon className={cn('size-3.5 transition-transform', open && 'rotate-90')} aria-hidden />
      {t('show')}
    </button>
  )
}
