import { useState, type FormEvent, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import {
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
import { errorMessage } from '@/lib/errors'
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
  const { t } = useTranslation('pkg', { keyPrefix: 'form' })
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
          <Label htmlFor={`q-${id}`}>{t('question')}</Label>
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
        <Label htmlFor={`a-${id}`}>{t('answer')}</Label>
        <Textarea
          id={`a-${id}`}
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          rows={4}
          maxLength={MAX_ANSWER}
          autoFocus={!withQuestion}
        />
        <p className="text-xs text-muted-foreground">{t('emptyHint')}</p>
      </div>
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {errorMessage(error)}
        </p>
      )}
      <div className="flex gap-2">
        <Button type="submit" size="sm" disabled={pending || !question.trim()}>
          {t('save')}
        </Button>
        <Button type="button" variant="ghost" size="sm" onClick={onCancel}>
          {t('cancel')}
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
  const { t } = useTranslation('pkg', { keyPrefix: 'item' })
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
          {t('needsInput')}
        </p>
      )}
      {!editing &&
        (empty ? (
          <p className="text-sm text-muted-foreground italic">{t('noAnswer')}</p>
        ) : (
          <p className="text-sm leading-relaxed whitespace-pre-wrap">{item.answer}</p>
        ))}
      {!editing && item.evidence.length > 0 && (
        <div className="text-xs text-muted-foreground">
          <p>{t('evidence')}</p>
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
          <CopyButton text={item.answer} disabled={empty} ariaLabel={t('copyAria', { n: index + 1 })} />
          {canEdit && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={onEdit}
              aria-label={t('editAria', { n: index + 1 })}
            >
              <PencilSimpleIcon />
              {t('edit')}
            </Button>
          )}
        </div>
      )}
      {editing && children}
    </li>
  )
}

function Answers({ pkg }: { pkg: JobPackage }) {
  const { t } = useTranslation('pkg', { keyPrefix: 'answers' })
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
          {t('title')}
          {pkg.answers?.edited_by_user && (
            <span className="ml-2 rounded-full bg-muted px-2 py-0.5 text-xs font-normal text-muted-foreground">
              {t('editedByYou')}
            </span>
          )}
        </h3>
        {pkg.can_edit && editing === null && items.length < MAX_ANSWERS && (
          <Button type="button" variant="outline" size="sm" onClick={() => open('new')}>
            <PlusIcon />
            {t('add')}
          </Button>
        )}
      </div>
      {pendingCount > 0 && (
        <p
          role="status"
          className="rounded-lg border border-amber-500/50 bg-amber-500/10 px-3 py-2 text-sm text-amber-800 dark:text-amber-300"
        >
          {t('pending', { count: pendingCount })}
        </p>
      )}
      {items.length === 0 && editing !== 'new' && (
        <p className="text-sm leading-relaxed text-muted-foreground">
          <InlineCode text={t('none')} />
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
  const { t } = useTranslation('pkg', { keyPrefix: 'cv' })
  const cv = pkg.cv
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-medium">{t('title')}</h3>
      {cv ? (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
          <a
            href={`${API_URL}${cv.pdf_url}`}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 font-medium underline-offset-4 hover:underline"
          >
            <FilePdfIcon className="size-4 text-primary" />
            {t('openPdf')}
          </a>
          <span className="text-muted-foreground">
            {cv.sent ? t('sent') : t('selected')} · {cv.template_id} · {t('pages', { count: cv.pages })}
          </span>
          {cv.verified && (
            <span className="flex items-center gap-1 text-muted-foreground">
              <SealCheckIcon className="size-4 text-primary" weight="duotone" />
              {t('verified')}
            </span>
          )}
          {pkg.can_edit && (
            <a href="#cv" className="text-muted-foreground underline underline-offset-4 hover:text-foreground">
              {t('change')}
            </a>
          )}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">{t('none')}</p>
      )}
    </div>
  )
}

function CoverLetterSlot({ pkg }: { pkg: JobPackage }) {
  const { t } = useTranslation('pkg', { keyPrefix: 'letter' })
  const letter = pkg.cover_letter
  // Sin carta, el hueco ya lo explica la sección Carta, justo debajo.
  if (!letter) return null
  const state = letter.edited_by_user ? t('editedByYou') : letter.verified ? t('verified') : t('notVerified')
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-medium">{t('title')}</h3>
      <p className="text-sm text-muted-foreground">
        {t('words', { count: letter.word_count, state })}
      </p>
      <p className="line-clamp-3 text-sm leading-relaxed whitespace-pre-line">{letter.text}</p>
      <div className="flex flex-wrap items-center gap-2">
        <CopyButton text={letter.text} label={t('copy')} />
        {letter.pdf_url && (
          <Button asChild variant="outline" size="sm">
            <a href={`${API_URL}${letter.pdf_url}`} target="_blank" rel="noopener noreferrer">
              <FilePdfIcon /> {t('openPdf')}
            </a>
          </Button>
        )}
        <a href="#carta" className="text-sm text-muted-foreground underline underline-offset-4 hover:text-foreground">
          {pkg.can_edit ? t('change') : t('see')}
        </a>
      </div>
    </div>
  )
}

export function PackageSection({ job }: { job: JobView }) {
  const { t } = useTranslation('pkg')
  const relevant = job.stage !== null && PACKAGE_STAGES.has(job.stage)
  const { data, isPending, isError, error, refetch } = useJobPackage(job.id, relevant)
  if (!relevant) return null
  if (job.stage && ONLY_WITH_ANSWERS.has(job.stage) && (isPending || isError || !data?.answers)) return null
  return (
    <section
      id="paquete"
      aria-label={t('title')}
      className="scroll-mt-6 rounded-xl border bg-card p-5 sm:p-6"
    >
      <h2 className="text-base font-semibold tracking-tight">{t('title')}</h2>
      <p className="mt-1 mb-5 text-sm text-muted-foreground">
        {t('intro')}
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
