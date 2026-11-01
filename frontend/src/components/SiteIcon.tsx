import { useEffect, useState } from 'react'
import { fileUrls } from '@/api/client'
import { cn } from '@/lib/utils'

/** Lo que tarda en volver a pedirlo: la app lo está descargando aparte (hasta unos segundos si la
 * web tarda en responder). */
export const ICON_RETRY_MS = 6000

/**
 * Icono de una web (un portal o una empresa). Lo sirve la app, que lo descarga una vez y lo guarda:
 * tu navegador no visita cada web al abrir «Dónde buscar». Sin icono (o sin web), la inicial del
 * nombre. `host` cambia la URL cuando cambia la web, para no ver el de antes.
 *
 * La primera vez la app responde sin icono mientras lo descarga: se vuelve a pedir una sola vez, al
 * rato. Si tampoco llega, se queda la inicial.
 */
export function SiteIcon({ name, sourceId, host }: { name: string; sourceId: number; host: string | null }) {
  const [state, setState] = useState<'first' | 'waiting' | 'retry' | 'failed'>('first')
  useEffect(() => {
    if (state !== 'waiting') return
    const timer = window.setTimeout(() => setState('retry'), ICON_RETRY_MS)
    return () => window.clearTimeout(timer)
  }, [state])
  const box = 'grid size-9 shrink-0 place-items-center rounded-lg border bg-white dark:bg-white/95'
  if (!host || state === 'waiting' || state === 'failed') {
    return (
      <span className={cn(box, 'bg-muted font-semibold text-muted-foreground dark:bg-muted')} aria-hidden>
        {name.trim().charAt(0).toUpperCase()}
      </span>
    )
  }
  const src = fileUrls.sourceIcon(sourceId, host)
  return (
    <span className={box} aria-hidden>
      <img
        key={state}
        src={state === 'retry' ? `${src}&retry=1` : src}
        alt=""
        width={20}
        height={20}
        loading="lazy"
        onError={() => setState(state === 'first' ? 'waiting' : 'failed')}
        className="size-5 object-contain"
      />
    </span>
  )
}
