import type { ReactNode } from 'react'
import { Link } from 'react-router'
import { ArrowRightIcon, CheckCircleIcon, CircleDashedIcon, ScalesIcon } from '@phosphor-icons/react'
import { useTranslation } from 'react-i18next'
import type { JobView } from '@/api/client'
import { useEditableProfile } from '@/api/queries'
import { AgentButton } from '@/components/AgentButton'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

function Step({ done, title, hint, action }: { done: boolean; title: string; hint: string; action: ReactNode }) {
  const { t } = useTranslation('job', { keyPrefix: 'fitSteps' })
  const Icon = done ? CheckCircleIcon : CircleDashedIcon
  return (
    <li className="flex items-start gap-2.5">
      <Icon
        className={cn('mt-0.5 size-5 shrink-0', done ? 'text-primary' : 'text-muted-foreground')}
        weight={done ? 'fill' : 'bold'}
        aria-hidden
      />
      <div className="min-w-0">
        <p className={cn('font-medium', done && 'text-muted-foreground')}>
          {title}
          <span className="sr-only">: {done ? t('done') : t('pending')}</span>
        </p>
        {!done && (
          <>
            <p className="text-sm text-muted-foreground">{hint}</p>
            {action && <div className="mt-2">{action}</div>}
          </>
        )}
      </div>
    </li>
  )
}

/**
 * Lo que falta para que una oferta tenga encaje: tu perfil y que tu agente la lea, con lo hecho
 * marcado y el botón de lo que falta. `null` si no falta nada o aún no se sabe si hay perfil.
 * `profileMissing`: ya se sabe que falta (leída y sin encaje: sin perfil no hay con qué comparar).
 */
export function FitSteps({ job, profileMissing = false }: { job: JobView; profileMissing?: boolean }) {
  const { t } = useTranslation('job', { keyPrefix: 'fitSteps' })
  const { t: tAgent } = useTranslation('agent')
  const profile = useEditableProfile()
  const read = job.extraction !== null
  // Sin saber si hay perfil (cargando o sin respuesta), mejor no afirmar que falta.
  const hasProfile = !profileMissing && (profile.data?.exists ?? true)
  if (read && hasProfile) return null
  if (!profileMissing && profile.isPending) return null
  return (
    <section aria-label={t('title')} className="flex items-start gap-4 rounded-xl border border-dashed p-6">
      <ScalesIcon className="mt-0.5 size-6 shrink-0 text-primary" weight="duotone" aria-hidden />
      <div className="min-w-0">
        <h2 className="font-semibold">{t('title')}</h2>
        <p className="mt-1 text-sm text-muted-foreground">{t('intro')}</p>
        <ol className="mt-3 grid gap-3">
          <Step
            done={hasProfile}
            title={t('profile')}
            hint={t('profileHint')}
            action={
              <Button asChild size="sm" variant="outline">
                <Link to="/perfil">
                  {t('profileAction')}
                  <ArrowRightIcon />
                </Link>
              </Button>
            }
          />
          <Step
            done={read}
            title={t('read')}
            hint={t('readHint')}
            action={
              job.stage === 'pending_extraction' && (
                <AgentButton action="process-jobs" primary={hasProfile}>
                  {tAgent('actions.process-jobs')}
                </AgentButton>
              )
            }
          />
        </ol>
      </div>
    </section>
  )
}
