import { useState, type FormEvent, type ReactNode } from 'react'
import {
  EnvelopeSimpleIcon,
  FilePdfIcon,
  PencilSimpleIcon,
  PlusIcon,
  SealCheckIcon,
  WarningIcon,
} from '@phosphor-icons/react'
import { API_URL, type JobPackage, type JobView, type Stage } from '@/api/client'
import { useJobPackage, useSaveAnswers, type ScreeningAnswer } from '@/api/queries'
import { CopyButton } from '@/components/CopyButton'
import { ErrorState, InlineCode } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'

/** Desde que hay CV listo; en «approved» y «closed», solo si ya hay respuestas. */
const PACKAGE_STAGES = new Set<Stage>(['approved', 'cv_ready', 'applied', 'in_process', 'closed'])
const ONLY_WITH_ANSWERS = new Set<Stage>(['approved', 'closed'])
/** Los límites de `ApplicationAnswers` (backend). */
const MAX_QUESTION = 1000
const MAX_ANSWER = 5000
const MAX_ANSWERS = 50

/**
 * Al editar, una respuesta vacía queda pendiente de un dato tuyo; con texto, ya no. Si cambias el
 * texto, el respaldo incluye `user`: ya no es solo lo que se validó con el perfil.
 */
function withAnswer(item: ScreeningAnswer, answer: string): ScreeningAnswer {
  const changed = answer !== item.answer && answer.trim() !== ''
  const evidence = changed && !item.evidence.includes('user') ? [...item.evidence, 'user'] : item.evidence
  return { ...item, answer, evidence, needs_user_input: answer.trim() === '' }
}

function AnswerForm({
  initial,
  withQuestion,
  pending,
  error,
  onSubmit,
  onCancel,
}: {
  initial?: ScreeningAnswer
  withQuestion: boolean
  pending: boolean
  error: Error | null
  onSubmit: (question: string, answer: string) => void
  onCancel: () => void
}) {
  const [question, setQuestion] = useState(initial?.question ?? '')
  const [answer, setAnswer] = useState(initial?.answer ?? '')
  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (question.trim()) onSubmit(question.trim(), answer)
  }
  const id = initial ? 'edit' : 'new'
  return (
    <form onSubmit={submit} className="grid gap-3 rounded-lg border bg-background p-3">
      {withQuestion && (
        <div className="space-y-1.5">
          <Label htmlFor={`q-${id}`}>Pregunta</Label>
          <Input
            id={`q-${id}`}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            maxLength={MAX_QUESTION}
            required
          />
        </div>
      )}
      <div className="space-y-1.5">
        <Label htmlFor={`a-${id}`}>Respuesta</Label>
        <Textarea
          id={`a-${id}`}
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          rows={4}
          maxLength={MAX_ANSWER}
          autoFocus={!withQuestion}
        />
        <p className="text-xs text-muted-foreground">Si la dejas vacía, queda pendiente de un dato tuyo.</p>
      </div>
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error.message}
        </p>
      )}
      <div className="flex gap-2">
        <Button type="submit" size="sm" disabled={pending || !question.trim()}>
          Guardar
        </Button>
        <Button type="button" variant="ghost" size="sm" onClick={onCancel}>
          Cancelar
        </Button>
      </div>
    </form>
  )
}

function AnswerItem({
  item,
  index,
  evidence,
  canEdit,
  editing,
  onEdit,
  children,
}: {
  item: ScreeningAnswer
  index: number
  evidence: Record<string, string>
  canEdit: boolean
  editing: boolean
  onEdit: () => void
  children?: ReactNode // el formulario, al editar
}) {
  const empty = item.answer.trim() === ''
  return (
    <li
      className={cn(
        'space-y-2 rounded-lg border p-4',
        item.needs_user_input && 'border-amber-500/50 bg-amber-500/5',
      )}
    >
      <p className="text-sm font-medium">
        <span className="mr-1.5 text-muted-foreground tabular-nums">{index + 1}.</span>
        {item.question}
      </p>
      {item.needs_user_input && (
        <p className="flex items-center gap-1.5 text-sm font-medium text-amber-700 dark:text-amber-400">
          <WarningIcon className="size-4 shrink-0" weight="fill" />
          Falta un dato tuyo: complétala antes de enviar.
        </p>
      )}
      {!editing &&
        (empty ? (
          <p className="text-sm text-muted-foreground italic">Sin respuesta.</p>
        ) : (
          <p className="text-sm leading-relaxed whitespace-pre-wrap">{item.answer}</p>
        ))}
      {!editing && item.evidence.length > 0 && (
        <div className="text-xs text-muted-foreground">
          <p>Respaldo:</p>
          <ul className="mt-0.5 space-y-0.5">
            {item.evidence.map((ref) => (
              <li key={ref}>
                <span className="font-mono">{ref}</span>
                {evidence[ref] && <> · {evidence[ref]}</>}
              </li>
            ))}
          </ul>
        </div>
      )}
      {!editing && (
        <div className="flex flex-wrap gap-2 pt-1">
          <CopyButton text={item.answer} disabled={empty} ariaLabel={`Copiar la respuesta ${index + 1}`} />
          {canEdit && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={onEdit}
              aria-label={`Editar la respuesta ${index + 1}`}
            >
              <PencilSimpleIcon />
              Editar
            </Button>
          )}
        </div>
      )}
      {editing && children}
    </li>
  )
}

function Answers({ pkg }: { pkg: JobPackage }) {
  const save = useSaveAnswers(pkg.job_id)
  const [editing, setEditing] = useState<number | 'new' | null>(null)
  const items = pkg.answers?.answers ?? []
  const pendingCount = items.filter((a) => a.needs_user_input).length

  const store = (next: ScreeningAnswer[]) => save.mutate(next, { onSuccess: () => setEditing(null) })
  const open = (target: number | 'new') => {
    save.reset()
    setEditing(target)
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-sm font-medium">
          Respuestas de screening
          {pkg.answers?.edited_by_user && (
            <span className="ml-2 rounded-full bg-muted px-2 py-0.5 text-xs font-normal text-muted-foreground">
              Editadas por ti
            </span>
          )}
        </h3>
        {pkg.can_edit && editing === null && items.length < MAX_ANSWERS && (
          <Button type="button" variant="outline" size="sm" onClick={() => open('new')}>
            <PlusIcon />
            Añadir pregunta
          </Button>
        )}
      </div>
      {pendingCount > 0 && (
        <p
          role="status"
          className="rounded-lg border border-amber-500/50 bg-amber-500/10 px-3 py-2 text-sm text-amber-800 dark:text-amber-300"
        >
          {pendingCount === 1
            ? '1 respuesta espera un dato tuyo (salario, disponibilidad…).'
            : `${pendingCount} respuestas esperan un dato tuyo (salario, disponibilidad…).`}
        </p>
      )}
      {items.length === 0 && editing !== 'new' && (
        <p className="text-sm leading-relaxed text-muted-foreground">
          <InlineCode text="Aún no hay respuestas. Pega las preguntas del formulario a tu agente con el skill `prepare-application`, o añádelas tú." />
        </p>
      )}
      {items.length > 0 && (
        <ol className="space-y-3">
          {items.map((item, i) => (
            <AnswerItem
              key={i}
              item={item}
              index={i}
              evidence={pkg.answers?.evidence ?? {}}
              canEdit={pkg.can_edit && editing === null}
              editing={editing === i}
              onEdit={() => open(i)}
            >
              <AnswerForm
                initial={item}
                withQuestion={false}
                pending={save.isPending}
                error={save.error}
                onSubmit={(_q, answer) => store(items.map((a, j) => (j === i ? withAnswer(a, answer) : a)))}
                onCancel={() => setEditing(null)}
              />
            </AnswerItem>
          ))}
        </ol>
      )}
      {editing === 'new' && (
        <AnswerForm
          withQuestion
          pending={save.isPending}
          error={save.error}
          onSubmit={(question, answer) =>
            store([...items, withAnswer({ question, answer: '', evidence: ['user'], needs_user_input: true }, answer)])
          }
          onCancel={() => setEditing(null)}
        />
      )}
    </div>
  )
}

function ChosenCv({ pkg }: { pkg: JobPackage }) {
  const cv = pkg.cv
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-medium">CV</h3>
      {cv ? (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
          <a
            href={`${API_URL}${cv.pdf_url}`}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 font-medium underline-offset-4 hover:underline"
          >
            <FilePdfIcon className="size-4 text-primary" />
            Abrir PDF
          </a>
          <span className="text-muted-foreground">
            {cv.sent ? 'El que enviaste' : 'Seleccionado para enviar'} · {cv.template_id} · {cv.pages}{' '}
            {cv.pages === 1 ? 'página' : 'páginas'}
          </span>
          {cv.verified && (
            <span className="flex items-center gap-1 text-muted-foreground">
              <SealCheckIcon className="size-4 text-primary" weight="duotone" />
              Verificado
            </span>
          )}
          {pkg.can_edit && (
            <a href="#cv" className="text-muted-foreground underline underline-offset-4 hover:text-foreground">
              Cambiarlo en la sección CV
            </a>
          )}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">Aún no hay un CV seleccionado para enviar.</p>
      )}
    </div>
  )
}

function CoverLetterSlot({ pkg }: { pkg: JobPackage }) {
  const letter = pkg.cover_letter
  if (!letter) {
    return (
      <div className="flex items-start gap-3 rounded-lg border border-dashed p-4">
        <EnvelopeSimpleIcon className="mt-0.5 size-5 shrink-0 text-muted-foreground" />
        <div>
          <h3 className="text-sm font-medium">Carta de presentación</h3>
          <p className="mt-0.5 text-sm text-muted-foreground">
            <InlineCode
              text={`Sin carta. Si la oferta la pide o la quieres, ejecuta \`generate-cover-letter ${pkg.job_id}\` en tu agente.`}
            />
          </p>
        </div>
      </div>
    )
  }
  const state = letter.edited_by_user ? 'Editada por ti' : letter.verified ? 'Verificada' : 'Sin verificar'
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-medium">Carta de presentación</h3>
      <p className="text-sm text-muted-foreground">
        {letter.word_count} palabras · {state}
      </p>
      <p className="line-clamp-3 text-sm leading-relaxed whitespace-pre-line">{letter.text}</p>
      <div className="flex flex-wrap items-center gap-2">
        <CopyButton text={letter.text} label="Copiar carta" />
        {letter.pdf_url && (
          <Button asChild variant="outline" size="sm">
            <a href={`${API_URL}${letter.pdf_url}`} target="_blank" rel="noopener noreferrer">
              <FilePdfIcon /> Abrir PDF
            </a>
          </Button>
        )}
        <a href="#carta" className="text-sm text-muted-foreground underline underline-offset-4 hover:text-foreground">
          {pkg.can_edit ? 'Cambiarla en la sección Carta' : 'Verla en la sección Carta'}
        </a>
      </div>
    </div>
  )
}

export function PackageSection({ job }: { job: JobView }) {
  const relevant = job.stage !== null && PACKAGE_STAGES.has(job.stage)
  const { data, isPending, isError, error, refetch } = useJobPackage(job.id, relevant)
  if (!relevant) return null
  if (job.stage && ONLY_WITH_ANSWERS.has(job.stage) && (isPending || isError || !data?.answers)) return null
  return (
    <section
      id="paquete"
      aria-label="Paquete de candidatura"
      className="scroll-mt-6 rounded-xl border bg-card p-5 sm:p-6"
    >
      <h2 className="text-base font-semibold tracking-tight">Paquete de candidatura</h2>
      <p className="mt-1 mb-5 text-sm text-muted-foreground">
        Todo lo que necesitas para enviarla a mano. Desde aquí no se envía nada.
      </p>
      {isPending ? (
        <Skeleton className="h-32" />
      ) : isError ? (
        <ErrorState error={error} onRetry={() => refetch()} className="border-0 p-0" />
      ) : (
        <div className="space-y-7">
          <ChosenCv pkg={data} />
          <Answers pkg={data} />
          <CoverLetterSlot pkg={data} />
        </div>
      )}
    </section>
  )
}
