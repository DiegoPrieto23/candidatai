import { useState } from 'react'
import { iconCandidates } from '@/lib/searches'
import { cn } from '@/lib/utils'

/**
 * Icono de una web (un portal o una empresa), que tu navegador carga de la propia web (sin
 * referer): prueba las rutas de `iconCandidates` en orden y, si ninguna carga, pone la inicial del
 * nombre.
 */
export function SiteIcon({ name, home }: { name: string; home: { origin: string; host: string } | null }) {
  const [attempt, setAttempt] = useState(0)
  const candidates = home ? iconCandidates(home) : []
  const box = 'grid size-9 shrink-0 place-items-center rounded-lg border bg-white dark:bg-white/95'
  if (attempt >= candidates.length) {
    return (
      <span className={cn(box, 'bg-muted font-semibold text-muted-foreground dark:bg-muted')} aria-hidden>
        {name.trim().charAt(0).toUpperCase()}
      </span>
    )
  }
  return (
    <span className={box} aria-hidden>
      <img
        key={candidates[attempt]}
        src={candidates[attempt]}
        alt=""
        width={20}
        height={20}
        loading="lazy"
        referrerPolicy="no-referrer"
        onError={() => setAttempt((n) => n + 1)}
        className="size-5 object-contain"
      />
    </span>
  )
}
