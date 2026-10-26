import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import {
  ArrowDownIcon,
  ArrowSquareOutIcon,
  ArrowsDownUpIcon,
  ArrowUpIcon,
  CaretDownIcon,
  MagnifyingGlassIcon,
  PlusIcon,
  ProhibitIcon,
  TrayIcon,
  WarningIcon,
  XIcon,
} from '@phosphor-icons/react'
import { Trans, useTranslation } from 'react-i18next'
import type { DiscardReason, JobRow, Stage } from '@/api/client'
import { type JobSort, PAGE_SIZE, type SortDirection, useJobEvent, useJobs, useStatus } from '@/api/queries'
import { DiscardDialog, type DiscardChoice } from '@/components/DiscardDialog'
import { SignalBadges } from '@/components/JobSignals'
import { KnownBadge } from '@/components/NetworkPanel'
import { Pager } from '@/components/Pager'
import { ScoreBadge } from '@/components/MatchDetails'
import { StageBadge } from '@/components/StageBadge'
import { EmptyState, ErrorState } from '@/components/States'
import { Button } from '@/components/ui/button'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { errorMessage } from '@/lib/errors'
import {
  discardReasonLabel,
  eventLabel,
  formatDate,
  formatRelative,
  formatSalary,
  REMOTE_LABEL,
  STAGE_LABEL,
  STAGES,
} from '@/lib/labels'
import { cn } from '@/lib/utils'

function isStage(value: string | null): value is Stage {
  return value !== null && (STAGES as readonly string[]).includes(value)
}

interface Sort {
  sort: JobSort
  dir: SortDirection
}

const DEFAULT_SORT: Sort = { sort: 'date', dir: 'desc' }

/** La fecha de cierre solo ordena en «Cerrada»; con otra etapa, un `sort=closed` se ignora. */
function sortsFor(stage: Stage | undefined): readonly JobSort[] {
  return stage === 'closed' ? ['date', 'score', 'salary', 'closed'] : ['date', 'score', 'salary']
}

function parseSort(params: URLSearchParams, stage: Stage | undefined): Sort {
  const sort = params.get('sort')
  if (!sort || !(sortsFor(stage) as readonly string[]).includes(sort)) return DEFAULT_SORT
  return { sort: sort as JobSort, dir: params.get('dir') === 'asc' ? 'asc' : 'desc' }
}

/** Para el selector del móvil, donde no hay cabeceras. */
const SORT_OPTIONS = [
  { value: 'date:desc', label: 'dateDesc' },
  { value: 'date:asc', label: 'dateAsc' },
  { value: 'score:desc', label: 'scoreDesc' },
  { value: 'score:asc', label: 'scoreAsc' },
  { value: 'salary:desc', label: 'salaryDesc' },
  { value: 'salary:asc', label: 'salaryAsc' },
  { value: 'closed:desc', label: 'closedDesc' },
  { value: 'closed:asc', label: 'closedAsc' },
] as const

/** Etapas en las que se descarta desde la propia Bandeja: completar o extraer cuesta. */
const QUICK_DISCARD: readonly Stage[] = ['pending_detail', 'pending_extraction']
const QUICK_REASON: DiscardReason = 'not_interested'

function without(set: Set<number>, ids: number[]): Set<number> {
  const next = new Set(set)
  for (const id of ids) next.delete(id)
  return next
}

/** Búsqueda con retardo: no se lanza una consulta por cada tecla. */
function useDebounced<T>(value: T, ms = 250): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), ms)
    return () => clearTimeout(id)
  }, [value, ms])
  return debounced
}

function RiskMark() {
  const { t } = useTranslation('inbox')
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="inline-flex text-warning-foreground" aria-label={t('risk')}>
          <WarningIcon className="size-4" weight="fill" />
        </span>
      </TooltipTrigger>
      <TooltipContent>{t('risk')}</TooltipContent>
    </Tooltip>
  )
}

/** Un dato que falta: un guion discreto, con el porqué para el lector de pantalla y el ratón. */
function Missing({ label }: { label: string }) {
  return (
    <span className="text-muted-foreground/50" title={label}>
      <span aria-hidden>—</span>
      <span className="sr-only">{label}</span>
    </span>
  )
}

function RemoteMode({ mode }: { mode: JobRow['remote_mode'] }) {
  const { t } = useTranslation('inbox')
  if (!mode) return <Missing label={t('notExtracted')} />
  return <span className={cn(mode === 'unknown' && 'text-muted-foreground')}>{REMOTE_LABEL[mode]}</span>
}

function Salary({ salary }: { salary: JobRow['salary'] }) {
  const { t } = useTranslation('inbox')
  const text = formatSalary(salary)
  if (!text) return <Missing label={t('noSalary')} />
  return <span className="tabular">{text}</span>
}

/** Cabecera que ordena: la primera pulsación, de mayor a menor; la siguiente, al revés. */
function SortHeader({
  field,
  current,
  onSort,
  className,
  children,
}: {
  field: JobSort
  current: Sort
  onSort: (sort: Sort) => void
  className?: string
  children: React.ReactNode
}) {
  const active = current.sort === field
  const Icon = !active ? ArrowsDownUpIcon : current.dir === 'desc' ? ArrowDownIcon : ArrowUpIcon
  return (
    <th
      aria-sort={active ? (current.dir === 'desc' ? 'descending' : 'ascending') : 'none'}
      className={cn('pb-3 font-medium', className)}
    >
      <button
        type="button"
        onClick={() => onSort({ sort: field, dir: active && current.dir === 'desc' ? 'asc' : 'desc' })}
        className={cn(
          'inline-flex items-center gap-1 rounded-sm outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring',
          active && 'text-foreground',
        )}
      >
        {children}
        <Icon className={cn('size-3.5', !active && 'opacity-50')} aria-hidden />
      </button>
    </th>
  )
}

/** Cuándo y cómo se cerró, con la fecha completa y el evento en el globo nativo. */
function ClosedDate({ job }: { job: JobRow }) {
  if (!job.closed_at) return <span className="text-muted-foreground/60">—</span>
  const how = job.closed_by ? ` · ${eventLabel(job.closed_by)}` : ''
  return (
    <time dateTime={job.closed_at} title={`${formatDate(job.closed_at)}${how}`}>
      {formatRelative(job.closed_at)}
    </time>
  )
}

/** Lo que hace falta para descartar desde la tabla («Por completar» y «Por extraer»). */
interface QuickActions {
  /** En «Por completar» se decide en el portal: «Abrir» lleva allí. */
  openable: boolean
  selected: Set<number>
  onToggle: (id: number) => void
  onToggleAll: () => void
  onDiscard: (job: JobRow) => void
  onDiscardWith: (job: JobRow) => void
}

function SelectBox({ job, actions }: { job: JobRow; actions: QuickActions }) {
  const { t } = useTranslation('inbox')
  return (
    <input
      type="checkbox"
      checked={actions.selected.has(job.id)}
      onChange={() => actions.onToggle(job.id)}
      onClick={(e) => e.stopPropagation()}
      aria-label={t('quick.select', { title: job.title })}
      className="size-4 shrink-0 cursor-pointer accent-primary"
    />
  )
}

function RowActions({ job, actions }: { job: JobRow; actions: QuickActions }) {
  const { t } = useTranslation('inbox')
  return (
    // Nada de aquí abre la ficha; los clics del menú (en un portal) también suben hasta la fila.
    <div className="flex items-center justify-end gap-1.5" onClick={(e) => e.stopPropagation()}>
      {actions.openable && job.url && (
        <Button variant="ghost" size="xs" asChild>
          <a href={job.url} target="_blank" rel="noopener noreferrer" aria-label={t('quick.openJob', { title: job.title })}>
            <ArrowSquareOutIcon />
            {t('quick.open')}
          </a>
        </Button>
      )}
      <div className="inline-flex">
        <Button
          variant="outline"
          size="xs"
          onClick={() => actions.onDiscard(job)}
          aria-label={t('quick.discardJob', { title: job.title })}
          className="rounded-r-none"
        >
          <ProhibitIcon />
          {t('quick.discard')}
        </Button>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="outline"
              size="icon-xs"
              aria-label={t('quick.moreReasons', { title: job.title })}
              className="rounded-l-none border-l-0"
            >
              <CaretDownIcon />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" onClick={(e) => e.stopPropagation()}>
            <DropdownMenuItem onSelect={() => actions.onDiscardWith(job)}>{t('quick.otherReason')}</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  )
}

function JobTable({
  jobs,
  sort,
  onSort,
  closedView,
  actions,
}: {
  jobs: JobRow[]
  sort: Sort
  onSort: (sort: Sort) => void
  closedView: boolean
  actions?: QuickActions
}) {
  const { t } = useTranslation('inbox')
  const navigate = useNavigate()
  const picked = actions ? jobs.filter((job) => actions.selected.has(job.id)).length : 0
  return (
    <>
      {/* Escritorio: tabla */}
      <table className="hidden w-full text-sm md:table">
        <thead>
          <tr className="text-left text-xs text-muted-foreground">
            {actions && (
              <th className="w-0 pb-3 pl-4 font-medium" onClick={(e) => e.stopPropagation()}>
                <input
                  type="checkbox"
                  checked={picked > 0 && picked === jobs.length}
                  ref={(el) => {
                    if (el) el.indeterminate = picked > 0 && picked < jobs.length
                  }}
                  onChange={actions.onToggleAll}
                  aria-label={t('quick.selectAll')}
                  className="size-4 cursor-pointer accent-primary"
                />
              </th>
            )}
            <th className="pb-3 pl-4 font-medium">{t('columns.job')}</th>
            <th className="pb-3 pr-6 font-medium">{t('columns.mode')}</th>
            <SortHeader field="salary" current={sort} onSort={onSort} className="pr-6">
              {t('columns.salary')}
            </SortHeader>
            <SortHeader field="score" current={sort} onSort={onSort} className="pr-6 text-right">
              {t('columns.fit')}
            </SortHeader>
            <th className="pb-3 font-medium">{t('columns.stage')}</th>
            <SortHeader
              field="date"
              current={sort}
              onSort={onSort}
              className={cn('text-right', closedView || actions ? 'pr-6' : 'pr-4')}
            >
              {t('columns.added')}
            </SortHeader>
            {closedView && (
              <SortHeader field="closed" current={sort} onSort={onSort} className="pr-4 text-right">
                {t('columns.closed')}
              </SortHeader>
            )}
            {actions && (
              <th className="pb-3 pr-4 text-right font-medium">
                <span className="sr-only">{t('columns.actions')}</span>
              </th>
            )}
          </tr>
        </thead>
        <tbody className="divide-y">
          {jobs.map((job) => (
            <tr
              key={job.id}
              onClick={() => navigate(`/jobs/${job.id}`)}
              className="group cursor-pointer transition-colors hover:bg-foreground/[0.025]"
            >
              {actions && (
                <td className="py-3.5 pl-4" onClick={(e) => e.stopPropagation()}>
                  <SelectBox job={job} actions={actions} />
                </td>
              )}
              <td className="py-3.5 pl-4 pr-6">
                <div className="flex items-center gap-2">
                  <Link
                    to={`/jobs/${job.id}`}
                    onClick={(e) => e.stopPropagation()}
                    className="font-medium text-foreground underline-offset-4 outline-none group-hover:underline focus-visible:underline"
                  >
                    {job.title}
                  </Link>
                  {job.risk_flags.length > 0 && <RiskMark />}
                  <SignalBadges signals={job.signals} />
                  <KnownBadge count={job.known_contacts} />
                </div>
                <div className="mt-0.5 text-muted-foreground">
                  {job.company}
                  {job.location && <span className="text-muted-foreground/70">, {job.location}</span>}
                </div>
              </td>
              <td className="py-3.5 pr-6 whitespace-nowrap">
                <RemoteMode mode={job.remote_mode} />
              </td>
              <td className="py-3.5 pr-6 whitespace-nowrap">
                <Salary salary={job.salary} />
              </td>
              <td className="py-3.5 pr-6 text-right">
                {job.score == null ? <Missing label={t('noScore')} /> : <ScoreBadge score={job.score} />}
              </td>
              <td className="py-3.5 pr-6">
                <StageBadge stage={job.stage} />
              </td>
              <td
                className={cn(
                  'py-3.5 text-right whitespace-nowrap text-muted-foreground',
                  closedView || actions ? 'pr-6' : 'pr-4',
                )}
              >
                <time dateTime={job.first_seen_at} title={formatDate(job.first_seen_at)}>
                  {formatRelative(job.first_seen_at)}
                </time>
              </td>
              {closedView && (
                <td className="py-3.5 pr-4 text-right whitespace-nowrap text-muted-foreground">
                  <ClosedDate job={job} />
                </td>
              )}
              {actions && (
                <td className="py-3.5 pr-4">
                  <RowActions job={job} actions={actions} />
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>

      {/* Móvil: lista */}
      <ul className="divide-y md:hidden">
        {jobs.map((job) => (
          <li key={job.id} className={cn(actions && 'flex items-start gap-3 pl-4')}>
            {actions && (
              <div className="pt-5">
                <SelectBox job={job} actions={actions} />
              </div>
            )}
            <div className="min-w-0 flex-1">
              <Link
                to={`/jobs/${job.id}`}
                className={cn('block py-4 active:bg-foreground/[0.03]', actions ? 'pr-4 pb-2' : 'px-4')}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="flex items-center gap-1.5 font-medium">
                      <span className="truncate">{job.title}</span>
                      {job.risk_flags.length > 0 && (
                        <WarningIcon className="size-4 shrink-0 text-warning-foreground" weight="fill" />
                      )}
                      <SignalBadges signals={job.signals} />
                    <KnownBadge count={job.known_contacts} />
                    </p>
                    <p className="truncate text-sm text-muted-foreground">{job.company}</p>
                  </div>
                  <StageBadge stage={job.stage} />
                </div>
                <p className="mt-2 flex gap-3 text-xs text-muted-foreground">
                  {job.score != null && <span className="tabular font-medium text-foreground">{job.score}/100</span>}
                  <RemoteMode mode={job.remote_mode} />
                  {job.salary && <Salary salary={job.salary} />}
                  {closedView && job.closed_at ? (
                    <time dateTime={job.closed_at}>{t('closedWhen', { when: formatRelative(job.closed_at) })}</time>
                  ) : (
                    <time dateTime={job.first_seen_at}>{formatRelative(job.first_seen_at)}</time>
                  )}
                </p>
              </Link>
              {actions && (
                <div className="pr-4 pb-3">
                  <RowActions job={job} actions={actions} />
                </div>
              )}
            </div>
          </li>
        ))}
      </ul>
    </>
  )
}

/** Las etapas como filtros, con cuántas hay en cada una. Las vacías se ven, atenuadas. */
function StageFilter({ stage, onChange }: { stage: Stage | undefined; onChange: (stage: Stage | undefined) => void }) {
  const { t } = useTranslation('inbox')
  const { data } = useStatus()
  const items: { key: Stage | undefined; label: string; count?: number }[] = [
    { key: undefined, label: t('allStages'), count: data?.total },
    ...STAGES.map((s) => ({ key: s, label: STAGE_LABEL[s], count: data?.by_stage[s] })),
  ]
  return (
    <nav aria-label={t('filterStage')} className="-mx-4 mb-3 overflow-x-auto px-4 sm:mx-0 sm:px-0">
      <ul className="flex min-w-max gap-1.5">
        {items.map(({ key, label, count }) => {
          const selected = stage === key
          return (
            <li key={key ?? 'all'}>
              <button
                type="button"
                aria-pressed={selected}
                onClick={() => onChange(key)}
                className={cn(
                  'flex items-baseline gap-1.5 rounded-full border px-3 py-1 text-sm transition-colors outline-none focus-visible:ring-2 focus-visible:ring-ring',
                  selected
                    ? 'border-foreground bg-foreground text-background'
                    : 'bg-card text-foreground/80 hover:border-foreground/30',
                  !selected && !count && 'text-muted-foreground/60',
                )}
              >
                {label}
                <span className={cn('tabular text-xs', selected ? 'text-background/70' : 'text-muted-foreground')}>
                  {count ?? 0}
                </span>
              </button>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}

function TableSkeleton() {
  const { t } = useTranslation('inbox')
  return (
    <div aria-busy="true" aria-label={t('loadingJobs')} className="divide-y">
      {Array.from({ length: 6 }, (_, i) => (
        <div key={i} className="flex items-center gap-6 px-4 py-4">
          <div className="flex-1 space-y-2">
            <Skeleton className="h-4 w-[min(22rem,70%)]" />
            <Skeleton className="h-3.5 w-40" />
          </div>
          <Skeleton className="hidden h-4 w-16 md:block" />
          <Skeleton className="h-6 w-20 rounded-full" />
          <Skeleton className="hidden h-4 w-16 md:block" />
        </div>
      ))}
    </div>
  )
}

export function InboxPage() {
  const { t } = useTranslation('inbox')
  const [params, setParams] = useSearchParams()
  const stageParam = params.get('stage')
  const stage = isStage(stageParam) ? stageParam : undefined
  const page = Math.max(1, Number(params.get('page')) || 1)
  const sort = parseSort(params, stage)
  const quick = stage !== undefined && QUICK_DISCARD.includes(stage)
  const event = useJobEvent()
  // Ofertas descartadas que se ocultan ya, antes de que la API responda.
  const [hidden, setHidden] = useState<Set<number>>(() => new Set())
  const [selected, setSelected] = useState<Set<number>>(() => new Set())
  // Descartes que «Deshacer» puede devolver; se acumulan si descartas otra antes de cerrar el aviso.
  const [done, setDone] = useState<{ id: number; title: string; reason: DiscardReason }[]>([])
  const [actionError, setActionError] = useState<string | null>(null)
  const [dialogJob, setDialogJob] = useState<JobRow | null>(null)
  const [search, setSearch] = useState(params.get('q') ?? '')
  const q = useDebounced(search.trim())

  // La búsqueda vive en la URL: se puede recargar o compartir la vista.
  useEffect(() => {
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        if ((prev.get('q') ?? '') === q) return prev
        if (q) next.set('q', q)
        else next.delete('q')
        next.delete('page')
        return next
      },
      { replace: true },
    )
  }, [q, setParams])

  const { data, isPending, isError, error, refetch, isPlaceholderData } = useJobs({ stage, q, page, ...sort })

  const update = (changes: Record<string, string | null>) => {
    const next = new URLSearchParams(params)
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value)
      else next.delete(key)
    }
    setParams(next)
  }

  // El orden vive en la URL, como el filtro; el de por defecto no se escribe.
  const setSort = (next: Sort) => {
    const isDefault = next.sort === DEFAULT_SORT.sort && next.dir === DEFAULT_SORT.dir
    update({ sort: isDefault ? null : next.sort, dir: isDefault ? null : next.dir, page: null })
  }

  const total = data?.total ?? 0
  const filtered = Boolean(stage || q)
  const visible = (data?.items ?? []).filter((job) => !hidden.has(job.id))
  const picked = quick ? visible.filter((job) => selected.has(job.id)) : []

  /**
   * Oculta las ofertas ya y las descarta una a una (SQLite no agradece escrituras a la vez). Las
   * que fallan vuelven a la tabla con un aviso; las demás se pueden deshacer.
   */
  const discard = async (targets: JobRow[], choice: DiscardChoice) => {
    const ids = targets.map((job) => job.id)
    setHidden((prev) => new Set([...prev, ...ids]))
    setSelected((prev) => without(prev, ids))
    setActionError(null)
    const discarded: JobRow[] = []
    let failure: unknown = null
    for (const job of targets) {
      try {
        await event.mutateAsync({
          jobId: job.id,
          body: { type: 'discarded', reason: choice.reason, note: choice.note },
        })
        discarded.push(job)
      } catch (err) {
        failure = err
        setHidden((prev) => without(prev, [job.id]))
      }
    }
    if (failure) setActionError(errorMessage(failure))
    if (discarded.length) {
      const added = discarded.map(({ id, title }) => ({ id, title, reason: choice.reason }))
      setDone((prev) => [...prev, ...added])
    }
  }

  /** Reabre lo descartado; las que fallan siguen en el aviso para reintentarlo. */
  const undo = async () => {
    const pending = done
    setActionError(null)
    for (const item of pending) {
      try {
        await event.mutateAsync({ jobId: item.id, body: { type: 'reopened' } })
        setHidden((prev) => without(prev, [item.id]))
        setDone((prev) => prev.filter((d) => d.id !== item.id))
      } catch (err) {
        setActionError(errorMessage(err))
      }
    }
  }
  const doneReasons = new Set(done.map((d) => d.reason))

  const actions: QuickActions | undefined = quick
    ? {
        openable: stage === 'pending_detail',
        selected,
        onToggle: (id) =>
          setSelected((prev) => (prev.has(id) ? without(prev, [id]) : new Set(prev).add(id))),
        onToggleAll: () =>
          setSelected(picked.length === visible.length ? new Set() : new Set(visible.map((job) => job.id))),
        onDiscard: (job) => void discard([job], { reason: QUICK_REASON }),
        onDiscardWith: setDialogJob,
      }
    : undefined

  return (
    <div className="animate-in fade-in duration-300">
      <div className="mb-6 flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">
          {stage ? STAGE_LABEL[stage] : t('title')}
        </h1>
        <p className="text-sm text-muted-foreground">
          {isPending ? t('loading', { ns: 'common' }) : t('count', { count: total })}
          {q && t('matching', { q })}
        </p>
      </div>

      <StageFilter stage={stage} onChange={(next) => update({ stage: next ?? null, page: null })} />

      <div className="mb-4 flex flex-col gap-2 sm:flex-row">
        <div className="relative flex-1">
          <MagnifyingGlassIcon className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="search"
            aria-label={t('search')}
            placeholder={t('search')}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="h-10 bg-card pl-9"
          />
        </div>
        <Select
          value={`${sort.sort}:${sort.dir}`}
          onValueChange={(value) => {
            const [field, dir] = value.split(':')
            setSort({ sort: field as JobSort, dir: dir as SortDirection })
          }}
        >
          <SelectTrigger aria-label={t('sortLabel')} className="h-10 w-full bg-card data-[size=default]:h-10 md:hidden">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {SORT_OPTIONS.filter((option) => sortsFor(stage).includes(option.value.split(':')[0] as JobSort)).map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {t(`sort.${option.label}`)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="mb-4 space-y-3 empty:hidden">
        {done.length > 0 && (
          <div role="status" className="flex items-center gap-3 rounded-xl border bg-card px-4 py-2.5 text-sm animate-in fade-in slide-in-from-top-1">
            <ProhibitIcon className="size-[18px] shrink-0 text-muted-foreground" />
            <p className="min-w-0 flex-1 truncate">
              {done.length === 1 ? (
                <>
                  {t('quick.discarded')} <span className="font-medium">{done[0].title}</span>
                </>
              ) : (
                t('quick.discardedMany', { count: done.length })
              )}
              {doneReasons.size === 1 && (
                <span className="text-muted-foreground"> · {discardReasonLabel(done[0].reason)}</span>
              )}
            </p>
            <Button variant="ghost" size="xs" onClick={() => void undo()}>
              {t('quick.undo')}
            </Button>
            <button
              type="button"
              onClick={() => setDone([])}
              className="text-muted-foreground hover:text-foreground"
              aria-label={t('quick.closeNotice')}
            >
              <XIcon className="size-4" />
            </button>
          </div>
        )}
        {actionError && (
          <p role="alert" className="rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-2.5 text-sm">
            {t('quick.failed', { error: actionError })}
          </p>
        )}
        {picked.length > 0 && (
          <div className="flex items-center gap-3 rounded-xl border bg-card px-4 py-2 text-sm">
            <p className="flex-1 tabular">{t('quick.selectedCount', { count: picked.length })}</p>
            <Button variant="ghost" size="sm" onClick={() => setSelected(new Set())}>
              {t('quick.clearSelection')}
            </Button>
            <Button size="sm" onClick={() => void discard(picked, { reason: QUICK_REASON })}>
              <ProhibitIcon />
              {t('quick.discardMany', { count: picked.length })}
            </Button>
          </div>
        )}
      </div>

      <section
        className={cn(
          'overflow-hidden rounded-xl border bg-card shadow-[0_1px_2px_oklch(0.2_0.02_250/0.04)] transition-opacity',
          isPlaceholderData && 'opacity-60',
        )}
      >
        {isPending ? (
          <TableSkeleton />
        ) : isError ? (
          <ErrorState error={error} onRetry={() => refetch()} className="m-4 border-0" />
        ) : data.items.length === 0 ? (
          filtered ? (
            <EmptyState
              icon={<MagnifyingGlassIcon className="size-6" weight="duotone" />}
              title={t('noResults.title')}
              action={
                <Button
                  variant="outline"
                  onClick={() => {
                    setSearch('')
                    setParams(new URLSearchParams())
                  }}
                >
                  <XIcon />
                  {t('noResults.clear')}
                </Button>
              }
            >
              {t('noResults.body')}
            </EmptyState>
          ) : (
            <EmptyState
              icon={<TrayIcon className="size-6" weight="duotone" />}
              title={t('empty.title')}
              action={
                <Button asChild>
                  <Link to="/nueva">
                    <PlusIcon weight="bold" />
                    {t('empty.addFirst')}
                  </Link>
                </Button>
              }
            >
              <Trans
                t={t}
                i18nKey="empty.body"
                components={{ code: <code className="font-mono text-foreground" /> }}
              />
            </EmptyState>
          )
        ) : (
          <div className="pt-3 md:pt-4">
            <JobTable
              jobs={visible}
              sort={sort}
              onSort={setSort}
              closedView={stage === 'closed'}
              actions={actions}
            />
          </div>
        )}
      </section>

      <DiscardDialog
        open={dialogJob !== null}
        onOpenChange={(open) => !open && setDialogJob(null)}
        jobTitle={dialogJob?.title ?? ''}
        onConfirm={(choice) => {
          if (dialogJob) void discard([dialogJob], choice)
          setDialogJob(null)
        }}
      />

      <Pager
        page={page}
        total={total}
        pageSize={PAGE_SIZE}
        onPage={(next) => update({ page: next > 1 ? String(next) : null })}
        className="mt-4"
      />
    </div>
  )
}
