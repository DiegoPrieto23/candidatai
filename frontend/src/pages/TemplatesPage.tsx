import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { ImageIcon, WarningIcon } from '@phosphor-icons/react'
import { fileUrls, type TemplateInfo } from '@/api/client'
import { useTemplates } from '@/api/queries'
import { MyCv } from '@/components/MyCv'
import { ErrorState } from '@/components/States'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

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
  const recreated = template.engine === 'html' ? t('recreation') : t('template')
  return (
    <div className="grid size-full grid-cols-2 gap-px bg-border" aria-label={t('originalAndRecreation')}>
      {[
        { label: t('original'), src: fileUrls.templateSource(template.id) },
        { label: recreated, src: template.has_preview ? fileUrls.templatePreview(template.id) : null },
      ].map(({ label, src }) => (
        <figure key={label} className="relative min-w-0 bg-white">
          {src ? (
            <Thumbnail src={src} alt={t('ofName', { label, name: template.name })} />
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

function TemplateCard({ template }: { template: TemplateInfo }) {
  const { t } = useTranslation('templates')
  const columns = t('columns', { count: template.columns })
  return (
    <article aria-label={template.name} className="flex flex-col overflow-hidden rounded-xl border bg-card">
      <div className="aspect-[210/297] border-b bg-white">
        {template.has_source_preview ? (
          <OriginalAndTemplate template={template} />
        ) : template.has_preview ? (
          <a href={fileUrls.templatePreview(template.id)} target="_blank" rel="noopener noreferrer">
            <img
              src={fileUrls.templatePreview(template.id)}
              alt={t('previewOf', { name: template.name })}
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
        <div>
          <h2 className="font-semibold tracking-tight">{template.name}</h2>
          <p className="font-mono text-xs text-muted-foreground">{template.id}</p>
        </div>
        {template.description && (
          <p className="text-sm leading-relaxed text-foreground/80">{template.description}</p>
        )}
        <ul className="mt-auto flex flex-wrap gap-1.5" aria-label={t('features')}>
          <Tag strong={template.ats_friendly}>{template.ats_friendly ? t('ats') : t('notAts')}</Tag>
          <Tag>{template.photo_supported ? t('withPhoto') : t('noPhoto')}</Tag>
          <Tag>{columns}</Tag>
          <Tag>{t('engine', { engine: template.engine })}</Tag>
          {template.engine === 'html' && <Tag>{t('pdfOnly')}</Tag>}
          {template.accent_colors && <Tag>{t('colors', { count: template.accent_colors.choices.length })}</Tag>}
          <Tag>{template.from_user_cv ? t('yourCv') : template.origin === 'builtin' ? t('builtin') : t('yours')}</Tag>
        </ul>
      </div>
    </article>
  )
}

export function TemplatesPage() {
  const { t } = useTranslation('templates')
  const { data, isPending, isError, error, refetch } = useTemplates()
  return (
    <div className="animate-in fade-in duration-300">
      <header className="mb-8 max-w-[65ch]">
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{t('title')}</h1>
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
              <TemplateCard key={template.id} template={template} />
            ))}
          </div>
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
                    <span className="font-mono font-medium">{item.id}</span>: {item.reason}
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
