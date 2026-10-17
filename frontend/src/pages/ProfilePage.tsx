import { FileTextIcon, FolderIcon, WarningIcon } from '@phosphor-icons/react'
import { Trans, useTranslation } from 'react-i18next'
import type { ContextFileInfo, ContextStatus } from '@/api/client'
import { useContextStatus } from '@/api/queries'
import { AgentButton } from '@/components/AgentButton'
import { OpenFolderButton } from '@/components/OpenFolderButton'
import { ErrorState } from '@/components/States'
import { Skeleton } from '@/components/ui/skeleton'
import { dateFormatter, formatNumber } from '@/lib/labels'
import { cn } from '@/lib/utils'

function formatSize(bytes: number): string {
  return bytes < 1024 ? `${bytes} B` : `${formatNumber(bytes / 1024, { minimumFractionDigits: 1, maximumFractionDigits: 1 })} KB`
}

function formatWhen(iso: string): string {
  return dateFormatter({ day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(iso))
}

function FileState({ file }: { file: ContextFileInfo }) {
  const { t } = useTranslation('profile', { keyPrefix: 'state' })
  const [label, tone] = !file.exists
    ? [t('missing'), 'text-muted-foreground']
    : file.empty
      ? [t('empty'), 'text-amber-700 dark:text-amber-400']
      : [t('filled'), 'text-emerald-700 dark:text-emerald-400']
  return <span className={cn('text-xs font-medium', tone)}>{label}</span>
}

function ContextFiles({ files }: { files: ContextFileInfo[] }) {
  const { t } = useTranslation('profile')
  return (
    <ul className="divide-y rounded-xl border bg-card">
      {files.map((file) => (
        <li key={file.section} className="grid gap-1 px-4 py-3">
          <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
            <span className="flex items-center gap-2 font-medium">
              <FileTextIcon className="size-4 text-muted-foreground" aria-hidden />
              {t(`sections.${file.section}.title`)}
            </span>
            <FileState file={file} />
          </div>
          <p className="text-sm text-muted-foreground">{t(`sections.${file.section}.hint`)}</p>
          <p className="font-mono text-xs text-muted-foreground">
            data/{file.path}
            {file.exists && (
              <>
                {' · '}
                {formatSize(file.size_bytes)}
                {file.modified_at && ` · ${formatWhen(file.modified_at)}`}
              </>
            )}
          </p>
          {file.warnings.map((warning) => (
            <p key={warning} className="flex items-start gap-1.5 text-xs text-amber-700 dark:text-amber-400">
              <WarningIcon className="mt-0.5 size-3.5 shrink-0" aria-hidden />
              {warning.replace(/^[a-z_]+: /, '')}
            </p>
          ))}
        </li>
      ))}
    </ul>
  )
}

function DocumentFolders({ folders }: { folders: ContextStatus['folders'] }) {
  const { t } = useTranslation('profile')
  return (
    <ul className="divide-y rounded-xl border bg-card">
      {folders.map((folder) => (
        <li key={folder.name} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3">
          <span className="grid gap-0.5">
            <span className="flex items-center gap-2 font-mono text-sm">
              <FolderIcon className="size-4 text-muted-foreground" aria-hidden />
              {folder.name}/
            </span>
            <span className="text-sm text-muted-foreground">{t(`folders.${folder.name}`)}</span>
          </span>
          <span className="text-xs text-muted-foreground">
            {t('files', { count: folder.files })}
          </span>
        </li>
      ))}
    </ul>
  )
}

/** El estilo de `InlineCode`, como componente para `Trans`. */
function InlineCodeTag({ children }: { children?: React.ReactNode }) {
  return <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em] text-foreground">{children}</code>
}

export function ProfilePage() {
  const { t } = useTranslation('profile')
  const status = useContextStatus()
  const code = <InlineCodeTag />

  let body
  if (status.isPending) {
    body = (
      <div className="grid gap-3">
        <Skeleton className="h-48" />
        <Skeleton className="h-40" />
      </div>
    )
  } else if (status.isError) {
    body = <ErrorState error={status.error} onRetry={() => status.refetch()} />
  } else {
    body = (
      <div className="grid gap-10">
        <section aria-labelledby="contexto" className="grid gap-3">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 id="contexto" className="text-lg font-semibold tracking-tight">
                {t('context')}
              </h2>
              <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                <Trans
                  t={t}
                  i18nKey="contextIntro"
                  components={{ strong: <strong className="font-medium text-foreground" />, code }}
                />
              </p>
            </div>
            <OpenFolderButton folder="contexto" ariaLabel={t('openContext')} />
          </div>
          <ContextFiles files={status.data.files} />
        </section>
        <section aria-labelledby="documentos" className="grid gap-3">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 id="documentos" className="text-lg font-semibold tracking-tight">
                {t('documents')}
              </h2>
              <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                <Trans t={t} i18nKey="documentsIntro" components={{ code }} />
              </p>
            </div>
            <OpenFolderButton folder="documentos" ariaLabel={t('openDocuments')} />
          </div>
          <DocumentFolders folders={status.data.folders} />
        </section>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-3xl animate-in fade-in duration-300">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold tracking-tight">{t('title')}</h1>
        <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
          <Trans t={t} i18nKey="intro" components={{ code }} />
        </p>
        {/* Fase 25.2: skill `expand`. Pregunta antes de escribir, así que solo en terminal. */}
        <div className="mt-4 grid gap-2">
          <AgentButton action="expand" variant="outline">
            {t('expand')}
          </AgentButton>
          <p className="text-xs leading-relaxed text-muted-foreground">{t('expandHint')}</p>
        </div>
      </div>
      {body}
    </div>
  )
}
