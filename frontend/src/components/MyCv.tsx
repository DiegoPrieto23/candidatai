import { useRef, useState, type ChangeEvent, type ReactNode } from 'react'
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
import { InlineCode } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { formatDateTime } from '@/lib/labels'
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
      <Button variant="ghost" size="xs" onClick={copy} aria-label="Copiar la petición para tu agente">
        {copied ? <CheckIcon /> : <CopyIcon />}
        {copied ? 'Copiado' : 'Copiar'}
      </Button>
    </div>
  )
}

function Page({ src, alt, note }: { src: string | null; alt: string; note?: string }) {
  return (
    <figure className="min-w-0">
      <figcaption className="mb-1.5 text-xs font-medium text-muted-foreground">{alt}</figcaption>
      <div className="aspect-[210/297] overflow-hidden rounded-md border bg-white">
        {src ? (
          <a href={src} target="_blank" rel="noopener noreferrer">
            <img src={src} alt={alt} loading="lazy" className="size-full object-cover object-top" />
          </a>
        ) : (
          <span className="grid size-full place-items-center px-3 text-center text-xs text-muted-foreground">
            <span className="flex flex-col items-center gap-2">
              <ImageIcon className="size-6" />
              {note ?? 'Sin vista'}
            </span>
          </span>
        )}
      </div>
    </figure>
  )
}

function PendingUpload({ upload }: { upload: UploadInfo }) {
  const recreated = upload.format !== 'docx'
  return (
    <div className="space-y-2">
      <p className="text-sm text-foreground/80">
        Pídele a tu agente que lo convierta en plantilla (una sola vez; después no gasta cuota):
      </p>
      <CopyCommand command={upload.agent_command} />
      {recreated && (
        <p className="flex items-start gap-2 text-xs leading-relaxed text-muted-foreground">
          <WarningIcon className="mt-0.5 size-3.5 shrink-0" weight="duotone" />
          <span>
            Desde {upload.format.toUpperCase()} el agente recrea el diseño en HTML: se parecerá mucho, pero no será
            exacto, y solo dará PDF. Necesita un agente que vea imágenes. Si tienes el Word, súbelo: se conserva
            tal cual.
          </span>
        </p>
      )}
    </div>
  )
}

function ImportedUpload({ template, isDefault }: { template: TemplateInfo; isDefault: boolean }) {
  const setDefault = useSetDefaultTemplate()
  const conflicts = setDefault.data?.conflicts ?? []
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3 sm:max-w-md">
        <Page
          src={template.has_source_preview ? fileUrls.templateSource(template.id) : null}
          alt="Original"
          note="Sin vista del original"
        />
        <Page
          src={fileUrls.templateRealPreview(template.id)}
          alt={template.engine === 'html' ? 'Recreación con tu perfil' : 'Con tu perfil'}
        />
      </div>
      {template.engine === 'html' && (
        <p className="text-xs text-muted-foreground">
          Plantilla html: solo PDF. Si un portal pide Word, renderiza ese CV con una plantilla docx.
        </p>
      )}
      <p className="text-xs text-muted-foreground">
        La vista con tu perfil es orientativa (los primeros logros de cada experiencia); la primera vez tarda unos
        segundos. Cada CV a medida lo redacta tu agente para la oferta.
      </p>
      <div className="flex flex-wrap items-center gap-2">
        {isDefault ? (
          <Chip tone="primary">
            <StarIcon weight="fill" /> Plantilla por defecto
          </Chip>
        ) : (
          <Button
            size="sm"
            onClick={() => setDefault.mutate(template.id)}
            disabled={setDefault.isPending}
            className="active:translate-y-px"
          >
            <StarIcon /> {setDefault.isPending ? 'Guardando…' : 'Usar por defecto'}
          </Button>
        )}
      </div>
      {setDefault.isError && (
        <p role="alert" className="text-sm text-destructive">
          <InlineCode text={setDefault.error.message} />
        </p>
      )}
      {conflicts.length > 0 && (
        <ul aria-label="Reglas que eligen otra plantilla" className="space-y-1 text-sm text-muted-foreground">
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
  const remove = useDeleteUpload()
  return (
    <li aria-label={upload.name} className="rounded-xl border bg-card p-4">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="flex flex-wrap items-center gap-2 font-medium">
            <span className="truncate">{template ? template.name : upload.name}</span>
            {template ? <Chip>Tu CV</Chip> : <Chip tone="warning">Pendiente de importar</Chip>}
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
            aria-label={`Quitar ${upload.name}`}
          >
            <TrashIcon /> Quitar
          </Button>
        )}
      </div>
      {template ? <ImportedUpload template={template} isDefault={isDefault} /> : <PendingUpload upload={upload} />}
    </li>
  )
}

/** «Mi CV»: el camino principal para usar tu propio diseño (fase 08.3). */
export function MyCv() {
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
  const byId = new Map((templates.data?.templates ?? []).map((t) => [t.id, t]))
  const uploads = uploadsQuery.data ?? []

  return (
    <section aria-labelledby="my-cv-title" className="mb-12">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div className="max-w-[65ch]">
          <h2 id="my-cv-title" className="text-lg font-semibold tracking-tight">
            Mi CV
          </h2>
          <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
            Sube tu CV y tu agente lo convierte una vez en plantilla. A partir de ahí, cada CV a medida sale con tu
            diseño y tu orden de secciones, con el texto adaptado a la oferta desde tu perfil.
          </p>
        </div>
        <input ref={input} type="file" accept={ACCEPT} onChange={onFile} className="sr-only" aria-label="Fichero del CV" />
        <Button onClick={() => input.current?.click()} disabled={upload.isPending} className="active:translate-y-px">
          <FileArrowUpIcon /> {upload.isPending ? 'Subiendo…' : 'Subir mi CV'}
        </Button>
      </div>
      {upload.isError && (
        <p role="alert" className="mb-4 text-sm text-destructive">
          <InlineCode text={upload.error.message} />
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
          <span className="font-medium text-foreground">Aún no has subido tu CV</span>
          <span>Mejor en Word (.docx): el diseño se conserva exacto. Máximo 10 MB.</span>
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
