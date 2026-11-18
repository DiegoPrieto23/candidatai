import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { CaretRightIcon, PlayIcon } from '@phosphor-icons/react'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'

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

/** «Ver cómo se hace», plegado. Con menos movimiento, el fotograma fijo y un botón para reproducirla. */
export function DemoPlayer({ animated, still }: { animated: string; still?: string }) {
  const { t } = useTranslation('extension', { keyPrefix: 'demo' })
  const [playing, setPlaying] = useState(() => !prefersReducedMotion())
  const showStill = !playing && still

  return (
    <Collapsible className="group/demo">
      <CollapsibleTrigger className="inline-flex items-center gap-1 text-sm font-medium text-primary underline-offset-4 hover:underline">
        <CaretRightIcon className="size-3.5 transition-transform group-data-[state=open]/demo:rotate-90" aria-hidden />
        {t('show')}
      </CollapsibleTrigger>
      <CollapsibleContent className="pt-3">
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

/** La demostración en el idioma de la UI; nada si aún no está grabada. */
export function ExtensionDemo() {
  const { i18n } = useTranslation()
  const language = i18n.language.split('-')[0] ?? 'en'
  const animated = media(language, false)
  return animated ? <DemoPlayer animated={animated} still={media(language, true)} /> : null
}
