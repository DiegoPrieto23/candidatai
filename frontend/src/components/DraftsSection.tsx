import { CheckIcon, EnvelopeSimpleIcon, PaperclipIcon, TrashIcon } from '@phosphor-icons/react'
import { useTranslation } from 'react-i18next'
import type { JobView, MessageDraftOut, Stage } from '@/api/client'
import { useDiscardDraft, useJobDrafts, useMarkDraftSent } from '@/api/queries'
import { AgentButton } from '@/components/AgentButton'
import { CopyButton } from '@/components/CopyButton'
import { Button } from '@/components/ui/button'
import { i18n } from '@/lib/i18n'
import { formatRelative } from '@/lib/labels'
import { errorMessage } from '@/lib/errors'
import { cn } from '@/lib/utils'

/** Candidaturas enviadas y abiertas: a las que se escribe un seguimiento o un agradecimiento. */
const SENT_STAGES: ReadonlySet<Stage> = new Set(['applied', 'in_process'])
/** Mensajes a personas de la empresa (fase 18): desde que apruebas la oferta. */
const OUTREACH_STAGES: ReadonlySet<Stage> = new Set(['approved', 'cv_ready', 'applied', 'in_process'])
const LINKEDIN_MAX_CHARS = 300

function recipient(draft: MessageDraftOut): string | null {
  if (!draft.recipient_role) return null
  const t = i18n.getFixedT(null, 'drafts')
  const role = t(`role.${draft.recipient_role}`)
  return draft.recipient_name ? t('toNamed', { name: draft.recipient_name, role }) : t('to', { role })
}

function DraftCard({ draft, jobId }: { draft: MessageDraftOut; jobId: number }) {
  const { t } = useTranslation('drafts')
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
          {t(`kind.${draft.kind}`)}
          {draft.agent_name && <span className="normal-case">{t('from', { agent: draft.agent_name })}</span>}
        </p>
        <span className="text-xs text-muted-foreground">{formatRelative(draft.updated_at)}</span>
      </div>
      {to && <p className="text-sm text-muted-foreground">{to}</p>}
      {draft.subject && (
        <div className="flex items-start justify-between gap-3">
          <p className="min-w-0 font-medium">{draft.subject}</p>
          <CopyButton text={draft.subject} label={t('copySubject')} ariaLabel={t('copySubjectAria', { subject: draft.subject })} />
        </div>
      )}
      <pre className="rounded-md border bg-card p-3 font-sans text-sm leading-relaxed whitespace-pre-wrap">{draft.body}</pre>
      {draft.kind === 'linkedin' && (
        <p className={cn('text-xs', chars > LINKEDIN_MAX_CHARS ? 'text-destructive' : 'text-muted-foreground')}>
          {t('chars', { count: chars, max: LINKEDIN_MAX_CHARS })}
        </p>
      )}
      {draft.attachments && draft.attachments.length > 0 && (
        <div className="text-sm">
          <p className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
            <PaperclipIcon className="size-3.5" />
            {t('attach')}
          </p>
          <ul className="mt-1 list-disc pl-5" aria-label={t('attachments')}>
            {draft.attachments.map((name) => (
              <li key={name}>{name}</li>
            ))}
          </ul>
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        <CopyButton text={draft.body} label={t('copyText')} />
        <Button type="button" size="sm" disabled={pending} onClick={() => sent.mutate(draft.id)} className="active:translate-y-px">
          <CheckIcon weight="bold" />
          {t('sent')}
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
          {t('discard')}
        </Button>
      </div>
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {t('saveFailed', { error: errorMessage(error) })}
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
  const { t } = useTranslation('drafts')
  const open = job.stage !== null && OUTREACH_STAGES.has(job.stage)
  const sentStage = job.stage !== null && SENT_STAGES.has(job.stage)
  const { data, isError, error } = useJobDrafts(job.id, open)
  if (!open) return null
  const capped = data ? data.followups_sent >= data.max_followups : false
  return (
    <section aria-label={t('title')} className="rounded-xl border bg-card p-5 sm:p-6">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 font-semibold">
            <EnvelopeSimpleIcon className="size-[18px] text-primary" weight="duotone" />
            {t('title')}
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {t('intro')}
            {data && sentStage && (
              <>
                {t('followups', { sent: data.followups_sent, max: data.max_followups })}
                {capped && t('capped')}.
              </>
            )}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <AgentButton action="draft-message" jobId={job.id}>
            {t('draftMessage')}
          </AgentButton>
          {sentStage && (
            <AgentButton action="draft-follow-up" jobId={job.id}>
              {t('draftFollowup')}
            </AgentButton>
          )}
        </div>
      </div>
      {isError ? (
        // Sale también antes de enviar: el fallo se dice sin `alert`, para no tapar los avisos de la ficha.
        <p className="text-sm text-muted-foreground">{t('loadFailed', { error: errorMessage(error) })}</p>
      ) : data?.drafts.length ? (
        <ul className="space-y-3">
          {data.drafts.map((draft) => (
            <DraftCard key={draft.id} draft={draft} jobId={job.id} />
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground">{sentStage ? t('noneSent') : t('none')}</p>
      )}
    </section>
  )
}
