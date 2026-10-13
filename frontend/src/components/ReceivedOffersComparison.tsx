import type { ReactNode } from 'react'
import { Link } from 'react-router'
import { HandshakeIcon } from '@phosphor-icons/react'
import { useTranslation } from 'react-i18next'
import type { OfferComparison } from '@/api/client'
import { useReceivedOffers } from '@/api/queries'
import { ErrorState } from '@/components/States'
import { formatDate, formatMoney, formatMoneyDiff, formatSalary, REMOTE_LABEL } from '@/lib/labels'
import { cn } from '@/lib/utils'

function Diff({ value, currency }: { value: number | null | undefined; currency: string }) {
  if (value == null) return <span className="text-muted-foreground">—</span>
  return (
    <span className={cn('font-medium tabular-nums', value < 0 ? 'text-destructive' : 'text-emerald-700 dark:text-emerald-400')}>
      {formatMoneyDiff(value, currency)}
    </span>
  )
}

function money(value: number | null | undefined, currency: string, approximate: boolean): ReactNode {
  if (value == null) return <span className="text-muted-foreground">—</span>
  return (
    <span className="tabular-nums">
      {approximate && '≈ '}
      {formatMoney(value, currency)}
    </span>
  )
}

type Row = { label: string; cell: (o: OfferComparison) => ReactNode }

/**
 * Procesos (fase 21): las ofertas recibidas lado a lado, con la diferencia con tu mínimo
 * (`private.salary_floor_eur` del perfil) y con el rango publicado. Se calcula en la API y solo lo
 * ves tú: tu agente nunca recibe el mínimo ni estas diferencias. No recomienda ninguna cifra.
 */
export function ReceivedOffersComparison() {
  const { t } = useTranslation('offers', { keyPrefix: 'comparison' })
  const { data, isPending, isError, error, refetch } = useReceivedOffers()
  if (isPending) return null
  if (isError) return <ErrorState error={error} onRetry={() => refetch()} />
  if (data.offers.length === 0) return null
  const floor = data.floor_eur
  const rows: Row[] = [
    { label: t('rows.annualBase'), cell: (o) => money(o.annual_base, o.offer.currency, o.approximate) },
    { label: t('rows.annualTotal'), cell: (o) => money(o.annual_total, o.offer.currency, o.approximate) },
    { label: t('rows.baseVsFloor'), cell: (o) => <Diff value={o.floor_diff_base} currency="EUR" /> },
    { label: t('rows.totalVsFloor'), cell: (o) => <Diff value={o.floor_diff_total} currency="EUR" /> },
    { label: t('rows.published'), cell: (o) => formatSalary(o.published) ?? <span className="text-muted-foreground">{t('notPublished')}</span> },
    {
      label: t('rows.baseVsRange'),
      cell: (o) =>
        o.published_diff_min == null ? (
          <span className="text-muted-foreground">—</span>
        ) : (
          <span className="space-x-1.5">
            <span className="text-muted-foreground">{t('min')}</span>
            <Diff value={o.published_diff_min} currency={o.offer.currency} />
            <span className="text-muted-foreground">{t('max')}</span>
            <Diff value={o.published_diff_max} currency={o.offer.currency} />
          </span>
        ),
    },
    { label: t('rows.mode'), cell: (o) => (o.offer.work_mode ? REMOTE_LABEL[o.offer.work_mode] : '—') },
    { label: t('rows.location'), cell: (o) => o.offer.location ?? '—' },
    { label: t('rows.start'), cell: (o) => (o.offer.start_date ? formatDate(o.offer.start_date) : '—') },
    { label: t('rows.respondBy'), cell: (o) => (o.offer.respond_by ? formatDate(o.offer.respond_by) : '—') },
    { label: t('rows.benefits'), cell: (o) => <span className="whitespace-pre-line">{o.offer.benefits ?? '—'}</span> },
  ]
  return (
    <section aria-label={t('label')} className="mt-10 rounded-xl border bg-card p-5 sm:p-6">
      <h2 className="flex items-center gap-2 font-medium">
        <HandshakeIcon className="size-[18px] text-primary" weight="duotone" />
        {t('label')}
      </h2>
      <p className="mt-1 mb-4 max-w-[70ch] text-sm text-muted-foreground">
        {floor != null ? t('floor', { amount: formatMoney(floor) }) : t('noFloor')}
        {t('private')}
      </p>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[32rem] text-sm">
          <thead>
            <tr className="border-b text-left">
              <th scope="col" className="w-48 py-2 pr-4 font-normal text-muted-foreground" />
              {data.offers.map((o) => (
                <th key={o.job_id} scope="col" className="py-2 pr-4 align-bottom font-medium">
                  <Link to={`/jobs/${o.job_id}`} className="underline-offset-4 hover:underline">
                    {o.company}
                  </Link>
                  <span className="block text-xs font-normal text-muted-foreground">{o.title}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.label} className="border-b last:border-0">
                <th scope="row" className="py-2 pr-4 text-left font-normal text-muted-foreground">
                  {row.label}
                </th>
                {data.offers.map((o) => (
                  <td key={o.job_id} className="py-2 pr-4 align-top">
                    {row.cell(o)}
                  </td>
                ))}
              </tr>
            ))}
            <tr>
              <th scope="row" className="py-2 pr-4 text-left font-normal text-muted-foreground">
                {t('rows.remarks')}
              </th>
              {data.offers.map((o) => (
                <td key={o.job_id} className="py-2 pr-4 align-top text-xs text-muted-foreground">
                  {o.remarks.length ? o.remarks.join(' ') : '—'}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  )
}
