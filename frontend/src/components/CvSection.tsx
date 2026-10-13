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
import { Trans, useTranslation } from 'react-i18next'
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
import { errorMessage } from '@/lib/errors'
import { codeLabel, i18n, serverText } from '@/lib/i18n'
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

function Code({ children }: { children?: ReactNode }) {
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
  const { t } = useTranslation('cv', { keyPrefix: 'verification' })
  const verification = cv.verification
  if (!verification) {
    return (
      <p className="flex items-start gap-2 text-sm text-muted-foreground">
        <SealWarningIcon className="mt-0.5 size-4 shrink-0" />
        <span>
          <Trans t={t} i18nKey="pending" components={{ code: <Code /> }} />
        </span>
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
        {verification.passed ? t('passed') : t('failed')}
      </p>
      {verification.issues.length > 0 && (
        <ul className="space-y-1.5 text-sm">
          {verification.issues.map((issue, i) => (
            <li key={i} className="rounded-md bg-muted/70 px-3 py-2">
              <span className={cn('font-medium', issue.severity === 'blocker' && 'text-destructive')}>
                {issue.severity === 'blocker' ? t('blocker') : t('warning')} · {issue.location}
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
  const { t } = useTranslation('cv', { keyPrefix: 'template' })
  return (
    <fieldset>
      <legend className="mb-2 text-sm font-medium">{t('legend')}</legend>
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
                {template.from_user_cv && <Chip>{t('yourCv')}</Chip>}
              </span>
              <span className="block truncate text-xs text-muted-foreground">
                {template.ats_friendly ? t('ats') : t('notAts')}
                {template.photo_supported && t('withPhoto')}
                {template.engine === 'html' && t('pdfOnly')}
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
  const { t } = useTranslation('cv', { keyPrefix: 'photo' })
  return (
    <fieldset disabled={!supported}>
      <legend className="mb-2 text-sm font-medium">{t('legend')}</legend>
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
          ? t('autoHint')
          : t('unsupported')}
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
  const { t } = useTranslation('cv')
  return (
    <fieldset>
      <legend className="mb-2 text-sm font-medium">{t('accent')}</legend>
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
  const { t } = useTranslation('cv')
  const toggle = (section: SectionName, hide: boolean) =>
    onChange(hide ? [...hidden, section] : hidden.filter((s) => s !== section))
  return (
    <fieldset>
      <legend className="mb-2 text-sm font-medium">{t('hideSections')}</legend>
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
  const { t } = useTranslation('cv')
  const base = cv.renders.find((r) => r.selected) ?? cv.renders.at(-1)
  const [templateId, setTemplateId] = useState(base?.template_id ?? templates[0]?.id ?? '')
  const [photo, setPhoto] = useState<PhotoMode>('auto')
  const [accent, setAccent] = useState<string | null>(base?.options.accent_color ?? null)
  const [hidden, setHidden] = useState<SectionName[]>(base?.options.hidden_sections ?? [])
  const render = useRenderCv(jobId)

  const template = templates.find((tpl) => tpl.id === templateId)
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
    <form onSubmit={submit} aria-label={t('renderForm')} className="space-y-6">
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
          <InlineCode text={errorMessage(render.error)} />
        </p>
      )}
      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" disabled={!template || render.isPending} className="active:translate-y-px">
          <ArrowsClockwiseIcon className={cn(render.isPending && 'animate-spin')} />
          {render.isPending ? t('rendering') : t('render')}
        </Button>
        <p className="text-xs text-muted-foreground">
          {render.isPending
            ? t('renderingHint')
            : t('renderHint')}
        </p>
      </div>
    </form>
  )
}

// --- Renders -------------------------------------------------------------------------------------

function optionsSummary(render: RenderResult): string {
  const t = i18n.getFixedT(null, 'cv', 'summary')
  const parts = [render.options.photo ? t('withPhoto') : t('noPhoto')]
  if (render.options.accent_color) parts.push(colorLabel(render.options.accent_color))
  if (render.options.hidden_sections.length)
    parts.push(t('without', { sections: render.options.hidden_sections.map((s) => SECTION_LABEL[s].toLowerCase()).join(', ') }))
  return parts.join(' · ')
}

/** Un aviso del render: el mensaje del servidor, con su código traducido fuera del español. */
function warningText(warning: { code: string; message: string }): string {
  return serverText(codeLabel(`cv:warnings.${warning.code}`), warning.message)
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
  const { t } = useTranslation('cv')
  const select = useSelectRender(jobId)
  const coverage = render.keyword_coverage
  const total = coverage.present.length + coverage.missing.length
  const tooLong = render.warnings.some((w) => w.code === 'too_long')
  return (
    <li
      aria-label={t('renderAria', { id: render.render_id })}
      className={cn('rounded-lg border bg-background p-4', render.selected && 'border-primary/50 ring-1 ring-primary/30')}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="flex flex-wrap items-center gap-2 text-sm font-medium">
            {templateName}
            {render.selected && (
              <Chip tone="primary">
                <PaperPlaneTiltIcon weight="fill" /> {t('toSend')}
              </Chip>
            )}
            {render.template_changed && <Chip tone="warning">{t('templateChanged')}</Chip>}
          </p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {optionsSummary(render)} · {formatDateTime(render.created_at)}
          </p>
        </div>
        <dl className="flex gap-4 text-right text-xs">
          <div>
            <dt className="text-muted-foreground">{t('pages')}</dt>
            <dd className={cn('tabular font-medium', tooLong && 'text-destructive')}>
              {render.pages}/{render.max_pages}
            </dd>
          </div>
          {total > 0 && (
            <div>
              <dt className="text-muted-foreground">{t('keywords')}</dt>
              <dd
                className="tabular font-medium"
                title={coverage.missing.length ? t('missingKeywords', { list: coverage.missing.join(', ') }) : undefined}
              >
                {t('keywordsOf', { present: coverage.present.length, total })}
              </dd>
            </div>
          )}
        </dl>
      </div>

      {render.template_changed && (
        <p className="mt-2 text-xs text-muted-foreground">
          {t('templateChangedHint')}
        </p>
      )}
      {render.warnings.length > 0 && (
        <ul className="mt-3 space-y-1.5">
          {render.warnings.map((warning, i) => (
            <li key={i} className="flex items-start gap-2 text-sm text-warning-foreground">
              <WarningIcon className="mt-0.5 size-4 shrink-0" weight="duotone" />
              <span>
                <InlineCode text={warningText(warning)} />
              </span>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Button asChild variant="outline" size="xs">
          <a href={fileUrls.renderPdf(render.render_id)} target="_blank" rel="noopener noreferrer">
            <FilePdfIcon /> {t('viewPdf')}
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
          {t('compare')}
        </label>
        {!render.selected && (
          <Button
            size="xs"
            variant="secondary"
            className="ml-auto"
            disabled={select.isPending}
            onClick={() => select.mutate(render.render_id)}
          >
            <PaperPlaneTiltIcon /> {t('useThis')}
          </Button>
        )}
      </div>
      {select.isError && (
        <p role="alert" className="mt-2 text-xs text-destructive">
          {errorMessage(select.error)}
        </p>
      )}
    </li>
  )
}

function Compare({ renders, names, onClose }: { renders: RenderResult[]; names: Map<string, string>; onClose: () => void }) {
  const { t } = useTranslation('cv')
  return (
    <section aria-label={t('comparison')} className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <h3 className="flex items-center gap-2 text-sm font-semibold">
          <ColumnsIcon className="size-4" /> {t('sideBySide')}
        </h3>
        <Button variant="ghost" size="xs" onClick={onClose}>
          {t('closeComparison')}
        </Button>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        {renders.map((render) => (
          <figure key={render.render_id} className="min-w-0">
            <figcaption className="mb-1.5 truncate text-xs text-muted-foreground">
              {names.get(render.template_id) ?? render.template_id} · {optionsSummary(render)}
            </figcaption>
            <iframe
              title={t('pdfOf', { id: render.render_id })}
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
  const { t } = useTranslation('cv')
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
        {t('renders')} <span className="tabular font-normal text-muted-foreground">({cv.renders.length})</span>
      </h3>
      {compared.length === 2 && <Compare renders={compared} names={names} onClose={() => setCompare([])} />}
      {compared.length === 1 && (
        <p className="text-xs text-muted-foreground">{t('pickAnother')}</p>
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
  const { t } = useTranslation('cv')
  if (!data.cv) {
    return (
      <div className="flex items-start gap-4 rounded-lg border border-dashed p-5">
        <TerminalWindowIcon className="mt-0.5 size-6 shrink-0 text-primary" weight="duotone" />
        <div className="text-sm leading-relaxed">
          <p className="font-semibold">{t('none.title')}</p>
          {data.can_render ? (
            <>
              <p className="mt-1 text-muted-foreground">
                <Trans t={t} i18nKey="none.hint" values={{ id: jobId }} components={{ code: <Code /> }} />
              </p>
              <AgentButton action="generate-cv" jobId={jobId} variant="default" className="mt-3">
                {t('none.generate')}
              </AgentButton>
              <ClosedHint signals={signals} />
            </>
          ) : (
            <p className="mt-1 text-muted-foreground">{t('none.never')}</p>
          )}
        </div>
      </div>
    )
  }
  const templates = templatesQuery.data?.templates ?? []
  const names = new Map(templates.map((tpl) => [tpl.id, tpl.name]))
  return (
    <div className="space-y-8">
      <Verification cv={data.cv} />
      {data.can_render && (
        <AgentButton action="generate-cv" jobId={jobId}>
          {t('rewrite')}
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
  const { t } = useTranslation('cv')
  const relevant = job.stage !== null && CV_SECTION_STAGES.has(job.stage)
  const cvQuery = useJobCv(job.id, relevant)
  const templatesQuery = useTemplates()
  if (!relevant) return null
  if (job.stage === 'closed' && cvQuery.data && !cvQuery.data.cv) return null
  return (
    <section id="cv" aria-label={t('title')} className="scroll-mt-6 rounded-xl border bg-card p-5 sm:p-6">
      <h2 className="mb-5 text-base font-semibold tracking-tight">{t('title')}</h2>
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
