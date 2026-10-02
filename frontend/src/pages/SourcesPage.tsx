import { useState, type FormEvent, type ReactNode } from 'react'
import { Link } from 'react-router'
import {
  BuildingsIcon,
  CheckCircleIcon,
  ClockIcon,
  MinusCircleIcon,
  PauseIcon,
  PlayIcon,
  WarningCircleIcon,
} from '@phosphor-icons/react'
import {
  ApiError,
  type ConnectorKind,
  type SourceInput,
  type SourceRunResult,
  type SourceTestResult,
  type SourceView,
} from '@/api/client'
import {
  useAddSource,
  usePreviewSource,
  useRunSource,
  useSetSourceActive,
  useSources,
} from '@/api/queries'
import { EmptyState, ErrorState, InlineCode } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

const KINDS: { value: ConnectorKind; label: string; hint: string }[] = [
  { value: 'greenhouse', label: 'Greenhouse', hint: 'boards.greenhouse.io/<slug>' },
  { value: 'lever', label: 'Lever', hint: 'jobs.lever.co/<slug>' },
  { value: 'ashby', label: 'Ashby', hint: 'jobs.ashbyhq.com/<slug>' },
  { value: 'infojobs', label: 'InfoJobs (búsqueda)', hint: 'Necesita claves en .env' },
  { value: 'adzuna', label: 'Adzuna (búsqueda)', hint: 'Necesita claves en .env' },
]
const ATS: ConnectorKind[] = ['greenhouse', 'lever', 'ashby']
const CONNECTOR_KINDS = new Set<string>(KINDS.map((k) => k.value))

function fieldErrors(error: unknown): Record<string, string> {
  if (!(error instanceof ApiError)) return {}
  return Object.fromEntries(error.details.map((d) => [d.field || 'form', d.reason]))
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Algo ha fallado.'
}

function formatWhen(iso: string): string {
  return new Date(iso).toLocaleString('es-ES', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

// --- Resultado de una prueba o de una ejecución ---------------------------------------------------

function Notice({ tone, children }: { tone: 'ok' | 'warn' | 'error'; children: ReactNode }) {
  const Icon = tone === 'ok' ? CheckCircleIcon : WarningCircleIcon
  return (
    <div
      role={tone === 'error' ? 'alert' : 'status'}
      className={cn(
        'flex items-start gap-2.5 rounded-lg border px-3.5 py-3 text-sm',
        tone === 'ok' && 'border-primary/25 bg-primary/5',
        tone === 'warn' && 'border-amber-500/30 bg-amber-500/5',
        tone === 'error' && 'border-destructive/30 bg-destructive/5',
      )}
    >
      <Icon
        weight="fill"
        className={cn(
          'mt-0.5 size-4 shrink-0',
          tone === 'ok' && 'text-primary',
          tone === 'warn' && 'text-amber-600 dark:text-amber-400',
          tone === 'error' && 'text-destructive',
        )}
      />
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  )
}

function Issues({ issues }: { issues: SourceTestResult['errors'] }) {
  if (issues.length === 0) return null
  return (
    <ul className="mt-1.5 space-y-0.5 text-xs text-muted-foreground">
      {issues.slice(0, 5).map((issue, i) => (
        <li key={i}>
          <InlineCode text={issue.message} />
        </li>
      ))}
      {issues.length > 5 && <li>… y {issues.length - 5} más.</li>}
    </ul>
  )
}

function PreviewResult({ result }: { result: SourceTestResult }) {
  const [showAll, setShowAll] = useState(false)
  const failed = result.found === 0 && result.errors.length > 0
  const jobs = showAll ? result.jobs : result.jobs.filter((j) => j.passed)
  return (
    <div className="grid gap-3">
      <Notice tone={failed ? 'error' : result.after_filters ? 'ok' : 'warn'}>
        <p className="font-medium">
          <InlineCode text={result.message} />
        </p>
        {!failed && <Issues issues={result.errors} />}
      </Notice>
      {result.jobs.length > 0 && (
        <div className="rounded-lg border">
          <ul className="max-h-72 divide-y overflow-y-auto text-sm">
            {jobs.map((job) => (
              <li key={job.external_id} className="flex items-start gap-2.5 px-3.5 py-2.5">
                {job.passed ? (
                  <CheckCircleIcon className="mt-0.5 size-4 shrink-0 text-primary" weight="fill" aria-label="Pasa" />
                ) : (
                  <MinusCircleIcon className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-label="Filtrada" />
                )}
                <div className="min-w-0 flex-1">
                  <a
                    href={job.url}
                    target="_blank"
                    rel="noreferrer noopener"
                    className={cn('font-medium hover:underline', !job.passed && 'text-muted-foreground')}
                  >
                    {job.title}
                  </a>
                  <p className="text-xs text-muted-foreground">
                    {[job.location, job.reason].filter(Boolean).join(' · ')}
                  </p>
                </div>
              </li>
            ))}
            {jobs.length === 0 && (
              <li className="px-3.5 py-2.5 text-muted-foreground">Ninguna pasa el filtro previo.</li>
            )}
          </ul>
          {result.found > result.after_filters && (
            <button
              type="button"
              onClick={() => setShowAll((v) => !v)}
              className="w-full border-t px-3.5 py-2 text-left text-xs font-medium text-primary hover:bg-muted/50"
            >
              {showAll ? 'Ver solo las que pasan' : `Ver también las ${result.found - result.after_filters} filtradas`}
            </button>
          )}
        </div>
      )}
    </div>
  )
}

function RunResult({ result }: { result: SourceRunResult }) {
  const tone = result.skipped || (result.errors.length > 0 && result.found === 0) ? 'error' : 'ok'
  return (
    <Notice tone={tone}>
      <p>
        <InlineCode text={result.message} />
      </p>
      {result.job_ids.length > 0 && (
        <p className="mt-1 text-xs text-muted-foreground">
          Quedan en «Por extraer»: ejecuta <InlineCode text="`procesar-ofertas`" /> en tu agente.{' '}
          <Link to="/?stage=pending_extraction" className="font-medium text-primary hover:underline">
            Verlas
          </Link>
        </p>
      )}
      {result.found > 0 && <Issues issues={result.errors} />}
    </Notice>
  )
}

// --- Formulario de alta --------------------------------------------------------------------------

function Field({ id, label, error, hint, children }: { id: string; label: string; error?: string; hint?: ReactNode; children: ReactNode }) {
  return (
    <div className="grid content-start gap-2">
      <Label htmlFor={id}>{label}</Label>
      {children}
      {error ? (
        <p className="text-sm text-destructive">{error}</p>
      ) : (
        hint && <p className="text-xs text-muted-foreground">{hint}</p>
      )}
    </div>
  )
}

const EMPTY = { kind: 'greenhouse' as ConnectorKind, name: '', slug: '', region: 'global' as 'global' | 'eu', query: '', where: '', province: '' }

function AddSourceForm() {
  const [form, setForm] = useState(EMPTY)
  const preview = usePreviewSource()
  const add = useAddSource()
  const isAts = ATS.includes(form.kind)
  const kind = KINDS.find((k) => k.value === form.kind)!
  const errors = { ...fieldErrors(preview.error), ...fieldErrors(add.error) }
  const set = (key: keyof typeof EMPTY) => (e: { target: { value: string } }) => {
    setForm((prev) => ({ ...prev, [key]: e.target.value }))
    preview.reset()
  }
  const ready = form.name.trim() && (isAts ? form.slug.trim() : form.query.trim())

  const body = (): SourceInput => ({
    kind: form.kind,
    name: form.name.trim(),
    slug: isAts ? form.slug.trim() : null,
    region: form.kind === 'lever' ? form.region : 'global',
    query: isAts ? null : form.query.trim(),
    where: form.kind === 'adzuna' ? form.where.trim() || null : null,
    province: form.kind === 'infojobs' ? form.province.trim() || null : null,
    country: 'es',
    title_keywords: [],
  })

  const test = () => {
    add.reset()
    preview.mutate(body())
  }
  const save = (e: FormEvent) => {
    e.preventDefault()
    add.mutate(body(), {
      onSuccess: () => {
        setForm(EMPTY)
        preview.reset()
      },
    })
  }
  const formError = [preview.error, add.error].find(
    (error) => error && !(error instanceof ApiError && error.details.length > 0),
  )

  return (
    <form onSubmit={save} className="grid gap-5" noValidate aria-label="Añadir fuente">
      <div className="grid gap-5 sm:grid-cols-2">
        <Field id="source-kind" label="Origen">
          <Select
            value={form.kind}
            onValueChange={(value) => {
              setForm((prev) => ({ ...prev, kind: value as ConnectorKind }))
              preview.reset()
            }}
          >
            <SelectTrigger id="source-kind" className="h-10 w-full bg-background">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {KINDS.map((k) => (
                <SelectItem key={k.value} value={k.value}>
                  {k.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
        <Field id="source-name" label={isAts ? 'Empresa' : 'Nombre de la búsqueda'} error={errors.name}>
          <Input id="source-name" value={form.name} onChange={set('name')} className="h-10 bg-background" />
        </Field>
        {isAts ? (
          <>
            <Field id="source-slug" label="Slug del tablero" error={errors.slug ?? errors.form} hint={<>Lo que va en la URL: <span className="font-mono">{kind.hint}</span></>}>
              <Input id="source-slug" value={form.slug} onChange={set('slug')} spellCheck={false} className="h-10 bg-background font-mono" />
            </Field>
            {form.kind === 'lever' && (
              <Field id="source-region" label="Región de Lever">
                <Select value={form.region} onValueChange={(value) => setForm((prev) => ({ ...prev, region: value as 'global' | 'eu' }))}>
                  <SelectTrigger id="source-region" className="h-10 w-full bg-background">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="global">Global (jobs.lever.co)</SelectItem>
                    <SelectItem value="eu">Europa (jobs.eu.lever.co)</SelectItem>
                  </SelectContent>
                </Select>
              </Field>
            )}
          </>
        ) : (
          <>
            <Field id="source-query" label="Palabras de búsqueda" error={errors.query ?? errors.form} hint={kind.hint}>
              <Input id="source-query" value={form.query} onChange={set('query')} className="h-10 bg-background" />
            </Field>
            {form.kind === 'adzuna' ? (
              <Field id="source-where" label="Ubicación (opcional)">
                <Input id="source-where" value={form.where} onChange={set('where')} className="h-10 bg-background" />
              </Field>
            ) : (
              <Field id="source-province" label="Provincia (opcional)" hint="Como la usa InfoJobs, p. ej. a-coruna">
                <Input id="source-province" value={form.province} onChange={set('province')} className="h-10 bg-background" />
              </Field>
            )}
          </>
        )}
      </div>

      {preview.data && <PreviewResult result={preview.data} />}
      {formError && (
        <Notice tone="error">
          <InlineCode text={errorMessage(formError)} />
        </Notice>
      )}
      {add.isSuccess && (
        <Notice tone="ok">
          «{add.data.name}» añadida. Entrará en la ingesta diaria; también puedes ejecutarla ahora.
        </Notice>
      )}

      <div className="flex flex-wrap justify-end gap-2">
        <Button type="button" variant="outline" disabled={!ready || preview.isPending} onClick={test} className="h-10">
          {preview.isPending ? 'Probando…' : 'Probar'}
        </Button>
        <Button type="submit" disabled={!ready || add.isPending} className="h-10 px-5 active:translate-y-px">
          {add.isPending ? 'Guardando…' : 'Añadir'}
        </Button>
      </div>
    </form>
  )
}

// --- Lista de fuentes ----------------------------------------------------------------------------

function SourceRow({ source }: { source: SourceView }) {
  const preview = usePreviewSource()
  const run = useRunSource()
  const toggle = useSetSourceActive()
  const target = String(source.config.slug ?? source.config.query ?? '')
  const last = source.last_run
  const busy = preview.isPending || run.isPending
  const error = preview.error ?? run.error ?? toggle.error

  return (
    <li className={cn('grid gap-3 px-4 py-4 sm:px-5', !source.active && 'opacity-70')}>
      <div className="flex flex-wrap items-start gap-x-4 gap-y-2">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-medium">{source.name}</h3>
            <span className="rounded-md border px-1.5 py-0.5 text-xs text-muted-foreground">{source.kind_label}</span>
            {!source.active && <span className="rounded-md bg-muted px-1.5 py-0.5 text-xs">Pausada</span>}
            {source.keys_missing && (
              <span className="rounded-md bg-amber-500/10 px-1.5 py-0.5 text-xs text-amber-700 dark:text-amber-400">
                Sin claves en .env
              </span>
            )}
          </div>
          <p className="mt-0.5 font-mono text-xs text-muted-foreground">{target}</p>
          <p className="mt-1.5 flex items-center gap-1.5 text-xs text-muted-foreground">
            <ClockIcon className="size-3.5" />
            {last ? (
              <span>
                {formatWhen(last.started_at)}: {last.found} encontradas, {last.after_filters} tras filtros,{' '}
                {last.created} nuevas
                {last.errors.length > 0 && last.found === 0 && (
                  <span className="text-destructive"> · {last.errors[0]!.message}</span>
                )}
              </span>
            ) : (
              <span>Aún no se ha ejecutado</span>
            )}
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <Button variant="outline" size="sm" disabled={busy} onClick={() => preview.mutate(source.id)}>
            {preview.isPending ? 'Probando…' : 'Probar'}
          </Button>
          <Button variant="outline" size="sm" disabled={busy || !source.active} onClick={() => run.mutate(source.id)}>
            <PlayIcon weight="fill" />
            {run.isPending ? 'Ejecutando…' : 'Ejecutar ahora'}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            disabled={toggle.isPending}
            onClick={() => toggle.mutate({ sourceId: source.id, active: !source.active })}
          >
            {source.active ? <PauseIcon /> : <PlayIcon />}
            {source.active ? 'Pausar' : 'Reactivar'}
          </Button>
        </div>
      </div>
      {preview.data && <PreviewResult result={preview.data} />}
      {run.data && <RunResult result={run.data} />}
      {error && (
        <Notice tone="error">
          <InlineCode text={errorMessage(error)} />
        </Notice>
      )}
    </li>
  )
}

function SourceList() {
  const sources = useSources()
  if (sources.isPending) {
    return (
      <div className="grid gap-3">
        <Skeleton className="h-20" />
        <Skeleton className="h-20" />
      </div>
    )
  }
  if (sources.isError) return <ErrorState error={sources.error} onRetry={() => sources.refetch()} />
  const items = sources.data.sources.filter((s) => CONNECTOR_KINDS.has(s.kind))
  if (items.length === 0) {
    return (
      <EmptyState icon={<BuildingsIcon className="size-6" weight="duotone" />} title="Aún no sigues ninguna empresa">
        Añade una con su ATS y su slug. Pruébala antes de guardarla para ver cuántas ofertas tiene y cuántas
        pasan tus filtros.
      </EmptyState>
    )
  }
  return (
    <ul className="divide-y rounded-xl border bg-card">
      {items.map((source) => (
        <SourceRow key={source.id} source={source} />
      ))}
    </ul>
  )
}

export function SourcesPage() {
  return (
    <div className="mx-auto max-w-3xl animate-in fade-in duration-300">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold tracking-tight">Empresas objetivo</h1>
        <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
          Sus ofertas llegan solas cada día con <InlineCode text="`jh worker`" />, desde las APIs públicas de
          su ATS. Solo se guardan las que encajan por título y ubicación con tus preferencias, y quedan en
          «Por extraer» para tu agente.
        </p>
      </div>
      <section className="mb-10 rounded-xl border bg-card p-5 sm:p-6">
        <h2 className="mb-4 font-medium">Añadir empresa o búsqueda</h2>
        <AddSourceForm />
      </section>
      <section>
        <h2 className="mb-3 font-medium">Seguidas</h2>
        <SourceList />
      </section>
    </div>
  )
}
