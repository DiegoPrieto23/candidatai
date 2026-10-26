import { useRef, useState, type ChangeEvent, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import {
  CheckIcon,
  CopyIcon,
  FileArrowUpIcon,
  ImageIcon,
  StarIcon,
  TrashIcon,
  WarningIcon,
} from '@phosphor-icons/react'
import { fileUrls, type TemplateInfo, type UploadInfo } from '@/api/client'
import {
  useDefaultTemplate,
  useDeleteUpload,
  useSetDefaultTemplate,
  useTemplates,
  useUploadCv,
  useUploads,
} from '@/api/queries'
import { AgentButton } from '@/components/AgentButton'
import { Reveal } from '@/components/Reveal'
import { InlineCode } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { formatDateTime } from '@/lib/labels'
import { errorMessage } from '@/lib/errors'
import { cn } from '@/lib/utils'

const ACCEPT = '.docx,.pdf,.png,.jpg,.jpeg,.html'

function Chip({ children, tone = 'plain' }: { children: ReactNode; tone?: 'plain' | 'primary' | 'warning' }) {
  return (
    <span
      className={cn(
        'inline-flex h-5 items-center gap-1 rounded-full px-2 text-[0.7rem] font-medium whitespace-nowrap',
        tone === 'primary' && 'bg-primary text-primary-foreground',
        tone === 'warning' && 'border border-warning-border bg-warning text-warning-foreground',
        tone === 'plain' && 'text-foreground/75 ring-1 ring-input ring-inset',
      )}
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
        {copied ? t('copied') : t('copy')}
      </Button>
    </div>
  )
}

function Page({ src, alt, note }: { src: string | null; alt: string; note?: string }) {
  const { t } = useTranslation('templates', { keyPrefix: 'myCv' })
  // Si la imagen no se puede hacer (p. ej. sin perfil), su aviso en vez del icono de imagen rota.
  const [failed, setFailed] = useState(false)
  return (
    <figure className="min-w-0">
      <figcaption className="mb-1.5 text-xs font-medium text-muted-foreground">{alt}</figcaption>
      <div className="aspect-[210/297] overflow-hidden rounded-md border bg-white">
        {src && !failed ? (
          <a href={src} target="_blank" rel="noopener noreferrer">
            <img
              src={src}
              alt={alt}
              loading="lazy"
              onError={() => setFailed(true)}
              className="size-full object-cover object-top"
            />
          </a>
        ) : (
          <span className="grid size-full place-items-center px-3 text-center text-xs text-muted-foreground">
            <span className="flex flex-col items-center gap-2">
              <ImageIcon className="size-6" />
              {note ?? t('noPreview')}
            </span>
          </span>
        )}
      </div>
    </figure>
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

function ImportedUpload({ template, isDefault }: { template: TemplateInfo; isDefault: boolean }) {
  const { t } = useTranslation('templates', { keyPrefix: 'myCv' })
  const setDefault = useSetDefaultTemplate()
  const conflicts = setDefault.data?.conflicts ?? []
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3 sm:max-w-md">
        <Page
          src={template.has_source_preview ? fileUrls.templateSource(template.id) : null}
          alt={t('original')}
          note={t('noOriginal')}
        />
        <Page
          key={fileUrls.templateRealPreview(template.id)}
          src={fileUrls.templateRealPreview(template.id)}
          alt={template.engine === 'html' ? t('recreation') : t('withProfile')}
          note={t('noRealPreview')}
        />
      </div>
      {template.engine === 'html' && (
        <p className="text-xs text-muted-foreground">
          {t('htmlOnly')}
        </p>
      )}
      <p className="text-xs text-muted-foreground">
        {t('previewHint')}
      </p>
      <div className="flex flex-wrap items-center gap-2">
        {isDefault ? (
          <Chip tone="primary">
            <StarIcon weight="fill" /> {t('default')}
          </Chip>
        ) : (
          <Button
            size="sm"
            onClick={() => setDefault.mutate(template.id)}
            disabled={setDefault.isPending}
            className="active:translate-y-px"
          >
            <StarIcon /> {setDefault.isPending ? t('saving') : t('useDefault')}
          </Button>
        )}
      </div>
      {setDefault.isError && (
        <p role="alert" className="text-sm text-destructive">
          <InlineCode text={errorMessage(setDefault.error)} />
        </p>
      )}
      {conflicts.length > 0 && (
        <ul aria-label={t('conflicts')} className="space-y-1 text-sm text-muted-foreground">
          {conflicts.map((conflict) => (
            <li key={conflict}>
              <InlineCode text={conflict} />
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function UploadCard({
  upload,
  template,
  isDefault,
}: {
  upload: UploadInfo
  template: TemplateInfo | undefined
  isDefault: boolean
}) {
  const { t } = useTranslation('templates', { keyPrefix: 'myCv' })
  const remove = useDeleteUpload()
  return (
    <li aria-label={upload.name} className="rounded-xl border bg-card p-4">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="flex flex-wrap items-center gap-2 font-medium">
            <span className="truncate">{template ? template.name : upload.name}</span>
            {template ? <Chip>{t('yourCv')}</Chip> : <Chip tone="warning">{t('pending')}</Chip>}
          </p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {upload.name} · {formatSize(upload.size)} · {formatDateTime(upload.uploaded_at)}
          </p>
        </div>
        {!template && (
          <Button
            variant="ghost"
            size="xs"
            onClick={() => remove.mutate(upload.name)}
            disabled={remove.isPending}
            aria-label={t('removeAria', { name: upload.name })}
          >
            <TrashIcon /> {t('remove')}
          </Button>
        )}
      </div>
      {template ? <ImportedUpload template={template} isDefault={isDefault} /> : <PendingUpload upload={upload} />}
    </li>
  )
}

/** «Mi CV»: el camino principal para usar tu propio diseño (fase 08.3). */
export function MyCv() {
  const { t } = useTranslation('templates', { keyPrefix: 'myCv' })
  const input = useRef<HTMLInputElement>(null)
  const uploadsQuery = useUploads()
  const templates = useTemplates()
  const defaultTemplate = useDefaultTemplate()
  const upload = useUploadCv()

  const onFile = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (file) upload.mutate(file)
    event.target.value = '' // permite volver a elegir el mismo fichero
  }
  const byId = new Map((templates.data?.templates ?? []).map((tpl) => [tpl.id, tpl]))
  const uploads = uploadsQuery.data ?? []

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
          <FileArrowUpIcon /> {upload.isPending ? t('uploading') : t('upload')}
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
        <ul className="space-y-4">
          {uploads.map((item) => {
            const template = item.template_id ? byId.get(item.template_id) : undefined
            return (
              <UploadCard
                key={item.name}
                upload={item}
                template={template}
                isDefault={!!template && defaultTemplate.data?.template_id === template.id}
              />
            )
          })}
        </ul>
      )}
    </section>
  )
}
