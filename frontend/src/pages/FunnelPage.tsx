import { useState, type ReactNode } from 'react'
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
import { useCalibration, useFunnelStats } from '@/api/queries'
import { AgentButton } from '@/components/AgentButton'
import { EmptyState, ErrorState } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { discardReasonLabel, HARD_FILTER_LABEL, SOURCE_KIND_LABEL } from '@/lib/labels'
import { toLocalDateInput } from '@/lib/time'
import { cn } from '@/lib/utils'

type Summary = Pick<Schemas['SourceFunnel'], 'found' | 'approved' | 'applied' | 'replied' | 'interview' | 'reply_rate'>

// --- Formato --------------------------------------------------------------------------------

const intFmt = new Intl.NumberFormat('es-ES')
const pctFmt = new Intl.NumberFormat('es-ES', { style: 'percent', maximumFractionDigits: 0 })
const daysFmt = new Intl.NumberFormat('es-ES', { maximumFractionDigits: 1 })
const weekFmt = new Intl.DateTimeFormat('es-ES', { day: 'numeric', month: 'short', timeZone: 'UTC' })

const pct = (value: number | null | undefined) => (value == null ? '—' : pctFmt.format(value))
const days = (value: number | null) => (value == null ? '—' : `${daysFmt.format(value)} días`)
const weekLabel = (weekStart: string) => weekFmt.format(new Date(`${weekStart}T00:00:00Z`))

// --- Periodo --------------------------------------------------------------------------------

const PRESETS: readonly { id: string; label: string; days: number | null }[] = [
  { id: 'all', label: 'Todo', days: null },
  { id: '30', label: '30 días', days: 30 },
  { id: '90', label: '90 días', days: 90 },
  { id: '365', label: '12 meses', days: 365 },
]

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
  return (
    <div className="flex flex-wrap items-end gap-3">
      <div role="group" aria-label="Periodo" className="inline-flex rounded-lg border bg-card p-0.5">
        {PRESETS.map((p) => (
          <Button
            key={p.id}
            size="sm"
            variant="ghost"
            aria-pressed={preset === p.id}
            className={cn('h-7 px-2.5', preset === p.id && 'bg-secondary font-medium')}
            onClick={() => onPreset(p.id)}
          >
            {p.label}
          </Button>
        ))}
      </div>
      <div className="grid gap-1">
        <Label htmlFor="funnel-since" className="text-xs text-muted-foreground">
          Desde
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
  const data = stats.steps.map((s, i) => ({
    name: s.label,
    value: s.count,
    label: i === 0 ? intFmt.format(s.count) : `${intFmt.format(s.count)} · ${pct(s.rate_from_previous)}`,
  }))
  return (
    <Panel
      title="Embudo"
      hint={
        <>
          Cada oferta cuenta una vez en cada paso al que llegó (y en los anteriores). El porcentaje es la
          conversión desde el paso anterior.
          {stats.duplicates_excluded > 0 && ` Sin contar ${stats.duplicates_excluded} duplicadas.`}
        </>
      }
    >
      <HorizontalBars data={data} caption="Ofertas por paso del embudo" valueHead="Ofertas (conversión)" />
    </Panel>
  )
}

function WeekChart({ weeks }: { weeks: Schemas['WeekFunnel'][] }) {
  const data = weeks.map((w) => ({ ...w, name: weekLabel(w.week_start) }))
  return (
    <Panel title="Por semana" hint="Semana en que se vio la oferta (lunes a domingo, hora de Madrid).">
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
                return week ? `Semana del ${week.name} (${week.week})` : ''
              }}
            />
            <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12, color: 'var(--muted-foreground)' }} />
            <Bar dataKey="found" name="Encontradas" fill="var(--chart-1)" radius={[4, 4, 0, 0]} maxBarSize={20} isAnimationActive={false} />
            <Bar dataKey="applied" name="Enviadas" fill="var(--chart-2)" radius={[4, 4, 0, 0]} maxBarSize={20} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <SrTable
        caption="Ofertas por semana"
        head={['Semana', 'Encontradas', 'Aprobadas', 'Enviadas', 'Con respuesta', 'Entrevista']}
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
  rows: { key: string; name: ReactNode; summary: Summary; muted?: boolean }[]
}) {
  return (
    <div className="-mx-1 overflow-x-auto">
      <table className="w-full min-w-[34rem] text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="border-b text-left text-xs text-muted-foreground">
            <th scope="col" className="px-1 pb-2 font-medium">
              {firstHead}
            </th>
            {['Encontradas', 'Aprobadas', 'Enviadas', 'Con respuesta', 'Entrevista'].map((h) => (
              <th key={h} scope="col" className="px-1 pb-2 text-right font-medium">
                {h}
              </th>
            ))}
            <th scope="col" className="px-1 pb-2 text-right font-medium">
              Respuesta
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ key, name, summary: s, muted }) => (
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
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ResponseTimePanel({ rt }: { rt: Schemas['ResponseTime'] }) {
  return (
    <Panel title="Primera respuesta" hint="Desde el envío hasta la primera respuesta, entrevista, prueba, oferta o rechazo.">
      {rt.applied === 0 ? (
        <p className="text-sm text-muted-foreground">Aún no has enviado ninguna candidatura en este periodo.</p>
      ) : (
        <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
          <div>
            <dt className="text-muted-foreground">Mediana</dt>
            <dd className="tabular text-lg font-semibold">{days(rt.median_days)}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Media</dt>
            <dd className="tabular text-lg font-semibold">{days(rt.mean_days)}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Con respuesta</dt>
            <dd className="tabular">
              {rt.replied} de {rt.applied}
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Sin respuesta</dt>
            <dd className="tabular">
              {rt.awaiting_reply} esperando · {rt.closed_without_reply} cerradas
            </dd>
          </div>
        </dl>
      )}
    </Panel>
  )
}

function ReasonsPanel({ stats }: { stats: FunnelStats }) {
  const discards = stats.discard_reasons.map((r) => ({
    name: r.reason === 'unspecified' ? 'Sin motivo' : discardReasonLabel(r.reason),
    value: r.count,
    label: intFmt.format(r.count),
  }))
  const filters = stats.hard_filter_failures.map((f) => ({
    name: HARD_FILTER_LABEL[f.filter] ?? f.filter,
    value: f.count,
    label: intFmt.format(f.count),
  }))
  return (
    <Panel title="Motivos de descarte" hint="Ofertas por motivo; una oferta puede fallar varios filtros a la vez.">
      <div className="grid gap-6 md:grid-cols-2">
        <div>
          <h3 className="mb-2 text-sm font-medium">Descartadas por ti</h3>
          {discards.length ? (
            <HorizontalBars data={discards} caption="Descartes por motivo" valueHead="Ofertas" />
          ) : (
            <p className="text-sm text-muted-foreground">Ningún descarte en este periodo.</p>
          )}
        </div>
        <div>
          <h3 className="mb-2 text-sm font-medium">Cerradas por los filtros duros</h3>
          {filters.length ? (
            <HorizontalBars data={filters} caption="Cierres por filtro duro" valueHead="Ofertas" />
          ) : (
            <p className="text-sm text-muted-foreground">Ningún cierre por filtros en este periodo.</p>
          )}
        </div>
      </div>
    </Panel>
  )
}

function Dashboard({ stats, since }: { stats: FunnelStats; since: string | null }) {
  const step = (name: string) => stats.steps.find((s) => s.step === name)
  const found = step('found')?.count ?? 0
  const applied = step('applied')
  const replied = step('replied')
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Encontradas" value={intFmt.format(found)} />
        <Stat
          label="Enviadas"
          value={intFmt.format(applied?.count ?? 0)}
          detail={`${pct(applied?.rate_from_start)} de las encontradas`}
        />
        <Stat
          label="Tasa de respuesta"
          value={pct(replied?.rate_from_previous)}
          detail={`${replied?.count ?? 0} con respuesta`}
        />
        <Stat
          label="Primera respuesta (mediana)"
          value={days(stats.response_time.median_days)}
          detail={`${stats.response_time.awaiting_reply} esperando respuesta`}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <FunnelChart stats={stats} />
        <ResponseTimePanel rt={stats.response_time} />
      </div>

      {stats.by_week.length > 0 && <WeekChart weeks={stats.by_week} />}

      <Panel title="Por fuente" hint="Por dónde llegan las ofertas que avanzan.">
        <BreakdownTable
          caption="Embudo por fuente"
          firstHead="Fuente"
          rows={stats.by_source.map((s) => ({
            key: String(s.source_id),
            name: (
              <>
                {s.name}
                <span className="ml-1.5 text-xs text-muted-foreground">{SOURCE_KIND_LABEL[s.kind] ?? s.kind}</span>
              </>
            ),
            summary: s,
          }))}
        />
      </Panel>

      <Panel title="Por tipo de puesto" hint="Título normalizado de la extracción; los menos frecuentes van en «Otros».">
        <BreakdownTable
          caption="Embudo por tipo de puesto"
          firstHead="Puesto"
          rows={stats.by_title.map((t) => ({
            key: `${t.group}-${t.title}`,
            name: t.title,
            summary: t,
            muted: t.group !== 'title',
          }))}
        />
      </Panel>

      {stats.by_referral.some((r) => r.group !== 'none' && r.found > 0) && (
        <Panel
          title="Por referencia"
          hint="Si algún contacto del proceso te dio una referencia, o solo se la pediste. Lo marcas en la ficha."
        >
          <BreakdownTable
            caption="Embudo por referencia"
            firstHead="Referencia"
            rows={stats.by_referral.map((r) => ({
              key: r.group,
              name: REFERRAL_GROUP_LABEL[r.group],
              summary: r,
              muted: r.group === 'none',
            }))}
          />
        </Panel>
      )}

      <CalibrationPanel since={since} />

      <ReasonsPanel stats={stats} />
    </div>
  )
}

// --- ¿Acierta el score? (fase 20) -------------------------------------------------------------

/** Por debajo de tantas enviadas, la calibración es poco más que anecdótica (el skill dice lo mismo). */
const CALIBRATION_MIN_SENT = 20

const CALIBRATION_TABS: readonly {
  id: string
  label: string
  hint: string
  pick: (c: Calibration) => CalibrationGroup[]
}[] = [
  { id: 'score', label: 'Score', hint: 'Score de la oferta al enviarla.', pick: (c) => c.by_score },
  { id: 'verdict', label: 'Veredicto', hint: 'Valoración del agente antes de enviarla.', pick: (c) => c.by_verdict },
  { id: 'source', label: 'Fuente', hint: 'Por dónde llegó la oferta.', pick: (c) => c.by_source },
  { id: 'platform', label: 'Portal', hint: 'Portal de empleo de la oferta, si se sabe.', pick: (c) => c.by_platform },
  { id: 'template', label: 'Plantilla', hint: 'Plantilla del CV enviado.', pick: (c) => c.by_template },
  { id: 'letter', label: 'Carta', hint: 'Si había carta de presentación al enviar.', pick: (c) => c.by_cover_letter },
  {
    id: 'referral',
    label: 'Referencia',
    hint: 'Si algún contacto del proceso te dio una referencia o se la pediste.',
    pick: (c) => c.by_referral,
  },
  { id: 'days', label: 'Rapidez', hint: 'Días entre que entró la oferta y la enviaste.', pick: (c) => c.by_days_to_apply },
]

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

function CalibrationTable({ caption, groups }: { caption: string; groups: CalibrationGroup[] }) {
  return (
    <div className="-mx-1 overflow-x-auto">
      <table className="w-full min-w-[36rem] text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="border-b text-left text-xs text-muted-foreground">
            <th scope="col" className="px-1 pb-2 font-medium">
              Grupo
            </th>
            {['Enviadas', 'Respuesta', 'Entrevista', 'Esperando'].map((h) => (
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
                {g.label}
                {g.applied > 0 && g.low_data && (
                  <span className="ml-2 rounded-full border px-1.5 py-px text-[11px] whitespace-nowrap text-muted-foreground">
                    pocos datos
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
  const calibration = useCalibration(since)
  const [tab, setTab] = useState('score')
  const data = calibration.data
  return (
    <Panel
      title="¿Acierta el score?"
      hint="Respuesta y entrevista de tus candidaturas enviadas (en el periodo elegido, por fecha de envío) según lo que sabías al enviarlas."
    >
      <div className="mb-4 flex flex-col gap-3 rounded-lg border border-dashed bg-muted/40 p-3 text-sm sm:flex-row sm:items-start sm:justify-between">
        <p className="flex gap-2 text-muted-foreground">
          <InfoIcon className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <span>
            Orientativo. Entre paréntesis, el intervalo al 95 %: si los de dos grupos se solapan, no hay una diferencia
            clara. Los pesos y filtros no cambian solos: tu agente propone y tú decides, comprobándolo con{' '}
            <code className="text-xs">cai eval matching</code>.
          </span>
        </p>
        <AgentButton action="revisar-busqueda" className="shrink-0">
          Revisar mi búsqueda
        </AgentButton>
      </div>
      {calibration.isPending ? (
        <Skeleton className="h-48 rounded-lg" />
      ) : calibration.isError ? (
        <ErrorState error={calibration.error} onRetry={() => calibration.refetch()} />
      ) : !data || data.total.applied === 0 ? (
        <p className="text-sm text-muted-foreground">
          Aún no has enviado ninguna candidatura en este periodo. Tiene sentido a partir de unas {CALIBRATION_MIN_SENT}-30 enviadas.
        </p>
      ) : (
        <>
          <p className="mb-3 text-sm">
            <span className="tabular font-medium">{intFmt.format(data.total.applied)}</span> enviadas · respuesta{' '}
            <span className="tabular font-medium">{pct(data.total.reply_rate.rate)}</span> · entrevista{' '}
            <span className="tabular font-medium">{pct(data.total.interview_rate.rate)}</span>
            {data.total.applied < CALIBRATION_MIN_SENT && (
              <span className="text-muted-foreground"> · con menos de {CALIBRATION_MIN_SENT}, tómalo con mucha cautela</span>
            )}
          </p>
          <Tabs value={tab} onValueChange={setTab} className="gap-3">
            <TabsList className="h-auto flex-wrap justify-start">
              {CALIBRATION_TABS.map((t) => (
                <TabsTrigger key={t.id} value={t.id} className="px-2.5">
                  {t.label}
                </TabsTrigger>
              ))}
            </TabsList>
            {CALIBRATION_TABS.map((t) => (
              <TabsContent key={t.id} value={t.id}>
                <p className="mb-2 text-xs text-muted-foreground">
                  {t.hint} «Pocos datos»: menos de {data.min_cases} enviadas.
                </p>
                <CalibrationTable caption={`Calibración por ${t.label.toLowerCase()}`} groups={t.pick(data)} />
              </TabsContent>
            ))}
          </Tabs>
        </>
      )}
    </Panel>
  )
}

const REFERRAL_GROUP_LABEL: Record<Schemas['ReferralFunnel']['group'], string> = {
  given: 'Con referencia',
  requested: 'Referencia pedida',
  none: 'Sin referencia',
}

function DashboardSkeleton() {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Cargando">
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
          <h1 className="text-2xl font-semibold tracking-tight">Embudo</h1>
          <p className="mt-1.5 max-w-[65ch] text-sm leading-relaxed text-muted-foreground">
            Qué funciona en tu búsqueda: cuántas ofertas avanzan en cada paso, por qué canal y tipo de puesto llegan, cuánto
            tardan en responder y por qué se descartan.
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
            title={since ? 'No hay ofertas en este periodo' : 'Aún no hay datos'}
          >
            {since ? (
              'Prueba con un periodo más largo.'
            ) : (
              <>
                El embudo se llena a medida que das de alta ofertas (
                <Link to="/nueva" className="underline underline-offset-4">
                  Nueva oferta
                </Link>
                ), las revisas y registras lo que pasa con cada candidatura.
              </>
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
