import { useEffect, useRef, useState, type ReactNode } from 'react'
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

const FIELD_STATUS: Record<FieldReport['status'], string> = {
  filled: 'Rellenado',
  empty: 'Vacío',
  needs_user_input: 'Falta un dato tuyo',
  sensitive: 'Dato sensible: decides tú',
  consent: 'Se acepta al enviar',
  skipped: 'Sin marcar',
  error: 'Error',
}

const ATTEMPT_STATUS: Record<string, string> = {
  ready: 'Listo para revisar',
  needs_user: 'Necesita tu intervención',
  submit_failed: 'No se pudo enviar',
  submit_unconfirmed: 'Envío sin confirmar',
  manual: 'Abierta en el navegador de CandidatAI',
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
  const task = attempt.pending_task
  if (!task || task.status !== 'queued' || task.waiting_seconds < WORKER_HINT_AFTER) return null
  return (
    <Notice tone="amber">
      <InlineCode text="El worker aún no lo ha recogido. ¿Está en marcha? Arráncalo con `uv run cai worker` en backend/." />
    </Notice>
  )
}

function Busy({ attempt }: { attempt: AttemptView }) {
  const text =
    attempt.status === 'submitting'
      ? 'Enviando… No cierres el navegador de CandidatAI.'
      : attempt.status === 'filling'
        ? `Rellenando el formulario de ${attempt.domain} en el navegador…`
        : 'En cola para el worker…'
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
  if (fields.length === 0) return null
  return (
    <div className="overflow-x-auto rounded-lg border">
      <table className="w-full text-left text-sm">
        <caption className="sr-only">Campos del formulario</caption>
        <thead className="bg-muted/50 text-xs text-muted-foreground">
          <tr>
            <th scope="col" className="px-3 py-2 font-medium">Campo</th>
            <th scope="col" className="px-3 py-2 font-medium">Estado</th>
            <th scope="col" className="px-3 py-2 font-medium">Valor</th>
            <th scope="col" className="px-3 py-2 font-medium">De dónde sale</th>
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
                    <span className="ml-1 text-muted-foreground" aria-hidden title="Obligatorio">
                      *
                    </span>
                  )}
                  {field.required && (
                    <span className="sr-only"> (obligatorio)</span>
                  )}
                </th>
                <td className="px-3 py-2 whitespace-nowrap">
                  {FIELD_STATUS[field.status]}
                  {missing && (
                    <span className="block text-xs font-medium text-amber-700 dark:text-amber-400">
                      Obligatorio sin respuesta
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
  const url = fileUrls.applicationScreenshot(attempt.id, kind, attempt.updated_at)
  const alt = kind === 'review' ? 'Captura del formulario rellenado' : 'Captura después de enviar'
  return (
    <a href={url} target="_blank" rel="noopener noreferrer" className="block w-fit">
      <img
        src={url}
        alt={alt}
        className="max-h-96 w-full max-w-xl rounded-lg border object-cover object-top"
      />
      <span className="mt-1 flex items-center gap-1 text-xs text-muted-foreground">
        <ArrowSquareOutIcon className="size-3.5" /> Ver la captura completa
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
        <DialogTitle>Enviar la candidatura a {attempt.company}</DialogTitle>
        <DialogDescription>
          Se pulsará {attempt.submit_button ? `«${attempt.submit_button}»` : 'el botón de envío'} en{' '}
          <strong className="font-medium text-foreground">{attempt.domain}</strong>. Esta confirmación vale
          solo para este envío.
        </DialogDescription>
      </DialogHeader>
      {attempt.consents.length > 0 && (
        <div className="space-y-1.5 text-sm">
          <p className="font-medium">Al enviar aceptas:</p>
          <ul className="list-disc space-y-1 pl-5 text-muted-foreground">
            {attempt.consents.map((c) => (
              <li key={c.marker}>{c.label}</li>
            ))}
          </ul>
        </div>
      )}
      <div className="space-y-2">
        <Label htmlFor="apply-company">Escribe el nombre de la empresa para confirmar</Label>
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
          {submit.error.message}
        </p>
      )}
      <DialogFooter>
        <Button type="button" variant="ghost" onClick={onClose}>
          Cancelar
        </Button>
        <Button type="button" onClick={confirm} disabled={!matches || submit.isPending}>
          <PaperPlaneTiltIcon aria-hidden />
          Enviar candidatura
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
        Rellenar esta página
      </Button>
      {fillPage.error && (
        <p role="alert" className="basis-full text-sm text-destructive">
          {fillPage.error.message}
        </p>
      )}
    </>
  )
}

function ManualDone({ jobId }: { jobId: number }) {
  const done = useMarkApplicationSent(jobId)
  return (
    <>
      <Button type="button" variant="outline" size="sm" onClick={() => done.mutate()} disabled={done.isPending}>
        <CheckCircleIcon />
        Marcar como enviada
      </Button>
      {done.error && (
        <p role="alert" className="basis-full text-sm text-destructive">
          {done.error.message}
        </p>
      )}
    </>
  )
}

function Review({ state, attempt, stage }: { state: AssistedApplication; attempt: AttemptView; stage: Stage | null }) {
  const rescan = useRescanApplication(attempt.job_id)
  const focus = useFocusApplication(attempt.job_id)
  const [confirming, setConfirming] = useState<AttemptView | null>(null)
  const working = attempt.pending_task !== null && attempt.pending_task !== undefined
  const warnings = attempt.warnings.filter((w) => w.code !== 'submit_button')
  const actionError = rescan.error ?? focus.error
  return (
    <div className="space-y-4">
      <p className="text-sm">
        <span className="font-medium">{ATTEMPT_STATUS[attempt.status] ?? attempt.status}</span>
        <span className="text-muted-foreground"> · {attempt.domain}</span>
      </p>
      {attempt.error && <Notice tone={attempt.status === 'submit_failed' ? 'red' : 'amber'}>{attempt.error}</Notice>}
      {warnings.length > 0 && (
        <ul className="space-y-1.5" aria-label="Avisos">
          {warnings.map((w, i) => (
            <li key={`${w.code}-${i}`}>
              <Notice tone={w.code === 'possible_duplicate' ? 'red' : 'amber'}>{w.message}</Notice>
            </li>
          ))}
        </ul>
      )}
      {attempt.has_screenshot && <Screenshot attempt={attempt} kind="review" />}
      <FieldsTable fields={attempt.fields} />
      {attempt.status === 'ready' && attempt.missing_required > 0 && (
        <Notice tone="amber">
          {attempt.missing_required === 1
            ? 'Falta 1 campo obligatorio: complétalo en el navegador y pulsa «Volver a revisar», o termina tú.'
            : `Faltan ${attempt.missing_required} campos obligatorios: complétalos en el navegador y pulsa «Volver a revisar», o termina tú.`}
        </Notice>
      )}
      <WorkerHint attempt={attempt} />
      <div className="flex flex-wrap items-center gap-2">
        <FillPage attempt={attempt} />
        {attempt.status === 'ready' && attempt.mode === 'fill' && (
          <Button type="button" size="sm" disabled={!attempt.can_submit || working} onClick={() => setConfirming(attempt)}>
            <PaperPlaneTiltIcon />
            Enviar
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
            Volver a revisar
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
          {attempt.mode === 'open' ? 'Volver a abrir la oferta' : 'Lo termino yo'}
        </Button>
        {MANUAL.has(attempt.status) && <ManualDone jobId={attempt.job_id} />}
        {attempt.status === 'submit_unconfirmed' && (
          <span className="basis-full text-xs text-muted-foreground">
            Antes de marcarla como enviada, comprueba en la web o en tu correo que llegó.
          </span>
        )}
        {working && (
          <span className="flex items-center gap-1.5 text-sm text-muted-foreground">
            <CircleNotchIcon aria-hidden className="size-4 animate-spin" /> Trabajando en el navegador…
          </span>
        )}
      </div>
      {actionError && (
        <p role="alert" className="text-sm text-destructive">
          {actionError.message}
        </p>
      )}
      {RETRY.has(attempt.status) && <Prepare state={state} stage={stage} again />}
      <SubmitDialog attempt={confirming} onClose={() => setConfirming(null)} />
    </div>
  )
}

function prepareText(state: AssistedApplication): string {
  if (state.mode === 'open') {
    return 'LinkedIn no se automatiza: se abrirá la oferta en el navegador de CandidatAI y copias el paquete desde arriba.'
  }
  return `Se abrirá ${state.domain} en el navegador de CandidatAI y se rellenará el formulario. No se envía nada hasta que lo confirmes.`
}

/**
 * Si ya tienes el enlace al formulario de la empresa (el que abre «Solicitar» en el portal), se
 * rellena directamente. Solo cuando la oferta está en «CV listo».
 */
function FormUrl({ state }: { state: AssistedApplication }) {
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
          <Label htmlFor={`form-url-${state.job_id}`}>URL del formulario</Label>
          <Input
            id={`form-url-${state.job_id}`}
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://empresa.com/empleo/…"
            autoComplete="off"
          />
        </div>
        <Button type="submit" size="sm" variant="outline" disabled={!valid || prepare.isPending}>
          Rellenar ese formulario
        </Button>
      </form>
      {prepare.error && (
        <p role="alert" className="mt-1 text-sm text-destructive">
          {prepare.error.message}
        </p>
      )}
    </div>
  )
}

/**
 * Oferta de un portal de empleo (ADR-021). Los portales bloquean los navegadores automatizados
 * (Cloudflare…) y eso no se esquiva: la oferta se abre en tu navegador, con tu sesión. Desde ahí
 * pegas el enlace al formulario de la empresa y CandidatAI lo rellena en el suyo.
 */
function PortalApply({ state, stage, again }: { state: AssistedApplication; stage: Stage | null; again: boolean }) {
  const portal = state.portal ?? state.domain
  const canFill = stage === 'cv_ready'
  return (
    <div className="space-y-4">
      {!again && (
        <>
          <p className="text-sm text-muted-foreground">
            {portal} es un portal de empleo y bloquea los navegadores automatizados, así que la oferta se abre en tu
            navegador, con tu sesión.
          </p>
          <ol className="list-decimal space-y-1 pl-5 text-sm text-muted-foreground">
            <li>Abre la oferta y pulsa «Solicitar» o «Inscribirme».</li>
            <li>
              Si te lleva al formulario de la empresa, copia la dirección de esa página y pégala abajo: CandidatAI lo
              rellena en su navegador y se para antes de enviar.
            </li>
            <li>
              Si la candidatura se completa dentro de {portal}, termínala allí (el CV está en «Paquete de
              candidatura») y pulsa «Marcar como enviada».
            </li>
          </ol>
        </>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <Button asChild size="sm" variant={again ? 'outline' : 'default'}>
          <a href={state.url} target="_blank" rel="noopener noreferrer">
            <ArrowSquareOutIcon />
            Abrir la oferta en {portal}
          </a>
        </Button>
        {!again && (stage === 'cv_ready' || stage === 'approved') && <ManualDone jobId={state.job_id} />}
      </div>
      {canFill && <FormUrl state={state} />}
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
  const prepare = usePrepareApplication(state.job_id)
  if (!state.can_prepare) {
    return again ? null : <Notice tone="muted">{state.reason}</Notice>
  }
  if (state.portal) return <PortalApply state={state} stage={stage} again={again} />
  const open = state.mode === 'open'
  const label = open ? 'Abrir y preparar' : again ? 'Preparar de nuevo' : 'Preparar candidatura'
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
          {prepare.error.message}
        </p>
      )}
    </div>
  )
}

function Done({ attempt, stage }: { attempt: AttemptView; stage: Stage | null }) {
  if (attempt.status === 'manual_done') {
    return <Notice tone="muted">Marcada como enviada por ti.</Notice>
  }
  const noEvidence = attempt.warnings.find((w) => w.code === 'no_evidence')
  return (
    <div className="space-y-3">
      <p className="flex items-center gap-2 text-sm font-medium">
        <CheckCircleIcon aria-hidden className="size-5 text-primary" weight="fill" />
        Enviada a {attempt.domain}: la web confirmó el envío.
      </p>
      {attempt.error && <Notice tone="amber">{attempt.error}</Notice>}
      {noEvidence && <Notice tone="amber">{noEvidence.message}</Notice>}
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
  const attempt = state.attempt
  if (!attempt || attempt.status === 'cancelled') return <Prepare state={state} stage={stage} />
  if (attempt.status === 'queued' || attempt.status === 'filling' || attempt.status === 'submitting') {
    return <Busy attempt={attempt} />
  }
  if (attempt.status === 'submitted' || attempt.status === 'manual_done') {
    return <Done attempt={attempt} stage={stage} />
  }
  if (attempt.status === 'failed') {
    return (
      <div className="space-y-3">
        <Notice tone="red">{attempt.error ?? 'No se pudo rellenar el formulario.'}</Notice>
        <Prepare state={state} stage={stage} again />
      </div>
    )
  }
  if (REVIEW.has(attempt.status)) return <Review state={state} attempt={attempt} stage={stage} />
  return null
}

/** Abre el navegador de CandidatAI con su página de inicio, para iniciar sesión en los portales. */
function OpenBrowser() {
  const open = useOpenBrowser()
  return (
    <div className="flex flex-col items-end gap-1">
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={() => open.mutate()}
        disabled={open.isPending}
        title="Abre el navegador de CandidatAI para iniciar sesión en tus portales. Tiene su propio perfil, separado de tu Chrome."
      >
        <BrowserIcon />
        Abrir navegador
      </Button>
      {open.isSuccess && <span className="text-xs text-muted-foreground">{open.data.message}</span>}
      {open.error && (
        <span role="alert" className="text-xs text-destructive">
          {open.error.message}
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
      aria-label="Candidatura asistida"
      className="scroll-mt-6 rounded-xl border bg-card p-5 sm:p-6"
    >
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold tracking-tight">Candidatura asistida</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            CandidatAI abre la oferta en su propio navegador, rellena el formulario de candidatura y se para antes
            de enviar. Nada se envía sin tu confirmación. Inicia sesión en tus portales con «Abrir navegador».
          </p>
        </div>
        <OpenBrowser />
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
