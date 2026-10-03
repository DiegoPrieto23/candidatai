import { useState, type FormEvent, type ReactNode } from 'react'
import { Link, useLocation, useParams } from 'react-router'
import {
  ArrowCounterClockwiseIcon,
  ArrowLeftIcon,
  ArrowSquareOutIcon,
  CaretDownIcon,
  CheckCircleIcon,
  CheckIcon,
  CopyIcon,
  HourglassMediumIcon,
  InfoIcon,
  NotePencilIcon,
  ShieldWarningIcon,
  XIcon,
} from '@phosphor-icons/react'
import type { AddJobResult, EventOut, JobView, Schemas } from '@/api/client'
import { useAddNote, useJob, useJobEvent, useJobMatch, type UserEventBody } from '@/api/queries'
import { CvSection } from '@/components/CvSection'
import { DiscardDialog } from '@/components/DiscardDialog'
import { MatchDetails, ScoreBadge } from '@/components/MatchDetails'
import { ProcessSection } from '@/components/ProcessSection'
import { StageBadge } from '@/components/StageBadge'
import { ErrorState } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import {
  actorLabel,
  discardReasonLabel,
  EMPLOYMENT_LABEL,
  eventLabel,
  formatDate,
  formatDateTime,
  formatSalary,
  REMOTE_LABEL,
  riskLabel,
  SENIORITY_LABEL,
  VERDICT_LABEL,
} from '@/lib/labels'
import { cn } from '@/lib/utils'

/** Lo que deja la pantalla de alta al navegar aquí. */
export interface AddedState {
  added: AddJobResult
}

function AddedNotice({ added }: { added: AddJobResult }) {
  const [open, setOpen] = useState(true)
  if (!open) return null
  const tone = added.created && !added.duplicate_of
  const Icon = tone ? CheckCircleIcon : added.created ? CopyIcon : InfoIcon
  let text: ReactNode
  if (!added.created) text = 'Esta oferta ya estaba dada de alta. No se ha cambiado nada.'
  else if (added.duplicate_of)
    text = (
      <>
        Dada de alta, pero parece un duplicado de la{' '}
        <Link to={`/jobs/${added.duplicate_of}`} className="font-medium underline underline-offset-4">
          oferta {added.duplicate_of}
        </Link>
        , así que queda cerrada.
      </>
    )
  else text = 'Oferta dada de alta. Tu agente la extraerá con el skill procesar-ofertas.'
  return (
    <div
      role="status"
      className={cn(
        'mb-6 flex items-start gap-3 rounded-xl border px-4 py-3 text-sm animate-in fade-in slide-in-from-top-1',
        tone ? 'border-primary/20 bg-accent/60 text-accent-foreground' : 'bg-card',
      )}
    >
      <Icon className="mt-0.5 size-[18px] shrink-0" weight="duotone" />
      <p className="flex-1">{text}</p>
      <button
        type="button"
        onClick={() => setOpen(false)}
        className="text-xs text-muted-foreground hover:text-foreground"
      >
        Cerrar
      </button>
    </div>
  )
}

function InjectionAlert({ injection }: { injection: NonNullable<JobView['injection']> }) {
  const excerpts = injection.reports.filter((r) => r.excerpt)
  return (
    <section
      aria-label="Aviso de posible inyección"
      className="rounded-xl border border-warning-border bg-warning p-5 text-warning-foreground"
    >
      <div className="flex items-start gap-3">
        <ShieldWarningIcon className="mt-0.5 size-6 shrink-0" weight="duotone" />
        <div className="min-w-0 flex-1 space-y-3">
          <div>
            <h2 className="font-semibold">Posible contenido dirigido a una IA</h2>
            <p className="mt-1 text-sm opacity-90">
              El texto de esta oferta podría intentar manipular a un agente. Se trata solo como datos,
              pero revísala con calma antes de confiar en la extracción.
            </p>
          </div>
          {injection.risk_flags.length > 0 && (
            <ul className="flex flex-wrap gap-1.5">
              {injection.risk_flags.map((flag) => (
                <li
                  key={flag}
                  className="rounded-full border border-warning-border/70 px-2.5 py-0.5 text-xs font-medium"
                >
                  {riskLabel(flag)}
                </li>
              ))}
            </ul>
          )}
          {excerpts.map((report, i) => (
            <figure key={i} className="text-sm">
              <blockquote className="border-l-2 border-warning-border pl-3 font-mono text-[0.8rem] leading-relaxed break-words">
                {report.excerpt}
              </blockquote>
              <figcaption className="mt-1 text-xs opacity-80">
                Detectado por {report.source === 'agent' ? actorLabel('agent', report.agent_name) : 'el sistema'}
              </figcaption>
            </figure>
          ))}
        </div>
      </div>
    </section>
  )
}

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-1 text-sm font-medium break-words">{children}</dd>
    </div>
  )
}

function SkillList({ skills, strong }: { skills: string[]; strong?: boolean }) {
  if (!skills.length) return <p className="text-sm text-muted-foreground">Ninguna indicada.</p>
  return (
    <ul className="flex flex-wrap gap-1.5">
      {skills.map((skill) => (
        <li
          key={skill}
          className={cn(
            'rounded-md px-2 py-1 text-[0.8rem] leading-none',
            strong
              ? 'bg-accent font-medium text-accent-foreground ring-1 ring-primary/15 ring-inset'
              : 'text-foreground/80 ring-1 ring-input ring-inset',
          )}
        >
          {skill}
        </li>
      ))}
    </ul>
  )
}

function ExtractionPanel({ extraction }: { extraction: Schemas['ExtractionView'] }) {
  const data = extraction.data
  const salary = formatSalary(data.salary)
  const languages = data.languages_required
    .map((l) => (l.level ? `${l.language} ${l.level}` : l.language))
    .join(', ')
  return (
    <div className="space-y-8">
      <dl className="grid grid-cols-2 gap-x-6 gap-y-5 sm:grid-cols-3">
        <Fact label="Seniority">{SENIORITY_LABEL[data.seniority]}</Fact>
        <Fact label="Modalidad">{REMOTE_LABEL[data.remote_mode]}</Fact>
        <Fact label="Experiencia mínima">
          {data.years_experience_min != null
            ? `${data.years_experience_min} ${data.years_experience_min === 1 ? 'año' : 'años'}`
            : <span className="font-normal text-muted-foreground">Sin especificar</span>}
        </Fact>
        <Fact label="Contrato">{EMPLOYMENT_LABEL[data.employment_type]}</Fact>
        <Fact label="Salario">
          {salary ?? <span className="font-normal text-muted-foreground">No lo indica</span>}
        </Fact>
        <Fact label="Idiomas">
          {languages || <span className="font-normal text-muted-foreground">No indica</span>}
        </Fact>
        {data.locations.length > 0 && <Fact label="Ubicación">{data.locations.join(', ')}</Fact>}
        {data.domain && <Fact label="Sector">{data.domain}</Fact>}
        {data.application_deadline && (
          <Fact label="Plazo">{formatDate(data.application_deadline)}</Fact>
        )}
      </dl>

      <div className="grid gap-6 sm:grid-cols-2">
        <div className="space-y-2.5">
          <h3 className="text-sm font-semibold">Obligatorias</h3>
          <SkillList skills={data.must_have_skills} strong />
        </div>
        <div className="space-y-2.5">
          <h3 className="text-sm font-semibold">Deseables</h3>
          <SkillList skills={data.nice_to_have_skills} />
        </div>
      </div>

      {data.responsibilities.length > 0 && (
        <div className="space-y-2.5">
          <h3 className="text-sm font-semibold">Responsabilidades</h3>
          <ul className="space-y-1.5 text-sm leading-relaxed text-foreground/85">
            {data.responsibilities.map((r) => (
              <li key={r} className="flex gap-2.5">
                <span className="mt-[0.6em] size-1 shrink-0 rounded-full bg-muted-foreground/50" />
                {r}
              </li>
            ))}
          </ul>
        </div>
      )}

      {data.red_flags.length > 0 && (
        <div className="space-y-2.5">
          <h3 className="text-sm font-semibold">A tener en cuenta</h3>
          <ul className="space-y-1.5 text-sm text-foreground/85">
            {data.red_flags.map((flag) => (
              <li key={flag} className="flex gap-2.5">
                <InfoIcon className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
                {flag}
              </li>
            ))}
          </ul>
        </div>
      )}

      <p className="text-xs text-muted-foreground">
        Extraída el {formatDateTime(extraction.created_at)}
      </p>
    </div>
  )
}

function Panel({ title, children, className }: { title: string; children: ReactNode; className?: string }) {
  return (
    <section className={cn('rounded-xl border bg-card p-5 sm:p-6', className)}>
      <h2 className="mb-5 text-base font-semibold tracking-tight">{title}</h2>
      {children}
    </section>
  )
}

function OriginalText({ text }: { text: string }) {
  const [open, setOpen] = useState(false)
  return (
    <Collapsible open={open} onOpenChange={setOpen} className="rounded-xl border bg-card">
      <CollapsibleTrigger className="flex w-full items-center justify-between gap-4 rounded-xl p-5 text-left outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 sm:px-6">
        <span>
          <span className="block text-base font-semibold tracking-tight">Texto original</span>
          <span className="text-xs text-muted-foreground">
            Tal cual se guardó. Contenido no confiable: se muestra, nunca se interpreta.
          </span>
        </span>
        <CaretDownIcon
          className={cn('size-4 shrink-0 text-muted-foreground transition-transform', open && 'rotate-180')}
        />
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className="border-t px-5 py-5 sm:px-6">
          <p className="max-w-[72ch] text-sm leading-relaxed whitespace-pre-wrap break-words text-foreground/85">
            {text}
          </p>
        </div>
      </CollapsibleContent>
    </Collapsible>
  )
}

function eventDetail(event: EventOut): string | null {
  const payload = event.payload as Record<string, unknown>
  if (event.type === 'discarded' && typeof payload.reason === 'string') {
    const note = typeof payload.note === 'string' ? `. ${payload.note}` : ''
    return `Motivo: ${discardReasonLabel(payload.reason)}${note}`
  }
  if (typeof payload.note === 'string') return payload.note
  if (event.type === 'hard_filter_failed' && Array.isArray(payload.failures))
    return (payload.failures as { reason?: string }[]).map((f) => f.reason).join('\n')
  if (event.type === 'scored' && typeof payload.score === 'number') return `Score ${payload.score}/100`
  if (event.type === 'fit_assessed' && typeof payload.verdict === 'string')
    return VERDICT_LABEL[payload.verdict as keyof typeof VERDICT_LABEL] ?? payload.verdict
  if (event.type === 'duplicate_detected' && payload.duplicate_of)
    return `Duplicado de la oferta ${String(payload.duplicate_of)}.`
  if (event.type === 'extraction_failed' && typeof payload.reason === 'string') return payload.reason
  return null
}

function Timeline({ events }: { events: EventOut[] }) {
  const ordered = [...events].reverse() // lo último, arriba
  return (
    <ol className="relative">
      {ordered.map((event, i) => {
        const detail = eventDetail(event)
        const warning = event.type === 'injection_suspected'
        return (
          <li key={event.id} className="relative flex gap-3.5 pb-5 last:pb-0">
            {i < ordered.length - 1 && (
              <span aria-hidden className="absolute top-5 bottom-0 left-[5px] w-px bg-border" />
            )}
            <span
              aria-hidden
              className={cn(
                'relative mt-1.5 size-[11px] shrink-0 rounded-full border-2 bg-card',
                warning
                  ? 'border-warning-border bg-warning'
                  : i === 0
                    ? 'border-primary bg-primary'
                    : 'border-input',
              )}
            />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium">{eventLabel(event.type)}</p>
              <p className="mt-0.5 text-xs text-muted-foreground">
                {actorLabel(event.actor, event.agent_name)}
                <span aria-hidden> · </span>
                <time dateTime={event.occurred_at}>{formatDateTime(event.occurred_at)}</time>
              </p>
              {detail && (
                <p className="mt-2 rounded-md bg-muted/70 px-3 py-2 text-sm leading-relaxed whitespace-pre-wrap break-words">
                  {detail}
                </p>
              )}
            </div>
          </li>
        )
      })}
    </ol>
  )
}

function NoteForm({ jobId }: { jobId: number }) {
  const [note, setNote] = useState('')
  const addNote = useAddNote(jobId)
  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!note.trim()) return
    addNote.mutate(note.trim(), { onSuccess: () => setNote('') })
  }
  return (
    <form onSubmit={submit} className="space-y-2">
      <Label htmlFor="note">Añadir nota</Label>
      <Textarea
        id="note"
        value={note}
        onChange={(e) => setNote(e.target.value)}
        maxLength={2000}
        rows={3}
        placeholder="Qué te ha dicho el recruiter, dudas, próximos pasos…"
        className="resize-y bg-background"
      />
      {addNote.isError && (
        <p role="alert" className="text-sm text-destructive">
          {addNote.error.message}
        </p>
      )}
      <div className="flex justify-end">
        <Button type="submit" size="sm" disabled={!note.trim() || addNote.isPending} className="active:translate-y-px">
          <NotePencilIcon />
          {addNote.isPending ? 'Guardando…' : 'Guardar nota'}
        </Button>
      </div>
    </form>
  )
}

function MatchPanel({ job }: { job: JobView }) {
  const { data: match, isPending, isError, error, refetch } = useJobMatch(job.id, job.extraction !== null)
  if (!job.extraction) return null
  return (
    <section className="rounded-xl border bg-card p-5 sm:p-6" aria-label="Encaje">
      <div className="mb-5 flex items-start justify-between gap-4">
        <h2 className="text-base font-semibold tracking-tight">Encaje</h2>
        {match && <ScoreBadge score={match.score} threshold={match.triage_threshold} size="lg" />}
      </div>
      {isPending ? (
        <Skeleton className="h-40" />
      ) : isError ? (
        <ErrorState error={error} onRetry={() => refetch()} className="border-0 p-0" />
      ) : match ? (
        <MatchDetails match={match} />
      ) : (
        <p className="text-sm text-muted-foreground">
          Sin score: importa tu perfil con{' '}
          <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em] text-foreground">jh profile import</code>.
        </p>
      )}
    </section>
  )
}

/** Aprobar o descartar (en triaje), descartar un resumen de una alerta y reabrir (si está cerrada). */
function Decision({ job }: { job: JobView }) {
  const event = useJobEvent()
  const [discarding, setDiscarding] = useState(false)
  const send = (body: UserEventBody) =>
    event.mutate({ jobId: job.id, body }, { onSuccess: () => setDiscarding(false) })
  if (job.stage === 'closed') {
    return (
      <div className="flex flex-col items-end gap-1">
        <Button variant="outline" size="sm" onClick={() => send({ type: 'reopened' })} disabled={event.isPending}>
          <ArrowCounterClockwiseIcon />
          Reabrir
        </Button>
        {event.isError && <p role="alert" className="text-xs text-destructive">{event.error.message}</p>}
      </div>
    )
  }
  if (job.stage !== 'pending_triage' && job.stage !== 'pending_detail') return null
  return (
    <div className="flex flex-col items-end gap-1">
      <div className="flex gap-2">
        {job.stage === 'pending_triage' && (
          <Button size="sm" onClick={() => send({ type: 'approved' })} disabled={event.isPending}>
            <CheckIcon weight="bold" />
            Aprobar
          </Button>
        )}
        <Button variant="outline" size="sm" onClick={() => setDiscarding(true)} disabled={event.isPending}>
          <XIcon weight="bold" />
          Descartar
        </Button>
      </div>
      {event.isError && !discarding && <p role="alert" className="text-xs text-destructive">{event.error.message}</p>}
      <DiscardDialog
        open={discarding}
        onOpenChange={setDiscarding}
        jobTitle={`${job.title} · ${job.company}`}
        pending={event.isPending}
        error={event.isError ? event.error.message : null}
        onConfirm={(choice) => send({ type: 'discarded', reason: choice.reason, note: choice.note })}
      />
    </div>
  )
}

function JobSkeleton() {
  return (
    <div aria-busy="true" aria-label="Cargando oferta" className="space-y-6">
      <div className="space-y-3">
        <Skeleton className="h-8 w-[min(28rem,80%)]" />
        <Skeleton className="h-4 w-56" />
      </div>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <Skeleton className="h-80 rounded-xl" />
        <Skeleton className="h-64 rounded-xl" />
      </div>
    </div>
  )
}

export function JobPage() {
  const id = Number(useParams().id)
  const location = useLocation()
  const added = (location.state as AddedState | null)?.added
  const { data: job, isPending, isError, error, refetch } = useJob(id)

  return (
    <div className="animate-in fade-in duration-300">
      <Link
        to="/"
        className="mb-6 inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeftIcon className="size-4" />
        Bandeja
      </Link>

      {added && <AddedNotice added={added} />}

      {!Number.isInteger(id) || id < 1 ? (
        <ErrorState error={new Error('Ese identificador de oferta no es válido.')} />
      ) : isPending ? (
        <JobSkeleton />
      ) : isError ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : (
        <>
          <header className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <h1 className="text-2xl leading-tight font-semibold tracking-tight text-balance sm:text-3xl">
                {job.title}
              </h1>
              <p className="mt-2 text-muted-foreground">
                <span className="text-foreground/90">{job.company}</span>
                {job.location && <>, {job.location}</>}
              </p>
            </div>
            <div className="flex shrink-0 flex-wrap items-start gap-3">
              <StageBadge stage={job.stage} className="mt-1" />
              <Decision job={job} />
              {job.url && (
                <Button asChild variant="outline" size="sm">
                  <a href={job.url} target="_blank" rel="noopener noreferrer nofollow">
                    Ver original
                    <ArrowSquareOutIcon />
                  </a>
                </Button>
              )}
            </div>
          </header>

          <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
            <div className="space-y-6">
              {job.injection && <InjectionAlert injection={job.injection} />}
              {job.extraction ? (
                <Panel title="Extracción">
                  <ExtractionPanel extraction={job.extraction} />
                </Panel>
              ) : (
                <section className="flex items-start gap-4 rounded-xl border border-dashed p-6">
                  <HourglassMediumIcon className="mt-0.5 size-6 shrink-0 text-primary" weight="duotone" />
                  <div>
                    <h2 className="font-semibold">Aún sin extraer</h2>
                    <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                      Ejecuta el skill{' '}
                      <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em] text-foreground">
                        procesar-ofertas
                      </code>{' '}
                      en tu agente. Cuando termine, aquí verás seniority, modalidad, skills y salario.
                    </p>
                  </div>
                </section>
              )}
              <ProcessSection job={job} />
              <CvSection job={job} />
              <OriginalText text={job.raw_text} />
            </div>

            <aside className="space-y-6">
              <MatchPanel job={job} />
              <Panel title="Historial">
                <Timeline events={job.events} />
              </Panel>
              <section className="rounded-xl border bg-card p-5 sm:p-6">
                <NoteForm jobId={job.id} />
              </section>
              <p className="px-1 text-xs text-muted-foreground">
                Alta el {formatDate(job.first_seen_at)}
                {job.posted_at && <>. Publicada el {formatDate(job.posted_at)}</>}.
              </p>
            </aside>
          </div>
        </>
      )}
    </div>
  )
}
