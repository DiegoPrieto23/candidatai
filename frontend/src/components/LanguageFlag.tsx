import { useId } from 'react'
import { cn } from '@/lib/utils'

/**
 * Bandera pequeña junto al nombre de un idioma (fase 23.6). En SVG: Windows no pinta los emojis
 * de banderas (enseña «ES»). Un idioma sin bandera no enseña nada.
 */
export function LanguageFlag({ language, className }: { language: string; className?: string }) {
  const id = useId()
  const box = cn('h-3 w-[18px] shrink-0 overflow-hidden rounded-[2px] ring-1 ring-foreground/15', className)
  if (language === 'es') {
    return (
      <svg viewBox="0 0 750 500" className={box} aria-hidden preserveAspectRatio="none">
        <rect width="750" height="500" fill="#AA151B" />
        <rect y="125" width="750" height="250" fill="#F1BF00" />
      </svg>
    )
  }
  if (language === 'en') {
    const clip = `${id}-uk`
    return (
      <svg viewBox="0 0 60 30" className={box} aria-hidden preserveAspectRatio="none">
        <clipPath id={clip}>
          <path d="M30,15 h30 v15 z v15 h-30 z h-30 v-15 z v-15 h30 z" />
        </clipPath>
        <rect width="60" height="30" fill="#012169" />
        <path d="M0,0 L60,30 M60,0 L0,30" stroke="#FFFFFF" strokeWidth="6" />
        <path d="M0,0 L60,30 M60,0 L0,30" clipPath={`url(#${clip})`} stroke="#C8102E" strokeWidth="4" />
        <path d="M30,0 v30 M0,15 h60" stroke="#FFFFFF" strokeWidth="10" />
        <path d="M30,0 v30 M0,15 h60" stroke="#C8102E" strokeWidth="6" />
      </svg>
    )
  }
  return null
}
