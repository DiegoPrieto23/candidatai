import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { ArrowsClockwiseIcon, EnvelopeSimpleIcon, ShieldWarningIcon, XIcon } from '@phosphor-icons/react'
import type { RepliesPollResult, ReplyInboxItem } from '@/api/client'
import { usePollReplies, useReplies, useReply, type ReplyStatus } from '@/api/queries'
import { AgentButton } from '@/components/AgentButton'
import { ReplyProposalCard } from '@/components/ReplyDecision'
import { EmptyState, ErrorState, InlineCode } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { formatRelative, STAGE_LABEL } from '@/lib/labels'
import { MATCH_REASON_LABEL, REPLY_EVENT_LABEL } from '@/lib/replies'
import { formatWhen } from '@/lib/time'
import { cn } from '@/lib/utils'

type Filter = 'pending' | 'accepted' | 'ignored' | 'all'

const FILTERS: { value: Filter; label: string; statuses: ReplyStatus[] }[] = [
  { value: 'pending', label: 'Pendientes', statuses: ['new', 'proposed'] },
  { value: 'accepted', label: 'Aceptadas', statuses: ['accepted'] },
  { value: 'ignored', label: 'Ignoradas', statuses: ['ignored'] },
  { value: 'all', label: 'Todas', statuses: ['new', 'proposed', 'accepted', 'ignored'] },
]

const RISK_TEXT: Record<string, string> = {
  hidden_text: 'texto oculto',
  injection_phrase: 'frases que parecen instrucciones para una IA',
}

const STATUS_LABEL: Record<ReplyStatus, string> = {
  new: 'Sin clasificar',
  proposed: 'Por revisar',
  accepted: 'Aceptada',
  ignored: 'Ignorada',
}

function from(item: ReplyInboxItem): string {
  return item.sender_name || item.sender
}

function PollResult({ result, onClose }: { result: RepliesPollResult; onClose: () => void }) {
  return (
    <div
      role="status"
      className="flex items-start gap-3 rounded-xl border bg-card px-4 py-2.5 text-sm animate-in fade-in slide-in-from-top-1"
    >
      <EnvelopeSimpleIcon className="mt-0.5 size-[18px] shrink-0 text-primary" weight="duotone" />
      <div className="min-w-0 flex-1">
        <p>{result.message}</p>
        {result.errors.length > 0 && (
          <ul className="mt-1 space-y-0.5 text-xs text-muted-foreground">
            {result.errors.slice(0, 5).map((issue, i) => (
              <li key={i}>{issue.message}</li>
            ))}
          </ul>
        )}
      </div>
      <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground" aria-label="Cerrar aviso">
        <XIcon className="size-4" />
      </button>
    </div>
  )
}

function ReplyRow({ item, selected, onSelect }: { item: ReplyInboxItem; selected: boolean; onSelect: () => void }) {
  const job = item.candidates.find((c) => c.job_id === (item.proposal?.job_id ?? item.job_id)) ?? item.candidates[0]
  return (
    <li>
      <button
        type="button"
        aria-current={selected ? 'true' : undefined}
        onClick={onSelect}
        className={cn(
          'relative flex w-full flex-col gap-1 px-4 py-3 text-left transition-colors outline-none focus-visible:bg-foreground/[0.04]',
          selected ? 'bg-accent/70' : 'hover:bg-foreground/[0.03]',
        )}
      >
        {selected && <span aria-hidden className="absolute inset-y-2 left-0 w-0.5 rounded-full bg-primary" />}
        <span className="flex items-baseline justify-between gap-3">
          <span className="flex min-w-0 items-center gap-1.5 text-sm font-medium">
            <span className="truncate">{from(item)}</span>
            {item.risk_flags.length > 0 && (
              <ShieldWarningIcon
                className="size-3.5 shrink-0 text-warning-foreground"
                weight="fill"
                aria-label="Posible contenido dirigido a una IA"
              />
            )}
          </span>
          {item.received_at && (
            <span className="tabular shrink-0 text-xs text-muted-foreground">{formatRelative(item.received_at)}</span>
          )}
        </span>
        <span className="truncate text-sm text-foreground/80">{item.subject || '(sin asunto)'}</span>
        <span className="flex items-center gap-2 text-xs text-muted-foreground">
          <span className="truncate">{job ? `${job.title} · ${job.company}` : 'Sin oferta'}</span>
          <span
            className={cn(
              'ml-auto shrink-0 rounded-full border px-2 py-0.5 font-medium',
              item.status === 'proposed' && 'border-primary/30 text-primary',
            )}
          >
            {item.status === 'proposed' && item.proposal
              ? REPLY_EVENT_LABEL[item.proposal.event_type]
              : STATUS_LABEL[item.status]}
          </span>
        </span>
      </button>
    </li>
  )
}

function ReplyDetail({ item }: { item: ReplyInboxItem }) {
  const { data, isPending, isError, error, refetch } = useReply(item.reply_id)
  return (
    <article aria-label="Correo" className="space-y-5 rounded-xl border bg-card p-5 sm:p-6">
      <header className="space-y-1">
        <h2 className="text-lg leading-snug font-semibold text-balance">{item.subject || '(sin asunto)'}</h2>
        <p className="text-sm text-muted-foreground">
          {item.sender_name ? (
            <>
              <span className="text-foreground/90">{item.sender_name}</span> &lt;{item.sender}&gt;
            </>
          ) : (
            item.sender
          )}
          {item.received_at && <> · {formatWhen(item.received_at)}</>}
        </p>
        <ul className="flex flex-wrap gap-x-4 gap-y-1 pt-1 text-xs text-muted-foreground">
          {item.candidates.map((c) => (
            <li key={c.job_id}>
              <Link to={`/jobs/${c.job_id}`} className="font-medium text-foreground/90 underline-offset-4 hover:underline">
                {c.title} · {c.company}
              </Link>{' '}
              ({STAGE_LABEL[c.stage]}; por {MATCH_REASON_LABEL[c.reason]})
            </li>
          ))}
        </ul>
      </header>

      <section aria-label="Propuesta" className="rounded-lg border border-primary/30 bg-primary/[0.03] p-4">
        <ReplyProposalCard item={item} />
      </section>

      {item.risk_flags.length > 0 && (
        <p role="note" className="flex items-start gap-2 rounded-lg border border-warning-border bg-warning px-3 py-2 text-sm text-warning-foreground">
          <ShieldWarningIcon className="mt-0.5 size-4 shrink-0" weight="fill" />
          <span>
            Este correo tiene {item.risk_flags.map((f) => RISK_TEXT[f] ?? f).join(' y ')}. Puede intentar engañar a tu
            agente: comprueba la propuesta con el texto.
          </span>
        </p>
      )}

      <section aria-label="Texto del correo">
        <h3 className="mb-2 text-xs font-medium tracking-wide text-muted-foreground uppercase">Texto del correo</h3>
        {isPending ? (
          <Skeleton className="h-40" />
        ) : isError ? (
          <ErrorState error={error} onRetry={() => void refetch()} />
        ) : (
          // Texto plano: el correo nunca se muestra como HTML.
          <pre className="max-h-[32rem] overflow-auto rounded-lg border bg-background p-4 font-sans text-sm leading-relaxed whitespace-pre-wrap">
            {data.body_text || '(vacío)'}
          </pre>
        )}
      </section>
    </article>
  )
}

function ListSkeleton() {
  return (
    <div aria-busy="true" aria-label="Cargando respuestas" className="space-y-2 rounded-xl border bg-card p-3">
      {Array.from({ length: 5 }, (_, i) => (
        <Skeleton key={i} className="h-14" />
      ))}
    </div>
  )
}

export function RepliesPage() {
  const { data, isPending, isError, error, refetch } = useReplies()
  const poll = usePollReplies()
  const [filter, setFilter] = useState<Filter>('pending')
  const [params] = useSearchParams()
  // `?correo=ID`: el enlace «Ver el correo» de la ficha de la oferta.
  const [selectedId, setSelectedId] = useState<number | null>(() => Number(params.get('correo')) || null)

  const statuses = FILTERS.find((f) => f.value === filter)!.statuses
  const items = useMemo(
    () => (data?.replies ?? []).filter((r) => statuses.includes(r.status)),
    [data, statuses],
  )
  const selected = items.find((r) => r.reply_id === selectedId) ?? items[0]
  const counts = data?.counts ?? {}
  const unclassified = counts.new ?? 0
  const countFor = (f: (typeof FILTERS)[number]) => f.statuses.reduce((n, s) => n + (counts[s] ?? 0), 0)

  return (
    <div className="animate-in fade-in duration-300">
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Respuestas</h1>
          <p className="max-w-prose text-sm text-muted-foreground">
            Correos de las empresas sobre tus candidaturas. Tu agente propone qué significa cada uno; nada cambia de
            etapa hasta que lo aceptas aquí.
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap items-start gap-2">
          {unclassified > 0 && (
            <AgentButton action="revisar-respuestas" variant="default">
              Revisar respuestas
            </AgentButton>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={() => poll.mutate()}
            disabled={poll.isPending}
            className="active:translate-y-px"
          >
            <ArrowsClockwiseIcon className={cn(poll.isPending && 'animate-spin')} />
            {poll.isPending ? 'Leyendo el correo…' : 'Revisar correo ahora'}
          </Button>
        </div>
      </div>

      <div className="mb-4 space-y-3 empty:hidden">
        {poll.data && <PollResult result={poll.data} onClose={() => poll.reset()} />}
        {poll.error && (
          <p role="alert" className="rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-2.5 text-sm">
            No se pudo leer el correo: {poll.error.message}
          </p>
        )}
        {unclassified > 0 && (
          <p role="status" className="text-sm text-muted-foreground">
            {unclassified === 1 ? '1 correo sin clasificar' : `${unclassified} correos sin clasificar`}: «Revisar
            respuestas» abre tu agente para que proponga qué es cada uno.
          </p>
        )}
      </div>

      <div role="group" aria-label="Filtrar por estado" className="mb-4 flex flex-wrap gap-1">
        {FILTERS.map((f) => (
          <button
            key={f.value}
            type="button"
            aria-pressed={filter === f.value}
            onClick={() => {
              setFilter(f.value)
              setSelectedId(null)
            }}
            className={cn(
              'flex items-baseline gap-2 rounded-md px-3 py-1.5 text-sm transition-colors',
              filter === f.value
                ? 'bg-foreground/[0.06] text-foreground dark:bg-foreground/10'
                : 'text-muted-foreground hover:bg-foreground/[0.04] hover:text-foreground',
            )}
          >
            {f.label}
            <span className="tabular text-xs font-medium">{countFor(f)}</span>
          </button>
        ))}
      </div>

      {isPending ? (
        <ListSkeleton />
      ) : isError ? (
        <ErrorState error={error} onRetry={() => void refetch()} />
      ) : items.length === 0 ? (
        <section className="rounded-xl border bg-card">
          <EmptyState icon={<EnvelopeSimpleIcon className="size-6" weight="duotone" />} title="Sin respuestas aquí">
            Los correos de las empresas a tus candidaturas enviadas aparecen aquí. Se leen por IMAP (
            <InlineCode text="CAI_IMAP_REPLIES_FOLDER" />) o de <InlineCode text="data/inbox/respuestas/" />.
          </EmptyState>
        </section>
      ) : (
        <div className="grid items-start gap-6 lg:grid-cols-[22rem_minmax(0,1fr)]">
          <section className="overflow-hidden rounded-xl border bg-card">
            <ul aria-label="Respuestas" className="divide-y">
              {items.map((item) => (
                <ReplyRow
                  key={item.reply_id}
                  item={item}
                  selected={item.reply_id === selected?.reply_id}
                  onSelect={() => setSelectedId(item.reply_id)}
                />
              ))}
            </ul>
          </section>
          {selected && <ReplyDetail key={selected.reply_id} item={selected} />}
        </div>
      )}
    </div>
  )
}
