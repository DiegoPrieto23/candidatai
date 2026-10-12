import { useState, type FormEvent, type ReactNode } from 'react'
import {
  ArrowsClockwiseIcon,
  CheckCircleIcon,
  ColumnsIcon,
  DownloadSimpleIcon,
  FilePdfIcon,
  ImageIcon,
  PaperPlaneTiltIcon,
  SealCheckIcon,
  SealWarningIcon,
  TerminalWindowIcon,
  WarningIcon,
} from '@phosphor-icons/react'
import {
  fileUrls,
  type CvRenderOptions,
  type CvView,
  type JobCv,
  type JobView,
  type RenderResult,
  type SectionName,
  type Stage,
  type TemplateInfo,
} from '@/api/client'
import { useJobCv, useRenderCv, useSelectRender, useTemplates } from '@/api/queries'
import { AgentButton } from '@/components/AgentButton'
import { ClosedHint } from '@/components/JobSignals'
import { ErrorState, InlineCode } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { colorLabel, formatDateTime, PHOTO_MODE_LABEL, SECTION_LABEL } from '@/lib/labels'
import { cn } from '@/lib/utils'

type PhotoMode = NonNullable<CvRenderOptions['photo']>
const PHOTO_MODES: PhotoMode[] = ['auto', 'include', 'exclude']

/**
 * Etapas con sección CV: de la aprobación en adelante. Es una lista explícita para que una etapa
 * nueva anterior a la aprobación (p. ej. `pending_detail`, fase 09b) no la muestre por defecto.
 * En `closed` solo aparece si la oferta llegó a tener CV.
 */
const CV_SECTION_STAGES = new Set<Stage>(['approved', 'cv_ready', 'applied', 'in_process', 'closed'])

function Code({ children }: { children: ReactNode }) {
  return (
    <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em] text-foreground">{children}</code>
  )
}

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

// --- Verificación --------------------------------------------------------------------------------

function Verification({ cv }: { cv: CvView }) {
  const verification = cv.verification
  if (!verification) {
    return (
      <p className="flex items-start gap-2 text-sm text-muted-foreground">
        <SealWarningIcon className="mt-0.5 size-4 shrink-0" />
        Sin verificar todavía: el skill <Code>generate-cv</Code> lo verifica tras redactarlo.
      </p>
    )
  }
  return (
    <div className="space-y-2">
      <p className={cn('flex items-center gap-2 text-sm font-medium', !verification.passed && 'text-destructive')}>
        {verification.passed ? (
          <SealCheckIcon className="size-[18px] text-primary" weight="duotone" />
        ) : (
          <SealWarningIcon className="size-[18px]" weight="duotone" />
        )}
        {verification.passed ? 'Verificado: nada inventado ni exagerado' : 'El verificador encontró problemas'}
      </p>
      {verification.issues.length > 0 && (
        <ul className="space-y-1.5 text-sm">
          {verification.issues.map((issue, i) => (
            <li key={i} className="rounded-md bg-muted/70 px-3 py-2">
              <span className={cn('font-medium', issue.severity === 'blocker' && 'text-destructive')}>
                {issue.severity === 'blocker' ? 'Bloqueante' : 'Aviso'} · {issue.location}
              </span>
              <span className="block text-foreground/85">{issue.problem}</span>
              {issue.suggestion && <span className="block text-muted-foreground">{issue.suggestion}</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

// --- Formulario de render -----------------------------------------------------------------------

function TemplatePicker({
  templates,
  value,
  onChange,
}: {
  templates: TemplateInfo[]
  value: string
  onChange: (id: string) => void
}) {
  return (
    <fieldset>
      <legend className="mb-2 text-sm font-medium">Plantilla</legend>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {templates.map((template) => {
          const checked = template.id === value
          return (
            <label
              key={template.id}
              className={cn(
                'group cursor-pointer rounded-lg border bg-background p-2 transition-colors has-[:focus-visible]:ring-[3px] has-[:focus-visible]:ring-ring/50',
                checked ? 'border-primary ring-1 ring-primary' : 'hover:border-foreground/25',
              )}
            >
              <input
                type="radio"
                name="template"
                value={template.id}
                checked={checked}
                onChange={() => onChange(template.id)}
                className="sr-only"
              />
              <span className="block aspect-[210/297] overflow-hidden rounded-md border bg-white">
                {template.has_preview ? (
                  <img
                    src={fileUrls.templatePreview(template.id)}
                    alt=""
                    loading="lazy"
                    className="size-full object-cover object-top"
                  />
                ) : (
                  <span className="grid size-full place-items-center text-muted-foreground">
                    <ImageIcon className="size-6" />
                  </span>
                )}
              </span>
              <span className="mt-2 flex items-center gap-1.5 text-sm font-medium">
                <span className="truncate">{template.name}</span>
                {template.from_user_cv && <Chip>Tu CV</Chip>}
              </span>
              <span className="block truncate text-xs text-muted-foreground">
                {template.ats_friendly ? 'Apta para ATS' : 'No apta para ATS'}
                {template.photo_supported && ' · con foto'}
                {template.engine === 'html' && ' · solo PDF'}
              </span>
            </label>
          )
        })}
      </div>
    </fieldset>
  )
}

function PhotoPicker({
  value,
  onChange,
  supported,
}: {
  value: PhotoMode
  onChange: (mode: PhotoMode) => void
  supported: boolean
}) {
  return (
    <fieldset disabled={!supported}>
      <legend className="mb-2 text-sm font-medium">Foto</legend>
      <div className="inline-flex rounded-md border bg-background p-0.5">
        {PHOTO_MODES.map((mode) => (
          <label
            key={mode}
            className={cn(
              'cursor-pointer rounded-[5px] px-3 py-1 text-sm transition-colors has-[:focus-visible]:ring-[3px] has-[:focus-visible]:ring-ring/50 has-[:disabled]:cursor-not-allowed has-[:disabled]:opacity-50',
              value === mode ? 'bg-accent font-medium text-accent-foreground' : 'text-muted-foreground hover:text-foreground',
            )}
          >
            <input
              type="radio"
              name="photo"
              value={mode}
              checked={value === mode}
              onChange={() => onChange(mode)}
              className="sr-only"
            />
            {PHOTO_MODE_LABEL[mode]}
          </label>
        ))}
      </div>
      <p className="mt-1.5 text-xs text-muted-foreground">
        {supported
          ? 'Automática: según el país de la oferta y tu photo_policy, si tienes data/photo.*.'
          : 'Esta plantilla no lleva foto.'}
      </p>
    </fieldset>
  )
}

function ColorPicker({
  colors,
  value,
  onChange,
}: {
  colors: NonNullable<TemplateInfo['accent_colors']>
  value: string
  onChange: (color: string) => void
}) {
  return (
    <fieldset>
      <legend className="mb-2 text-sm font-medium">Color de acento</legend>
      <div className="flex flex-wrap gap-2">
        {colors.choices.map((color) => (
          <label
            key={color}
            title={colorLabel(color)}
            className={cn(
              'grid size-8 cursor-pointer place-items-center rounded-full ring-offset-2 ring-offset-card transition-shadow has-[:focus-visible]:ring-[3px] has-[:focus-visible]:ring-ring/50',
              value === color && 'ring-2 ring-foreground',
            )}
            style={{ backgroundColor: color }}
          >
            <input
              type="radio"
              name="accent"
              value={color}
              checked={value === color}
              onChange={() => onChange(color)}
              aria-label={colorLabel(color)}
              className="sr-only"
            />
            {value === color && <CheckCircleIcon className="size-4 text-white" weight="fill" />}
          </label>
        ))}
      </div>
    </fieldset>
  )
}

function SectionsPicker({
  sections,
  hidden,
  onChange,
}: {
  sections: SectionName[]
  hidden: SectionName[]
  onChange: (hidden: SectionName[]) => void
}) {
  const toggle = (section: SectionName, hide: boolean) =>
    onChange(hide ? [...hidden, section] : hidden.filter((s) => s !== section))
  return (
    <fieldset>
      <legend className="mb-2 text-sm font-medium">Ocultar secciones</legend>
      <div className="flex flex-wrap gap-x-4 gap-y-2">
        {sections.map((section) => (
          <label key={section} className="flex cursor-pointer items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={hidden.includes(section)}
              onChange={(e) => toggle(section, e.target.checked)}
              className="size-4 accent-[var(--primary)]"
            />
            {SECTION_LABEL[section]}
          </label>
        ))}
      </div>
    </fieldset>
  )
}

function RenderForm({
  cv,
  jobId,
  templates,
}: {
  cv: CvView
  jobId: number
  templates: TemplateInfo[]
}) {
  const base = cv.renders.find((r) => r.selected) ?? cv.renders.at(-1)
  const [templateId, setTemplateId] = useState(base?.template_id ?? templates[0]?.id ?? '')
  const [photo, setPhoto] = useState<PhotoMode>('auto')
  const [accent, setAccent] = useState<string | null>(base?.options.accent_color ?? null)
  const [hidden, setHidden] = useState<SectionName[]>(base?.options.hidden_sections ?? [])
  const render = useRenderCv(jobId)

  const template = templates.find((t) => t.id === templateId)
  const colors = template?.accent_colors ?? null
  const color = colors ? (accent && colors.choices.includes(accent) ? accent : colors.default) : null

  const chooseTemplate = (id: string) => {
    setTemplateId(id)
    setAccent(null) // cada plantilla tiene sus colores: vuelve al suyo por defecto
  }
  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!template) return
    render.mutate({
      documentId: cv.document_id,
      options: {
        template_id: template.id,
        photo: template.photo_supported ? photo : 'exclude',
        accent_color: color,
        hidden_sections: hidden.filter((s) => template.sections.includes(s)),
      },
    })
  }

  return (
    <form onSubmit={submit} aria-label="Renderizar el CV" className="space-y-6">
      <TemplatePicker templates={templates} value={templateId} onChange={chooseTemplate} />
      {template && (
        <div className="grid gap-6 sm:grid-cols-2">
          <PhotoPicker value={photo} onChange={setPhoto} supported={template.photo_supported} />
          {colors && color && <ColorPicker colors={colors} value={color} onChange={setAccent} />}
          <div className="sm:col-span-2">
            <SectionsPicker sections={template.sections} hidden={hidden} onChange={setHidden} />
          </div>
        </div>
      )}
      {render.isError && (
        <p role="alert" className="text-sm text-destructive">
          <InlineCode text={render.error.message} />
        </p>
      )}
      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" disabled={!template || render.isPending} className="active:translate-y-px">
          <ArrowsClockwiseIcon className={cn(render.isPending && 'animate-spin')} />
          {render.isPending ? 'Renderizando…' : 'Renderizar'}
        </Button>
        <p className="text-xs text-muted-foreground">
          {render.isPending
            ? 'Convirtiendo a PDF: tarda unos segundos.'
            : 'Mismo contenido verificado, otra presentación. Sin IA.'}
        </p>
      </div>
    </form>
  )
}

// --- Renders -------------------------------------------------------------------------------------

function optionsSummary(render: RenderResult): string {
  const parts = [render.options.photo ? 'Con foto' : 'Sin foto']
  if (render.options.accent_color) parts.push(colorLabel(render.options.accent_color))
  if (render.options.hidden_sections.length)
    parts.push(`sin ${render.options.hidden_sections.map((s) => SECTION_LABEL[s].toLowerCase()).join(', ')}`)
  return parts.join(' · ')
}

function RenderCard({
  render,
  templateName,
  comparing,
  onCompare,
  jobId,
}: {
  render: RenderResult
  templateName: string
  comparing: boolean
  onCompare: (on: boolean) => void
  jobId: number
}) {
  const select = useSelectRender(jobId)
  const coverage = render.keyword_coverage
  const total = coverage.present.length + coverage.missing.length
  const tooLong = render.warnings.some((w) => w.code === 'too_long')
  return (
    <li
      aria-label={`Render ${render.render_id}`}
      className={cn('rounded-lg border bg-background p-4', render.selected && 'border-primary/50 ring-1 ring-primary/30')}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="flex flex-wrap items-center gap-2 text-sm font-medium">
            {templateName}
            {render.selected && (
              <Chip tone="primary">
                <PaperPlaneTiltIcon weight="fill" /> Para enviar
              </Chip>
            )}
            {render.template_changed && <Chip tone="warning">Plantilla cambiada</Chip>}
          </p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {optionsSummary(render)} · {formatDateTime(render.created_at)}
          </p>
        </div>
        <dl className="flex gap-4 text-right text-xs">
          <div>
            <dt className="text-muted-foreground">Páginas</dt>
            <dd className={cn('tabular font-medium', tooLong && 'text-destructive')}>
              {render.pages}/{render.max_pages}
            </dd>
          </div>
          {total > 0 && (
            <div>
              <dt className="text-muted-foreground">Keywords</dt>
              <dd
                className="tabular font-medium"
                title={coverage.missing.length ? `Faltan: ${coverage.missing.join(', ')}` : undefined}
              >
                {coverage.present.length} de {total}
              </dd>
            </div>
          )}
        </dl>
      </div>

      {render.template_changed && (
        <p className="mt-2 text-xs text-muted-foreground">
          La plantilla ha cambiado desde este render: vuelve a renderizar para ver la versión actual.
        </p>
      )}
      {render.warnings.length > 0 && (
        <ul className="mt-3 space-y-1.5">
          {render.warnings.map((warning, i) => (
            <li key={i} className="flex items-start gap-2 text-sm text-warning-foreground">
              <WarningIcon className="mt-0.5 size-4 shrink-0" weight="duotone" />
              <span>
                <InlineCode text={warning.message} />
              </span>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Button asChild variant="outline" size="xs">
          <a href={fileUrls.renderPdf(render.render_id)} target="_blank" rel="noopener noreferrer">
            <FilePdfIcon /> Ver PDF
          </a>
        </Button>
        {render.docx_path && (
          <Button asChild variant="ghost" size="xs">
            <a href={fileUrls.renderDocx(render.render_id)} download>
              <DownloadSimpleIcon /> DOCX
            </a>
          </Button>
        )}
        <label className="flex cursor-pointer items-center gap-1.5 px-1 text-xs text-muted-foreground">
          <input
            type="checkbox"
            checked={comparing}
            onChange={(e) => onCompare(e.target.checked)}
            className="size-3.5 accent-[var(--primary)]"
          />
          Comparar
        </label>
        {!render.selected && (
          <Button
            size="xs"
            variant="secondary"
            className="ml-auto"
            disabled={select.isPending}
            onClick={() => select.mutate(render.render_id)}
          >
            <PaperPlaneTiltIcon /> Usar este para enviar
          </Button>
        )}
      </div>
      {select.isError && (
        <p role="alert" className="mt-2 text-xs text-destructive">
          {select.error.message}
        </p>
      )}
    </li>
  )
}

function Compare({ renders, names, onClose }: { renders: RenderResult[]; names: Map<string, string>; onClose: () => void }) {
  return (
    <section aria-label="Comparación de renders" className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <h3 className="flex items-center gap-2 text-sm font-semibold">
          <ColumnsIcon className="size-4" /> Lado a lado
        </h3>
        <Button variant="ghost" size="xs" onClick={onClose}>
          Cerrar comparación
        </Button>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        {renders.map((render) => (
          <figure key={render.render_id} className="min-w-0">
            <figcaption className="mb-1.5 truncate text-xs text-muted-foreground">
              {names.get(render.template_id) ?? render.template_id} · {optionsSummary(render)}
            </figcaption>
            <iframe
              title={`PDF del render ${render.render_id}`}
              src={`${fileUrls.renderPdf(render.render_id)}#view=FitH`}
              className="h-[75vh] w-full rounded-lg border bg-white"
            />
          </figure>
        ))}
      </div>
    </section>
  )
}

function Renders({ cv, jobId, names }: { cv: CvView; jobId: number; names: Map<string, string> }) {
  const [compare, setCompare] = useState<number[]>([])
  const newest = [...cv.renders].reverse()
  const toggle = (id: number, on: boolean) =>
    setCompare((current) => (on ? [...current.filter((c) => c !== id), id].slice(-2) : current.filter((c) => c !== id)))
  const compared = compare
    .map((id) => cv.renders.find((r) => r.render_id === id))
    .filter((r): r is RenderResult => r !== undefined)

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold">
        Renders <span className="tabular font-normal text-muted-foreground">({cv.renders.length})</span>
      </h3>
      {compared.length === 2 && <Compare renders={compared} names={names} onClose={() => setCompare([])} />}
      {compared.length === 1 && (
        <p className="text-xs text-muted-foreground">Marca otro render para verlos lado a lado.</p>
      )}
      <ul className="space-y-3">
        {newest.map((render) => (
          <RenderCard
            key={render.render_id}
            render={render}
            templateName={names.get(render.template_id) ?? render.template_id}
            comparing={compare.includes(render.render_id)}
            onCompare={(on) => toggle(render.render_id, on)}
            jobId={jobId}
          />
        ))}
      </ul>
    </div>
  )
}

// --- Sección ------------------------------------------------------------------------------------

function CvBody({
  data,
  jobId,
  signals,
  templatesQuery,
}: {
  data: JobCv
  jobId: number
  signals?: JobView['signals']
  templatesQuery: ReturnType<typeof useTemplates>
}) {
  if (!data.cv) {
    return (
      <div className="flex items-start gap-4 rounded-lg border border-dashed p-5">
        <TerminalWindowIcon className="mt-0.5 size-6 shrink-0 text-primary" weight="duotone" />
        <div className="text-sm leading-relaxed">
          <p className="font-semibold">Aún sin CV</p>
          {data.can_render ? (
            <>
              <p className="mt-1 text-muted-foreground">
                Tu agente redacta el contenido desde tu perfil, lo verifica y lo renderiza (skill{' '}
                <Code>generate-cv {jobId}</Code>). Después podrás cambiar plantilla, foto y color aquí, sin IA.
              </p>
              <AgentButton action="generate-cv" jobId={jobId} variant="default" className="mt-3">
                Generar CV
              </AgentButton>
              <ClosedHint signals={signals} />
            </>
          ) : (
            <p className="mt-1 text-muted-foreground">Esta oferta no llegó a tener CV.</p>
          )}
        </div>
      </div>
    )
  }
  const templates = templatesQuery.data?.templates ?? []
  const names = new Map(templates.map((t) => [t.id, t.name]))
  return (
    <div className="space-y-8">
      <Verification cv={data.cv} />
      {data.can_render && (
        <AgentButton action="generate-cv" jobId={jobId}>
          Volver a redactar
        </AgentButton>
      )}
      {data.can_render &&
        (templatesQuery.isPending ? (
          <Skeleton className="h-40" />
        ) : templatesQuery.isError ? (
          <ErrorState error={templatesQuery.error} onRetry={() => templatesQuery.refetch()} className="border-0 p-0" />
        ) : (
          <RenderForm key={data.cv.document_id} cv={data.cv} jobId={jobId} templates={templates} />
        ))}
      <Renders cv={data.cv} jobId={jobId} names={names} />
    </div>
  )
}

export function CvSection({ job }: { job: JobView }) {
  const relevant = job.stage !== null && CV_SECTION_STAGES.has(job.stage)
  const cvQuery = useJobCv(job.id, relevant)
  const templatesQuery = useTemplates()
  if (!relevant) return null
  if (job.stage === 'closed' && cvQuery.data && !cvQuery.data.cv) return null
  return (
    <section id="cv" aria-label="CV" className="scroll-mt-6 rounded-xl border bg-card p-5 sm:p-6">
      <h2 className="mb-5 text-base font-semibold tracking-tight">CV</h2>
      {cvQuery.isPending ? (
        <Skeleton className="h-48" />
      ) : cvQuery.isError ? (
        <ErrorState error={cvQuery.error} onRetry={() => cvQuery.refetch()} className="border-0 p-0" />
      ) : (
        <CvBody data={cvQuery.data} jobId={job.id} signals={job.signals} templatesQuery={templatesQuery} />
      )}
    </section>
  )
}
