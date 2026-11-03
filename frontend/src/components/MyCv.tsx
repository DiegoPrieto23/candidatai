import { useRef, useState, type ChangeEvent, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { CheckIcon, CopyIcon, FileArrowUpIcon, TrashIcon, WarningIcon } from '@phosphor-icons/react'
import type { UploadInfo } from '@/api/client'
import { useDeleteUpload, useTemplates, useUploadCv, useUploads } from '@/api/queries'
import { AgentButton } from '@/components/AgentButton'
import { Reveal } from '@/components/Reveal'
import { InlineCode } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { formatDateTime } from '@/lib/labels'
import { errorMessage } from '@/lib/errors'
import { BusyLabel } from '@/components/StableLabel'

const ACCEPT = '.docx,.pdf,.png,.jpg,.jpeg,.html'

function Chip({ children }: { children: ReactNode; tone: 'warning' }) {
  return (
    <span
      className="inline-flex h-5 items-center gap-1 rounded-full border border-warning-border bg-warning px-2 text-[0.7rem] font-medium whitespace-nowrap text-warning-foreground"
    >
      {children}
    </span>
  )
}

function formatSize(bytes: number): string {
  return bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1048576).toFixed(1)} MB`
}

function CopyCommand({ command }: { command: string }) {
  const { t } = useTranslation('templates', { keyPrefix: 'myCv' })
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(command)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      setCopied(false)
    }
  }
  return (
    <div className="flex items-center gap-2 rounded-lg border bg-muted/50 py-1.5 pr-1.5 pl-3">
      <code className="min-w-0 flex-1 truncate font-mono text-[0.8rem]" title={command}>
        {command}
      </code>
      <Button variant="ghost" size="xs" onClick={copy} aria-label={t('copyAria')}>
        {copied ? <CheckIcon /> : <CopyIcon />}
        <BusyLabel busy={copied} busyText={t('copied')} text={t('copy')} />
      </Button>
    </div>
  )
}

function PendingUpload({ upload }: { upload: UploadInfo }) {
  const { t } = useTranslation('templates', { keyPrefix: 'myCv' })
  const recreated = upload.format !== 'docx'
  return (
    <div className="space-y-2">
      <p className="text-sm text-foreground/80">{t('askAgent')}</p>
      {/* Se abre en una terminal: ves lo que hace el agente y lo apruebas tú. */}
      <AgentButton action="import-cv-template" upload={upload.name}>
        {t('convert')}
      </AgentButton>
      <Reveal label={t('orCopy')} className="space-y-2">
        <CopyCommand command={upload.agent_command} />
      </Reveal>
      {recreated && (
        <p className="flex items-start gap-2 text-xs leading-relaxed text-muted-foreground">
          <WarningIcon className="mt-0.5 size-3.5 shrink-0" weight="duotone" />
          <span>
            {t('recreated', { format: upload.format.toUpperCase() })}
          </span>
        </p>
      )}
    </div>
  )
}

function UploadCard({ upload }: { upload: UploadInfo }) {
  const { t } = useTranslation('templates', { keyPrefix: 'myCv' })
  const remove = useDeleteUpload()
  return (
    <li aria-label={upload.name} className="rounded-xl border bg-card p-4">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="flex flex-wrap items-center gap-2 font-medium">
            <span className="truncate">{upload.name}</span>
            <Chip tone="warning">{t('pending')}</Chip>
          </p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {formatSize(upload.size)} · {formatDateTime(upload.uploaded_at)}
          </p>
        </div>
        <Button
          variant="ghost"
          size="xs"
          onClick={() => remove.mutate(upload.name)}
          disabled={remove.isPending}
          aria-label={t('removeAria', { name: upload.name })}
        >
          <TrashIcon /> {t('remove')}
        </Button>
      </div>
      <PendingUpload upload={upload} />
    </li>
  )
}

/**
 * «Mi CV»: subir tu CV para convertirlo en plantilla. Aquí solo se queda lo que falta por convertir;
 * lo ya convertido es una plantilla más de la lista de abajo.
 */
export function MyCv() {
  const { t } = useTranslation('templates', { keyPrefix: 'myCv' })
  const input = useRef<HTMLInputElement>(null)
  const uploadsQuery = useUploads()
  const templates = useTemplates()
  const upload = useUploadCv()

  const onFile = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (file) upload.mutate(file)
    event.target.value = '' // permite volver a elegir el mismo fichero
  }
  const known = new Set((templates.data?.templates ?? []).map((tpl) => tpl.id))
  const uploads = uploadsQuery.data ?? []
  const pending = uploads.filter((item) => !item.template_id || !known.has(item.template_id))

  return (
    <section aria-labelledby="my-cv-title" className="mb-12">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div className="max-w-[65ch]">
          <h2 id="my-cv-title" className="text-lg font-semibold tracking-tight">
            {t('title')}
          </h2>
          <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
            {t('intro')}
          </p>
        </div>
        <input ref={input} type="file" accept={ACCEPT} onChange={onFile} className="sr-only" aria-label={t('file')} />
        <Button onClick={() => input.current?.click()} disabled={upload.isPending} className="active:translate-y-px">
          <FileArrowUpIcon /> <BusyLabel busy={upload.isPending} busyText={t('uploading')} text={t('upload')} />
        </Button>
      </div>
      {upload.isError && (
        <p role="alert" className="mb-4 text-sm text-destructive">
          <InlineCode text={errorMessage(upload.error)} />
        </p>
      )}

      {uploadsQuery.isPending ? (
        <Skeleton className="h-28 rounded-xl" />
      ) : uploads.length === 0 ? (
        <button
          type="button"
          onClick={() => input.current?.click()}
          className="flex w-full flex-col items-center gap-2 rounded-xl border border-dashed px-6 py-10 text-center text-sm text-muted-foreground transition-colors hover:border-foreground/30 hover:text-foreground"
        >
          <FileArrowUpIcon className="size-6 text-primary" weight="duotone" />
          <span className="font-medium text-foreground">{t('none')}</span>
          <span>{t('noneHint')}</span>
        </button>
      ) : (
        pending.length > 0 && (
          <ul className="space-y-4">
            {pending.map((item) => (
              <UploadCard key={item.name} upload={item} />
            ))}
          </ul>
        )
      )}
    </section>
  )
}
