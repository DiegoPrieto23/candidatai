import type { ReactNode } from 'react'
import { Link } from 'react-router'
import { ArrowRightIcon, SignpostIcon } from '@phosphor-icons/react'
import { Trans, useTranslation } from 'react-i18next'
import type { Stage } from '@/api/client'
import { AgentButton } from '@/components/AgentButton'
import { Button } from '@/components/ui/button'

const link = 'font-medium text-foreground underline underline-offset-2 hover:text-primary'
const strong = <strong className="font-medium text-foreground" />

/** Los pasos de «Por completar»: lo que hace la extensión, el agente no puede hacerlo. */
const DETAIL_STEPS = ['open', 'send', 'discard'] as const

/**
 * Qué es la etapa que se está viendo en la Bandeja y qué hay que hacer para que sus ofertas pasen
 * a la siguiente, con el botón o el enlace que lo hace. Sin etapa, el recorrido entero.
 */
export function StageGuide({ stage }: { stage: Stage | undefined }) {
  const { t } = useTranslation('inbox', { keyPrefix: 'guide' })
  const key = stage ?? 'all'
  const components = {
    strong,
    extension: <Link to="/fuentes/extension" className={link} />,
    alerts: <Link to="/bandeja/por-completar" className={link} />,
    triage: <Link to="/bandeja/revision" className={link} />,
    processes: <Link to="/procesos" className={link} />,
  }

  let next: ReactNode
  if (stage === 'pending_detail') {
    next = (
      <>
        <ol className="mt-1 grid list-decimal gap-1 pl-5">
          {DETAIL_STEPS.map((step) => (
            <li key={step}>
              <Trans t={t} i18nKey={`pending_detail.steps.${step}`} components={components} />
            </li>
          ))}
        </ol>
        <p className="mt-2">
          <Trans t={t} i18nKey="pending_detail.extension" components={components} />
        </p>
      </>
    )
  } else {
    next = <Trans t={t} i18nKey={`${stage ?? 'all'}.next`} components={components} />
  }

  let actions: ReactNode = null
  if (stage === 'pending_detail') {
    actions = (
      <Button asChild size="sm">
        <Link to="/bandeja/por-completar">
          {t('openComplete')}
          <ArrowRightIcon />
        </Link>
      </Button>
    )
  } else if (stage === 'pending_extraction') {
    actions = (
      <AgentButton action="process-jobs" primary>
        {t('processJobs')}
      </AgentButton>
    )
  } else if (stage === 'pending_triage') {
    actions = (
      <>
        <Button asChild size="sm">
          <Link to="/bandeja/revision">
            {t('openTriage')}
            <ArrowRightIcon />
          </Link>
        </Button>
        <AgentButton action="assess-fit">{t('assessFit')}</AgentButton>
      </>
    )
  }

  return (
    <section
      aria-label={t('label')}
      className="mb-5 flex gap-3 rounded-xl border bg-card p-4 text-sm leading-relaxed text-muted-foreground"
    >
      <SignpostIcon className="mt-0.5 size-5 shrink-0 text-primary" weight="duotone" aria-hidden />
      <div className="min-w-0 flex-1">
        <p className="text-foreground/90">{t(`${key}.what`)}</p>
        <div className="mt-2">
          <span className="font-medium text-foreground">{t('nextLabel')} </span>
          {stage === 'pending_detail' ? <div>{next}</div> : next}
        </div>
        {actions && <div className="mt-3 flex flex-wrap items-start gap-2">{actions}</div>}
      </div>
    </section>
  )
}
