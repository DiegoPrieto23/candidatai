import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import {
  ArrowDownIcon,
  ArrowLeftIcon,
  ArrowRightIcon,
  ArrowsDownUpIcon,
  ArrowUpIcon,
  MagnifyingGlassIcon,
  PlusIcon,
  TrayIcon,
  WarningIcon,
  XIcon,
} from '@phosphor-icons/react'
import type { JobRow, Stage } from '@/api/client'
import { type JobSort, PAGE_SIZE, type SortDirection, useJobs } from '@/api/queries'
import { SignalBadges } from '@/components/JobSignals'
import { ScoreBadge } from '@/components/MatchDetails'
import { StageBadge } from '@/components/StageBadge'
import { EmptyState, ErrorState } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { formatDate, formatRelative, formatSalary, REMOTE_LABEL, STAGE_LABEL, STAGES } from '@/lib/labels'
import { cn } from '@/lib/utils'

function isStage(value: string | null): value is Stage {
  return value !== null && (STAGES as readonly string[]).includes(value)
}

interface Sort {
  sort: JobSort
  dir: SortDirection
}

const SORTS: readonly JobSort[] = ['date', 'score', 'salary']
const DEFAULT_SORT: Sort = { sort: 'date', dir: 'desc' }

function parseSort(params: URLSearchParams): Sort {
  const sort = params.get('sort')
  if (!sort || !(SORTS as readonly string[]).includes(sort)) return DEFAULT_SORT
  return { sort: sort as JobSort, dir: params.get('dir') === 'asc' ? 'asc' : 'desc' }
}

/** Para el selector del móvil, donde no hay cabeceras. */
const SORT_OPTIONS: { value: string; label: string }[] = [
  { value: 'date:desc', label: 'Más recientes' },
  { value: 'date:asc', label: 'Más antiguas' },
  { value: 'score:desc', label: 'Más encaje' },
  { value: 'score:asc', label: 'Menos encaje' },
  { value: 'salary:desc', label: 'Más salario' },
  { value: 'salary:asc', label: 'Menos salario' },
]

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
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="inline-flex text-warning-foreground" aria-label="Posible contenido dirigido a una IA">
          <WarningIcon className="size-4" weight="fill" />
        </span>
      </TooltipTrigger>
      <TooltipContent>Posible contenido dirigido a una IA</TooltipContent>
    </Tooltip>
  )
}

function RemoteMode({ mode }: { mode: JobRow['remote_mode'] }) {
  if (!mode) return <span className="text-muted-foreground/60">Sin extraer</span>
  return <span className={cn(mode === 'unknown' && 'text-muted-foreground')}>{REMOTE_LABEL[mode]}</span>
}

function Salary({ salary }: { salary: JobRow['salary'] }) {
  const text = formatSalary(salary)
  if (!text) return <span className="text-muted-foreground/60">No lo indica</span>
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

function JobTable({ jobs, sort, onSort }: { jobs: JobRow[]; sort: Sort; onSort: (sort: Sort) => void }) {
  const navigate = useNavigate()
  return (
    <>
      {/* Escritorio: tabla */}
      <table className="hidden w-full text-sm md:table">
        <thead>
          <tr className="text-left text-xs text-muted-foreground">
            <th className="pb-3 pl-4 font-medium">Oferta</th>
            <th className="pb-3 font-medium">Modalidad</th>
            <SortHeader field="salary" current={sort} onSort={onSort}>
              Salario
            </SortHeader>
            <SortHeader field="score" current={sort} onSort={onSort} className="pr-6 text-right">
              Encaje
            </SortHeader>
            <th className="pb-3 font-medium">Etapa</th>
            <SortHeader field="date" current={sort} onSort={onSort} className="pr-4 text-right">
              Alta
            </SortHeader>
          </tr>
        </thead>
        <tbody className="divide-y">
          {jobs.map((job) => (
            <tr
              key={job.id}
              onClick={() => navigate(`/jobs/${job.id}`)}
              className="group cursor-pointer transition-colors hover:bg-foreground/[0.025]"
            >
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
                <ScoreBadge score={job.score} />
              </td>
              <td className="py-3.5 pr-6">
                <StageBadge stage={job.stage} />
              </td>
              <td className="py-3.5 pr-4 text-right whitespace-nowrap text-muted-foreground">
                <time dateTime={job.first_seen_at} title={formatDate(job.first_seen_at)}>
                  {formatRelative(job.first_seen_at)}
                </time>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Móvil: lista */}
      <ul className="divide-y md:hidden">
        {jobs.map((job) => (
          <li key={job.id}>
            <Link to={`/jobs/${job.id}`} className="block px-4 py-4 active:bg-foreground/[0.03]">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="flex items-center gap-1.5 font-medium">
                    <span className="truncate">{job.title}</span>
                    {job.risk_flags.length > 0 && (
                      <WarningIcon className="size-4 shrink-0 text-warning-foreground" weight="fill" />
                    )}
                    <SignalBadges signals={job.signals} />
                  </p>
                  <p className="truncate text-sm text-muted-foreground">{job.company}</p>
                </div>
                <StageBadge stage={job.stage} />
              </div>
              <p className="mt-2 flex gap-3 text-xs text-muted-foreground">
                {job.score != null && <span className="tabular font-medium text-foreground">{job.score}/100</span>}
                <RemoteMode mode={job.remote_mode} />
                {job.salary && <Salary salary={job.salary} />}
                <time dateTime={job.first_seen_at}>{formatRelative(job.first_seen_at)}</time>
              </p>
            </Link>
          </li>
        ))}
      </ul>
    </>
  )
}

function TableSkeleton() {
  return (
    <div aria-busy="true" aria-label="Cargando ofertas" className="divide-y">
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
  const [params, setParams] = useSearchParams()
  const stageParam = params.get('stage')
  const stage = isStage(stageParam) ? stageParam : undefined
  const page = Math.max(1, Number(params.get('page')) || 1)
  const sort = parseSort(params)
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
  const from = total ? (page - 1) * PAGE_SIZE + 1 : 0
  const to = Math.min(page * PAGE_SIZE, total)
  const filtered = Boolean(stage || q)

  return (
    <div className="animate-in fade-in duration-300">
      <div className="mb-6 flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">
          {stage ? STAGE_LABEL[stage] : 'Bandeja'}
        </h1>
        <p className="text-sm text-muted-foreground">
          {isPending ? 'Cargando…' : total === 1 ? '1 oferta' : `${total} ofertas`}
          {q && <> que coinciden con «{q}»</>}
        </p>
      </div>

      <div className="mb-4 flex flex-col gap-2 sm:flex-row">
        <div className="relative flex-1">
          <MagnifyingGlassIcon className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="search"
            aria-label="Buscar por título o empresa"
            placeholder="Buscar por título o empresa"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="h-10 bg-card pl-9"
          />
        </div>
        <Select
          value={stage ?? 'all'}
          onValueChange={(value) => update({ stage: value === 'all' ? null : value, page: null })}
        >
          <SelectTrigger aria-label="Filtrar por etapa" className="h-10 w-full bg-card data-[size=default]:h-10 sm:w-48">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todas las etapas</SelectItem>
            {STAGES.map((s) => (
              <SelectItem key={s} value={s}>
                {STAGE_LABEL[s]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select
          value={`${sort.sort}:${sort.dir}`}
          onValueChange={(value) => {
            const [field, dir] = value.split(':')
            setSort({ sort: field as JobSort, dir: dir as SortDirection })
          }}
        >
          <SelectTrigger aria-label="Ordenar" className="h-10 w-full bg-card data-[size=default]:h-10 md:hidden">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {SORT_OPTIONS.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
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
              title="Nada por aquí"
              action={
                <Button
                  variant="outline"
                  onClick={() => {
                    setSearch('')
                    setParams(new URLSearchParams())
                  }}
                >
                  <XIcon />
                  Quitar filtros
                </Button>
              }
            >
              Ninguna oferta coincide con estos filtros.
            </EmptyState>
          ) : (
            <EmptyState
              icon={<TrayIcon className="size-6" weight="duotone" />}
              title="Tu bandeja está vacía"
              action={
                <Button asChild>
                  <Link to="/nueva">
                    <PlusIcon weight="bold" />
                    Añadir la primera
                  </Link>
                </Button>
              }
            >
              Da de alta una oferta desde su URL o pegando el texto. Después, tu agente la extrae con
              el skill <code className="font-mono text-foreground">procesar-ofertas</code>.
            </EmptyState>
          )
        ) : (
          <div className="pt-3 md:pt-4">
            <JobTable jobs={data.items} sort={sort} onSort={setSort} />
          </div>
        )}
      </section>

      {total > PAGE_SIZE && (
        <div className="mt-4 flex items-center justify-between text-sm text-muted-foreground">
          <span className="tabular">
            {from}-{to} de {total}
          </span>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => update({ page: page > 2 ? String(page - 1) : null })}
            >
              <ArrowLeftIcon />
              Anteriores
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={to >= total}
              onClick={() => update({ page: String(page + 1) })}
            >
              Siguientes
              <ArrowRightIcon />
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
