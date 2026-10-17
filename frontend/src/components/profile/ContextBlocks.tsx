/** Contexto (los cuatro Markdown de `data/contexto/`) y muestras de estilo (fase 25.7b). */
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { FileTextIcon, TrashIcon, UploadSimpleIcon, WarningIcon } from '@phosphor-icons/react'
import { ApiError } from '@/api/client'
import {
  useContextDocument,
  useDeleteStyleSample,
  useSaveContextDocument,
  useStyleSamples,
  useStyleSampleText,
  useUploadStyleSample,
  type ContextSectionName,
  type StyleSample,
} from '@/api/queries'
import { OpenFolderButton } from '@/components/OpenFolderButton'
import { ErrorState } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import { errorMessage } from '@/lib/errors'
import { formatNumber } from '@/lib/labels'
import { cn } from '@/lib/utils'
import { Block } from './fields'
import { MarkdownPreview } from './MarkdownPreview'
import { useProfileState } from './editor'

export const CONTEXT_SECTIONS: ContextSectionName[] = ['estilo-redaccion', 'perfil-conductual', 'criterios', 'narrativa']

const kb = (bytes: number) => formatNumber(bytes / 1024, { minimumFractionDigits: 1, maximumFractionDigits: 1 })

export function ContextFileEditor({ section }: { section: ContextSectionName }) {
  const { t } = useTranslation('profileEditor')
  const { t: tp } = useTranslation('profile')
  const { setDirty } = useProfileState()
  const document = useContextDocument(section)
  const save = useSaveContextDocument()
  const [text, setText] = useState<string | null>(null)
  const [tab, setTab] = useState<'edit' | 'preview'>('edit')
  const [error, setError] = useState<string | null>(null)
  const [conflict, setConflict] = useState(false)
  const [saved, setSaved] = useState(false)
  const server = document.data?.text ?? ''
  const value = text ?? server
  const dirty = text !== null && text !== server
  const bytes = new TextEncoder().encode(value).length
  const max = document.data?.max_bytes ?? 20 * 1024
  const id = `context-${section}`
  useEffect(() => setDirty(id, dirty), [id, dirty, setDirty])
  useEffect(() => () => setDirty(id, false), [id, setDirty])

  if (document.isPending) return <Skeleton className="h-40" />
  if (document.isError) return <ErrorState error={document.error} onRetry={() => document.refetch()} />

  const submit = () => {
    setError(null)
    setSaved(false)
    save.mutate(
      { section, file_hash: document.data.file_hash ?? null, text: value },
      {
        onSuccess: () => {
          setText(null)
          setSaved(true)
        },
        onError: (e) => {
          setConflict(e instanceof ApiError && e.type === 'conflict')
          setError(errorMessage(e))
        },
      },
    )
  }
  return (
    <Block title={tp(`sections.${section}.title`)} hint={tp(`sections.${section}.hint`)}>
      <div className="flex gap-1" role="tablist" aria-label={t('context.mode')}>
        {(['edit', 'preview'] as const).map((mode) => (
          <Button key={mode} type="button" size="sm" role="tab" aria-selected={tab === mode} variant={tab === mode ? 'secondary' : 'ghost'} onClick={() => setTab(mode)}>
            {t(`context.${mode}`)}
          </Button>
        ))}
      </div>
      {tab === 'edit' ? (
        <Textarea
          aria-label={t('context.editorLabel', { name: tp(`sections.${section}.title`) })}
          rows={12}
          className="font-mono text-xs"
          value={value}
          onChange={(e) => {
            setSaved(false)
            setText(e.target.value)
          }}
        />
      ) : (
        <div className="rounded-md border p-3">
          <MarkdownPreview text={value} empty={t('context.emptyPreview')} />
        </div>
      )}
      <p className={cn('text-xs', bytes > max ? 'text-destructive' : 'text-muted-foreground')}>
        {t('context.size', { size: kb(bytes), max: kb(max) })}
        {!document.data.exists && ` · ${t('context.newFile')}`}
      </p>
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {conflict ? t('errors.conflict') : error}
        </p>
      )}
      <div className="flex flex-wrap items-center gap-2 border-t pt-3">
        <Button type="button" size="sm" disabled={!dirty || save.isPending || bytes > max} onClick={submit}>
          {save.isPending ? t('actions.saving') : t('actions.save')}
        </Button>
        {(dirty || conflict) && (
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={() => {
              setText(null)
              setError(null)
              setConflict(false)
              if (conflict) void document.refetch()
            }}
          >
            {conflict ? t('actions.reload') : t('actions.discard')}
          </Button>
        )}
        <span role="status" className="text-xs text-muted-foreground">
          {saved && !dirty ? t('actions.saved') : dirty ? t('unsaved.badge') : null}
        </span>
      </div>
    </Block>
  )
}

function SampleRow({ sample }: { sample: StyleSample }) {
  const { t } = useTranslation('profileEditor')
  const [open, setOpen] = useState(false)
  const text = useStyleSampleText(sample.name, open)
  const remove = useDeleteStyleSample()
  return (
    <li className="grid gap-2 px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="flex items-center gap-2 font-mono text-sm">
          <FileTextIcon className="size-4 text-muted-foreground" aria-hidden />
          {sample.name}
        </span>
        <span className="flex items-center gap-1">
          <span className="text-xs text-muted-foreground">{t('style.chars', { count: sample.chars })}</span>
          <Button type="button" size="sm" variant="ghost" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
            {open ? t('style.hideText') : t('style.showText')}
          </Button>
          <Button type="button" size="sm" variant="ghost" aria-label={t('style.delete', { name: sample.name })} disabled={remove.isPending} onClick={() => remove.mutate(sample.name)}>
            <TrashIcon />
          </Button>
        </span>
      </div>
      {sample.risk_flags.length > 0 && (
        <p className="flex items-start gap-1.5 text-xs text-amber-700 dark:text-amber-400">
          <WarningIcon className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          {t('style.risk', { excerpt: sample.excerpt ?? '' })}
        </p>
      )}
      {open && (
        <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded-md bg-muted/50 p-3 text-xs">{text.data?.text ?? '…'}</pre>
      )}
    </li>
  )
}

export function StyleSamplesBlock() {
  const { t } = useTranslation('profileEditor')
  const samples = useStyleSamples()
  const upload = useUploadStyleSample()
  const input = useRef<HTMLInputElement>(null)
  const [error, setError] = useState<string | null>(null)
  return (
    <Block
      title={t('style.title')}
      hint={t('style.hint')}
      actions={
        <div className="flex flex-wrap gap-2">
          <Button type="button" size="sm" variant="outline" disabled={upload.isPending} onClick={() => input.current?.click()}>
            <UploadSimpleIcon /> {upload.isPending ? t('style.uploading') : t('style.upload')}
          </Button>
          <OpenFolderButton folder="estilo" ariaLabel={t('style.openFolder')} />
        </div>
      }
    >
      <input
        ref={input}
        type="file"
        accept=".txt,.md,.docx,.pdf"
        className="sr-only"
        aria-label={t('style.fileLabel')}
        onChange={(e) => {
          const file = e.target.files?.[0]
          e.target.value = ''
          if (!file) return
          setError(null)
          upload.mutate(file, { onError: (err) => setError(errorMessage(err)) })
        }}
      />
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      {samples.isPending ? (
        <Skeleton className="h-16" />
      ) : samples.isError ? (
        <ErrorState error={samples.error} onRetry={() => samples.refetch()} />
      ) : samples.data.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t('style.empty')}</p>
      ) : (
        <ul className="divide-y rounded-lg border">
          {samples.data.map((sample) => (
            <SampleRow key={sample.name} sample={sample} />
          ))}
        </ul>
      )}
    </Block>
  )
}
