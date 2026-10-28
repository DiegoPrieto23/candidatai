import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router'
import { CaretLeftIcon, CaretRightIcon, DownloadSimpleIcon } from '@phosphor-icons/react'
import { fileUrls, type CalendarItem } from '@/api/client'
import { useCalendar } from '@/api/queries'
import { ErrorState } from '@/components/States'
import { Hint } from '@/components/Hint'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Skeleton } from '@/components/ui/skeleton'
import {
  AGENDA_DAYS,
  CALENDAR_VIEWS,
  dayOf,
  daysBetween,
  formatDay,
  isDay,
  minutesOf,
  monthGrid,
  rangeLabel,
  sameMonth,
  shift,
  today,
  viewRange,
  type CalendarView,
  type Day,
} from '@/lib/calendar'
import { dateFormatter, MILESTONE_STATUS_LABEL, STAGE_LABEL, UPCOMING_KIND_LABEL } from '@/lib/labels'
import { APP_TIME_ZONE, formatWhen } from '@/lib/time'
import { cn } from '@/lib/utils'

type Kind = CalendarItem['kind']

/** Color de cada tipo de hito: el plazo de la oferta, con borde discontinuo (no es un hito tuyo). */
const KIND_STYLE: Record<Kind, { chip: string; dot: string }> = {
  interview: { chip: 'border-primary/25 bg-primary/10 text-primary', dot: 'bg-primary' },
  test: {
    chip: 'border-violet-500/25 bg-violet-500/10 text-violet-800 dark:text-violet-300',
    dot: 'bg-violet-500',
  },
  deadline: {
    chip: 'border-amber-500/30 bg-amber-500/10 text-amber-900 dark:text-amber-300',
    dot: 'bg-amber-500',
  },
  application_deadline: {
    chip: 'border-dashed border-amber-500/60 bg-transparent text-amber-900 dark:text-amber-300',
    dot: 'bg-amber-500/60',
  },
  other: { chip: 'border-border bg-muted text-foreground', dot: 'bg-foreground/40' },
}

const KINDS: readonly Kind[] = ['interview', 'test', 'deadline', 'application_deadline', 'other']

const STATUS_STYLE: Record<CalendarItem['status'], string> = {
  scheduled: '',
  done: 'opacity-60',
  cancelled: 'line-through opacity-50',
}

/** El plazo de la oferta viene con un título fijo del servidor: se traduce con su tipo. */
function itemTitle(item: CalendarItem): string {
  return item.kind === 'application_deadline' ? UPCOMING_KIND_LABEL[item.kind] : item.title
}

function formatTime(iso: string): string {
  return dateFormatter({ timeZone: APP_TIME_ZONE, hour: '2-digit', minute: '2-digit' }).format(new Date(iso))
}

function byDay(items: CalendarItem[]): Map<Day, CalendarItem[]> {
  const days = new Map<Day, CalendarItem[]>()
  for (const item of items) {
    const day = dayOf(item.starts_at)
    days.set(day, [...(days.get(day) ?? []), item])
  }
  return days
}

/** La hora de ahora, al minuto, para la línea roja de las vistas de semana y día. */
function useNow(): Date {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 60_000)
    return () => window.clearInterval(id)
  }, [])
  return now
}

// --- Hito ------------------------------------------------------------------------------------

/**
 * En una línea (mes y «Todo el día») se ve la hora y la empresa; en un bloque de la semana o del día,
 * también el título. El nombre accesible y el tooltip llevan siempre todo.
 */
function EventChip({
  item,
  onOpen,
  block = false,
  className,
}: {
  item: CalendarItem
  onOpen: (item: CalendarItem) => void
  block?: boolean
  className?: string
}) {
  const time = item.all_day ? null : formatTime(item.starts_at)
  const name = `${time ? `${time} ` : ''}${itemTitle(item)} · ${item.company}`
  return (
    <button
      type="button"
      onClick={() => onOpen(item)}
      aria-label={name}
      title={`${name} (${item.job_title})`}
      className={cn(
        'block w-full rounded border px-1.5 py-0.5 text-left text-xs leading-snug transition-colors hover:brightness-95 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none dark:hover:brightness-125',
        block ? 'overflow-hidden' : 'truncate',
        KIND_STYLE[item.kind].chip,
        STATUS_STYLE[item.status],
        className,
      )}
    >
      {block ? (
        <>
          <span className="block truncate">
            {time && <span className="tabular font-medium">{time} </span>}
            <span className="font-medium">{item.company}</span>
          </span>
          <span className="line-clamp-2 opacity-90">{itemTitle(item)}</span>
        </>
      ) : (
        <>
          {time && <span className="tabular font-medium">{time} </span>}
          {item.all_day ? `${itemTitle(item)} · ${item.company}` : item.company}
        </>
      )}
    </button>
  )
}

function EventDialog({ item, onClose }: { item: CalendarItem | null; onClose: () => void }) {
  const { t } = useTranslation('calendar', { keyPrefix: 'detail' })
  const when = item
    ? `${formatWhen(item.starts_at, item.all_day)}${item.ends_at && !item.all_day ? ` – ${formatTime(item.ends_at)}` : ''}`
    : ''
  const isLink = item?.location ? /^https?:\/\//i.test(item.location) : false
  return (
    <Dialog open={item != null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        {item && (
          <>
            <DialogHeader>
              <p className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                <span className={cn('size-2 rounded-full', KIND_STYLE[item.kind].dot)} aria-hidden />
                {UPCOMING_KIND_LABEL[item.kind]}
              </p>
              <DialogTitle className={cn(item.status === 'cancelled' && 'line-through')}>{itemTitle(item)}</DialogTitle>
              <DialogDescription>
                {item.job_title} · {item.company}
              </DialogDescription>
            </DialogHeader>
            <dl className="grid grid-cols-[7rem_minmax(0,1fr)] gap-x-3 gap-y-2 text-sm">
              <dt className="text-muted-foreground">{t('when')}</dt>
              <dd>{when}</dd>
              {item.location && (
                <>
                  <dt className="text-muted-foreground">{t('where')}</dt>
                  <dd className="break-words">
                    {isLink ? (
                      <a href={item.location} target="_blank" rel="noreferrer" className="underline underline-offset-4">
                        {item.location}
                      </a>
                    ) : (
                      item.location
                    )}
                  </dd>
                </>
              )}
              {item.milestone_id != null && (
                <>
                  <dt className="text-muted-foreground">{t('status')}</dt>
                  <dd>{MILESTONE_STATUS_LABEL[item.status]}</dd>
                </>
              )}
              <dt className="text-muted-foreground">{t('stage')}</dt>
              <dd>{STAGE_LABEL[item.stage]}</dd>
            </dl>
            <div className="flex flex-wrap gap-2">
              <Button asChild size="sm">
                <Link to={`/jobs/${item.job_id}`}>{t('openJob')}</Link>
              </Button>
              {item.milestone_id != null && item.status === 'scheduled' && (
                <Button asChild size="sm" variant="outline">
                  <a href={fileUrls.milestoneIcs(item.milestone_id)} download>
                    <DownloadSimpleIcon />
                    {t('ics')}
                  </a>
                </Button>
              )}
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}

// --- Mes -------------------------------------------------------------------------------------

const MONTH_VISIBLE = 3

function MonthView({
  day,
  items,
  onOpen,
  onOpenDay,
}: {
  day: Day
  items: CalendarItem[]
  onOpen: (item: CalendarItem) => void
  onOpenDay: (day: Day) => void
}) {
  const { t } = useTranslation('calendar')
  const grid = monthGrid(day)
  const days = byDay(items)
  const now = today()
  return (
    <div className="overflow-hidden rounded-xl border bg-card">
      <div className="grid grid-cols-7 border-b bg-muted/40 text-xs font-medium text-muted-foreground" aria-hidden>
        {grid.slice(0, 7).map((d) => (
          <div key={d} className="px-2 py-2 text-center sm:text-left">
            {formatDay(d, { weekday: 'short' })}
          </div>
        ))}
      </div>
      <ol className="grid grid-cols-7">
        {grid.map((d, i) => {
          const list = days.get(d) ?? []
          const hidden = list.length - MONTH_VISIBLE
          const label = formatDay(d, { weekday: 'long', day: 'numeric', month: 'long' })
          return (
            <li
              key={d}
              aria-label={label}
              className={cn(
                'flex min-h-20 min-w-0 flex-col gap-1 border-b p-1 sm:min-h-28 sm:p-1.5',
                i % 7 !== 6 && 'border-r',
                i >= grid.length - 7 && 'border-b-0',
                !sameMonth(d, day) && 'bg-muted/30 text-muted-foreground',
              )}
            >
              <button
                type="button"
                onClick={() => onOpenDay(d)}
                aria-label={t('openDay', { day: label })}
                className="flex flex-col items-center gap-1 self-stretch rounded-md py-0.5 hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none sm:items-start sm:self-start sm:px-1"
              >
                <span
                  className={cn(
                    'tabular grid size-6 place-items-center rounded-full text-xs',
                    d === now && 'bg-primary font-semibold text-primary-foreground',
                  )}
                >
                  {Number(d.slice(8))}
                </span>
                {list.length > 0 && (
                  <span className="flex flex-wrap justify-center gap-0.5 sm:hidden" aria-hidden>
                    {list.slice(0, 4).map((item) => (
                      <span key={`${item.kind}-${item.milestone_id ?? item.job_id}`} className={cn('size-1.5 rounded-full', KIND_STYLE[item.kind].dot)} />
                    ))}
                  </span>
                )}
              </button>
              <ul className="hidden min-w-0 flex-col gap-1 sm:flex">
                {list.slice(0, MONTH_VISIBLE).map((item) => (
                  <li key={`${item.kind}-${item.milestone_id ?? item.job_id}`} className="min-w-0">
                    <EventChip item={item} onOpen={onOpen} />
                  </li>
                ))}
              </ul>
              {hidden > 0 && (
                <button
                  type="button"
                  onClick={() => onOpenDay(d)}
                  aria-label={t('moreAria', { count: hidden, day: label })}
                  className="hidden self-start rounded px-1.5 text-xs font-medium text-muted-foreground hover:text-foreground sm:block"
                >
                  {t('more', { count: hidden })}
                </button>
              )}
            </li>
          )
        })}
      </ol>
    </div>
  )
}

// --- Semana y día ----------------------------------------------------------------------------

const HOUR_PX = 56
const MIN_HEIGHT = 30 // minutos: lo mínimo para que quepa el texto

type Placed = { item: CalendarItem; start: number; end: number; col: number; cols: number }

/** Minutos de inicio y fin de cada hito del día, en columnas cuando se solapan. */
function layout(items: CalendarItem[]): Placed[] {
  const spans = items
    .map((item) => {
      const start = minutesOf(item.starts_at)
      const realEnd = item.ends_at
        ? dayOf(item.ends_at) === dayOf(item.starts_at)
          ? minutesOf(item.ends_at)
          : 24 * 60
        : start + 60
      return { item, start, end: Math.min(24 * 60, Math.max(realEnd, start + MIN_HEIGHT)) }
    })
    .sort((a, b) => a.start - b.start || b.end - a.end)
  const placed: Placed[] = []
  let cluster: Placed[] = []
  let columns: number[] = [] // fin de lo último colocado en cada columna
  let clusterEnd = -1
  const close = () => cluster.forEach((p) => (p.cols = columns.length))
  for (const span of spans) {
    if (span.start >= clusterEnd) {
      close()
      cluster = []
      columns = []
    }
    let col = columns.findIndex((end) => end <= span.start)
    if (col === -1) col = columns.push(0) - 1
    columns[col] = span.end
    const p = { ...span, col, cols: 1 }
    cluster.push(p)
    placed.push(p)
    clusterEnd = Math.max(clusterEnd, span.end)
  }
  close()
  return placed
}

function TimeGrid({ days, items, onOpen }: { days: Day[]; items: CalendarItem[]; onOpen: (item: CalendarItem) => void }) {
  const { t } = useTranslation('calendar')
  const byDate = byDay(items)
  const now = useNow()
  const nowDay = dayOf(now.toISOString())
  const nowMinutes = minutesOf(now.toISOString())
  const placedByDay = new Map(days.map((d) => [d, layout((byDate.get(d) ?? []).filter((i) => !i.all_day))]))
  const timed = [...placedByDay.values()].flat()
  const firstHour = Math.min(8, ...timed.map((p) => Math.floor(p.start / 60)))
  const lastHour = Math.max(20, ...timed.map((p) => Math.ceil(p.end / 60)))
  const hours = Array.from({ length: lastHour - firstHour }, (_, i) => firstHour + i)
  const hasAllDay = days.some((d) => byDate.get(d)?.some((i) => i.all_day))
  const cols = { gridTemplateColumns: `3.5rem repeat(${days.length}, minmax(0, 1fr))` }
  const hourLabel = (h: number) =>
    dateFormatter({ timeZone: 'UTC', hour: '2-digit', minute: '2-digit' }).format(new Date(Date.UTC(2026, 0, 1, h)))

  return (
    <div className="-mx-4 overflow-x-auto overflow-y-hidden px-4 sm:mx-0 sm:px-0">
      <div className={cn('overflow-hidden rounded-xl border bg-card', days.length > 1 && 'min-w-[44rem]')}>
        <div className="grid border-b bg-muted/40" style={cols}>
          <div />
          {days.map((d) => (
            <div key={d} className="border-l px-2 py-2 text-xs">
              <span className="text-muted-foreground">{formatDay(d, { weekday: 'short' })}</span>{' '}
              <span
                className={cn(
                  'tabular inline-grid size-6 place-items-center rounded-full font-medium',
                  d === today() && 'bg-primary text-primary-foreground',
                )}
              >
                {Number(d.slice(8))}
              </span>
            </div>
          ))}
        </div>
        {hasAllDay && (
          <div className="grid border-b" style={cols}>
            <div className="px-1.5 py-1.5 text-right text-[0.7rem] leading-tight text-muted-foreground">{t('allDay')}</div>
            {days.map((d) => (
              <ul key={d} className="flex min-w-0 flex-col gap-1 border-l p-1">
                {(byDate.get(d) ?? [])
                  .filter((i) => i.all_day)
                  .map((item) => (
                    <li key={`${item.kind}-${item.milestone_id ?? item.job_id}`} className="min-w-0">
                      <EventChip item={item} onOpen={onOpen} />
                    </li>
                  ))}
              </ul>
            ))}
          </div>
        )}
        <div className="grid" style={cols}>
          <div aria-hidden>
            {hours.map((h) => (
              <div key={h} style={{ height: HOUR_PX }} className="relative">
                {h !== firstHour && (
                  <span className="tabular absolute -top-2 right-1.5 text-[0.7rem] text-muted-foreground">{hourLabel(h)}</span>
                )}
              </div>
            ))}
          </div>
          {days.map((d) => (
            <div key={d} className="relative border-l" style={{ height: hours.length * HOUR_PX }}>
              {hours.map((h) => (
                <div key={h} className="border-b border-border/60" style={{ height: HOUR_PX }} aria-hidden />
              ))}
              <ul>
                {(placedByDay.get(d) ?? []).map((p) => (
                  <li
                    key={`${p.item.kind}-${p.item.milestone_id ?? p.item.job_id}`}
                    className="absolute px-0.5"
                    style={{
                      top: ((p.start - firstHour * 60) / 60) * HOUR_PX,
                      height: ((p.end - p.start) / 60) * HOUR_PX,
                      left: `${(p.col / p.cols) * 100}%`,
                      width: `${100 / p.cols}%`,
                    }}
                  >
                    <EventChip item={p.item} onOpen={onOpen} block className="h-full" />
                  </li>
                ))}
              </ul>
              {d === nowDay && nowMinutes >= firstHour * 60 && nowMinutes < lastHour * 60 && (
                <div
                  role="presentation"
                  title={t('now')}
                  className="pointer-events-none absolute inset-x-0 z-10 h-0.5 bg-destructive"
                  style={{ top: ((nowMinutes - firstHour * 60) / 60) * HOUR_PX }}
                >
                  <span className="absolute -top-1 -left-1 size-2.5 rounded-full bg-destructive" />
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// --- Agenda ----------------------------------------------------------------------------------

function AgendaView({ items, onOpen }: { items: CalendarItem[]; onOpen: (item: CalendarItem) => void }) {
  const { t } = useTranslation('calendar')
  const days = [...byDay(items).entries()]
  if (days.length === 0)
    return (
      <p className="rounded-xl border border-dashed px-4 py-10 text-center text-sm text-muted-foreground">
        {t('agendaEmpty', { count: AGENDA_DAYS })}
      </p>
    )
  return (
    <ol className="divide-y rounded-xl border bg-card">
      {days.map(([d, list]) => (
        <li key={d} className="grid gap-2 px-4 py-3 sm:grid-cols-[11rem_minmax(0,1fr)] sm:gap-4">
          <h2 className={cn('text-sm font-medium', d === today() && 'text-primary')}>
            {formatDay(d, { weekday: 'long', day: 'numeric', month: 'long' })}
          </h2>
          <ul className="grid gap-1.5">
            {list.map((item) => (
              <li key={`${item.kind}-${item.milestone_id ?? item.job_id}`}>
                <button
                  type="button"
                  onClick={() => onOpen(item)}
                  className={cn(
                    'flex w-full items-baseline gap-3 rounded-md px-2 py-1 text-left text-sm hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none',
                    STATUS_STYLE[item.status],
                  )}
                >
                  <span className="tabular w-24 shrink-0 text-muted-foreground">
                    {item.all_day ? t('allDay') : formatTime(item.starts_at)}
                  </span>
                  <span className={cn('size-2 shrink-0 self-center rounded-full', KIND_STYLE[item.kind].dot)} aria-hidden />
                  <span className="min-w-0">
                    <span className="font-medium">{itemTitle(item)}</span>
                    <span className="text-muted-foreground">
                      {' · '}
                      {item.job_title} ({item.company})
                    </span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </li>
      ))}
    </ol>
  )
}

// --- Página ----------------------------------------------------------------------------------

/**
 * «Calendario»: los hitos de todos los procesos (entrevistas, pruebas, plazos y otros, también los
 * hechos, los cancelados y los de procesos cerrados) y los plazos de las ofertas sin enviar, por
 * mes, semana, día o agenda. La vista y la fecha van en la URL (`?view=week&date=2026-10-23`).
 */
export function CalendarPage() {
  const { t } = useTranslation('calendar')
  const [params, setParams] = useSearchParams()
  const viewParam = params.get('view')
  const view: CalendarView = CALENDAR_VIEWS.includes(viewParam as CalendarView) ? (viewParam as CalendarView) : 'month'
  const dateParam = params.get('date')
  const day = isDay(dateParam) ? dateParam : today()
  const { start, end } = viewRange(view, day)
  const calendar = useCalendar(start, end)
  const [selected, setSelected] = useState<CalendarItem | null>(null)

  const go = (next: { view?: CalendarView; date?: Day }) =>
    setParams({ view: next.view ?? view, date: next.date ?? day })

  return (
    <div className="animate-in fade-in duration-300">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">{t('title')}</h1>
        <p className="mt-1.5 max-w-[65ch] text-sm leading-relaxed text-muted-foreground">{t('intro')}</p>
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-x-3 gap-y-3">
        <Button variant="outline" size="sm" onClick={() => go({ date: today() })}>
          {t('today')}
        </Button>
        <div className="flex">
          <Hint text={t('previous')}>
            <Button variant="ghost" size="icon" className="size-8" aria-label={t('previous')} onClick={() => go({ date: shift(view, day, -1) })}>
              <CaretLeftIcon />
            </Button>
          </Hint>
          <Hint text={t('next')}>
            <Button variant="ghost" size="icon" className="size-8" aria-label={t('next')} onClick={() => go({ date: shift(view, day, 1) })}>
              <CaretRightIcon />
            </Button>
          </Hint>
        </div>
        <h2 className="min-w-0 text-lg font-medium first-letter:uppercase" aria-live="polite">
          {rangeLabel(view, day)}
        </h2>
        <div role="group" aria-label={t('views.label')} className="ml-auto inline-flex gap-1 rounded-lg border bg-card p-1">
          {CALENDAR_VIEWS.map((v) => (
            <button
              key={v}
              type="button"
              aria-pressed={v === view}
              onClick={() => go({ view: v })}
              className={cn(
                'rounded-md px-2.5 py-1 text-sm transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none',
                v === view
                  ? 'bg-foreground/[0.07] font-medium text-foreground dark:bg-foreground/10'
                  : 'text-muted-foreground hover:text-foreground',
              )}
            >
              {t(`views.${v}`)}
            </button>
          ))}
        </div>
      </div>

      {calendar.isPending ? (
        <Skeleton className="h-[32rem] rounded-xl" />
      ) : calendar.isError ? (
        <ErrorState error={calendar.error} onRetry={() => calendar.refetch()} />
      ) : view === 'month' ? (
        <MonthView
          day={day}
          items={calendar.data.items}
          onOpen={setSelected}
          onOpenDay={(d) => go({ view: 'day', date: d })}
        />
      ) : view === 'agenda' ? (
        <AgendaView items={calendar.data.items} onOpen={setSelected} />
      ) : (
        <TimeGrid days={daysBetween(start, end)} items={calendar.data.items} onOpen={setSelected} />
      )}

      <ul aria-label={t('legend')} className="mt-4 flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-muted-foreground">
        {KINDS.map((kind) => (
          <li key={kind} className="inline-flex items-center gap-1.5">
            <span className={cn('size-2 rounded-full', KIND_STYLE[kind].dot)} aria-hidden />
            {UPCOMING_KIND_LABEL[kind]}
          </li>
        ))}
        <li className="inline-flex items-center gap-1.5 opacity-60">{MILESTONE_STATUS_LABEL.done}</li>
        <li className="inline-flex items-center gap-1.5 line-through opacity-50">{MILESTONE_STATUS_LABEL.cancelled}</li>
      </ul>

      <EventDialog item={selected} onClose={() => setSelected(null)} />
    </div>
  )
}

