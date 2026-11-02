import { useState } from 'react'
import { FilePdfIcon } from '@phosphor-icons/react'
import { cn } from '@/lib/utils'

/**
 * La portada de un PDF en pequeño, que lo abre en otra pestaña. Es decorativa: quien la usa pone al
 * lado su enlace con nombre. Si la imagen no llega (PDF borrado), queda el icono.
 */
export function PdfCover({ href, src, className }: { href: string; src: string; className: string }) {
  const [failed, setFailed] = useState(false)
  return (
    <a href={href} target="_blank" rel="noreferrer" tabIndex={-1} aria-hidden className="shrink-0">
      {failed ? (
        <FilePdfIcon className="size-8 text-primary" weight="duotone" />
      ) : (
        <img
          src={src}
          alt=""
          loading="lazy"
          onError={() => setFailed(true)}
          className={cn(
            'aspect-[1/1.414] rounded-sm border bg-white object-cover object-top shadow-sm transition-shadow hover:shadow-md',
            className,
          )}
        />
      )}
    </a>
  )
}
