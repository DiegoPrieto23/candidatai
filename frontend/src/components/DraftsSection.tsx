import { CheckIcon, EnvelopeSimpleIcon, TrashIcon } from '@phosphor-icons/react'
import type { JobView, MessageDraftOut } from '@/api/client'
import { useDiscardDraft, useJobDrafts, useMarkDraftSent } from '@/api/queries'
import { AgentButton } from '@/components/AgentButton'
import { CopyButton } from '@/components/CopyButton'
import { Button } from '@/components/ui/button'
import { formatRelative } from '@/lib/labels'

/** Candidaturas enviadas y abiertas: a las que se escribe un seguimiento o un agradecimiento. */
const OPEN_STAGES = new Set(['applied', 'in_process'])

const KIND_LABEL: Record<MessageDraftOut['kind'], string> = {
  followup: 'Seguimiento',
  thank_you: 'Agradecimiento',
}

function DraftCard({ draft, jobId }: { draft: MessageDraftOut; jobId: number }) {
  const sent = useMarkDraftSent(jobId)
  const discard = useDiscardDraft(jobId)
  const pending = sent.isPending || discard.isPending
  const error = sent.error ?? discard.error
  return (
    <li className="space-y-3 rounded-lg border bg-background p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          {KIND_LABEL[draft.kind]}
          {draft.agent_name && <span className="normal-case"> · de {draft.agent_name}</span>}
        </p>
        <span className="text-xs text-muted-foreground">{formatRelative(draft.updated_at)}</span>
      </div>
      <div className="flex items-start justify-between gap-3">
        <p className="min-w-0 font-medium">{draft.subject}</p>
        <CopyButton text={draft.subject} label="Copiar asunto" ariaLabel={`Copiar el asunto: ${draft.subject}`} />
      </div>
      <pre className="rounded-md border bg-card p-3 font-sans text-sm leading-relaxed whitespace-pre-wrap">{draft.body}</pre>
      <div className="flex flex-wrap gap-2">
        <CopyButton text={draft.body} label="Copiar texto" />
        <Button type="button" size="sm" disabled={pending} onClick={() => sent.mutate(draft.id)} className="active:translate-y-px">
          <CheckIcon weight="bold" />
          Ya lo he enviado
        </Button>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          disabled={pending}
          onClick={() => discard.mutate(draft.id)}
          className="active:translate-y-px"
        >
          <TrashIcon />
          Descartar
        </Button>
      </div>
      {error && (
        <p role="alert" className="text-sm text-destructive">
          No se pudo guardar: {error.message}
        </p>
      )}
    </li>
  )
}

/**
 * Ficha (fase 15): borradores de seguimiento y agradecimiento que redacta tu agente. La app no
 * envía nada: copias el texto, lo mandas desde tu correo y pulsas «Ya lo he enviado».
 */
export function DraftsSection({ job }: { job: JobView }) {
  const open = job.stage !== null && OPEN_STAGES.has(job.stage)
  const { data, isError, error } = useJobDrafts(job.id, open)
  if (!open) return null
  const capped = data ? data.followups_sent >= data.max_followups : false
  return (
    <section aria-label="Borradores" className="rounded-xl border bg-card p-5 sm:p-6">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 font-semibold">
            <EnvelopeSimpleIcon className="size-[18px] text-primary" weight="duotone" />
            Borradores
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Tu agente los redacta; la app nunca envía nada.
            {data && (
              <>
                {' '}
                {data.followups_sent} de {data.max_followups} seguimientos enviados
                {capped && ': no conviene insistir más'}.
              </>
            )}
          </p>
        </div>
        <AgentButton action="redactar-seguimiento" jobId={job.id}>
          Redactar seguimiento
        </AgentButton>
      </div>
      {isError ? (
        <p role="alert" className="text-sm text-destructive">
          No se pudieron cargar: {error.message}
        </p>
      ) : data?.drafts.length ? (
        <ul className="space-y-3">
          {data.drafts.map((draft) => (
            <DraftCard key={draft.id} draft={draft} jobId={job.id} />
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground">
          Sin borradores. Tu agente redacta un seguimiento si la candidatura lleva días sin respuesta, o un
          agradecimiento tras una entrevista hecha.
        </p>
      )}
    </section>
  )
}
