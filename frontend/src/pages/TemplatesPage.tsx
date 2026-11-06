import { useState, type FormEvent, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import {
  ArrowCounterClockwiseIcon,
  CheckIcon,
  ImageIcon,
  PencilSimpleIcon,
  StarIcon,
  TrashIcon,
  WarningIcon,
  XIcon,
} from '@phosphor-icons/react'
import { fileUrls, type TemplateInfo } from '@/api/client'
import {
  useDefaultTemplate,
  useDeleteTemplate,
  useHiddenTemplates,
  useRenameTemplate,
  useRestoreTemplate,
  useSetDefaultTemplate,
  useTemplates,
} from '@/api/queries'
import { MyCv } from '@/components/MyCv'
import { BusyLabel } from '@/components/StableLabel'
import { ErrorState, InlineCode } from '@/components/States'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { errorMessage } from '@/lib/errors'
import { cn } from '@/lib/utils'
import { useTemplateText } from '@/lib/templateText'

function Tag({ children, strong }: { children: ReactNode; strong?: boolean }) {
  return (
    <li
      className={cn(
        'rounded-md px-2 py-1 text-[0.75rem] leading-none',
        strong
          ? 'bg-accent font-medium text-accent-foreground ring-1 ring-primary/15 ring-inset'
          : 'text-foreground/80 ring-1 ring-input ring-inset',
      )}
    >
      {children}
    </li>
  )
}

function Thumbnail({ src, alt }: { src: string; alt: string }) {
  return (
    <a href={src} target="_blank" rel="noopener noreferrer">
      <img src={src} alt={alt} loading="lazy" className="size-full object-cover object-top" />
    </a>
  )
}

/** Plantilla creada desde un CV: el original y cómo queda la plantilla, uno al lado del otro. */
function OriginalAndTemplate({ template }: { template: TemplateInfo }) {
  const { t } = useTranslation('templates')
  const text = useTemplateText()
  const recreated = template.engine === 'html' ? t('recreation') : t('template')
  return (
    <div className="grid size-full grid-cols-2 gap-px bg-border" aria-label={t('originalAndRecreation')}>
      {[
        { label: t('original'), src: fileUrls.templateSource(template.id) },
        { label: recreated, src: template.has_preview ? fileUrls.templatePreview(template.id) : null },
      ].map(({ label, src }) => (
        <figure key={label} className="relative min-w-0 bg-white">
          {src ? (
            <Thumbnail src={src} alt={t('ofName', { label, name: text.name(template) })} />
          ) : (
            <span className="grid size-full place-items-center text-muted-foreground">
              <ImageIcon className="size-5" />
            </span>
          )}
          <figcaption className="absolute top-1.5 left-1.5 rounded bg-background/90 px-1.5 py-0.5 text-[0.7rem] font-medium shadow-sm">
            {label}
          </figcaption>
        </figure>
      ))}
    </div>
  )
}

/** El nombre de la plantilla; en las tuyas, con el lápiz para cambiarlo. */
function TemplateName({ template }: { template: TemplateInfo }) {
  const { t } = useTranslation('templates', { keyPrefix: 'actions' })
  const text = useTemplateText()
  const rename = useRenameTemplate()
  const name = text.name(template)
  const [draft, setDraft] = useState<string | null>(null)
  const save = (event: FormEvent) => {
    event.preventDefault()
    const value = (draft ?? '').trim()
    if (!value || value === name) return setDraft(null)
    rename.mutate({ templateId: template.id, name: value }, { onSuccess: () => setDraft(null) })
  }
  if (draft === null) {
    return (
      <div className="flex items-start justify-between gap-2">
        <h2 className="min-w-0 font-semibold tracking-tight break-words">{name}</h2>
        {template.editable && (
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            className="-mt-1 -mr-1 shrink-0"
            aria-label={t('rename', { name })}
            onClick={() => setDraft(name)}
          >
            <PencilSimpleIcon />
          </Button>
        )}
      </div>
    )
  }
  return (
    <form onSubmit={save} className="space-y-1">
      <div className="flex items-center gap-1">
        <Input
          autoFocus
          value={draft}
          maxLength={80}
          aria-label={t('nameLabel')}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Escape') setDraft(null)
          }}
          className="h-8"
        />
        <Button type="submit" variant="ghost" size="icon-sm" disabled={rename.isPending} aria-label={t('saveName')}>
          <CheckIcon />
        </Button>
        <Button type="button" variant="ghost" size="icon-sm" aria-label={t('cancel')} onClick={() => setDraft(null)}>
          <XIcon />
        </Button>
      </div>
      {rename.isError && (
        <p role="alert" className="text-xs text-destructive">
          {errorMessage(rename.error)}
        </p>
      )}
    </form>
  )
}

/**
 * Usar por defecto y eliminar, en todas. Eliminar una tuya la borra; una de la app se quita de tu lista
 * (no se borra del programa) y se restaura desde «Plantillas eliminadas».
 */
function TemplateActions({ template, isDefault }: { template: TemplateInfo; isDefault: boolean }) {
  const { t } = useTranslation('templates', { keyPrefix: 'actions' })
  const text = useTemplateText()
  const setDefault = useSetDefaultTemplate()
  const remove = useDeleteTemplate()
  const [confirming, setConfirming] = useState(false)
  const conflicts = setDefault.data?.conflicts ?? []
  const name = text.name(template)
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        {isDefault ? (
          <span className="inline-flex items-center gap-1 text-xs font-medium text-primary">
            <StarIcon weight="fill" /> {t('default')}
          </span>
        ) : (
          <Button size="xs" variant="outline" onClick={() => setDefault.mutate(template.id)} disabled={setDefault.isPending}>
            <StarIcon /> <BusyLabel busy={setDefault.isPending} busyText={t('saving')} text={t('useDefault')} />
          </Button>
        )}
        <Button size="xs" variant="ghost" aria-label={t('deleteAria', { name })} onClick={() => setConfirming(true)}>
          <TrashIcon /> {t('delete')}
        </Button>
      </div>
      {setDefault.isError && (
        <p role="alert" className="text-sm text-destructive">
          <InlineCode text={errorMessage(setDefault.error)} />
        </p>
      )}
      {conflicts.length > 0 && (
        <ul aria-label={t('conflicts')} className="space-y-1 text-xs text-muted-foreground">
          {conflicts.map((conflict) => (
            <li key={conflict}>
              <InlineCode text={conflict} />
            </li>
          ))}
        </ul>
      )}
      <Dialog open={confirming} onOpenChange={setConfirming}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t(template.editable ? 'confirmTitle' : 'confirmTitleBuiltin', { name })}</DialogTitle>
            <DialogDescription>
              {template.editable
                ? isDefault
                  ? t('confirmDefault')
                  : t('confirmBody')
                : isDefault
                  ? t('confirmBuiltinDefault')
                  : t('confirmBuiltin')}
            </DialogDescription>
          </DialogHeader>
          {remove.isError && (
            <p role="alert" className="text-sm text-destructive">
              {errorMessage(remove.error)}
            </p>
          )}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setConfirming(false)}>
              {t('cancel')}
            </Button>
            <Button
              type="button"
              variant="destructive"
              disabled={remove.isPending}
              onClick={() => remove.mutate(template.id, { onSuccess: () => setConfirming(false) })}
            >
              {t('confirmDelete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

function TemplateCard({ template, isDefault }: { template: TemplateInfo; isDefault: boolean }) {
  const { t } = useTranslation('templates')
  const text = useTemplateText()
  const columns = t('columns', { count: template.columns })
  return (
    <article aria-label={text.name(template)} className="flex flex-col overflow-hidden rounded-xl border bg-card">
      <div className="aspect-[210/297] border-b bg-white">
        {template.has_source_preview ? (
          <OriginalAndTemplate template={template} />
        ) : template.has_preview ? (
          <a href={fileUrls.templatePreview(template.id)} target="_blank" rel="noopener noreferrer">
            <img
              src={fileUrls.templatePreview(template.id)}
              alt={t('previewOf', { name: text.name(template) })}
              loading="lazy"
              className="size-full object-cover object-top"
            />
          </a>
        ) : (
          <div className="grid size-full place-items-center text-sm text-muted-foreground">
            <span className="flex flex-col items-center gap-2">
              <ImageIcon className="size-6" />
              {t('noPreview')}
            </span>
          </div>
        )}
      </div>
      <div className="flex flex-1 flex-col gap-3 p-4">
        <TemplateName template={template} />
        {template.description && (
          <p className="text-sm leading-relaxed text-foreground/80">{text.description(template)}</p>
        )}
        <ul className="mt-auto flex flex-wrap gap-1.5" aria-label={t('features')}>
          <Tag strong={template.ats_friendly}>{template.ats_friendly ? t('ats') : t('notAts')}</Tag>
          <Tag>{template.photo_supported ? t('withPhoto') : t('noPhoto')}</Tag>
          <Tag>{columns}</Tag>
          <Tag>{template.engine === 'html' ? t('pdfOnly') : t('pdfAndWord')}</Tag>
          {template.accent_colors && <Tag>{t('colors', { count: template.accent_colors.choices.length })}</Tag>}
          <Tag>{template.from_user_cv ? t('yourCv') : template.origin === 'builtin' ? t('builtin') : t('yours')}</Tag>
        </ul>
        <TemplateActions template={template} isDefault={isDefault} />
      </div>
    </article>
  )
}

/** Las de la app que eliminaste de tu lista, con su botón para restaurarlas. */
function HiddenTemplates() {
  const { t } = useTranslation('templates')
  const text = useTemplateText()
  const hidden = useHiddenTemplates()
  const restore = useRestoreTemplate()
  const items = hidden.data ?? []
  if (items.length === 0) return null
  return (
    <section aria-label={t('hidden.label')} className="rounded-xl border border-dashed p-5">
      <h2 className="font-semibold tracking-tight">{t('hidden.title', { count: items.length })}</h2>
      <p className="mt-1 text-sm text-muted-foreground">{t('hidden.intro')}</p>
      <ul className="mt-3 divide-y text-sm">
        {items.map((template) => {
          const name = text.name(template)
          return (
            <li key={template.id} className="flex items-center justify-between gap-3 py-2">
              <span className="min-w-0 truncate font-medium">{name}</span>
              <Button
                size="xs"
                variant="outline"
                aria-label={t('hidden.restoreAria', { name })}
                disabled={restore.isPending}
                onClick={() => restore.mutate(template.id)}
              >
                <ArrowCounterClockwiseIcon /> {t('hidden.restore')}
              </Button>
            </li>
          )
        })}
      </ul>
      {restore.isError && (
        <p role="alert" className="mt-2 text-sm text-destructive">
          {errorMessage(restore.error)}
        </p>
      )}
    </section>
  )
}

export function TemplatesPage() {
  const { t } = useTranslation('templates')
  const { data, isPending, isError, error, refetch } = useTemplates()
  const defaultTemplate = useDefaultTemplate()
  return (
    <div className="animate-in fade-in duration-300">
      <header className="mb-8 max-w-[65ch]">
        <h1 className="text-2xl font-semibold tracking-tight">{t('title')}</h1>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          {t('intro')}
        </p>
      </header>

      <MyCv />

      <h2 className="mb-4 text-lg font-semibold tracking-tight">{t('all')}</h2>

      {isPending ? (
        <div aria-busy="true" aria-label={t('loading')} className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="aspect-[210/297] rounded-xl" />
          ))}
        </div>
      ) : isError ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : (
        <div className="space-y-8">
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {data.templates.map((template) => (
              <TemplateCard key={template.id} template={template} isDefault={defaultTemplate.data?.template_id === template.id} />
            ))}
          </div>
          <HiddenTemplates />
          {data.invalid.length > 0 && (
            <section
              aria-label={t('invalidLabel')}
              className="rounded-xl border border-warning-border bg-warning p-5 text-warning-foreground"
            >
              <h2 className="flex items-center gap-2 font-semibold">
                <WarningIcon className="size-5" weight="duotone" />
                {t('invalidTitle')}
              </h2>
              <ul className="mt-3 space-y-2 text-sm">
                {data.invalid.map((item) => (
                  <li key={item.id}>
                    <span className="font-medium">{item.id}</span>: {item.reason}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      )}
    </div>
  )
}
