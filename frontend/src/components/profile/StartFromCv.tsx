/** «Mi perfil» sin perfil: subir el CV y que tu agente lo rellene, sin escribir nada a mano. */
import { useRef, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { CheckCircleIcon, UploadSimpleIcon, UserCircleIcon } from '@phosphor-icons/react'
import { useSourceDocuments, useUploadSourceDocument } from '@/api/queries'
import { AgentButton } from '@/components/AgentButton'
import { Button } from '@/components/ui/button'
import { errorMessage } from '@/lib/errors'

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

export function StartFromCv() {
  const { t } = useTranslation('profileEditor', { keyPrefix: 'noProfile.start' })
  const { t: tAgent } = useTranslation('agent')
  const cvs = useSourceDocuments('cv')
  const upload = useUploadSourceDocument('cv')
  const input = useRef<HTMLInputElement>(null)
  const [error, setError] = useState<string | null>(null)
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
          <input
            ref={input}
            type="file"
            accept=".pdf,.docx,.txt,.md"
            className="sr-only"
            aria-label={t('fileLabel')}
            onChange={(e) => {
              const file = e.target.files?.[0]
              e.target.value = ''
              if (!file) return
              setError(null)
              upload.mutate(file, { onError: (err) => setError(errorMessage(err)) })
            }}
          />
          <div className="flex flex-wrap items-center gap-3">
            <Button
              type="button"
              size="sm"
              variant={latest ? 'outline' : 'default'}
              disabled={upload.isPending}
              onClick={() => input.current?.click()}
            >
              <UploadSimpleIcon />
              {upload.isPending ? t('uploading') : latest ? t('uploadAnother') : t('uploadButton')}
            </Button>
            {latest && (
              <span role="status" className="flex items-center gap-1.5 text-emerald-700 dark:text-emerald-400">
                <CheckCircleIcon className="size-4" weight="duotone" aria-hidden />
                {t('uploaded', { name: latest.name })}
              </span>
            )}
          </div>
          {error && (
            <p role="alert" className="text-destructive">
              {error}
            </p>
          )}
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
      <p className="mt-6 border-t pt-4 text-xs text-muted-foreground">{t('manual')}</p>
    </section>
  )
}
