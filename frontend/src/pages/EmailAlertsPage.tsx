import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { ArrowsClockwiseIcon, EnvelopeSimpleIcon, PlusIcon, XIcon } from '@phosphor-icons/react'
import type { EmailPollResult } from '@/api/client'
import { useMailSources, usePollAlerts } from '@/api/queries'
import { MailboxDialog, MailboxesPanel, type MailboxDialogState } from '@/components/Mailboxes'
import { EmptyState } from '@/components/States'
import { Button } from '@/components/ui/button'
import { errorMessage } from '@/lib/errors'
import { cn } from '@/lib/utils'

function PollResult({ result, onClose }: { result: EmailPollResult; onClose: () => void }) {
  const { t } = useTranslation('alerts')
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
      <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground" aria-label={t('closeNotice')}>
        <XIcon className="size-4" />
      </button>
    </div>
  )
}

/** «Alertas por correo», dentro de «Dónde buscar»: los buzones de los que salen las alertas de empleo. */
export function EmailAlertsPage() {
  const { t } = useTranslation('alerts')
  const poll = usePollAlerts()
  const sources = useMailSources()
  const [mailDialog, setMailDialog] = useState<MailboxDialogState>(null)
  const empty = sources.isSuccess && sources.data.sources.length === 0

  return (
    <div className="mx-auto w-full max-w-3xl animate-in fade-in duration-300">
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{t('email.title')}</h1>
          <p className="mt-1.5 max-w-prose text-sm leading-relaxed text-muted-foreground">{t('email.intro')}</p>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          <Button variant="outline" size="sm" onClick={() => setMailDialog({ mode: 'add' })} className="active:translate-y-px">
            <PlusIcon />
            {t('addMailbox')}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => poll.mutate()}
            disabled={poll.isPending}
            className="active:translate-y-px"
          >
            <ArrowsClockwiseIcon className={cn(poll.isPending && 'animate-spin')} />
            {poll.isPending ? t('reading') : t('poll')}
          </Button>
        </div>
      </div>

      <div className="space-y-3">
        <MailboxesPanel defaultOpen onEdit={(source) => setMailDialog({ mode: 'edit', source })} />
        {empty && (
          <section className="rounded-xl border bg-card">
            <EmptyState icon={<EnvelopeSimpleIcon className="size-6" weight="duotone" />} title={t('email.emptyTitle')}>
              <p>{t('email.emptyBody')}</p>
              <Button size="sm" className="mt-3" onClick={() => setMailDialog({ mode: 'add' })}>
                <PlusIcon />
                {t('addMailbox')}
              </Button>
            </EmptyState>
          </section>
        )}
        {poll.data && <PollResult result={poll.data} onClose={() => poll.reset()} />}
        {poll.error && (
          <p role="alert" className="rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-2.5 text-sm">
            {t('pollFailed', { error: errorMessage(poll.error) })}
          </p>
        )}
        {!empty && (
          <p className="px-1 text-sm text-muted-foreground">
            {t('email.goToComplete')}{' '}
            <Link to="/bandeja/por-completar" className="font-medium text-foreground underline underline-offset-2 hover:text-primary">
              {t('title')}
            </Link>
          </p>
        )}
      </div>

      <MailboxDialog state={mailDialog} onClose={() => setMailDialog(null)} />
    </div>
  )
}
