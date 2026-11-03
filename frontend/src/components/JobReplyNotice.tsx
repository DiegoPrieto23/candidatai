import { Link } from 'react-router'
import { EnvelopeSimpleIcon } from '@phosphor-icons/react'
import { useTranslation } from 'react-i18next'
import { useReplies } from '@/api/queries'
import { ReplyProposalCard } from '@/components/ReplyDecision'
import { formatWhen } from '@/lib/time'

/**
 * Ficha de la oferta (fase 15): las respuestas de la empresa que tu agente ya ha clasificado y
 * esperan tu decisión. Nada cambia de etapa hasta que pulsas «Aceptar».
 */
export function JobReplyNotice({ jobId }: { jobId: number }) {
  const { t } = useTranslation('job', { keyPrefix: 'replyNotice' })
  const { data } = useReplies({ jobId, status: 'proposed' })
  const items = data?.replies ?? []
  if (!items.length) return null
  return (
    <section
      aria-label={t('label')}
      className="space-y-5 divide-y divide-primary/15 rounded-xl border border-primary/30 bg-accent/60 p-5 text-accent-foreground animate-in fade-in slide-in-from-top-1 sm:p-6"
    >
      {items.map((item) => (
        <div key={item.reply_id} className="space-y-3 pt-5 first:pt-0">
          <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
            <EnvelopeSimpleIcon className="size-4 text-primary" weight="duotone" />
            <span>
              {t('from', { sender: item.sender_name || item.sender })}
              {item.received_at && <> · {formatWhen(item.received_at)}</>}
            </span>
            <Link to={`/respuestas?correo=${item.reply_id}`} className="underline underline-offset-4 hover:text-foreground">
              {t('see')}
            </Link>
          </p>
          <ReplyProposalCard item={item} />
        </div>
      ))}
    </section>
  )
}
