import { Fragment, useState, type FormEvent, type ReactNode } from 'react'
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
import { Trans, useTranslation } from 'react-i18next'
import { SafeTrans } from '@/components/SafeTrans'
import type { AddJobResult, EventOut, JobView, Schemas } from '@/api/client'
import { useAddNote, useAssessThreshold, useJob, useJobEvent, useJobMatch, type UserEventBody } from '@/api/queries'
import { JobCostPanel } from '@/components/JobCostPanel'
import { ApplySection } from '@/components/ApplySection'
import { ArchivedApplication } from '@/components/ArchivedApplication'
import { CoverLetterSection } from '@/components/CoverLetterSection'
import { CompanyResearchSection } from '@/components/CompanyResearchSection'
import { CvSection } from '@/components/CvSection'
import { JobReplyNotice } from '@/components/JobReplyNotice'
import { ClosedNotice, DoubtfulNote, RepostNote } from '@/components/JobSignals'
import { DiscardDialog } from '@/components/DiscardDialog'
import { DraftsSection } from '@/components/DraftsSection'
import { MatchDetails, ScoreBadge } from '@/components/MatchDetails'
import { NetworkPanel } from '@/components/NetworkPanel'
import { PackageSection } from '@/components/PackageSection'
import { ProcessSection } from '@/components/ProcessSection'
import { ReceivedOfferSection } from '@/components/ReceivedOfferSection'
import { StatusUpdate } from '@/components/StatusUpdate'
import { StageBadge } from '@/components/StageBadge'
import { ErrorState } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import { errorMessage } from '@/lib/errors'
import { i18n, serverText } from '@/lib/i18n'
import {
  actorLabel,
  discardReasonLabel,
  EMPLOYMENT_LABEL,
  eventLabel,
  formatDate,
  formatDateTime,
  formatSalary,
  HARD_FILTER_LABEL,
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
  const { t } = useTranslation('job', { keyPrefix: 'added' })
  const [open, setOpen] = useState(true)
  if (!open) return null
  const tone = added.created && !added.duplicate_of
  const Icon = tone ? CheckCircleIcon : added.created ? CopyIcon : InfoIcon
  let text: ReactNode
  if (!added.created) text = t('exists')
  else if (added.duplicate_of)
    text = (
      <SafeTrans
        t={t}
        i18nKey="duplicate"
        values={{ id: added.duplicate_of }}
        components={{
          to: <Link to={`/jobs/${added.duplicate_of}`} className="font-medium underline underline-offset-4" />,
        }}
      />
    )
  else text = t('created')
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
        {t('close')}
      </button>
    </div>
  )
}

function InjectionAlert({ injection }: { injection: NonNullable<JobView['injection']> }) {
  const { t } = useTranslation('job', { keyPrefix: 'injection' })
  const excerpts = injection.reports.filter((r) => r.excerpt)
  return (
    <section
      aria-label={t('label')}
      className="rounded-xl border border-warning-border bg-warning p-5 text-warning-foreground"
    >
      <div className="flex items-start gap-3">
        <ShieldWarningIcon className="mt-0.5 size-6 shrink-0" weight="duotone" />
        <div className="min-w-0 flex-1 space-y-3">
          <div>
            <h2 className="font-semibold">{t('title')}</h2>
            <p className="mt-1 text-sm opacity-90">
              {t('body')}
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
                {t('detectedBy', {
                  who: report.source === 'agent' ? actorLabel('agent', report.agent_name) : t('system'),
                })}
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
  const { t } = useTranslation('job', { keyPrefix: 'extraction' })
  if (!skills.length) return <p className="text-sm text-muted-foreground">{t('noneListed')}</p>
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
  const { t } = useTranslation('job', { keyPrefix: 'extraction' })
  const data = extraction.data
  const salary = formatSalary(data.salary)
  const languages = data.languages_required
    .map((l) => (l.level ? `${l.language} ${l.level}` : l.language))
    .join(', ')
  return (
    <div className="space-y-8">
      <dl className="grid grid-cols-2 gap-x-6 gap-y-5 sm:grid-cols-3">
        <Fact label={t('seniority')}>{SENIORITY_LABEL[data.seniority]}</Fact>
        <Fact label={t('mode')}>{REMOTE_LABEL[data.remote_mode]}</Fact>
        <Fact label={t('minExperience')}>
          {data.years_experience_min != null
            ? t('years', { count: data.years_experience_min })
            : <span className="font-normal text-muted-foreground">{t('unspecified')}</span>}
        </Fact>
        <Fact label={t('contract')}>{EMPLOYMENT_LABEL[data.employment_type]}</Fact>
        <Fact label={t('salary')}>
          {salary ?? <span className="font-normal text-muted-foreground">{t('noSalary')}</span>}
        </Fact>
        <Fact label={t('languages')}>
          {languages || <span className="font-normal text-muted-foreground">{t('noLanguages')}</span>}
        </Fact>
        {data.locations.length > 0 && <Fact label={t('location')}>{data.locations.join(', ')}</Fact>}
        {data.domain && <Fact label={t('sector')}>{data.domain}</Fact>}
        {data.application_deadline && (
          <Fact label={t('deadline')}>{formatDate(data.application_deadline)}</Fact>
        )}
      </dl>

      <div className="grid gap-6 sm:grid-cols-2">
        <div className="space-y-2.5">
          <h3 className="text-sm font-semibold">{t('mustHave')}</h3>
          <SkillList skills={data.must_have_skills} strong />
        </div>
        <div className="space-y-2.5">
          <h3 className="text-sm font-semibold">{t('niceToHave')}</h3>
          <SkillList skills={data.nice_to_have_skills} />
        </div>
      </div>

      {data.responsibilities.length > 0 && (
        <div className="space-y-2.5">
          <h3 className="text-sm font-semibold">{t('responsibilities')}</h3>
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
          <h3 className="text-sm font-semibold">{t('redFlags')}</h3>
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
        {t('extractedAt', { date: formatDateTime(extraction.created_at) })}
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
  const { t } = useTranslation('job', { keyPrefix: 'original' })
  const [open, setOpen] = useState(false)
  return (
    <Collapsible open={open} onOpenChange={setOpen} className="rounded-xl border bg-card">
      <CollapsibleTrigger className="flex w-full items-center justify-between gap-4 rounded-xl p-5 text-left outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 sm:px-6">
        <span>
          <span className="block text-base font-semibold tracking-tight">{t('title')}</span>
          <span className="text-xs text-muted-foreground">
            {t('hint')}
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
  const t = i18n.getFixedT(null, 'job', 'events')
  const payload = event.payload as Record<string, unknown>
  if (event.type === 'discarded' && typeof payload.reason === 'string') {
    const note = typeof payload.note === 'string' ? `. ${payload.note}` : ''
    return `${t('reason', { reason: discardReasonLabel(payload.reason) })}${note}`
  }
  if (typeof payload.note === 'string') return payload.note
  if (event.type === 'hard_filter_failed' && Array.isArray(payload.failures))
    return (payload.failures as { filter?: string; reason?: string }[])
      .map((f) => serverText(f.filter ? HARD_FILTER_LABEL[f.filter] : null, f.reason ?? ''))
      .join('\n')
  if (event.type === 'scored' && typeof payload.score === 'number') return t('score', { score: payload.score })
  if (event.type === 'fit_assessed' && typeof payload.verdict === 'string')
    return VERDICT_LABEL[payload.verdict as keyof typeof VERDICT_LABEL] ?? payload.verdict
  if (event.type === 'duplicate_detected' && payload.duplicate_of)
    return t('duplicateOf', { id: String(payload.duplicate_of) })
  if (event.type === 'extraction_failed' && typeof payload.reason === 'string') return payload.reason
  if (event.type === 'closure_suspected' && typeof payload.detail === 'string')
    return t('closureSuspected', { detail: `${payload.detail.charAt(0).toUpperCase()}${payload.detail.slice(1)}` })
  return null
}

/** Con más eventos que esto, el historial se compacta: los últimos y el alta, el resto plegado. */
const TIMELINE_COMPACT_FROM = 7
const TIMELINE_RECENT = 4

function TimelineItem({ event, first, line }: { event: EventOut; first: boolean; line: boolean }) {
  const detail = eventDetail(event)
  const warning = event.type === 'injection_suspected'
  return (
    <li className="relative flex gap-3.5 pb-5 last:pb-0">
      {line && <span aria-hidden className="absolute top-5 bottom-0 left-[5px] w-px bg-border" />}
      <span
        aria-hidden
        className={cn(
          'relative mt-1.5 size-[11px] shrink-0 rounded-full border-2 bg-card',
          warning ? 'border-warning-border bg-warning' : first ? 'border-primary bg-primary' : 'border-input',
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
}

/**
 * Historial, lo último arriba. Si es largo, se ven las últimas interacciones y el alta; lo de en
 * medio se despliega con un botón (los avisos de posible inyección se ven siempre).
 */
function Timeline({ events }: { events: EventOut[] }) {
  const { t } = useTranslation('job', { keyPrefix: 'timeline' })
  const [expanded, setExpanded] = useState(false)
  const ordered = [...events].reverse() // lo último, arriba
  const compact = !expanded && ordered.length >= TIMELINE_COMPACT_FROM
  const last = ordered.length - 1
  const visible = compact
    ? ordered.filter((e, i) => i < TIMELINE_RECENT || i === last || e.type === 'injection_suspected')
    : ordered
  const hidden = ordered.length - visible.length
  const firstHidden = compact ? visible.findIndex((e) => ordered.indexOf(e) >= TIMELINE_RECENT) : -1
  return (
    <ol className="relative">
      {visible.map((event, i) => (
        <Fragment key={event.id}>
          {compact && i === firstHidden && hidden > 0 && (
            <li className="relative flex gap-3.5 pb-5">
              <span aria-hidden className="absolute top-0 bottom-0 left-[5px] w-px border-l border-dashed" />
              <button
                type="button"
                onClick={() => setExpanded(true)}
                className="ml-[25px] text-xs font-medium text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
              >
                {t('more', { count: hidden })}
              </button>
            </li>
          )}
          <TimelineItem event={event} first={i === 0} line={i < visible.length - 1} />
        </Fragment>
      ))}
      {expanded && ordered.length >= TIMELINE_COMPACT_FROM && (
        <li className="pt-3">
          <button
            type="button"
            onClick={() => setExpanded(false)}
            className="text-xs font-medium text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
          >
            {t('less')}
          </button>
        </li>
      )}
    </ol>
  )
}

function NoteForm({ jobId }: { jobId: number }) {
  const { t } = useTranslation('job', { keyPrefix: 'note' })
  const [note, setNote] = useState('')
  const addNote = useAddNote(jobId)
  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!note.trim()) return
    addNote.mutate(note.trim(), { onSuccess: () => setNote('') })
  }
  return (
    <form onSubmit={submit} className="space-y-2">
      <Label htmlFor="note">{t('label')}</Label>
      <Textarea
        id="note"
        value={note}
        onChange={(e) => setNote(e.target.value)}
        maxLength={2000}
        rows={3}
        placeholder={t('placeholder')}
        className="resize-y bg-background"
      />
      {addNote.isError && (
        <p role="alert" className="text-sm text-destructive">
          {errorMessage(addNote.error)}
        </p>
      )}
      <div className="flex justify-end">
        <Button type="submit" size="sm" disabled={!note.trim() || addNote.isPending} className="active:translate-y-px">
          <NotePencilIcon />
          {addNote.isPending ? t('saving') : t('save')}
        </Button>
      </div>
    </form>
  )
}

function MatchPanel({ job }: { job: JobView }) {
  const { t } = useTranslation('job', { keyPrefix: 'match' })
  const { data: match, isPending, isError, error, refetch } = useJobMatch(job.id, job.extraction !== null)
  // Fase 25.4: solo en triaje importa el umbral de «Evaluar encaje» en segundo plano.
  const assessThreshold = useAssessThreshold(job.stage === 'pending_triage')
  if (!job.extraction) return null
  return (
    <section className="rounded-xl border bg-card p-5 sm:p-6" aria-label={t('title')}>
      <div className="mb-5 flex items-start justify-between gap-4">
        <h2 className="text-base font-semibold tracking-tight">{t('title')}</h2>
        {match && <ScoreBadge score={match.score} threshold={match.triage_threshold} size="lg" />}
      </div>
      {isPending ? (
        <Skeleton className="h-40" />
      ) : isError ? (
        <ErrorState error={error} onRetry={() => refetch()} className="border-0 p-0" />
      ) : match ? (
        <MatchDetails
          match={match}
          assessMinScore={job.stage === 'pending_triage' ? assessThreshold.data?.value : undefined}
        />
      ) : (
        <p className="text-sm text-muted-foreground">
          <Trans
            t={t}
            i18nKey="noScore"
            components={{ code: <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em] text-foreground" /> }}
          />
        </p>
      )}
    </section>
  )
}

/** Aprobar o descartar (por revisar), descartar un resumen de una alerta y reabrir (si está cerrada). */
function Decision({ job }: { job: JobView }) {
  const { t } = useTranslation('job', { keyPrefix: 'decision' })
  const event = useJobEvent()
  const [discarding, setDiscarding] = useState(false)
  const send = (body: UserEventBody) =>
    event.mutate({ jobId: job.id, body }, { onSuccess: () => setDiscarding(false) })
  if (job.stage === 'closed') {
    return (
      <div className="flex flex-col items-end gap-1">
        <Button variant="outline" size="sm" onClick={() => send({ type: 'reopened' })} disabled={event.isPending}>
          <ArrowCounterClockwiseIcon />
          {t('reopen')}
        </Button>
        {event.isError && <p role="alert" className="text-xs text-destructive">{errorMessage(event.error)}</p>}
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
            {t('approve')}
          </Button>
        )}
        <Button variant="outline" size="sm" onClick={() => setDiscarding(true)} disabled={event.isPending}>
          <XIcon weight="bold" />
          {t('discard')}
        </Button>
      </div>
      {event.isError && !discarding && <p role="alert" className="text-xs text-destructive">{errorMessage(event.error)}</p>}
      <DiscardDialog
        open={discarding}
        onOpenChange={setDiscarding}
        jobTitle={`${job.title} · ${job.company}`}
        pending={event.isPending}
        error={event.isError ? errorMessage(event.error) : null}
        onConfirm={(choice) => send({ type: 'discarded', reason: choice.reason, note: choice.note })}
      />
    </div>
  )
}

/** Ya enviada: lo que importa es qué pasa ahora; lo de etapas anteriores queda plegado. */
function wasSent(job: JobView): boolean {
  if (job.stage === 'applied' || job.stage === 'in_process') return true
  return job.stage === 'closed' && job.events.some((e) => e.type === 'applied' || e.type === 'applied_manually')
}

function ExtractionBlock({ job }: { job: JobView }) {
  const { t } = useTranslation('job', { keyPrefix: 'extraction' })
  if (job.extraction) {
    return (
      <Panel title={t('title')}>
        <ExtractionPanel extraction={job.extraction} />
      </Panel>
    )
  }
  return (
    <section className="flex items-start gap-4 rounded-xl border border-dashed p-6">
      <HourglassMediumIcon className="mt-0.5 size-6 shrink-0 text-primary" weight="duotone" />
      <div>
        <h2 className="font-semibold">{t('pendingTitle')}</h2>
        <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
          <Trans
            t={t}
            i18nKey="pendingBody"
            components={{ code: <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em] text-foreground" /> }}
          />
        </p>
      </div>
    </section>
  )
}

/** Lo de antes de enviar (candidatura asistida, paquete, CV, carta y texto), plegado. Se carga al abrirlo. */
function EarlierStages({ children }: { children: ReactNode }) {
  const { t } = useTranslation('job', { keyPrefix: 'earlier' })
  const [open, setOpen] = useState(false)
  return (
    <section aria-label={t('label')} className="rounded-xl border border-dashed">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between gap-3 px-5 py-4 text-left text-sm sm:px-6"
      >
        <span>
          <span className="font-medium">{t('label')}</span>
          <span className="text-muted-foreground">{t('hint')}</span>
        </span>
        <CaretDownIcon className={cn('size-4 shrink-0 transition-transform', open && 'rotate-180')} />
      </button>
      {open && <div className="space-y-6 border-t p-4 sm:p-5">{children}</div>}
    </section>
  )
}

function JobSkeleton() {
  const { t } = useTranslation('job')
  return (
    <div aria-busy="true" aria-label={t('loading')} className="space-y-6">
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
  const { t } = useTranslation('job')
  const id = Number(useParams().id)
  const location = useLocation()
  const added = (location.state as AddedState | null)?.added
  const { data: job, isPending, isError, error, refetch } = useJob(id)
  const sent = job ? wasSent(job) : false

  return (
    <div className="animate-in fade-in duration-300">
      <Link
        to="/bandeja"
        className="mb-6 inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeftIcon className="size-4" />
        {t('back')}
      </Link>

      {added && <AddedNotice added={added} />}

      {!Number.isInteger(id) || id < 1 ? (
        <ErrorState error={new Error(t('invalidId'))} />
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
                    {t('viewOriginal')}
                    <ArrowSquareOutIcon />
                  </a>
                </Button>
              )}
            </div>
          </header>

          {sent && (
            <div className="mb-6 space-y-6">
              <JobReplyNotice jobId={job.id} />
              <StatusUpdate job={job} />
            </div>
          )}

          <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
            <div className="space-y-6">
              {job.injection && <InjectionAlert injection={job.injection} />}
              <ClosedNotice job={job} />
              <RepostNote job={job} />
              <DoubtfulNote job={job} />
              {sent ? (
                <>
                  <ProcessSection job={job} />
                  <ReceivedOfferSection job={job} />
                  <DraftsSection job={job} />
                  <CompanyResearchSection job={job} />
                  <ArchivedApplication job={job} />
                  <ExtractionBlock job={job} />
                  <EarlierStages>
                    <ApplySection job={job} />
                    <PackageSection job={job} />
                    <CvSection job={job} />
                    <CoverLetterSection job={job} />
                    <OriginalText text={job.raw_text} />
                  </EarlierStages>
                </>
              ) : (
                <>
                  <ExtractionBlock job={job} />
                  <ProcessSection job={job} />
                  <DraftsSection job={job} />
                  <CompanyResearchSection job={job} />
                  <PackageSection job={job} />
                  <ApplySection job={job} />
                  <CvSection job={job} />
                  <CoverLetterSection job={job} />
                  <OriginalText text={job.raw_text} />
                </>
              )}
            </div>

            <aside className="space-y-6">
              <MatchPanel job={job} />
              {job.stage !== 'pending_detail' && <NetworkPanel job={job} />}
              <JobCostPanel jobId={job.id} />
              <Panel title={t('timeline.title')}>
                <Timeline events={job.events} />
              </Panel>
              <section className="rounded-xl border bg-card p-5 sm:p-6">
                <NoteForm jobId={job.id} />
              </section>
              <p className="px-1 text-xs text-muted-foreground">
                {t('addedOn', { date: formatDate(job.first_seen_at) })}
                {job.posted_at && t('postedOn', { date: formatDate(job.posted_at) })}.
              </p>
            </aside>
          </div>
        </>
      )}
    </div>
  )
}
