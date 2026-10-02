import type { ReactNode } from 'react'
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

function TemplateCard({ template }: { template: TemplateInfo }) {
  const columns = template.columns === 1 ? '1 columna' : `${template.columns} columnas`
  return (
    <article aria-label={template.name} className="flex flex-col overflow-hidden rounded-xl border bg-card">
      <div className="aspect-[210/297] border-b bg-white">
        {template.has_preview ? (
          <a href={fileUrls.templatePreview(template.id)} target="_blank" rel="noopener noreferrer">
            <img
              src={fileUrls.templatePreview(template.id)}
              alt={`Vista previa de ${template.name}`}
              loading="lazy"
              className="size-full object-cover object-top"
            />
          </a>
        ) : (
          <div className="grid size-full place-items-center text-sm text-muted-foreground">
            <span className="flex flex-col items-center gap-2">
              <ImageIcon className="size-6" />
              Sin vista previa
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
        <ul className="mt-auto flex flex-wrap gap-1.5" aria-label="Características">
          <Tag strong={template.ats_friendly}>{template.ats_friendly ? 'Apta para ATS' : 'No apta para ATS'}</Tag>
          <Tag>{template.photo_supported ? 'Con foto' : 'Sin foto'}</Tag>
          <Tag>{columns}</Tag>
          <Tag>Motor {template.engine}</Tag>
          {template.accent_colors && <Tag>{template.accent_colors.choices.length} colores</Tag>}
          <Tag>{template.from_user_cv ? 'Tu CV' : template.origin === 'builtin' ? 'Integrada' : 'Tuya'}</Tag>
        </ul>
      </div>
    </article>
  )
}

export function TemplatesPage() {
  const { data, isPending, isError, error, refetch } = useTemplates()
  return (
    <div className="animate-in fade-in duration-300">
      <header className="mb-8 max-w-[65ch]">
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Plantillas de CV</h1>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          El contenido de cada CV lo redacta tu agente; la plantilla solo decide cómo se ve. Puedes cambiarla
          en la ficha de cada oferta sin volver a usar IA.
        </p>
      </header>

      <MyCv />

      <h2 className="mb-4 text-lg font-semibold tracking-tight">Todas las plantillas</h2>

      {isPending ? (
        <div aria-busy="true" aria-label="Cargando plantillas" className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
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
              aria-label="Plantillas con problemas"
              className="rounded-xl border border-warning-border bg-warning p-5 text-warning-foreground"
            >
              <h2 className="flex items-center gap-2 font-semibold">
                <WarningIcon className="size-5" weight="duotone" />
                Plantillas que no se pueden usar
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
