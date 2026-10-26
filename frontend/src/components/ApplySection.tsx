import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Trans, useTranslation } from 'react-i18next'
import {
  ArrowClockwiseIcon,
  ArrowSquareOutIcon,
  BrowserIcon,
  CursorClickIcon,
  CheckCircleIcon,
  CircleNotchIcon,
  PaperPlaneTiltIcon,
  WarningIcon,
} from '@phosphor-icons/react'
import {
  fileUrls,
  type AssistedApplication,
  type AttemptView,
  type FieldReport,
  type JobView,
  type Stage,
} from '@/api/client'
import {
  useAssistedApplication,
  useFillApplicationPage,
  useFocusApplication,
  useMarkApplicationSent,
  useOpenBrowser,
  usePrepareApplication,
  useRefreshAfterApply,
  useRescanApplication,
  useSubmitApplication,
} from '@/api/queries'
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
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { errorMessage } from '@/lib/errors'
import { codeLabel, i18n, serverText } from '@/lib/i18n'
import { cn } from '@/lib/utils'

/** Etapas en las que la sección puede tener algo que enseñar. */
const APPLY_STAGES = new Set<Stage>(['approved', 'cv_ready', 'applied', 'in_process', 'closed'])
/** Intentos con pantalla de revisión. */
const REVIEW = new Set(['ready', 'needs_user', 'submit_failed', 'submit_unconfirmed', 'manual'])
/** Después de un intento así, se puede preparar otro. */
const RETRY = new Set(['failed', 'cancelled', 'needs_user', 'submit_failed', 'submit_unconfirmed', 'manual'])
/** «Marcar como enviada» tras terminar tú. */
const MANUAL = new Set(['manual', 'needs_user', 'submit_failed', 'submit_unconfirmed'])
/** Segundos en cola tras los que se sospecha que el worker no está en marcha. */
const WORKER_HINT_AFTER = 15

/** Un aviso del intento: el mensaje del servidor, con su código traducido fuera del español. */
function warningText(warning: { code: string; message: string }): string {
  return serverText(codeLabel(`apply:warnings.${warning.code}`), warning.message)
}

/** Igual que el servidor, a grandes rasgos: sin mayúsculas, acentos ni espacios de más. */
function fold(text: string): string {
  return text
    .normalize('NFKD')
    .replace(/\p{M}/gu, '')
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .trim()
}

function Notice({ tone, children }: { tone: 'amber' | 'red' | 'muted'; children: ReactNode }) {
  return (
    <p
      role={tone === 'red' ? 'alert' : 'status'}
      className={cn(
        'flex items-start gap-2 rounded-lg border px-3 py-2 text-sm',
        tone === 'amber' && 'border-amber-500/50 bg-amber-500/10 text-amber-800 dark:text-amber-300',
        tone === 'red' && 'border-destructive/40 bg-destructive/5 text-destructive',
        tone === 'muted' && 'text-muted-foreground',
      )}
    >
      {tone !== 'muted' && <WarningIcon aria-hidden className="mt-0.5 size-4 shrink-0" weight="fill" />}
      <span>{children}</span>
    </p>
  )
}

function WorkerHint({ attempt }: { attempt: AttemptView }) {
  const { t } = useTranslation('apply')
  const task = attempt.pending_task
  if (!task || task.status !== 'queued' || task.waiting_seconds < WORKER_HINT_AFTER) return null
  return (
    <Notice tone="amber">
      <InlineCode text={t('workerHint')} />
    </Notice>
  )
}

function Busy({ attempt }: { attempt: AttemptView }) {
  const { t } = useTranslation('apply', { keyPrefix: 'busy' })
  const text =
    attempt.status === 'submitting'
      ? t('submitting')
      : attempt.status === 'filling'
        ? t('filling', { domain: attempt.domain })
        : t('queued')
  return (
    <div className="space-y-3">
      <p className="flex items-center gap-2 text-sm">
        <CircleNotchIcon aria-hidden className="size-4 animate-spin text-primary" />
        {text}
      </p>
      <WorkerHint attempt={attempt} />
    </div>
  )
}

function FieldsTable({ fields }: { fields: FieldReport[] }) {
  const { t } = useTranslation('apply')
  if (fields.length === 0) return null
  return (
    <div className="overflow-x-auto rounded-lg border">
      <table className="w-full text-left text-sm">
        <caption className="sr-only">{t('fields.caption')}</caption>
        <thead className="bg-muted/50 text-xs text-muted-foreground">
          <tr>
            <th scope="col" className="px-3 py-2 font-medium">{t('fields.field')}</th>
            <th scope="col" className="px-3 py-2 font-medium">{t('fields.status')}</th>
            <th scope="col" className="px-3 py-2 font-medium">{t('fields.value')}</th>
            <th scope="col" className="px-3 py-2 font-medium">{t('fields.source')}</th>
          </tr>
        </thead>
        <tbody>
          {fields.map((field) => {
            const missing = field.required && field.status !== 'filled' && field.status !== 'consent'
            return (
              <tr
                key={field.marker}
                className={cn('border-t align-top', missing && 'bg-amber-500/10')}
                data-missing={missing || undefined}
              >
                <th scope="row" className="px-3 py-2 font-medium">
                  {field.label}
                  {field.required && (
                    <span className="ml-1 text-muted-foreground" aria-hidden title={t('fields.required')}>
                      *
                    </span>
                  )}
                  {field.required && (
                    <span className="sr-only">{t('fields.requiredSr')}</span>
                  )}
                </th>
                <td className="px-3 py-2 whitespace-nowrap">
                  {t(`fieldStatus.${field.status}`)}
                  {missing && (
                    <span className="block text-xs font-medium text-amber-700 dark:text-amber-400">
                      {t('fields.missing')}
                    </span>
                  )}
                </td>
                <td className="max-w-xs px-3 py-2 break-words">
                  {field.value ?? <span className="text-muted-foreground italic">{field.note ?? '—'}</span>}
                </td>
                <td className="px-3 py-2 text-muted-foreground">{field.source ?? '—'}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function Screenshot({ attempt, kind }: { attempt: AttemptView; kind: 'review' | 'confirmation' }) {
  const { t } = useTranslation('apply', { keyPrefix: 'screenshot' })
  const url = fileUrls.applicationScreenshot(attempt.id, kind, attempt.updated_at)
  const alt = t(kind)
  return (
    <a href={url} target="_blank" rel="noopener noreferrer" className="block w-fit">
      <img
        src={url}
        alt={alt}
        className="max-h-96 w-full max-w-xl rounded-lg border object-cover object-top"
      />
      <span className="mt-1 flex items-center gap-1 text-xs text-muted-foreground">
        <ArrowSquareOutIcon className="size-3.5" /> {t('full')}
      </span>
    </a>
  )
}

/**
 * Confirmación del envío. Se le pasa una foto del intento tomada al pulsar «Enviar»: se confirma
 * la versión que revisaste aunque llegue otra mientras el diálogo está abierto. Sin formulario, a
 * propósito: Intro en el campo no envía, solo el clic en «Enviar candidatura».
 */
function SubmitDialog({ attempt, onClose }: { attempt: AttemptView | null; onClose: () => void }) {
  return (
    <Dialog open={attempt !== null} onOpenChange={(next) => !next && onClose()}>
      {/* Radix desmonta el contenido al cerrar: cada apertura empieza con el campo vacío. */}
      <DialogContent>{attempt && <SubmitConfirm attempt={attempt} onClose={onClose} />}</DialogContent>
    </Dialog>
  )
}

function SubmitConfirm({ attempt, onClose }: { attempt: AttemptView; onClose: () => void }) {
  const { t } = useTranslation('apply', { keyPrefix: 'submit' })
  const submit = useSubmitApplication(attempt.job_id)
  const [typed, setTyped] = useState('')
  const matches = fold(typed) !== '' && fold(typed) === fold(attempt.company)
  const confirm = () => {
    if (!matches || submit.isPending) return
    submit.mutate(
      { attemptId: attempt.id, company: typed, reviewedAt: attempt.updated_at },
      { onSuccess: onClose },
    )
  }
  return (
    <div className="grid gap-5">
      <DialogHeader>
        <DialogTitle>{t('title', { company: attempt.company })}</DialogTitle>
        <DialogDescription>
          {/* El botón y el dominio vienen de la web del formulario: van como nodos, nunca interpolados. */}
          <Trans
            t={t}
            i18nKey="description"
            components={{
              button: <>{attempt.submit_button ? t('button', { label: attempt.submit_button }) : t('defaultButton')}</>,
              domain: <strong className="font-medium text-foreground">{attempt.domain}</strong>,
            }}
          />
        </DialogDescription>
      </DialogHeader>
      {attempt.consents.length > 0 && (
        <div className="space-y-1.5 text-sm">
          <p className="font-medium">{t('consents')}</p>
          <ul className="list-disc space-y-1 pl-5 text-muted-foreground">
            {attempt.consents.map((c) => (
              <li key={c.marker}>{c.label}</li>
            ))}
          </ul>
        </div>
      )}
      <div className="space-y-2">
        <Label htmlFor="apply-company">{t('typeCompany')}</Label>
        <Input
          id="apply-company"
          value={typed}
          onChange={(e) => setTyped(e.target.value)}
          placeholder={attempt.company}
          autoComplete="off"
          autoFocus
        />
      </div>
      {submit.error && (
        <p role="alert" className="text-sm text-destructive">
          {errorMessage(submit.error)}
        </p>
      )}
      <DialogFooter>
        <Button type="button" variant="ghost" onClick={onClose}>
          {t('cancel')}
        </Button>
        <Button type="button" onClick={confirm} disabled={!matches || submit.isPending}>
          <PaperPlaneTiltIcon aria-hidden />
          {t('send')}
        </Button>
      </DialogFooter>
    </div>
  )
}

/**
 * «Rellenar esta página»: cuando el portal te ha llevado al formulario de la empresa, la app rellena
 * la pestaña que tienes delante en su navegador. Nunca una página del portal ni de LinkedIn.
 */
function FillPage({ attempt }: { attempt: AttemptView }) {
  const { t } = useTranslation('apply')
  const fillPage = useFillApplicationPage(attempt.job_id)
  if (!attempt.can_fill_page) return null
  return (
    <>
      <Button
        type="button"
        size="sm"
        disabled={fillPage.isPending || attempt.pending_task != null}
        onClick={() => fillPage.mutate(attempt.id)}
      >
        <CursorClickIcon />
        {t('fillPage')}
      </Button>
      {fillPage.error && (
        <p role="alert" className="basis-full text-sm text-destructive">
          {errorMessage(fillPage.error)}
        </p>
      )}
    </>
  )
}

function ManualDone({ jobId }: { jobId: number }) {
  const { t } = useTranslation('apply')
  const done = useMarkApplicationSent(jobId)
  return (
    <>
      <Button type="button" variant="outline" size="sm" onClick={() => done.mutate()} disabled={done.isPending}>
        <CheckCircleIcon />
        {t('markSent')}
      </Button>
      {done.error && (
        <p role="alert" className="basis-full text-sm text-destructive">
          {errorMessage(done.error)}
        </p>
      )}
    </>
  )
}

function Review({ state, attempt, stage }: { state: AssistedApplication; attempt: AttemptView; stage: Stage | null }) {
  const { t } = useTranslation('apply')
  const rescan = useRescanApplication(attempt.job_id)
  const focus = useFocusApplication(attempt.job_id)
  const [confirming, setConfirming] = useState<AttemptView | null>(null)
  const working = attempt.pending_task !== null && attempt.pending_task !== undefined
  const warnings = attempt.warnings.filter((w) => w.code !== 'submit_button')
  const actionError = rescan.error ?? focus.error
  return (
    <div className="space-y-4">
      <p className="text-sm">
        <span className="font-medium">{codeLabel(`apply:attemptStatus.${attempt.status}`) ?? attempt.status}</span>
        <span className="text-muted-foreground"> · {attempt.domain}</span>
      </p>
      {attempt.error && <Notice tone={attempt.status === 'submit_failed' ? 'red' : 'amber'}>{attempt.error}</Notice>}
      {warnings.length > 0 && (
        <ul className="space-y-1.5" aria-label={t('review.warnings')}>
          {warnings.map((w, i) => (
            <li key={`${w.code}-${i}`}>
              <Notice tone={w.code === 'possible_duplicate' ? 'red' : 'amber'}>{warningText(w)}</Notice>
            </li>
          ))}
        </ul>
      )}
      {attempt.has_screenshot && <Screenshot attempt={attempt} kind="review" />}
      <FieldsTable fields={attempt.fields} />
      {attempt.status === 'ready' && attempt.missing_required > 0 && (
        <Notice tone="amber">
          {t('review.missing', { count: attempt.missing_required })}
        </Notice>
      )}
      <WorkerHint attempt={attempt} />
      <div className="flex flex-wrap items-center gap-2">
        <FillPage attempt={attempt} />
        {attempt.status === 'ready' && attempt.mode === 'fill' && (
          <Button type="button" size="sm" disabled={!attempt.can_submit || working} onClick={() => setConfirming(attempt)}>
            <PaperPlaneTiltIcon />
            {t('review.send')}
          </Button>
        )}
        {attempt.can_rescan && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={working || rescan.isPending}
            onClick={() => rescan.mutate(attempt.id)}
          >
            <ArrowClockwiseIcon />
            {t('review.rescan')}
          </Button>
        )}
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={working || focus.isPending}
          onClick={() => focus.mutate(attempt.id)}
        >
          <BrowserIcon />
          {attempt.mode === 'open' ? t('review.reopen') : t('review.finishMyself')}
        </Button>
        {MANUAL.has(attempt.status) && <ManualDone jobId={attempt.job_id} />}
        {attempt.status === 'submit_unconfirmed' && (
          <span className="basis-full text-xs text-muted-foreground">
            {t('review.checkFirst')}
          </span>
        )}
        {working && (
          <span className="flex items-center gap-1.5 text-sm text-muted-foreground">
            <CircleNotchIcon aria-hidden className="size-4 animate-spin" /> {t('review.working')}
          </span>
        )}
      </div>
      {actionError && (
        <p role="alert" className="text-sm text-destructive">
          {errorMessage(actionError)}
        </p>
      )}
      {RETRY.has(attempt.status) && <Prepare state={state} stage={stage} again />}
      <SubmitDialog attempt={confirming} onClose={() => setConfirming(null)} />
    </div>
  )
}

function prepareText(state: AssistedApplication): string {
  if (state.mode === 'open') return i18n.t('apply:prepare.linkedin')
  return i18n.t('apply:prepare.fill', { domain: state.domain })
}

/**
 * Si ya tienes el enlace al formulario de la empresa (el que abre «Solicitar» en el portal), se
 * rellena directamente. Solo cuando la oferta está en «CV listo».
 */
function FormUrl({ state }: { state: AssistedApplication }) {
  const { t } = useTranslation('apply', { keyPrefix: 'formUrl' })
  const prepare = usePrepareApplication(state.job_id)
  const [url, setUrl] = useState('')
  const valid = /^https?:\/\/\S+$/.test(url.trim())
  return (
    <div className="text-sm">
      <form
        className="flex flex-wrap items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          if (valid) prepare.mutate(url.trim())
        }}
      >
        <div className="grid min-w-64 flex-1 gap-1.5">
          <Label htmlFor={`form-url-${state.job_id}`}>{t('label')}</Label>
          <Input
            id={`form-url-${state.job_id}`}
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder={t('placeholder')}
            autoComplete="off"
          />
        </div>
        <Button type="submit" size="sm" variant="outline" disabled={!valid || prepare.isPending}>
          {t('fill')}
        </Button>
      </form>
      {prepare.error && (
        <p role="alert" className="mt-1 text-sm text-destructive">
          {errorMessage(prepare.error)}
        </p>
      )}
    </div>
  )
}

/**
 * Oferta de un portal de empleo. Los portales bloquean los navegadores automatizados
 * (Cloudflare…) y eso no se esquiva: la oferta se abre en tu navegador, con tu sesión. Desde ahí
 * pegas el enlace al formulario de la empresa y CandidatAI lo rellena en el suyo.
 */
function PortalApply({ state, stage, again }: { state: AssistedApplication; stage: Stage | null; again: boolean }) {
  const { t } = useTranslation('apply', { keyPrefix: 'portal' })
  const portal = state.portal ?? state.domain
  const canFill = stage === 'cv_ready'
  return (
    <div className="space-y-4">
      {!again && (
        <>
          <p className="text-sm text-muted-foreground">
            {t('intro', { portal })}
          </p>
          <ol className="list-decimal space-y-1 pl-5 text-sm text-muted-foreground">
            <li>{t('step1')}</li>
            <li>{t('step2')}</li>
            <li>{t('step3', { portal })}</li>
          </ol>
        </>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <Button asChild size="sm" variant={again ? 'outline' : 'default'}>
          <a href={state.url} target="_blank" rel="noopener noreferrer">
            <ArrowSquareOutIcon />
            {t('open', { portal })}
          </a>
        </Button>
        {!again && (stage === 'cv_ready' || stage === 'approved') && <ManualDone jobId={state.job_id} />}
      </div>
      {canFill && <FormUrl state={state} />}
    </div>
  )
}

/**
 * En Docker (fase 26.3) no hay navegador visible: la oferta se abre en el tuyo, la envías tú y la
 * marcas. Nada se envía sin ti, tampoco aquí.
 */
function DockerApply({ state, stage }: { state: AssistedApplication; stage: Stage | null }) {
  const { t } = useTranslation('apply', { keyPrefix: 'docker' })
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">{t('intro')}</p>
      <p className="text-sm text-muted-foreground">{t('step')}</p>
      <div className="flex flex-wrap items-center gap-2">
        <Button asChild size="sm">
          <a href={state.url} target="_blank" rel="noopener noreferrer">
            <ArrowSquareOutIcon />
            {t('open')}
          </a>
        </Button>
        {(stage === 'cv_ready' || stage === 'approved') && <ManualDone jobId={state.job_id} />}
      </div>
    </div>
  )
}

function Prepare({
  state,
  stage,
  again = false,
}: {
  state: AssistedApplication
  stage: Stage | null
  again?: boolean
}) {
  const { t } = useTranslation('apply', { keyPrefix: 'prepare' })
  const prepare = usePrepareApplication(state.job_id)
  if (!state.can_prepare) {
    return again ? null : <Notice tone="muted">{state.reason}</Notice>
  }
  if (state.portal) return <PortalApply state={state} stage={stage} again={again} />
  const open = state.mode === 'open'
  const label = open ? t('openAndPrepare') : again ? t('again') : t('prepare')
  return (
    <div className="space-y-3">
      {!again && <p className="text-sm text-muted-foreground">{prepareText(state)}</p>}
      <Button
        type="button"
        size="sm"
        variant={again ? 'ghost' : 'default'}
        disabled={prepare.isPending}
        onClick={() => prepare.mutate(undefined)}
      >
        {label}
      </Button>
      {prepare.error && (
        <p role="alert" className="text-sm text-destructive">
          {errorMessage(prepare.error)}
        </p>
      )}
    </div>
  )
}

function Done({ attempt, stage }: { attempt: AttemptView; stage: Stage | null }) {
  const { t } = useTranslation('apply', { keyPrefix: 'done' })
  if (attempt.status === 'manual_done') {
    return <Notice tone="muted">{t('manual')}</Notice>
  }
  const noEvidence = attempt.warnings.find((w) => w.code === 'no_evidence')
  return (
    <div className="space-y-3">
      <p className="flex items-center gap-2 text-sm font-medium">
        <CheckCircleIcon aria-hidden className="size-5 text-primary" weight="fill" />
        {t('sent', { domain: attempt.domain })}
      </p>
      {attempt.error && <Notice tone="amber">{attempt.error}</Notice>}
      {noEvidence && <Notice tone="amber">{warningText(noEvidence)}</Notice>}
      {attempt.has_confirmation && <Screenshot attempt={attempt} kind="confirmation" />}
      {/* Si no se pudo registrar el envío, la oferta sigue en «CV listo»: lo registras tú. */}
      {stage === 'cv_ready' && (
        <div className="flex flex-wrap gap-2">
          <ManualDone jobId={attempt.job_id} />
        </div>
      )}
    </div>
  )
}

function Body({ state, stage }: { state: AssistedApplication; stage: Stage | null }) {
  const { t } = useTranslation('apply')
  const attempt = state.attempt
  if (attempt?.status === 'submitted' || attempt?.status === 'manual_done') {
    return <Done attempt={attempt} stage={stage} />
  }
  // Un intento de antes de pasar a Docker no se puede seguir: aquí no está su navegador.
  if (state.in_docker) return <DockerApply state={state} stage={stage} />
  if (!attempt || attempt.status === 'cancelled') return <Prepare state={state} stage={stage} />
  if (attempt.status === 'queued' || attempt.status === 'filling' || attempt.status === 'submitting') {
    return <Busy attempt={attempt} />
  }
  if (attempt.status === 'failed') {
    return (
      <div className="space-y-3">
        <Notice tone="red">{attempt.error ?? t('fillFailed')}</Notice>
        <Prepare state={state} stage={stage} again />
      </div>
    )
  }
  if (REVIEW.has(attempt.status)) return <Review state={state} attempt={attempt} stage={stage} />
  return null
}

/** Abre el navegador de CandidatAI con su página de inicio, para iniciar sesión en los portales. */
function OpenBrowser() {
  const { t } = useTranslation('apply', { keyPrefix: 'openBrowser' })
  const open = useOpenBrowser()
  return (
    <div className="flex flex-col items-end gap-1">
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={() => open.mutate()}
        disabled={open.isPending}
        title={t('title')}
      >
        <BrowserIcon />
        {t('label')}
      </Button>
      {open.isSuccess && <span className="text-xs text-muted-foreground">{open.data.message}</span>}
      {open.error && (
        <span role="alert" className="text-xs text-destructive">
          {errorMessage(open.error)}
        </span>
      )}
    </div>
  )
}

/** Cuando el worker termina el envío (o lo marcas tú), cambia la etapa: se refresca la ficha. */
function useRefreshWhenSent(jobId: number, status: string | undefined) {
  const refresh = useRefreshAfterApply(jobId)
  const previous = useRef(status)
  useEffect(() => {
    const before = previous.current
    previous.current = status
    if (before !== undefined && before !== status && (status === 'submitted' || status === 'manual_done')) {
      void refresh()
    }
  }, [status, refresh])
}

export function ApplySection({ job }: { job: JobView }) {
  const { t } = useTranslation('apply')
  const relevant = job.stage !== null && APPLY_STAGES.has(job.stage)
  const { data, isPending, isError, error, refetch } = useAssistedApplication(job.id, relevant)
  useRefreshWhenSent(job.id, data?.attempt?.status)
  if (!relevant) return null
  const startable = job.stage === 'cv_ready' || (job.stage === 'approved' && data?.mode === 'open')
  if (!isPending && !isError && !data.attempt && !startable) return null
  if (isPending && job.stage !== 'cv_ready') return null
  return (
    <section
      id="candidatura"
      aria-label={t('title')}
      className="scroll-mt-6 rounded-xl border bg-card p-5 sm:p-6"
    >
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold tracking-tight">{t('title')}</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {data?.in_docker ? t('docker.sectionIntro') : t('intro')}
          </p>
        </div>
        {!data?.in_docker && <OpenBrowser />}
      </div>
      {isPending ? (
        <Skeleton className="h-16" />
      ) : isError ? (
        <ErrorState error={error} onRetry={() => refetch()} className="border-0 p-0" />
      ) : (
        <Body state={data} stage={job.stage} />
      )}
    </section>
  )
}
