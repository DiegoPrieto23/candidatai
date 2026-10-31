import { useState } from 'react'
import { fileUrls } from '@/api/client'
import { cn } from '@/lib/utils'

/**
 * Icono de una web (un portal o una empresa). Lo sirve la app, que lo descarga una vez y lo guarda:
 * tu navegador no visita cada web al abrir «Dónde buscar». Sin icono (o sin web), la inicial del
 * nombre. `host` cambia la URL cuando cambia la web, para no ver el de antes.
 */
export function SiteIcon({ name, sourceId, host }: { name: string; sourceId: number; host: string | null }) {
  const [failed, setFailed] = useState(false)
  const box = 'grid size-9 shrink-0 place-items-center rounded-lg border bg-white dark:bg-white/95'
  if (!host || failed) {
    return (
      <span className={cn(box, 'bg-muted font-semibold text-muted-foreground dark:bg-muted')} aria-hidden>
        {name.trim().charAt(0).toUpperCase()}
      </span>
    )
  }
  return (
    <span className={box} aria-hidden>
      <img
        src={fileUrls.sourceIcon(sourceId, host)}
        alt=""
        width={20}
        height={20}
        loading="lazy"
        onError={() => setFailed(true)}
        className="size-5 object-contain"
      />
    </span>
  )
}
