import { useState, type FormEvent, type ReactNode } from 'react'
import {
  ArrowsClockwiseIcon,
  DownloadSimpleIcon,
  EnvelopeSimpleIcon,
  FilePdfIcon,
  PaperPlaneTiltIcon,
  PencilSimpleIcon,
  SealCheckIcon,
  SealWarningIcon,
  WarningIcon,
} from '@phosphor-icons/react'
import {
  fileUrls,
  type CoverLetterView,
  type JobCoverLetter,
  type JobView,
  type LetterRenderResult,
  type Stage,
} from '@/api/client'
import {
  useJobCoverLetter,
  useRenderLetter,
  useSaveLetterBrief,
  useSaveUserLetter,
  useSelectRender,
  type CoverLetterContent,
  type CoverLetterRenderOptions,
} from '@/api/queries'
import { CopyButton } from '@/components/CopyButton'
import { ErrorState, InlineCode } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import { colorLabel, formatDateTime, PHOTO_MODE_LABEL } from '@/lib/labels'
import { countWords } from '@/lib/letters'
import { cn } from '@/lib/utils'

/** Desde la aprobación; en «closed», solo si hubo carta. */
const LETTER_STAGES = new Set<Stage>(['approved', 'cv_ready', 'applied', 'in_process', 'closed'])
type PhotoMode = NonNullable<CoverLetterRenderOptions['photo']>
const PHOTO_MODES: PhotoMode[] = ['auto', 'include', 'exclude']
const MAX_INSTRUCTIONS = 4000

function Code({ children }: { children: ReactNode }) {
  return (
    <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em] text-foreground">{children}</code>
  )
}

function Block({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-sm font-medium">{title}</h3>
        {action}
      </div>
      {children}
    </div>
  )
}

// --- Indicaciones -------------------------------------------------------------------------------

function Instructions({ data, jobId }: { data: JobCoverLetter; jobId: number }) {
  const { brief, preferences, max_words } = data.info
  const save = useSaveLetterBrief(jobId)
  const [editing, setEditing] = useState(false)
  const [instructions, setInstructions] = useState(brief?.instructions ?? '')
  const [maxWords, setMaxWords] = useState(brief?.max_words ? String(brief.max_words) : '')

  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate(
      { instructions, max_words: maxWords ? Number(maxWords) : null },
      { onSuccess: () => setEditing(false) },
    )
  }
  const general = [
    preferences?.max_words ? `máximo ${preferences.max_words} palabras` : null,
    preferences?.tone ? `tono ${preferences.tone}` : null,
    preferences?.avoid?.length ? `evitar: ${preferences.avoid.join(', ')}` : null,
  ].filter(Boolean)

  return (
    <Block
      title="Indicaciones"
      action={
        data.can_edit &&
        !editing && (
          <Button type="button" variant="outline" size="sm" onClick={() => setEditing(true)}>
            <PencilSimpleIcon />
            {brief?.instructions || brief?.max_words ? 'Editar indicaciones' : 'Añadir indicaciones'}
          </Button>
        )
      }
    >
      {editing ? (
        <form onSubmit={submit} className="grid gap-3 rounded-lg border bg-background p-3">
          <div className="space-y-1.5">
            <Label htmlFor="brief-instructions">Para esta oferta</Label>
            <Textarea
              id="brief-instructions"
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              maxLength={MAX_INSTRUCTIONS}
              rows={4}
              placeholder="Qué quieres que cuente: por qué esta empresa, algo que la carta deba mencionar…"
            />
            <p className="text-xs text-muted-foreground">
              Lo que escribas aquí es lo único que la carta puede contar de ti fuera de tu perfil.
            </p>
          </div>
          <div className="max-w-48 space-y-1.5">
            <Label htmlFor="brief-max-words">Máximo de palabras (opcional)</Label>
            <Input
              id="brief-max-words"
              type="number"
              min={50}
              max={600}
              value={maxWords}
              onChange={(e) => setMaxWords(e.target.value)}
            />
          </div>
          {save.error && (
            <p role="alert" className="text-sm text-destructive">
              {save.error.message}
            </p>
          )}
          <div className="flex gap-2">
            <Button type="submit" size="sm" disabled={save.isPending}>
              Guardar
            </Button>
            <Button type="button" variant="ghost" size="sm" onClick={() => setEditing(false)}>
              Cancelar
            </Button>
          </div>
        </form>
      ) : (
        <div className="space-y-2 text-sm">
          <p>
            <span className="text-muted-foreground">Para esta oferta: </span>
            {brief?.instructions || <span className="text-muted-foreground italic">ninguna</span>}
          </p>
          <p>
            <span className="text-muted-foreground">Generales (tu perfil): </span>
            {preferences?.instructions || general.length ? (
              <>
                {preferences?.instructions}
                {general.length > 0 && (
                  <span className="text-muted-foreground">
                    {preferences?.instructions ? ' · ' : ''}
                    {general.join(' · ')}
                  </span>
                )}
              </>
            ) : (
              <span className="text-muted-foreground">
                ninguna. Puedes añadirlas con el skill <Code>actualizar-perfil</Code>.
              </span>
            )}
          </p>
          <p className="text-muted-foreground">Límite: {max_words} palabras (mandan las de la oferta).</p>
        </div>
      )}
    </Block>
  )
}

// --- Carta --------------------------------------------------------------------------------------

function LetterStatus({ letter, maxWords }: { letter: CoverLetterView; maxWords: number }) {
  const verification = letter.verification
  return (
    <div className="space-y-2 text-sm">
      <p className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className={cn('tabular', letter.word_count > maxWords && 'text-destructive')}>
          {letter.word_count} de {maxWords} palabras
        </span>
        {letter.edited_by_user ? (
          <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">Editada por ti</span>
        ) : verification ? (
          <span className={cn('flex items-center gap-1.5', !verification.passed && 'text-destructive')}>
            {verification.passed ? (
              <SealCheckIcon className="size-4 text-primary" weight="duotone" />
            ) : (
              <SealWarningIcon className="size-4" weight="duotone" />
            )}
            {verification.passed ? 'Verificada' : 'El verificador encontró problemas'}
          </span>
        ) : (
          <span className="flex items-center gap-1.5 text-muted-foreground">
            <SealWarningIcon className="size-4" /> Sin verificar
          </span>
        )}
      </p>
      {verification && !letter.edited_by_user && verification.issues.length > 0 && (
        <ul className="space-y-1.5">
          {verification.issues.map((issue, i) => (
            <li key={i} className="rounded-md bg-muted/70 px-3 py-2">
              <span className={cn('font-medium', issue.severity === 'blocker' && 'text-destructive')}>
                {issue.severity === 'blocker' ? 'Bloqueante' : 'Aviso'} · {issue.location}
              </span>
              <span className="block text-foreground/85">{issue.problem}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function LetterText({ content }: { content: CoverLetterContent }) {
  return (
    <div className="space-y-3 rounded-lg border bg-background p-4 text-sm leading-relaxed">
      {content.recipient && <p className="font-medium">{content.recipient}</p>}
      <p>{content.greeting}</p>
      {content.paragraphs.map((p, i) => (
        <p key={i}>{p.text}</p>
      ))}
      <p>{content.sign_off}</p>
    </div>
  )
}

function LetterEditor({
  letter,
  jobId,
  maxWords,
  onDone,
}: {
  letter: CoverLetterView
  jobId: number
  maxWords: number
  onDone: () => void
}) {
  const original = letter.content
  const [greeting, setGreeting] = useState(original.greeting)
  const [paragraphs, setParagraphs] = useState(original.paragraphs.map((p) => p.text))
  const [signOff, setSignOff] = useState(original.sign_off)
  const save = useSaveUserLetter(jobId)
  const words = countWords(paragraphs)
  const texts = paragraphs.map((p) => p.trim())
  const changed =
    greeting !== original.greeting ||
    signOff !== original.sign_off ||
    texts.some((text, i) => text !== original.paragraphs[i]?.text)
  const empty = texts.every((text) => !text)

  // Los párrafos cambiados pasan a citar también `user`: lo marca el servidor al guardar.
  const submit = (e: FormEvent) => {
    e.preventDefault()
    const kept = original.paragraphs
      .map((p, i) => ({ ...p, text: texts[i] ?? '' }))
      .filter((p) => p.text)
    save.mutate({ ...original, greeting, sign_off: signOff, paragraphs: kept }, { onSuccess: onDone })
  }

  return (
    <form onSubmit={submit} aria-label="Editar la carta" className="grid gap-3 rounded-lg border bg-background p-3">
      <div className="space-y-1.5">
        <Label htmlFor="letter-greeting">Saludo</Label>
        <Input id="letter-greeting" value={greeting} onChange={(e) => setGreeting(e.target.value)} required />
      </div>
      {paragraphs.map((text, i) => (
        <div key={i} className="space-y-1.5">
          <Label htmlFor={`letter-p${i}`}>Párrafo {i + 1}</Label>
          <Textarea
            id={`letter-p${i}`}
            value={text}
            rows={4}
            onChange={(e) => setParagraphs((all) => all.map((p, j) => (j === i ? e.target.value : p)))}
          />
        </div>
      ))}
      <div className="space-y-1.5">
        <Label htmlFor="letter-sign-off">Despedida</Label>
        <Input id="letter-sign-off" value={signOff} onChange={(e) => setSignOff(e.target.value)} required />
      </div>
      <p className={cn('text-xs', words > maxWords ? 'text-destructive' : 'text-muted-foreground')}>
        {words} de {maxWords} palabras. Se guarda como una carta nueva «Editada por ti», sin verificar.
        Un párrafo vacío se quita.
      </p>
      {empty && (
        <p role="alert" className="text-sm text-destructive">
          La carta necesita al menos un párrafo.
        </p>
      )}
      {save.error && (
        <p role="alert" className="text-sm text-destructive">
          <InlineCode text={save.error.message} />
        </p>
      )}
      <div className="flex gap-2">
        <Button type="submit" size="sm" disabled={save.isPending || !changed || empty}>
          {save.isPending ? 'Guardando…' : 'Guardar'}
        </Button>
        <Button type="button" variant="ghost" size="sm" onClick={onDone}>
          Cancelar
        </Button>
      </div>
    </form>
  )
}

// --- Renders ------------------------------------------------------------------------------------

const MATCH_CV = ''

function RenderForm({ data, letter, jobId }: { data: JobCoverLetter; letter: CoverLetterView; jobId: number }) {
  const [templateId, setTemplateId] = useState(MATCH_CV)
  const [photo, setPhoto] = useState<PhotoMode>('auto')
  const [accent, setAccent] = useState<string | null>(null)
  const render = useRenderLetter(jobId)
  const names = new Map(data.templates.map((t) => [t.id, t.name]))
  const template = data.templates.find((t) => t.id === templateId)
  const colors = template?.accent_colors ?? null
  const cvName = data.cv_template_id ? (names.get(data.cv_template_id) ?? data.cv_template_id) : null

  const submit = (e: FormEvent) => {
    e.preventDefault()
    render.mutate({
      documentId: letter.document_id,
      options: {
        template_id: templateId || null,
        photo: template && !template.photo_supported ? 'exclude' : photo,
        accent_color: colors ? (accent ?? colors.default) : null,
      },
    })
  }

  return (
    <form onSubmit={submit} aria-label="Renderizar la carta" className="grid gap-4 sm:grid-cols-3">
      <div className="space-y-1.5 sm:col-span-3">
        <Label htmlFor="letter-template">Diseño</Label>
        <select
          id="letter-template"
          value={templateId}
          onChange={(e) => {
            setTemplateId(e.target.value)
            setAccent(null)
          }}
          className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
        >
          <option value={MATCH_CV}>A juego con el CV{cvName ? ` (${cvName})` : ''}</option>
          {data.templates.map((t) => (
            <option key={t.id} value={t.id}>
              {t.name}
            </option>
          ))}
        </select>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="letter-photo">Foto</Label>
        <select
          id="letter-photo"
          value={template && !template.photo_supported ? 'exclude' : photo}
          disabled={Boolean(template && !template.photo_supported)}
          onChange={(e) => setPhoto(e.target.value as PhotoMode)}
          className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
        >
          {PHOTO_MODES.map((mode) => (
            <option key={mode} value={mode}>
              {mode === 'auto' ? 'Como el CV' : PHOTO_MODE_LABEL[mode]}
            </option>
          ))}
        </select>
      </div>
      {colors && (
        <div className="space-y-1.5">
          <Label htmlFor="letter-color">Color</Label>
          <select
            id="letter-color"
            value={accent ?? colors.default}
            onChange={(e) => setAccent(e.target.value)}
            className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
          >
            {colors.choices.map((c) => (
              <option key={c} value={c}>
                {colorLabel(c)}
              </option>
            ))}
          </select>
        </div>
      )}
      <div className="flex items-end sm:col-span-3">
        <Button type="submit" disabled={render.isPending}>
          <ArrowsClockwiseIcon className={cn(render.isPending && 'animate-spin')} />
          {render.isPending ? 'Renderizando…' : 'Renderizar'}
        </Button>
      </div>
      {render.isError && (
        <p role="alert" className="text-sm text-destructive sm:col-span-3">
          <InlineCode text={render.error.message} />
        </p>
      )}
    </form>
  )
}

function RenderCard({ render, name, jobId }: { render: LetterRenderResult; name: string; jobId: number }) {
  const select = useSelectRender(jobId)
  const parts = [render.options.photo ? 'Con foto' : 'Sin foto']
  if (render.options.accent_color) parts.push(colorLabel(render.options.accent_color))
  return (
    <li
      aria-label={`Render de carta ${render.render_id}`}
      className={cn('rounded-lg border bg-background p-4', render.selected && 'border-primary/50 ring-1 ring-primary/30')}
    >
      <p className="flex flex-wrap items-center gap-2 text-sm font-medium">
        {name}
        {render.selected && (
          <span className="inline-flex h-5 items-center gap-1 rounded-full bg-primary px-2 text-[0.7rem] text-primary-foreground">
            <PaperPlaneTiltIcon weight="fill" /> Para enviar
          </span>
        )}
      </p>
      <p className="mt-0.5 text-xs text-muted-foreground">
        {parts.join(' · ')} · {render.pages} pág. · {formatDateTime(render.created_at)}
      </p>
      {render.warnings.length > 0 && (
        <ul className="mt-2 space-y-1.5">
          {render.warnings.map((w, i) => (
            <li key={i} className="flex items-start gap-2 text-sm text-warning-foreground">
              <WarningIcon className="mt-0.5 size-4 shrink-0" weight="duotone" />
              <span>
                <InlineCode text={w.message} />
              </span>
            </li>
          ))}
        </ul>
      )}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Button asChild variant="outline" size="xs">
          <a href={fileUrls.renderPdf(render.render_id)} target="_blank" rel="noopener noreferrer">
            <FilePdfIcon /> Descargar PDF
          </a>
        </Button>
        {render.docx_path && (
          <Button asChild variant="ghost" size="xs">
            <a href={fileUrls.renderDocx(render.render_id)} download>
              <DownloadSimpleIcon /> DOCX
            </a>
          </Button>
        )}
        {!render.selected && (
          <Button
            size="xs"
            variant="secondary"
            className="ml-auto"
            disabled={select.isPending}
            onClick={() => select.mutate(render.render_id)}
            aria-label={`Usar el render ${render.render_id} de la carta para enviar`}
          >
            <PaperPlaneTiltIcon /> Usar esta para enviar
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

// --- Sección ------------------------------------------------------------------------------------

function Letter({ data, jobId }: { data: JobCoverLetter; jobId: number }) {
  const letter = data.info.letter
  const [editing, setEditing] = useState(false)
  if (!letter) {
    return (
      <div className="flex items-start gap-4 rounded-lg border border-dashed p-5">
        <EnvelopeSimpleIcon className="mt-0.5 size-6 shrink-0 text-primary" weight="duotone" />
        <div className="text-sm leading-relaxed">
          <p className="font-semibold">Aún sin carta</p>
          {data.can_edit ? (
            <p className="mt-1 text-muted-foreground">
              Ejecuta <Code>generar-carta {jobId}</Code> en tu agente: la redacta con tus indicaciones,
              la verifica y la deja a juego con tu CV. Después podrás copiarla, retocarla y cambiar el
              diseño aquí, sin IA.
            </p>
          ) : (
            <p className="mt-1 text-muted-foreground">Esta oferta no llegó a tener carta.</p>
          )}
        </div>
      </div>
    )
  }
  const names = new Map(data.templates.map((t) => [t.id, t.name]))
  return (
    <div className="space-y-6">
      <LetterStatus letter={letter} maxWords={data.info.max_words} />
      {editing ? (
        <LetterEditor
          key={letter.document_id}
          letter={letter}
          jobId={jobId}
          maxWords={data.info.max_words}
          onDone={() => setEditing(false)}
        />
      ) : (
        <>
          <LetterText content={letter.content} />
          <div className="flex flex-wrap gap-2">
            <CopyButton text={data.plain_text ?? ''} label="Copiar texto" />
            <Button asChild variant="outline" size="sm">
              <a href={fileUrls.letterText(letter.document_id)} download>
                <DownloadSimpleIcon /> Descargar TXT
              </a>
            </Button>
            {data.can_edit && (
              <Button type="button" variant="ghost" size="sm" onClick={() => setEditing(true)}>
                <PencilSimpleIcon /> Editar
              </Button>
            )}
          </div>
        </>
      )}
      {data.can_edit && <RenderForm key={letter.document_id} data={data} letter={letter} jobId={jobId} />}
      <Block title={`Renders (${letter.renders.length})`}>
        <ul className="space-y-3">
          {[...letter.renders].reverse().map((render) => (
            <RenderCard
              key={render.render_id}
              render={render}
              name={names.get(render.template_id) ?? render.template_id}
              jobId={jobId}
            />
          ))}
        </ul>
      </Block>
    </div>
  )
}

export function CoverLetterSection({ job }: { job: JobView }) {
  const relevant = job.stage !== null && LETTER_STAGES.has(job.stage)
  const { data, isPending, isError, error, refetch } = useJobCoverLetter(job.id, relevant)
  if (!relevant) return null
  if (job.stage === 'closed' && data && !data.info.letter) return null
  return (
    <section
      id="carta"
      aria-label="Carta de presentación"
      className="scroll-mt-6 rounded-xl border bg-card p-5 sm:p-6"
    >
      <h2 className="mb-5 text-base font-semibold tracking-tight">Carta de presentación</h2>
      {isPending ? (
        <Skeleton className="h-40" />
      ) : isError ? (
        <ErrorState error={error} onRetry={() => refetch()} className="border-0 p-0" />
      ) : (
        <div className="space-y-8">
          <Instructions key={data.info.brief?.updated_at ?? 'none'} data={data} jobId={job.id} />
          <Letter data={data} jobId={job.id} />
        </div>
      )}
    </section>
  )
}
