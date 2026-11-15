/** «Mi perfil» sin perfil: subir el CV y que tu agente lo rellene, sin escribir nada a mano (sin
 * agente, «Empezar a mano», en `StartByHand`). */
import { useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { CheckCircleIcon, FileArrowUpIcon, UploadSimpleIcon, UserCircleIcon } from '@phosphor-icons/react'
import { useSourceDocuments, useUploadSourceDocument } from '@/api/queries'
import { AgentButton } from '@/components/AgentButton'
import { FileDropZone } from '@/components/FileDropZone'
import { Button } from '@/components/ui/button'
import { errorMessage } from '@/lib/errors'
import { cn } from '@/lib/utils'

const CV_FORMATS = '.pdf,.docx,.txt,.md'

function Step({ n, children }: { n: number; children: ReactNode }) {
  return (
    <li className="flex gap-3">
      <span aria-hidden className="grid size-6 shrink-0 place-items-center rounded-full border bg-background text-xs font-semibold">
        {n}
      </span>
      <div className="min-w-0 flex-1 space-y-3 pt-0.5">{children}</div>
    </li>
  )
}

/**
 * Subir el CV (a tus documentos, `cv/`) en una caja donde arrastrarlo o hacer clic; con uno ya
 * subido, la caja se queda en una línea con su nombre. Lo usan «Mi perfil» (sin perfil y en
 * «Importar información desde un CV») e Inicio («Primeros pasos»).
 */
export function UploadCv() {
  const { t } = useTranslation('profileEditor', { keyPrefix: 'noProfile.start' })
  const cvs = useSourceDocuments('cv')
  const upload = useUploadSourceDocument('cv')
  const [error, setError] = useState<string | null>(null)
  const latest = cvs.data?.[0]
  const label = upload.isPending ? t('uploading') : latest ? t('uploadAnother') : t('uploadButton')
  return (
    <div className="space-y-2">
      <FileDropZone
        accept={CV_FORMATS}
        label={t('fileLabel')}
        disabled={upload.isPending}
        onWrongType={() => setError(t('wrongType'))}
        onFile={(file) => {
          setError(null)
          upload.mutate(file, { onError: (err) => setError(errorMessage(err)) })
        }}
        className={latest ? 'px-4 py-3' : 'px-6 py-8'}
      >
        {(dragging) => {
          // Sin `onClick`: su clic llega a la caja, que abre el selector.
          const button = (
            <Button type="button" size="sm" variant={latest ? 'outline' : 'default'} disabled={upload.isPending}>
              <UploadSimpleIcon />
              {label}
            </Button>
          )
          if (latest)
            // Ya hay CV: la caja se encoge a una línea, pero se puede soltar otro encima.
            return (
              <div className="flex flex-wrap items-center justify-between gap-3">
                {dragging ? (
                  <span className="text-sm font-medium text-primary">{t('dropHere')}</span>
                ) : (
                  <span role="status" className="flex min-w-0 items-center gap-1.5 text-sm text-emerald-700 dark:text-emerald-400">
                    <CheckCircleIcon className="size-4 shrink-0" weight="duotone" aria-hidden />
                    <span className="truncate">{t('uploaded', { name: latest.name })}</span>
                  </span>
                )}
                {button}
              </div>
            )
          return (
            <div className="flex flex-col items-center gap-2 text-center">
              <FileArrowUpIcon
                className={cn('size-8 text-primary transition-transform', dragging && '-translate-y-0.5')}
                weight="duotone"
                aria-hidden
              />
              <p className="font-medium">{dragging ? t('dropHere') : t('dropOr')}</p>
              <p className="text-xs text-muted-foreground">{t('formats')}</p>
              <div className="mt-1">{button}</div>
            </div>
          )
        }}
      </FileDropZone>
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
    </div>
  )
}

export function StartFromCv() {
  const { t } = useTranslation('profileEditor', { keyPrefix: 'noProfile.start' })
  const { t: tAgent } = useTranslation('agent')
  const cvs = useSourceDocuments('cv')
  const latest = cvs.data?.[0]

  return (
    <section aria-labelledby="start-from-cv" className="rounded-xl border bg-card p-5 sm:p-6">
      <div className="mb-5 flex items-start gap-3">
        <UserCircleIcon className="size-8 shrink-0 text-primary" weight="duotone" aria-hidden />
        <div>
          <h2 id="start-from-cv" className="text-lg font-semibold tracking-tight">
            {t('title')}
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">{t('intro')}</p>
        </div>
      </div>
      <ol className="grid gap-5 text-sm">
        <Step n={1}>
          <p>{t('upload')}</p>
          <UploadCv />
        </Step>
        <Step n={2}>
          <p>{t('agent')}</p>
          <AgentButton action="create-profile" primary={Boolean(latest)}>
            {tAgent('actions.create-profile')}
          </AgentButton>
        </Step>
        <Step n={3}>
          <p>{t('review')}</p>
        </Step>
      </ol>
    </section>
  )
}
