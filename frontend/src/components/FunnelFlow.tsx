import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { ArrowRightIcon } from '@phosphor-icons/react'
import { useTranslation } from 'react-i18next'
import type { Schemas } from '@/api/client'
import { useFunnelFlow } from '@/api/queries'
import { Reveal } from '@/components/Reveal'
import { ErrorState } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import {
  biggestStop,
  END_WIDTH,
  FLOW_STEPS,
  layoutFlow,
  NODE_WIDTH,
  stopLink,
  type FlowStep,
  type StopOutcome,
} from '@/lib/funnelFlow'
import { formatNumber } from '@/lib/labels'
import { toLocalDateInput } from '@/lib/time'
import { cn } from '@/lib/utils'

type Flow = Schemas['FunnelFlow']

const pct = (value: number | null | undefined) =>
  value == null ? '—' : formatNumber(value, { style: 'percent', maximumFractionDigits: 0 })

const STEP_COLOR: Record<FlowStep, string> = {
  applied: 'var(--flow-1)',
  replied: 'var(--flow-2)',
  interview: 'var(--flow-3)',
  offer: 'var(--flow-4)',
  accepted: 'var(--primary)',
}

/** Lo abierto sigue con el color de su paso; lo cerrado no compite con él. */
function outcomeColor(step: FlowStep, outcome: StopOutcome | null): string {
  if (outcome === 'rejected') return 'var(--flow-rejected)'
  if (outcome === 'withdrawn' || outcome === 'expired') return 'var(--flow-closed)'
  return STEP_COLOR[step]
}

/** Los periodos de la portada; en «Embudo», el selector de la página manda. */
const PERIODS = [
  { id: '30', days: 30 },
  { id: '90', days: 90 },
  { id: 'all', days: null },
] as const

function sinceOf(days: number | null): string | null {
  return days ? toLocalDateInput(new Date(Date.now() - (days - 1) * 86_400_000)) : null
}

function useWidth() {
  const ref = useRef<HTMLDivElement>(null)
  // Antes de medir (y en los tests, sin diseño), un ancho razonable.
  const [width, setWidth] = useState(1000)
  useEffect(() => {
    const element = ref.current
    if (!element) return
    const measure = () => {
      if (element.clientWidth > 0) setWidth(element.clientWidth)
    }
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(element)
    return () => observer.disconnect()
  }, [])
  return { ref, width }
}

function Chart({ flow, counts }: { flow: Flow; counts: Record<FlowStep, number> }) {
  const { t } = useTranslation('funnel', { keyPrefix: 'flow' })
  const { t: tRoot } = useTranslation('funnel')
  const navigate = useNavigate()
  const { ref, width } = useWidth()
  const [hover, setHover] = useState<{ key: string; text: string; x: number; y: number } | null>(null)
  const layout = layoutFlow(counts, flow.stops as Parameters<typeof layoutFlow>[1], width)
  const stepInfo = (step: FlowStep) => flow.steps.find((s) => s.step === step)

  const stopLabel = (step: string, outcome: StopOutcome, count: number) => t(`stops.${step}.${outcome}` as never, { count })
  const stopHint = (step: string, outcome: StopOutcome, count: number) =>
    t('stopHint', { what: stopLabel(step, outcome, count), pct: pct(count / Math.max(1, counts.applied)) })

  const track = (key: string, text: string) => ({
    onMouseEnter: (e: React.MouseEvent) => place(key, text, e),
    onMouseMove: (e: React.MouseEvent) => place(key, text, e),
    onMouseLeave: () => setHover(null),
  })
  const place = (key: string, text: string, e: React.MouseEvent) => {
    const box = ref.current?.getBoundingClientRect()
    if (box) setHover({ key, text, x: e.clientX - box.left, y: e.clientY - box.top })
  }
  const dim = (key: string) => (hover && hover.key !== key ? 0.35 : 1)

  const summary = t('chartLabel', {
    applied: counts.applied,
    replied: counts.replied,
    interview: counts.interview,
    offer: counts.offer,
    accepted: counts.accepted,
  })

  return (
    <div ref={ref} className="relative mt-4">
      {/* Cada paso, encima de su columna. */}
      <div className="relative h-[4.75rem]">
        {layout.nodes.map((node, index) => {
          const last = index === layout.nodes.length - 1
          const info = stepInfo(node.step)
          return (
            <div
              key={node.step}
              className={cn('absolute top-0 whitespace-nowrap', last && 'right-0 text-right')}
              style={last ? undefined : { left: node.x }}
            >
              <p className="text-sm font-medium">{tRoot(`steps.${node.step}`)}</p>
              <p className="tabular text-2xl leading-tight font-semibold tracking-tight">{formatNumber(node.count)}</p>
              <p className="text-xs text-muted-foreground">
                {index === 0
                  ? t('everything')
                  : node.count === 0 && last
                    ? t('noneYet')
                    : t('ofPrevious', { pct: pct(info?.rate_from_previous), step: tRoot(`steps.${FLOW_STEPS[index - 1]}`).toLowerCase() })}
              </p>
            </div>
          )
        })}
      </div>

      <svg role="img" aria-label={summary} width={width} height={layout.height} className="mt-1 block overflow-visible">
        {layout.ribbons.map((r) => {
          const next = FLOW_STEPS[FLOW_STEPS.indexOf(r.step) + 1]
          const text = r.outcome
            ? stopHint(r.step, r.outcome, r.count)
            : t('passed', { count: r.count, from: tRoot(`steps.${r.step}`).toLowerCase(), to: tRoot(`steps.${next}`).toLowerCase() })
          return (
            <path
              key={r.key}
              d={r.path}
              fill={outcomeColor(r.step, r.outcome)}
              fillOpacity={0.3 * dim(r.key)}
              className={cn('transition-[fill-opacity] duration-150', r.outcome && 'cursor-pointer')}
              onClick={r.outcome ? () => void navigate(stopLink(r.step, r.outcome!)) : undefined}
              {...track(r.key, text)}
            />
          )
        })}
        {layout.nodes.map((node) =>
          node.count > 0 ? (
            <rect
              key={node.step}
              x={node.x}
              y={node.y}
              width={NODE_WIDTH}
              height={node.height}
              rx={2}
              fill={STEP_COLOR[node.step]}
            />
          ) : (
            <EmptyStep key={node.step} x={node.x} />
          ),
        )}
        {layout.ends.map((end) => {
          const label = stopLabel(end.step, end.outcome, end.count)
          return (
            <g
              key={end.key}
              className="cursor-pointer"
              opacity={dim(end.key)}
              onClick={() => void navigate(stopLink(end.step, end.outcome))}
              {...track(end.key, stopHint(end.step, end.outcome, end.count))}
            >
              <rect x={end.x} y={end.y} width={END_WIDTH} height={end.height} rx={2} fill={outcomeColor(end.step, end.outcome)} />
              <text
                x={end.x + END_WIDTH + 6}
                y={end.y + end.height / 2}
                dominantBaseline="central"
                className="fill-foreground/80 text-xs"
              >
                {label}
              </text>
            </g>
          )
        })}
      </svg>

      {hover && (
        <div
          aria-hidden
          className="pointer-events-none absolute z-10 max-w-64 -translate-x-1/2 -translate-y-full rounded-md bg-foreground px-2 py-1 text-xs text-background shadow-md"
          style={{ left: hover.x, top: hover.y - 8 }}
        >
          {hover.text}
        </div>
      )}
    </div>
  )
}

/** Un paso al que no ha llegado nada: una raya, para que se vea que el paso existe. */
function EmptyStep({ x }: { x: number }) {
  return <rect x={x} y={0} width={NODE_WIDTH} height={2} rx={1} fill="var(--flow-closed)" />
}

function Numbers({ flow }: { flow: Flow }) {
  const { t } = useTranslation('funnel', { keyPrefix: 'flow' })
  const { t: tRoot } = useTranslation('funnel')
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <table className="w-full text-sm">
        <caption className="sr-only">{tRoot('funnel.caption')}</caption>
        <thead>
          <tr className="border-b text-left text-xs text-muted-foreground">
            <th scope="col" className="py-1.5 font-normal">{t('stepHead')}</th>
            <th scope="col" className="py-1.5 text-right font-normal">{tRoot('funnel.countHead')}</th>
            <th scope="col" className="py-1.5 text-right font-normal">{tRoot('funnel.fromPreviousHead')}</th>
            <th scope="col" className="py-1.5 text-right font-normal">{tRoot('funnel.fromStartHead')}</th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {flow.steps.map((s) => (
            <tr key={s.step}>
              <th scope="row" className="py-1.5 text-left font-normal">{tRoot(`steps.${s.step}`)}</th>
              <td className="tabular py-1.5 text-right">{formatNumber(s.count)}</td>
              <td className="tabular py-1.5 text-right text-muted-foreground">{pct(s.rate_from_previous)}</td>
              <td className="tabular py-1.5 text-right text-muted-foreground">{pct(s.rate_from_start)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {flow.stops.length > 0 && (
        <div>
          <h3 className="border-b py-1.5 text-xs text-muted-foreground">{t('whereTheyStopped')}</h3>
          <ul className="divide-y text-sm">
            {flow.stops.map((stop) => (
              <li key={`${stop.step}:${stop.outcome}`} className="flex items-baseline justify-between gap-4 py-1.5">
                <Link to={stopLink(stop.step, stop.outcome)} className="underline-offset-4 hover:underline">
                  {t(`stops.${stop.step}.${stop.outcome}` as never, { count: stop.count })}
                </Link>
                <span className="text-xs text-muted-foreground">{tRoot(`steps.${stop.step}`)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

/**
 * «Tu embudo»: hasta dónde ha llegado cada candidatura enviada y dónde están las que pararon. Cada
 * rama lleva a esas candidaturas. Sin `since`, tiene su propio selector de periodo (la portada); con
 * él, el periodo lo decide quien lo pinta (la página «Embudo»).
 */
export function FunnelFlow({ since, more = false }: { since?: string | null; more?: boolean }) {
  const { t } = useTranslation('funnel', { keyPrefix: 'flow' })
  const { t: tRoot } = useTranslation('funnel')
  const [period, setPeriod] = useState<(typeof PERIODS)[number]['id']>('all')
  const ownPeriod = since === undefined
  const days = PERIODS.find((p) => p.id === period)?.days ?? null
  const query = useFunnelFlow(ownPeriod ? sinceOf(days) : since)
  const flow = query.data

  const count = (step: string) => flow?.steps.find((s) => s.step === step)?.count ?? 0
  const counts = Object.fromEntries(FLOW_STEPS.map((step) => [step, count(step)])) as Record<FlowStep, number>
  const replyRate = flow?.steps.find((s) => s.step === 'replied')?.rate_from_previous
  const biggest = biggestStop(flow?.stops ?? [])

  return (
    <section aria-labelledby="funnel-flow" className="rounded-xl border bg-card p-5">
      <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-4">
        <div className="min-w-0 max-w-[75ch]">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
            <h2 id="funnel-flow" className="text-lg font-semibold tracking-tight">{t('title')}</h2>
            {ownPeriod && (
              <div role="group" aria-label={tRoot('period')} className="flex gap-1">
                {PERIODS.map((p) => (
                  <Button
                    key={p.id}
                    size="xs"
                    variant="ghost"
                    aria-pressed={period === p.id}
                    className={cn(period === p.id ? 'bg-foreground/[0.07] text-foreground' : 'font-normal text-muted-foreground')}
                    onClick={() => setPeriod(p.id)}
                  >
                    {tRoot(`presets.${p.id}`)}
                  </Button>
                ))}
              </div>
            )}
          </div>
          <p className="mt-0.5 text-sm text-muted-foreground">
            {t('hint')}
            {!ownPeriod && !!flow?.duplicates_excluded && tRoot('funnel.duplicates', { count: flow.duplicates_excluded })}
          </p>
        </div>
        {/* En «Embudo», estas cifras ya están en las tarjetas de arriba. */}
        {ownPeriod && flow && counts.applied > 0 && (
          <dl className="flex gap-7">
            {[
              { label: t('stats.sent'), value: formatNumber(counts.applied) },
              { label: t('stats.heardBack'), value: pct(replyRate) },
              { label: t('stats.reachedInterview'), value: formatNumber(counts.interview) },
            ].map((stat) => (
              <div key={stat.label} className="flex flex-col-reverse">
                <dt className="text-xs text-muted-foreground">{stat.label}</dt>
                <dd className="tabular text-2xl leading-tight font-semibold tracking-tight">{stat.value}</dd>
              </div>
            ))}
          </dl>
        )}
      </div>

      {query.isPending ? (
        <Skeleton className="mt-6 h-64" />
      ) : query.isError ? (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} className="mt-6" />
      ) : counts.applied === 0 ? (
        <>
          <p className="mt-6 text-sm text-muted-foreground">{ownPeriod && days ? t('emptyPeriod') : t('empty')}</p>
          {count('found') > 0 && (
            <Reveal label={t('numbers')} className="mt-3">
              <Numbers flow={flow!} />
            </Reveal>
          )}
        </>
      ) : (
        <>
          <Chart flow={flow!} counts={counts} />
          <div className="mt-3 flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2">
            {biggest && counts.applied >= 5 && (
              <p className="text-sm text-muted-foreground">
                {t('biggest', {
                  what: t(`stops.${biggest.step}.${biggest.outcome}` as never, { count: biggest.count }),
                  pct: pct(biggest.count / counts.applied),
                })}
              </p>
            )}
            {more && (
              <Link to="/embudo" className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
                {t('more')}
                <ArrowRightIcon className="size-3" />
              </Link>
            )}
          </div>
          <Reveal label={t('numbers')} className="mt-3">
            <Numbers flow={flow!} />
          </Reveal>
        </>
      )}
    </section>
  )
}
