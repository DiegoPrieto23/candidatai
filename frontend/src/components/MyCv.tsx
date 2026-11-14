import { useEffect, useId, useRef, useState, type ChangeEvent, type DragEvent, type FormEvent, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { CheckIcon, CircleNotchIcon, CopyIcon, FileArrowUpIcon, TrashIcon, WarningIcon } from '@phosphor-icons/react'
import type { UploadInfo } from '@/api/client'
import { useDeleteUpload, useTemplates, useUploadCv, useUploads } from '@/api/queries'
import { AgentButton } from '@/components/AgentButton'
import { Reveal } from '@/components/Reveal'
import { InlineCode } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { formatDateTime } from '@/lib/labels'
import { errorMessage } from '@/lib/errors'
import { cn } from '@/lib/utils'
import { useTemplateText } from '@/lib/templateText'
import { nextTemplateName, setConverting, useConverting } from '@/lib/convertingUploads'
import { BusyLabel } from '@/components/StableLabel'

const ACCEPT = '.docx,.pdf,.png,.jpg,.jpeg,.html'
const EXTENSIONS = ACCEPT.split(',')


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

function Converting({ upload }: { upload: UploadInfo }) {
  const { t } = useTranslation('templates', { keyPrefix: 'myCv' })
  return (
    <div role="status" className="flex flex-wrap items-center gap-3 rounded-lg bg-muted/50 p-3">
      <CircleNotchIcon className="size-5 shrink-0 animate-spin text-primary motion-reduce:animate-none" aria-hidden />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium">{t('converting')}</p>
        <p className="text-xs text-muted-foreground">{t('convertingHint')}</p>
      </div>
      <Button variant="ghost" size="xs" onClick={() => setConverting(upload.name, false)}>
        {t('stopWaiting')}
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
      <AgentButton action="import-cv-template" upload={upload.name} onStarted={() => setConverting(upload.name, true)}>
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

function UploadCard({ upload, isConverting }: { upload: UploadInfo; isConverting: boolean }) {
  const { t } = useTranslation('templates', { keyPrefix: 'myCv' })
  const remove = useDeleteUpload()
  return (
    <li aria-label={upload.name} className="rounded-xl border bg-card p-4">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="flex flex-wrap items-center gap-2 font-medium">
            <span className="truncate">{upload.template_name ?? upload.name}</span>
            {!isConverting && <Chip tone="warning">{t('pending')}</Chip>}
          </p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {upload.template_name ? `${upload.name} · ` : ''}
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
      {isConverting ? <Converting upload={upload} /> : <PendingUpload upload={upload} />}
    </li>
  )
}

/** Antes de subirlo: el nombre de la plantilla, con «Mi CV» (o el siguiente libre) ya puesto. */
function NameStep({
  file,
  suggested,
  busy,
  onCancel,
  onContinue,
}: {
  file: File
  suggested: string
  busy: boolean
  onCancel: () => void
  onContinue: (name: string) => void
}) {
  const { t } = useTranslation('templates', { keyPrefix: 'myCv' })
  const inputId = useId()
  const [name, setName] = useState(suggested)
  const chosen = name.trim() || suggested
  const submit = (event: FormEvent) => {
    event.preventDefault()
    onContinue(chosen)
  }
  return (
    <form onSubmit={submit} aria-label={t('nameStep')} className="mb-4 space-y-3 rounded-xl border bg-card p-4">
      <p className="text-sm text-muted-foreground">
        <span className="font-medium text-foreground">{file.name}</span> · {formatSize(file.size)}
      </p>
      <div className="grid max-w-sm gap-1.5">
        <label htmlFor={inputId} className="text-sm font-medium">
          {t('nameLabel')}
        </label>
        <Input id={inputId} value={name} maxLength={80} autoFocus onChange={(e) => setName(e.target.value)} />
      </div>
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={busy}>
          <BusyLabel busy={busy} busyText={t('uploading')} text={t('continueWith', { name: chosen })} />
        </Button>
        <Button type="button" variant="ghost" disabled={busy} onClick={onCancel}>
          {t('cancel')}
        </Button>
      </div>
    </form>
  )
}

/**
 * «Mi CV»: subir tu CV para convertirlo en plantilla. Aquí solo se queda lo que falta por convertir;
 * lo ya convertido es una plantilla más de la lista de abajo. Se elige el fichero (o se arrastra),
 * se le pone nombre y tu agente lo convierte; mientras, la tarjeta dice que lo está haciendo.
 */
export function MyCv() {
  const { t } = useTranslation('templates', { keyPrefix: 'myCv' })
  const text = useTemplateText()
  const input = useRef<HTMLInputElement>(null)
  const convertingNow = useConverting()
  const waiting = Object.keys(convertingNow).length > 0
  const uploadsQuery = useUploads(waiting)
  const templates = useTemplates(waiting)
  const upload = useUploadCv()
  const [chosenFile, setChosenFile] = useState<File | null>(null)
  const [dragging, setDragging] = useState(false)
  const [wrongType, setWrongType] = useState(false)

  const choose = (file: File | undefined) => {
    if (!file) return
    upload.reset()
    const ok = EXTENSIONS.some((ext) => file.name.toLowerCase().endsWith(ext))
    setWrongType(!ok)
    setChosenFile(ok ? file : null)
  }
  const onFile = (event: ChangeEvent<HTMLInputElement>) => {
    choose(event.target.files?.[0])
    event.target.value = '' // permite volver a elegir el mismo fichero
  }
  const onDrop = (event: DragEvent) => {
    event.preventDefault()
    setDragging(false)
    choose(event.dataTransfer.files?.[0])
  }
  const onDragOver = (event: DragEvent) => {
    if (!event.dataTransfer.types.includes('Files')) return
    event.preventDefault()
    setDragging(true)
  }
  const known = new Set((templates.data?.templates ?? []).map((tpl) => tpl.id))
  const uploads = uploadsQuery.data ?? []
  const pending = uploads.filter((item) => !item.template_id || !known.has(item.template_id))
  // Ya convertida (o retirada): deja de esperarla.
  const pendingNames = pending.map((item) => item.name).join('/')
  useEffect(() => {
    if (!uploadsQuery.isSuccess) return
    // Los nombres de las subidas no llevan «/»: sirve de separador.
    const still = new Set(pendingNames.split('/'))
    for (const name of Object.keys(convertingNow)) if (!still.has(name)) setConverting(name, false)
  }, [uploadsQuery.isSuccess, pendingNames, convertingNow])
  const suggested = nextTemplateName(t('defaultName'), [
    ...(templates.data?.templates ?? []).map((tpl) => text.name(tpl)),
    ...pending.map((item) => item.template_name ?? ''),
  ])

  return (
    <section
      aria-labelledby="my-cv-title"
      className={cn('-m-3 mb-9 rounded-2xl p-3 transition-colors', dragging && 'bg-accent/60 ring-2 ring-primary/40 ring-dashed')}
      onDragOver={onDragOver}
      onDragLeave={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setDragging(false)
      }}
      onDrop={onDrop}
    >
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
          <FileArrowUpIcon /> {t('upload')}
        </Button>
      </div>
      {dragging && (
        <p role="status" className="mb-4 text-sm font-medium text-primary">
          {t('dropHere')}
        </p>
      )}
      {(upload.isError || wrongType) && (
        <p role="alert" className="mb-4 text-sm text-destructive">
          {wrongType ? t('wrongType') : <InlineCode text={errorMessage(upload.error)} />}
        </p>
      )}
      {chosenFile && (
        <NameStep
          key={`${chosenFile.name}-${chosenFile.size}-${chosenFile.lastModified}`}
          file={chosenFile}
          suggested={suggested}
          busy={upload.isPending}
          onCancel={() => setChosenFile(null)}
          onContinue={(templateName) =>
            upload.mutate({ file: chosenFile, templateName }, { onSuccess: () => setChosenFile(null) })
          }
        />
      )}

      {uploadsQuery.isPending ? (
        <Skeleton className="h-28 rounded-xl" />
      ) : uploads.length === 0 && !chosenFile ? (
        <button
          type="button"
          onClick={() => input.current?.click()}
          className="flex w-full flex-col items-center gap-2 rounded-xl border border-dashed px-6 py-10 text-center text-sm text-muted-foreground transition-colors hover:border-foreground/30 hover:text-foreground"
        >
          <FileArrowUpIcon className="size-6 text-primary" weight="duotone" />
          <span className="font-medium text-foreground">{t('none')}</span>
          <span>{t('dropOr')}</span>
          <span>{t('noneHint')}</span>
        </button>
      ) : (
        pending.length > 0 && (
          <ul className="space-y-4">
            {pending.map((item) => (
              <UploadCard key={item.name} upload={item} isConverting={item.name in convertingNow} />
            ))}
          </ul>
        )
      )}
    </section>
  )
}
