import { FolderOpenIcon } from '@phosphor-icons/react'
import { useTranslation } from 'react-i18next'
import { useOpenFolder, type FolderKind } from '@/api/queries'
import { CopyButton } from '@/components/CopyButton'
import { Button } from '@/components/ui/button'
import { errorMessage } from '@/lib/errors'

/**
 * Abre una carpeta de datos en el explorador de archivos. Si no se puede (otro sistema, la API
 * no corre en tu sesión), enseña la ruta para copiarla.
 */
export function OpenFolderButton({
  folder,
  jobId,
  label,
  ariaLabel,
}: {
  folder: FolderKind
  jobId?: number
  label?: string
  ariaLabel?: string
}) {
  const { t } = useTranslation()
  const open = useOpenFolder()
  const result = open.data
  return (
    <div className="grid justify-items-start gap-1.5">
      <Button
        type="button"
        variant="outline"
        size="sm"
        aria-label={ariaLabel}
        disabled={open.isPending}
        onClick={() => open.mutate({ folder, ...(jobId ? { job_id: jobId } : {}) })}
      >
        <FolderOpenIcon />
        {label ?? t('folder.open')}
      </Button>
      {result && !result.opened && (
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground" role="status">
          <span>{t('folder.notOpened')}</span>
          <code className="rounded bg-muted px-1.5 py-0.5 font-mono break-all">{result.path}</code>
          <CopyButton text={result.path} label={t('copy.path')} />
        </div>
      )}
      {open.isError && (
        <p className="text-xs text-destructive" role="alert">
          {errorMessage(open.error)}
        </p>
      )}
    </div>
  )
}
