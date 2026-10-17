import { CoinsIcon } from '@phosphor-icons/react'
import { useTranslation } from 'react-i18next'
import { useJobCosts } from '@/api/queries'
import { formatDate, formatTokens, formatUsd } from '@/lib/labels'

/**
 * Ficha (fase 25.4): lo que se ha gastado en esta oferta en segundo plano. Sus ejecuciones enteras
 * y su parte de las de lote. Sin ejecuciones, no se enseña.
 */
export function JobCostPanel({ jobId }: { jobId: number }) {
  const { t } = useTranslation('agent', { keyPrefix: 'jobCost' })
  const { data } = useJobCosts(jobId)
  if (!data || data.runs.length === 0) return null
  const total = data.total
  return (
    <section aria-label={t('title')} className="rounded-xl border bg-card p-5 text-sm sm:p-6">
      <h2 className="mb-3 flex items-center gap-2 text-base font-semibold tracking-tight">
        <CoinsIcon className="size-[18px] text-muted-foreground" weight="duotone" aria-hidden />
        {t('title')}
      </h2>
      <p className="tabular">
        {t('total', {
          tokens: formatTokens(total.input_tokens + total.output_tokens),
          cost: formatUsd(total.cost_usd),
          count: total.runs,
        })}
      </p>
      <ul className="mt-2 space-y-1 text-xs text-muted-foreground" aria-label={t('runs')}>
        {data.runs.map((run) => (
          <li key={run.run_id} className="tabular">
            {run.label} · {run.agent}
            {run.model && ` · ${run.model}`}
            {run.finished_at && ` · ${formatDate(run.finished_at)}`}
            {run.shared_with > 1 && ` · ${t('shared', { count: run.shared_with })}`}
          </li>
        ))}
      </ul>
      <p className="mt-2 text-xs text-muted-foreground">{t('terminal')}</p>
    </section>
  )
}
