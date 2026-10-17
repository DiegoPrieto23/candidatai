import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { CostGroup, CostTotals, CostWindow } from '@/api/client'
import { useAgentCosts, useAssessThreshold, useSaveAssessThreshold } from '@/api/queries'
import { ErrorState } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { errorMessage } from '@/lib/errors'
import { formatNumber, formatTokens, formatUsd } from '@/lib/labels'

function minutes(ms: number | null | undefined): string {
  return ms == null ? '—' : `${formatNumber(ms / 60_000, { maximumFractionDigits: 1 })} min`
}

function Totals({ total }: { total: CostTotals }) {
  const { t } = useTranslation('agent', { keyPrefix: 'costs' })
  const items = [
    [t('runs'), formatNumber(total.runs)],
    [t('tokens'), formatTokens(total.input_tokens + total.output_tokens)],
    [t('cost'), formatUsd(total.cost_usd)],
    [t('avgTokens'), formatTokens(total.avg_tokens)],
  ]
  return (
    <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {items.map(([label, value]) => (
        <div key={label} className="rounded-lg border bg-card px-3 py-2">
          <dt className="text-xs text-muted-foreground">{label}</dt>
          <dd className="font-medium tabular">{value}</dd>
        </div>
      ))}
    </dl>
  )
}

function GroupTable({ caption, groups, withInstructions }: { caption: string; groups: CostGroup[]; withInstructions?: boolean }) {
  const { t } = useTranslation('agent', { keyPrefix: 'costs' })
  if (groups.length === 0) return <p className="text-sm text-muted-foreground">{t('empty')}</p>
  const heads = [t('runs'), t('avgTokens'), t('avgDuration'), t('cost'), t('avgCost')]
  if (withInstructions) heads.push(t('instructions'))
  return (
    <div className="-mx-1 overflow-x-auto">
      <table className="w-full min-w-[36rem] text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="border-b text-left text-xs text-muted-foreground">
            <th scope="col" className="px-1 pb-2 font-medium">
              {caption}
            </th>
            {heads.map((h) => (
              <th key={h} scope="col" className="px-1 pb-2 text-right font-medium">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {groups.map((g) => (
            <tr key={g.key} className="border-b last:border-0">
              <th scope="row" className="px-1 py-1.5 text-left font-normal">
                {g.label}
              </th>
              <td className="px-1 py-1.5 text-right tabular">
                {formatNumber(g.runs)}
                {g.with_usage < g.runs && (
                  <span className="text-xs text-muted-foreground"> {t('withUsage', { count: g.with_usage })}</span>
                )}
              </td>
              <td className="px-1 py-1.5 text-right tabular">{formatTokens(g.avg_tokens)}</td>
              <td className="px-1 py-1.5 text-right tabular">{minutes(g.avg_duration_ms)}</td>
              <td className="px-1 py-1.5 text-right tabular">{formatUsd(g.cost_usd)}</td>
              <td className="px-1 py-1.5 text-right tabular">{formatUsd(g.avg_cost_usd)}</td>
              {withInstructions && <td className="px-1 py-1.5 text-right tabular">{formatTokens(g.instruction_tokens)}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function CostWindowView({ data }: { data: CostWindow }) {
  const { t } = useTranslation('agent', { keyPrefix: 'costs' })
  return (
    <div className="grid gap-5">
      <Totals total={data.total} />
      <GroupTable caption={t('byAction')} groups={data.by_action} withInstructions />
      <GroupTable caption={t('byAgent')} groups={data.by_agent} />
      <GroupTable caption={t('byModel')} groups={data.by_model} />
    </div>
  )
}

/** Umbral de «Evaluar encaje» en segundo plano: por debajo, la oferta se queda sin valorar. */
function Threshold() {
  const { t } = useTranslation('agent', { keyPrefix: 'costs' })
  const { data } = useAssessThreshold()
  const save = useSaveAssessThreshold()
  const [draft, setDraft] = useState<string | null>(null)
  if (!data) return null
  const value = draft ?? String(data.value)
  const parsed = Number(value)
  const valid = value.trim() !== '' && Number.isInteger(parsed) && parsed >= 0 && parsed <= 100
  return (
    <div className="rounded-xl border bg-card p-4">
      <h3 className="font-medium">{t('threshold')}</h3>
      <p className="mt-1 text-sm text-muted-foreground">
        {t('thresholdIntro', { triage: data.triage_threshold, default: data.default })}
      </p>
      <form
        className="mt-3 flex flex-wrap items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          if (valid) save.mutate(parsed, { onSuccess: () => setDraft(null) })
        }}
      >
        <label className="grid gap-1 text-sm">
          <span>{t('thresholdLabel')}</span>
          <Input
            type="number"
            min={0}
            max={100}
            className="w-24"
            value={value}
            onChange={(e) => setDraft(e.target.value)}
            aria-invalid={!valid}
          />
        </label>
        <Button type="submit" size="sm" disabled={!valid || save.isPending || parsed === data.value}>
          {t('thresholdSave')}
        </Button>
        {data.source === 'ui' && (
          <Button type="button" size="sm" variant="ghost" disabled={save.isPending} onClick={() => save.mutate(null, { onSuccess: () => setDraft(null) })}>
            {t('thresholdReset', { value: data.default })}
          </Button>
        )}
      </form>
      <p className="mt-2 text-xs text-muted-foreground">{t(`thresholdSource.${data.source}`)}</p>
      {save.isError && <p role="alert" className="mt-2 text-sm text-destructive">{errorMessage(save.error)}</p>}
    </div>
  )
}

/** Página «Agente» (fase 25.4): lo que gasta cada acción, agente y modelo, y el umbral antes de gastar. */
export function CostsSection() {
  const { t } = useTranslation('agent', { keyPrefix: 'costs' })
  const { data, isPending, isError, error, refetch } = useAgentCosts()
  return (
    <div className="grid gap-5">
      <p className="max-w-prose text-sm text-muted-foreground">{t('intro')}</p>
      {isPending ? (
        <Skeleton className="h-48" />
      ) : isError ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : (
        <Tabs defaultValue={String(data.windows[0]?.days ?? 7)}>
          <TabsList aria-label={t('window')}>
            {data.windows.map((w) => (
              <TabsTrigger key={w.days} value={String(w.days)}>
                {t('days', { count: w.days })}
              </TabsTrigger>
            ))}
          </TabsList>
          {data.windows.map((w) => (
            <TabsContent key={w.days} value={String(w.days)}>
              <CostWindowView data={w} />
            </TabsContent>
          ))}
          <p className="text-xs text-muted-foreground">{t('terminal')}</p>
        </Tabs>
      )}
      <Threshold />
    </div>
  )
}
