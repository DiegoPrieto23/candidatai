import { CheckIcon, EnvelopeSimpleIcon, PaperclipIcon, TrashIcon } from '@phosphor-icons/react'
import type { JobView, MessageDraftOut, Stage } from '@/api/client'
import { useDiscardDraft, useJobDrafts, useMarkDraftSent } from '@/api/queries'
import { AgentButton } from '@/components/AgentButton'
import { CopyButton } from '@/components/CopyButton'
import { Button } from '@/components/ui/button'
import { formatRelative } from '@/lib/labels'
import { cn } from '@/lib/utils'

/** Candidaturas enviadas y abiertas: a las que se escribe un seguimiento o un agradecimiento. */
const SENT_STAGES: ReadonlySet<Stage> = new Set(['applied', 'in_process'])
/** Mensajes a personas de la empresa (fase 18): desde que apruebas la oferta. */
const OUTREACH_STAGES: ReadonlySet<Stage> = new Set(['approved', 'cv_ready', 'applied', 'in_process'])
const LINKEDIN_MAX_CHARS = 300

const KIND_LABEL: Record<MessageDraftOut['kind'], string> = {
  followup: 'Seguimiento',
  thank_you: 'Agradecimiento',
  linkedin: 'LinkedIn',
  email: 'Correo',
}

const ROLE_LABEL: Record<NonNullable<MessageDraftOut['recipient_role']>, string> = {
  recruiter: 'recruiter',
  hiring_manager: 'responsable del puesto',
  peer: 'compañero',
}

function recipient(draft: MessageDraftOut): string | null {
  if (!draft.recipient_role) return null
  const role = ROLE_LABEL[draft.recipient_role]
  return draft.recipient_name ? `Para ${draft.recipient_name} (${role})` : `Para: ${role}`
}

function DraftCard({ draft, jobId }: { draft: MessageDraftOut; jobId: number }) {
  const sent = useMarkDraftSent(jobId)
  const discard = useDiscardDraft(jobId)
  const pending = sent.isPending || discard.isPending
  const error = sent.error ?? discard.error
  const to = recipient(draft)
  // Caracteres Unicode, como cuenta el backend (un emoji es uno, no dos).
  const chars = Array.from(draft.body).length
  return (
    <li className="space-y-3 rounded-lg border bg-background p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          {KIND_LABEL[draft.kind]}
          {draft.agent_name && <span className="normal-case"> · de {draft.agent_name}</span>}
        </p>
        <span className="text-xs text-muted-foreground">{formatRelative(draft.updated_at)}</span>
      </div>
      {to && <p className="text-sm text-muted-foreground">{to}</p>}
      {draft.subject && (
        <div className="flex items-start justify-between gap-3">
          <p className="min-w-0 font-medium">{draft.subject}</p>
          <CopyButton text={draft.subject} label="Copiar asunto" ariaLabel={`Copiar el asunto: ${draft.subject}`} />
        </div>
      )}
      <pre className="rounded-md border bg-card p-3 font-sans text-sm leading-relaxed whitespace-pre-wrap">{draft.body}</pre>
      {draft.kind === 'linkedin' && (
        <p className={cn('text-xs', chars > LINKEDIN_MAX_CHARS ? 'text-destructive' : 'text-muted-foreground')}>
          {chars}/{LINKEDIN_MAX_CHARS} caracteres
        </p>
      )}
      {draft.attachments && draft.attachments.length > 0 && (
        <div className="text-sm">
          <p className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
            <PaperclipIcon className="size-3.5" />
            Adjunta tú:
          </p>
          <ul className="mt-1 list-disc pl-5" aria-label="Adjuntos">
            {draft.attachments.map((name) => (
              <li key={name}>{name}</li>
            ))}
          </ul>
        </div>
      )}
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
 * Ficha: borradores que redacta tu agente. Seguimientos y agradecimientos (fase 15), con la
 * candidatura enviada; mensajes de LinkedIn y correos a personas de la empresa (fase 18), desde
 * que la apruebas. La app no envía nada: copias el texto, lo mandas tú y pulsas «Ya lo he enviado».
 */
export function DraftsSection({ job }: { job: JobView }) {
  const open = job.stage !== null && OUTREACH_STAGES.has(job.stage)
  const sentStage = job.stage !== null && SENT_STAGES.has(job.stage)
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
            {data && sentStage && (
              <>
                {' '}
                {data.followups_sent} de {data.max_followups} seguimientos enviados
                {capped && ': no conviene insistir más'}.
              </>
            )}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <AgentButton action="redactar-mensaje" jobId={job.id}>
            Redactar mensaje
          </AgentButton>
          {sentStage && (
            <AgentButton action="redactar-seguimiento" jobId={job.id}>
              Redactar seguimiento
            </AgentButton>
          )}
        </div>
      </div>
      {isError ? (
        // Sale también antes de enviar: el fallo se dice sin `alert`, para no tapar los avisos de la ficha.
        <p className="text-sm text-muted-foreground">No se pudieron cargar los borradores: {error.message}</p>
      ) : data?.drafts.length ? (
        <ul className="space-y-3">
          {data.drafts.map((draft) => (
            <DraftCard key={draft.id} draft={draft} jobId={job.id} />
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground">
          Sin borradores. Tu agente redacta un mensaje de LinkedIn o un correo para alguien de la empresa
          {sentStage && ', un seguimiento si la candidatura lleva días sin respuesta o un agradecimiento tras una entrevista'}.
        </p>
      )}
    </section>
  )
}
