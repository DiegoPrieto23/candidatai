import { useEffect } from 'react'
import { FolderSimpleIcon } from '@phosphor-icons/react'
import { useQueryClient } from '@tanstack/react-query'
import type { JobView } from '@/api/client'
import { keys } from '@/api/queries'
import { OpenFolderButton } from '@/components/OpenFolderButton'
import { InlineCode } from '@/components/States'

/**
 * Oferta ya enviada: la carpeta con la copia de lo que se envió (CV, carta, respuestas y un
 * README), en `data/documentos/candidaturas/`. La escribe el worker al marcarla como enviada.
 */
const RECHECK_MS = 5000
const RECHECK_TIMES = 12

/** Recién enviada: el worker la archiva en unos segundos; vuelve a pedir la ficha un rato. */
function useRecheckUntilArchived(job: JobView) {
  const client = useQueryClient()
  const waiting = job.stage === 'applied' && !job.archive_folder
  useEffect(() => {
    if (!waiting) return
    let times = 0
    const timer = setInterval(() => {
      times += 1
      if (times >= RECHECK_TIMES) clearInterval(timer)
      void client.invalidateQueries({ queryKey: keys.job(job.id) })
    }, RECHECK_MS)
    return () => clearInterval(timer)
  }, [waiting, client, job.id])
}

export function ArchivedApplication({ job }: { job: JobView }) {
  useRecheckUntilArchived(job)
  if (!job.archive_folder) {
    if (job.stage === 'closed') return null
    return (
      <p className="flex items-start gap-2 px-1 text-sm text-muted-foreground">
        <FolderSimpleIcon className="mt-0.5 size-4 shrink-0" aria-hidden />
        <span>
          <InlineCode text="Aún sin copia de lo enviado: la guarda el worker al marcarla como enviada. Para las de antes, `cai applications archive --all`." />
        </span>
      </p>
    )
  }
  return (
    <section
      aria-label="Candidatura archivada"
      className="flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-card px-5 py-4"
    >
      <div className="flex min-w-0 items-start gap-2.5 text-sm">
        <FolderSimpleIcon className="mt-0.5 size-5 shrink-0 text-muted-foreground" weight="duotone" aria-hidden />
        <span className="min-w-0">
          <span className="font-medium">Copia de lo que enviaste</span>
          <span className="block font-mono text-xs break-all text-muted-foreground">data/{job.archive_folder}</span>
        </span>
      </div>
      <OpenFolderButton
        folder="candidatura"
        jobId={job.id}
        label="Abrir carpeta"
        ariaLabel="Abrir la carpeta archivada de la candidatura"
      />
    </section>
  )
}
