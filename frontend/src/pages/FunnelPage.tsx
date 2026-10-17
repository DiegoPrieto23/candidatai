import { useState, type ReactNode } from 'react'
import { Trans, useTranslation } from 'react-i18next'
import { SafeTrans } from '@/components/SafeTrans'
import { Link } from 'react-router'
import { ChartBarHorizontalIcon, InfoIcon } from '@phosphor-icons/react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { Calibration, CalibrationGroup, FunnelStats, Schemas } from '@/api/client'
import { useCalibration, useFunnelStats, useSearchStory } from '@/api/queries'
import { AgentButton } from '@/components/AgentButton'
import { CopyButton } from '@/components/CopyButton'
import { EmptyState, ErrorState } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { i18n } from '@/lib/i18n'
import {
  dateFormatter,
  discardReasonLabel,
  formatNumber,
  formatTokens,
  formatUsd,
  HARD_FILTER_LABEL,
  SOURCE_KIND_LABEL,
} from '@/lib/labels'
import { toLocalDateInput } from '@/lib/time'
import { cn } from '@/lib/utils'

type Summary = Pick<Schemas['SourceFunnel'], 'found' | 'approved' | 'applied' | 'replied' | 'interview' | 'reply_rate'>

// --- Formato --------------------------------------------------------------------------------

// Formateadores del idioma activo (cambian al cambiar de idioma).
const intFmt = { format: (n: number) => formatNumber(n) }
const pct = (value: number | null | undefined) =>
  value == null ? '—' : formatNumber(value, { style: 'percent', maximumFractionDigits: 0 })
const days = (value: number | null) =>
  value == null
    ? '—'
    : i18n.t('funnel:days', { count: value, value: formatNumber(value, { maximumFractionDigits: 1 }) })
const weekLabel = (weekStart: string) =>
  dateFormatter({ day: 'numeric', month: 'short', timeZone: 'UTC' }).format(new Date(`${weekStart}T00:00:00Z`))

// --- Periodo --------------------------------------------------------------------------------

const PRESETS = [
  { id: 'all', days: null },
  { id: '30', days: 30 },
  { id: '90', days: 90 },
  { id: '365', days: 365 },
] as const

/** Fecha (Madrid) de hace `n - 1` días: «30 días» incluye hoy y los 29 anteriores. */
function daysAgo(n: number): string {
  return toLocalDateInput(new Date(Date.now() - (n - 1) * 86_400_000))
}

function PeriodPicker({
  preset,
  custom,
  onPreset,
  onCustom,
}: {
  preset: string | null
  custom: string
  onPreset: (id: string) => void
  onCustom: (value: string) => void
}) {
  const { t } = useTranslation('funnel')
  return (
    <div className="flex flex-wrap items-end gap-3">
      <div role="group" aria-label={t('period')} className="inline-flex rounded-lg border bg-card p-0.5">
        {PRESETS.map((p) => (
          <Button
            key={p.id}
            size="sm"
            variant="ghost"
            aria-pressed={preset === p.id}
            className={cn('h-7 px-2.5', preset === p.id && 'bg-secondary font-medium')}
            onClick={() => onPreset(p.id)}
          >
            {t(`presets.${p.id}`)}
          </Button>
        ))}
      </div>
      <div className="grid gap-1">
        <Label htmlFor="funnel-since" className="text-xs text-muted-foreground">
          {t('since')}
        </Label>
        <Input
          id="funnel-since"
          type="date"
          className="h-8 w-40"
          value={custom}
          onChange={(e) => onCustom(e.target.value)}
        />
      </div>
    </div>
  )
}

// --- Piezas ---------------------------------------------------------------------------------

function Panel({ title, hint, children, className }: { title: string; hint?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section aria-label={title} className={cn('rounded-xl border bg-card p-5 sm:p-6', className)}>
      <h2 className="font-medium">{title}</h2>
      {hint && <p className="mt-0.5 text-sm text-muted-foreground">{hint}</p>}
      <div className="mt-4">{children}</div>
    </section>
  )
}

function Stat({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <div className="rounded-xl border bg-card px-4 py-3.5">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="tabular mt-1 text-2xl font-semibold tracking-tight">{value}</p>
      {detail && <p className="mt-0.5 text-xs text-muted-foreground">{detail}</p>}
    </div>
  )
}

const AXIS_TICK = { fill: 'var(--muted-foreground)', fontSize: 12 }
const TOOLTIP_PROPS = {
  cursor: { fill: 'var(--muted)', opacity: 0.6 },
  contentStyle: {
    background: 'var(--popover)',
    border: '1px solid var(--border)',
    borderRadius: 8,
    color: 'var(--popover-foreground)',
    fontSize: 12,
  },
  labelStyle: { color: 'var(--popover-foreground)', fontWeight: 500 },
  itemStyle: { color: 'var(--popover-foreground)' },
} as const

/** Tabla accesible con los mismos datos que la gráfica (lectores de pantalla). */
function SrTable({ caption, head, rows }: { caption: string; head: string[]; rows: (string | number)[][] }) {
  return (
    <table className="sr-only">
      <caption>{caption}</caption>
      <thead>
        <tr>
          {head.map((h) => (
            <th key={h} scope="col">
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={String(row[0])}>
            {row.map((cell, i) => (i === 0 ? <th key={i} scope="row">{cell}</th> : <td key={i}>{cell}</td>))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}

/** Barras horizontales de una sola serie con la cifra al final de cada barra. */
function HorizontalBars({
  data,
  caption,
  valueHead,
}: {
  data: { name: string; value: number; label: string }[]
  caption: string
  valueHead: string
}) {
  const height = Math.max(data.length * 36 + 8, 80)
  return (
    <>
      <div aria-hidden="true">
        <ResponsiveContainer width="100%" height={height} initialDimension={{ width: 520, height }}>
          <BarChart data={data} layout="vertical" margin={{ top: 0, right: 96, bottom: 0, left: 0 }} barCategoryGap={8}>
            <XAxis type="number" hide domain={[0, 'dataMax']} />
            <YAxis
              type="category"
              dataKey="name"
              width={150}
              tick={AXIS_TICK}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip {...TOOLTIP_PROPS} formatter={(v) => [intFmt.format(Number(v)), valueHead]} />
            <Bar dataKey="value" fill="var(--chart-1)" radius={[0, 4, 4, 0]} maxBarSize={24} isAnimationActive={false}>
              <LabelList dataKey="label" position="right" fill="var(--foreground)" fontSize={12} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <SrTable caption={caption} head={['', valueHead]} rows={data.map((d) => [d.name, d.label])} />
    </>
  )
}

// --- Secciones ------------------------------------------------------------------------------

function FunnelChart({ stats }: { stats: FunnelStats }) {
  const { t } = useTranslation('funnel')
  const data = stats.steps.map((s, i) => ({
    name: t(`steps.${s.step}`),
    value: s.count,
    label: i === 0 ? intFmt.format(s.count) : `${intFmt.format(s.count)} · ${pct(s.rate_from_previous)}`,
  }))
  return (
    <Panel
      title={t('funnel.title')}
      hint={
        <>
          {t('funnel.hint')}
          {stats.duplicates_excluded > 0 && t('funnel.duplicates', { count: stats.duplicates_excluded })}
        </>
      }
    >
      <HorizontalBars data={data} caption={t('funnel.caption')} valueHead={t('funnel.valueHead')} />
    </Panel>
  )
}

function WeekChart({ weeks }: { weeks: Schemas['WeekFunnel'][] }) {
  const { t } = useTranslation('funnel')
  const data = weeks.map((w) => ({ ...w, name: weekLabel(w.week_start) }))
  return (
    <Panel title={t('week.title')} hint={t('week.hint')}>
      <div aria-hidden="true">
        <ResponsiveContainer width="100%" height={240} initialDimension={{ width: 640, height: 240 }}>
          <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -16 }} barGap={2}>
            <CartesianGrid vertical={false} stroke="var(--border)" />
            <XAxis dataKey="name" tick={AXIS_TICK} tickLine={false} axisLine={false} minTickGap={16} />
            <YAxis allowDecimals={false} tick={AXIS_TICK} tickLine={false} axisLine={false} />
            <Tooltip
              {...TOOLTIP_PROPS}
              labelFormatter={(_, payload) => {
                const week = payload?.[0]?.payload as (typeof data)[number] | undefined
                return week ? t('week.label', { date: week.name, week: week.week }) : ''
              }}
            />
            <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12, color: 'var(--muted-foreground)' }} />
            <Bar dataKey="found" name={t('cols.found')} fill="var(--chart-1)" radius={[4, 4, 0, 0]} maxBarSize={20} isAnimationActive={false} />
            <Bar dataKey="applied" name={t('cols.applied')} fill="var(--chart-2)" radius={[4, 4, 0, 0]} maxBarSize={20} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <SrTable
        caption={t('week.caption')}
        head={[
          t('week.head'),
          t('cols.found'),
          t('cols.approved'),
          t('cols.applied'),
          t('cols.replied'),
          t('cols.interview'),
        ]}
        rows={weeks.map((w) => [`${weekLabel(w.week_start)} (${w.week})`, w.found, w.approved, w.applied, w.replied, w.interview])}
      />
    </Panel>
  )
}

function RateBar({ value }: { value: number | null }) {
  return (
    <span className="inline-flex items-center gap-2">
      <span className="tabular w-9 text-right">{pct(value)}</span>
      <span className="hidden h-1.5 w-16 overflow-hidden rounded-full bg-muted sm:block" aria-hidden="true">
        <span className="block h-full rounded-full bg-chart-1" style={{ width: `${(value ?? 0) * 100}%` }} />
      </span>
    </span>
  )
}

function BreakdownTable({
  caption,
  firstHead,
  rows,
}: {
  caption: string
  firstHead: string
  rows: { key: string; name: ReactNode; summary: Summary; muted?: boolean; spend?: Spend }[]
}) {
  const { t } = useTranslation('funnel', { keyPrefix: 'cols' })
  const withCost = rows.some((r) => r.spend !== undefined)
  return (
    <div className="-mx-1 overflow-x-auto">
      <table className="w-full min-w-[34rem] text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="border-b text-left text-xs text-muted-foreground">
            <th scope="col" className="px-1 pb-2 font-medium">
              {firstHead}
            </th>
            {[t('found'), t('approved'), t('applied'), t('replied'), t('interview')].map((h) => (
              <th key={h} scope="col" className="px-1 pb-2 text-right font-medium">
                {h}
              </th>
            ))}
            <th scope="col" className="px-1 pb-2 text-right font-medium">
              {t('reply')}
            </th>
            {withCost && (
              <th scope="col" className="px-1 pb-2 text-right font-medium">
                {t('costPerApplied')}
              </th>
            )}
          </tr>
        </thead>
        <tbody>
          {rows.map(({ key, name, summary: s, muted, spend }) => (
            <tr key={key} className="border-b last:border-0">
              <th scope="row" className={cn('max-w-56 px-1 py-2 text-left font-normal', muted && 'text-muted-foreground')}>
                {name}
              </th>
              {[s.found, s.approved, s.applied, s.replied, s.interview].map((v, i) => (
                <td key={i} className="tabular px-1 py-2 text-right">
                  {intFmt.format(v)}
                </td>
              ))}
              <td className="px-1 py-2 text-right">
                <RateBar value={s.reply_rate} />
              </td>
              {withCost && <td className="tabular px-1 py-2 text-right">{perApplied(spend, s.applied)}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** Fase 25.4: lo gastado en segundo plano por las ofertas de una fila. */
type Spend = { tokens: number; cost_usd: number | null }

/** Por candidatura enviada: dólares si algún agente los dio; si no, tokens. */
function perApplied(spend: Spend | undefined, applied: number): string {
  if (!spend || applied === 0 || (spend.tokens === 0 && spend.cost_usd == null)) return '—'
  if (spend.cost_usd != null) return formatUsd(spend.cost_usd / applied)
  return i18n.t('funnel:cost.tokens', { tokens: formatTokens(spend.tokens / applied) })
}

function CostPanel({ cost }: { cost: Schemas['FunnelCost'] }) {
  const { t } = useTranslation('funnel', { keyPrefix: 'cost' })
  const value = (usd: number | null, tokens: number | null) =>
    usd != null ? formatUsd(usd) : tokens != null ? t('tokens', { tokens: formatTokens(tokens) }) : '—'
  return (
    <Panel title={t('title')} hint={t('hint')}>
      {cost.runs === 0 ? (
        <p className="text-sm text-muted-foreground">{t('none')}</p>
      ) : (
        <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm sm:grid-cols-3">
          <div>
            <dt className="text-muted-foreground">{t('total')}</dt>
            <dd className="tabular text-lg font-semibold">{value(cost.cost_usd, cost.tokens)}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">{t('perApplied')}</dt>
            <dd className="tabular text-lg font-semibold">{value(cost.cost_per_applied_usd, cost.tokens_per_applied)}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">{t('perInterview')}</dt>
            <dd className="tabular text-lg font-semibold">{value(cost.cost_per_interview_usd, cost.tokens_per_interview)}</dd>
          </div>
        </dl>
      )}
    </Panel>
  )
}

function ResponseTimePanel({ rt }: { rt: Schemas['ResponseTime'] }) {
  const { t } = useTranslation('funnel', { keyPrefix: 'response' })
  return (
    <Panel title={t('title')} hint={t('hint')}>
      {rt.applied === 0 ? (
        <p className="text-sm text-muted-foreground">{t('none')}</p>
      ) : (
        <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
          <div>
            <dt className="text-muted-foreground">{t('median')}</dt>
            <dd className="tabular text-lg font-semibold">{days(rt.median_days)}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">{t('mean')}</dt>
            <dd className="tabular text-lg font-semibold">{days(rt.mean_days)}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">{t('replied')}</dt>
            <dd className="tabular">
              {t('repliedOf', { replied: rt.replied, applied: rt.applied })}
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">{t('noReply')}</dt>
            <dd className="tabular">
              {t('waiting', { waiting: rt.awaiting_reply, closed: rt.closed_without_reply })}
            </dd>
          </div>
        </dl>
      )}
    </Panel>
  )
}

function ReasonsPanel({ stats }: { stats: FunnelStats }) {
  const { t } = useTranslation('funnel', { keyPrefix: 'reasons' })
  const discards = stats.discard_reasons.map((r) => ({
    name: r.reason === 'unspecified' ? t('unspecified') : discardReasonLabel(r.reason),
    value: r.count,
    label: intFmt.format(r.count),
  }))
  const filters = stats.hard_filter_failures.map((f) => ({
    name: HARD_FILTER_LABEL[f.filter] ?? f.filter,
    value: f.count,
    label: intFmt.format(f.count),
  }))
  return (
    <Panel title={t('title')} hint={t('hint')}>
      <div className="grid gap-6 md:grid-cols-2">
        <div>
          <h3 className="mb-2 text-sm font-medium">{t('byYou')}</h3>
          {discards.length ? (
            <HorizontalBars data={discards} caption={t('byYouCaption')} valueHead={t('jobs')} />
          ) : (
            <p className="text-sm text-muted-foreground">{t('noDiscards')}</p>
          )}
        </div>
        <div>
          <h3 className="mb-2 text-sm font-medium">{t('byFilters')}</h3>
          {filters.length ? (
            <HorizontalBars data={filters} caption={t('byFiltersCaption')} valueHead={t('jobs')} />
          ) : (
            <p className="text-sm text-muted-foreground">{t('noFilters')}</p>
          )}
        </div>
      </div>
    </Panel>
  )
}

function Dashboard({ stats, since }: { stats: FunnelStats; since: string | null }) {
  const { t } = useTranslation('funnel')
  const step = (name: string) => stats.steps.find((s) => s.step === name)
  const found = step('found')?.count ?? 0
  const applied = step('applied')
  const replied = step('replied')
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label={t('stats.found')} value={intFmt.format(found)} />
        <Stat
          label={t('stats.applied')}
          value={intFmt.format(applied?.count ?? 0)}
          detail={t('stats.appliedDetail', { pct: pct(applied?.rate_from_start) })}
        />
        <Stat
          label={t('stats.replyRate')}
          value={pct(replied?.rate_from_previous)}
          detail={t('stats.replyDetail', { count: replied?.count ?? 0 })}
        />
        <Stat
          label={t('stats.firstReply')}
          value={days(stats.response_time.median_days)}
          detail={t('stats.waitingDetail', { count: stats.response_time.awaiting_reply })}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <FunnelChart stats={stats} />
        <ResponseTimePanel rt={stats.response_time} />
      </div>

      {stats.by_week.length > 0 && <WeekChart weeks={stats.by_week} />}

      <Panel title={t('bySource.title')} hint={t('bySource.hint')}>
        <BreakdownTable
          caption={t('bySource.caption')}
          firstHead={t('bySource.head')}
          rows={stats.by_source.map((s) => ({
            key: String(s.source_id),
            name: (
              <>
                {s.name}
                <span className="ml-1.5 text-xs text-muted-foreground">{SOURCE_KIND_LABEL[s.kind] ?? s.kind}</span>
              </>
            ),
            summary: s,
            spend: { tokens: s.tokens, cost_usd: s.cost_usd },
          }))}
        />
      </Panel>

      <CostPanel cost={stats.agent_cost} />

      <Panel title={t('byTitle.title')} hint={t('byTitle.hint')}>
        <BreakdownTable
          caption={t('byTitle.caption')}
          firstHead={t('byTitle.head')}
          rows={stats.by_title.map((row) => ({
            key: `${row.group}-${row.title}`,
            name: row.group === 'title' ? row.title : t(`byTitle.${row.group}`),
            summary: row,
            muted: row.group !== 'title',
          }))}
        />
      </Panel>

      {stats.by_referral.some((r) => r.group !== 'none' && r.found > 0) && (
        <Panel
          title={t('byReferral.title')}
          hint={t('byReferral.hint')}
        >
          <BreakdownTable
            caption={t('byReferral.caption')}
            firstHead={t('byReferral.head')}
            rows={stats.by_referral.map((r) => ({
              key: r.group,
              name: t(`byReferral.groups.${r.group}`),
              summary: r,
              muted: r.group === 'none',
            }))}
          />
        </Panel>
      )}

      <CalibrationPanel since={since} />

      <ReasonsPanel stats={stats} />

      <StoryPanel />
    </div>
  )
}

// --- ¿Acierta el score? (fase 20) -------------------------------------------------------------

/** Por debajo de tantas enviadas, la calibración es poco más que anecdótica (el skill dice lo mismo). */
const CALIBRATION_MIN_SENT = 20

const CALIBRATION_TABS = [
  { id: 'score', pick: (c: Calibration) => c.by_score },
  { id: 'verdict', pick: (c: Calibration) => c.by_verdict },
  { id: 'source', pick: (c: Calibration) => c.by_source },
  { id: 'platform', pick: (c: Calibration) => c.by_platform },
  { id: 'template', pick: (c: Calibration) => c.by_template },
  { id: 'letter', pick: (c: Calibration) => c.by_cover_letter },
  { id: 'referral', pick: (c: Calibration) => c.by_referral },
  { id: 'days', pick: (c: Calibration) => c.by_days_to_apply },
  { id: 'signal', pick: (c: Calibration) => c.by_signal },
] as const

type CalibrationTab = (typeof CALIBRATION_TABS)[number]['id']

/** La etiqueta de un grupo: la traducida si su clave es estable («none», «with»…); si no, la del servidor. */
function groupLabel(tab: CalibrationTab, group: CalibrationGroup): string {
  const key = `funnel:calibration.groups.${tab}.${group.key}`
  return i18n.exists(key) ? String(i18n.t(key as never)) : group.label
}

/** Tasa con su intervalo: la banda clara es el intervalo; la marca, la tasa. */
function IntervalBar({ interval }: { interval: CalibrationGroup['reply_rate'] }) {
  const { rate, low, high } = interval
  return (
    <span className="inline-flex items-center justify-end gap-2">
      <span className="tabular whitespace-nowrap text-right">
        {pct(rate)}
        {rate != null && (
          <>
            {' '}
            <span className="text-xs text-muted-foreground">
              ({pct(low)}–{pct(high)})
            </span>
          </>
        )}
      </span>
      <span className="relative hidden h-1.5 w-20 rounded-full bg-muted sm:block" aria-hidden="true">
        {rate != null && low != null && high != null && (
          <>
            <span
              className="absolute inset-y-0 rounded-full bg-chart-1/35"
              style={{ left: `${low * 100}%`, width: `${(high - low) * 100}%` }}
            />
            <span
              className="absolute -top-0.5 h-2.5 w-0.5 -translate-x-1/2 rounded-full bg-chart-1"
              style={{ left: `${rate * 100}%` }}
            />
          </>
        )}
      </span>
    </span>
  )
}

function CalibrationTable({ caption, tab, groups }: { caption: string; tab: CalibrationTab; groups: CalibrationGroup[] }) {
  const { t } = useTranslation('funnel', { keyPrefix: 'calibration' })
  return (
    <div className="-mx-1 overflow-x-auto">
      <table className="w-full min-w-[36rem] text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="border-b text-left text-xs text-muted-foreground">
            <th scope="col" className="px-1 pb-2 font-medium">
              {t('cols.group')}
            </th>
            {[t('cols.applied'), t('cols.reply'), t('cols.interview'), t('cols.waiting')].map((h) => (
              <th key={h} scope="col" className="px-1 pb-2 text-right font-medium">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {groups.map((g) => (
            <tr key={g.key} className={cn('border-b last:border-0', g.applied === 0 && 'text-muted-foreground')}>
              <th scope="row" className="max-w-56 px-1 py-2 text-left font-normal">
                {groupLabel(tab, g)}
                {g.applied > 0 && g.low_data && (
                  <span className="ml-2 rounded-full border px-1.5 py-px text-[11px] whitespace-nowrap text-muted-foreground">
                    {t('lowData')}
                  </span>
                )}
              </th>
              <td className="tabular px-1 py-2 text-right">{intFmt.format(g.applied)}</td>
              <td className="px-1 py-2 text-right">
                <IntervalBar interval={g.reply_rate} />
              </td>
              <td className="px-1 py-2 text-right">
                <IntervalBar interval={g.interview_rate} />
              </td>
              <td className="tabular px-1 py-2 text-right">{g.applied ? intFmt.format(g.awaiting) : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function CalibrationPanel({ since }: { since: string | null }) {
  const { t } = useTranslation('funnel', { keyPrefix: 'calibration' })
  const calibration = useCalibration(since)
  const [tab, setTab] = useState('score')
  const data = calibration.data
  return (
    <Panel
      title={t('title')}
      hint={t('hint')}
    >
      <div className="mb-4 flex flex-col gap-3 rounded-lg border border-dashed bg-muted/40 p-3 text-sm sm:flex-row sm:items-start sm:justify-between">
        <p className="flex gap-2 text-muted-foreground">
          <InfoIcon className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <span>
            <Trans t={t} i18nKey="note" components={{ code: <code className="text-xs" /> }} />
          </span>
        </p>
        <AgentButton action="review-search" className="shrink-0">
          {t('review')}
        </AgentButton>
      </div>
      {calibration.isPending ? (
        <Skeleton className="h-48 rounded-lg" />
      ) : calibration.isError ? (
        <ErrorState error={calibration.error} onRetry={() => calibration.refetch()} />
      ) : !data || data.total.applied === 0 ? (
        <p className="text-sm text-muted-foreground">
          {t('none', { min: CALIBRATION_MIN_SENT })}
        </p>
      ) : (
        <>
          <p className="mb-3 text-sm">
            <SafeTrans
              t={t}
              i18nKey="summary"
              values={{
                applied: intFmt.format(data.total.applied),
                reply: pct(data.total.reply_rate.rate),
                interview: pct(data.total.interview_rate.rate),
              }}
              components={{ strong: <span className="tabular font-medium" /> }}
            />
            {data.total.applied < CALIBRATION_MIN_SENT && (
              <span className="text-muted-foreground">{t('caution', { min: CALIBRATION_MIN_SENT })}</span>
            )}
          </p>
          <Tabs value={tab} onValueChange={setTab} className="gap-3">
            <TabsList className="h-auto flex-wrap justify-start">
              {CALIBRATION_TABS.map((tab) => (
                <TabsTrigger key={tab.id} value={tab.id} className="px-2.5">
                  {t(`tabs.${tab.id}.label`)}
                </TabsTrigger>
              ))}
            </TabsList>
            {CALIBRATION_TABS.map((tab) => (
              <TabsContent key={tab.id} value={tab.id}>
                <p className="mb-2 text-xs text-muted-foreground">
                  {t(`tabs.${tab.id}.hint`)} {t('lowDataHint', { count: data.min_cases })}
                </p>
                <CalibrationTable
                  caption={t('caption', { tab: t(`tabs.${tab.id}.label`).toLowerCase() })}
                  tab={tab.id}
                  groups={tab.pick(data)}
                />
              </TabsContent>
            ))}
          </Tabs>
        </>
      )}
    </Panel>
  )
}

// --- Tu búsqueda en números (fase 25.6) -------------------------------------------------------

const storyDay = (iso: string) =>
  dateFormatter({ day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }).format(new Date(`${iso}T00:00:00Z`))

/** Toda la búsqueda, sin periodo, en números agregados y con la línea para el README en los dos idiomas. */
function StoryPanel() {
  const { t, i18n: { language } } = useTranslation('funnel', { keyPrefix: 'story' })
  const story = useSearchStory()
  const data = story.data
  if (story.isPending) return <Skeleton className="h-40 rounded-xl" />
  if (story.isError) return <ErrorState error={story.error} onRetry={() => story.refetch()} />
  if (!data || data.found === 0) return null
  const line = language.startsWith('en') ? data.markdown.en : data.markdown.es
  const counts = [
    ['evaluated', data.evaluated],
    ['applied', data.applied],
    ['replied', data.replied],
    ['interviews', data.interviews],
    ['offers', data.offers],
  ] as const
  return (
    <Panel
      title={t('title')}
      hint={
        data.started_on && data.last_activity_on
          ? `${t('period', { start: storyDay(data.started_on), end: storyDay(data.last_activity_on) })}. ${t('hint')}`
          : t('hint')
      }
    >
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        {counts.map(([key, value]) => (
          <div key={key} className="rounded-lg border px-3 py-2.5">
            <dt className="text-xs text-muted-foreground">{t(key)}</dt>
            <dd className="tabular mt-0.5 text-xl font-semibold tracking-tight">{intFmt.format(value)}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-4 text-xs text-muted-foreground">{t('lineLabel')}</p>
      <pre className="mt-1 overflow-x-auto whitespace-pre-wrap rounded-lg border bg-muted/40 p-3 font-mono text-xs leading-relaxed">
        {line}
      </pre>
      <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-muted-foreground">
          <Trans t={t} i18nKey="note" components={{ code: <code className="text-xs" /> }} />
        </p>
        <div className="flex shrink-0 flex-wrap gap-2">
          <CopyButton text={data.markdown.es} label={t('copyEs')} />
          <CopyButton text={data.markdown.en} label={t('copyEn')} />
        </div>
      </div>
    </Panel>
  )
}

function DashboardSkeleton() {
  const { t } = useTranslation('funnel')
  return (
    <div className="space-y-6" aria-busy="true" aria-label={t('loading')}>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-20 rounded-xl" />
        ))}
      </div>
      <Skeleton className="h-80 rounded-xl" />
    </div>
  )
}

export function FunnelPage() {
  const { t } = useTranslation('funnel')
  const [preset, setPreset] = useState<string | null>('all')
  const [custom, setCustom] = useState('')
  const presetDays = PRESETS.find((p) => p.id === preset)?.days
  const since = preset ? (presetDays ? daysAgo(presetDays) : null) : custom || null
  const stats = useFunnelStats(since)
  const empty = stats.data && stats.data.steps[0].count === 0

  return (
    <div className="animate-in fade-in duration-300">
      <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{t('title')}</h1>
          <p className="mt-1.5 max-w-[65ch] text-sm leading-relaxed text-muted-foreground">
            {t('intro')}
          </p>
        </div>
        <PeriodPicker
          preset={preset}
          custom={custom}
          onPreset={(id) => {
            setPreset(id)
            setCustom('')
          }}
          onCustom={(value) => {
            setCustom(value)
            setPreset(value ? null : 'all')
          }}
        />
      </div>

      {stats.isPending ? (
        <DashboardSkeleton />
      ) : stats.isError ? (
        <ErrorState error={stats.error} onRetry={() => stats.refetch()} />
      ) : empty ? (
        <>
          <EmptyState
            icon={<ChartBarHorizontalIcon className="size-7" weight="duotone" />}
            title={since ? t('empty.periodTitle') : t('empty.title')}
          >
            {since ? (
              t('empty.period')
            ) : (
              <Trans
                t={t}
                i18nKey="empty.body"
                components={{ to: <Link to="/nueva" className="underline underline-offset-4" /> }}
              />
            )}
          </EmptyState>
          {/* La calibración va por fecha de envío: puede haber envíos de ofertas vistas antes. */}
          {since && (
            <div className="mt-6">
              <CalibrationPanel since={since} />
            </div>
          )}
        </>
      ) : (
        <Dashboard stats={stats.data} since={since} />
      )}
    </div>
  )
}
