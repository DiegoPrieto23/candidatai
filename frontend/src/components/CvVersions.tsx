/**
 * Las versiones del texto de un CV: de dónde sale cada una, qué cambió y «Volver a esta versión».
 * Volver no borra nada ni usa al agente: solo cambia cuál es la vigente.
 */
import { ArrowCounterClockwiseIcon, FilePdfIcon } from '@phosphor-icons/react'
import { useTranslation } from 'react-i18next'
import { fileUrls, type CvVersion, type SectionChange } from '@/api/client'
import { useCvHistory, useRestoreCvVersion } from '@/api/queries'
import { Reveal } from '@/components/Reveal'
import { Button } from '@/components/ui/button'
import { errorMessage } from '@/lib/errors'
import { formatDateTime } from '@/lib/labels'

function Change({ change }: { change: SectionChange }) {
  const { t } = useTranslation('cv', { keyPrefix: 'history' })
  const section = t(`sections.${change.section}`)
  return (
    <li className="space-y-1 text-sm">
      <p className="font-medium">{change.item ? `${section} · ${change.item}` : section}</p>
      {change.reordered && <p className="text-muted-foreground">{t('reordered')}</p>}
      {change.removed.map((text, i) => (
        <p key={`r${i}`} className="break-words rounded-sm bg-destructive/10 px-2 py-1">
          <span className="font-mono text-muted-foreground" aria-label={t('removed')}>− </span>
          <span className="line-through decoration-foreground/40">{text}</span>
        </p>
      ))}
      {change.added.map((text, i) => (
        <p key={`a${i}`} className="break-words rounded-sm bg-primary/10 px-2 py-1">
          <span className="font-mono text-muted-foreground" aria-label={t('added')}>+ </span>
          {text}
        </p>
      ))}
    </li>
  )
}

function Version({ version, jobId, canRestore }: { version: CvVersion; jobId: number; canRestore: boolean }) {
  const { t } = useTranslation('cv', { keyPrefix: 'history' })
  const restore = useRestoreCvVersion(jobId)
  const verified = version.verified === null ? 'unverified' : version.verified ? 'verified' : 'rejected'
  return (
    <li
      aria-label={t('aria', { date: formatDateTime(version.created_at) })}
      className="rounded-lg border bg-background p-4"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="flex flex-wrap items-center gap-2 text-sm font-medium">
            {t(`origin.${version.origin}`)}
            {version.current && (
              <span className="inline-flex h-5 items-center rounded-full bg-primary px-2 text-[0.7rem] font-medium text-primary-foreground">
                {t('current')}
              </span>
            )}
          </p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {formatDateTime(version.created_at)} · {t(verified)}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {version.render && (
            <Button asChild variant="outline" size="xs">
              <a href={fileUrls.renderPdf(version.render.render_id)} target="_blank" rel="noopener noreferrer">
                <FilePdfIcon /> {t('viewPdf')}
              </a>
            </Button>
          )}
          {canRestore && !version.current && (
            <Button
              type="button"
              variant="secondary"
              size="xs"
              disabled={restore.isPending}
              onClick={() => restore.mutate(version.document_id)}
            >
              <ArrowCounterClockwiseIcon /> {t('restore')}
            </Button>
          )}
        </div>
      </div>
      {version.instruction && (
        <p className="mt-2 break-words text-sm">
          <span className="text-muted-foreground">{t('asked')} </span>
          {version.instruction}
        </p>
      )}
      {version.note && <p className="mt-1 break-words text-sm text-muted-foreground">{version.note}</p>}
      {version.changes.length > 0 && (
        <Reveal label={t('changes', { count: version.changes.length })} className="mt-3" defaultOpen={version.current}>
          <ul className="space-y-3">
            {version.changes.map((change, i) => (
              <Change key={i} change={change} />
            ))}
          </ul>
        </Reveal>
      )}
      {restore.error && (
        <p role="alert" className="mt-2 text-sm text-destructive">
          {errorMessage(restore.error)}
        </p>
      )}
    </li>
  )
}

export function CvVersions({ jobId, canRestore }: { jobId: number; canRestore: boolean }) {
  const { t } = useTranslation('cv', { keyPrefix: 'history' })
  const history = useCvHistory(jobId)
  const versions = history.data?.versions ?? []
  // Con una sola no hay historia que contar. Si falla, el resto de la sección sigue sirviendo.
  if (versions.length < 2) return null
  return (
    <section aria-label={t('title')}>
      <Reveal label={`${t('title')} (${versions.length})`}>
        <ul className="space-y-3">
          {versions.map((version) => (
            <Version key={version.document_id} version={version} jobId={jobId} canRestore={canRestore} />
          ))}
        </ul>
      </Reveal>
    </section>
  )
}
