import { useMemo, useState, type FormEvent, type ReactNode } from 'react'
import { Link } from 'react-router'
import { CheckCircleIcon, EqualsIcon, ProhibitIcon, PuzzlePieceIcon, UserCircleIcon } from '@phosphor-icons/react'
import { ApiError } from '@/api/client'
import { useAddSkillAlias, useSetSkillMark, useSkillGaps, type SkillGap, type SkillMark } from '@/api/queries'
import { AgentButton } from '@/components/AgentButton'
import { EmptyState, ErrorState, InlineCode } from '@/components/States'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { LEVEL_LABEL } from '@/lib/labels'
import { cn } from '@/lib/utils'

type Kind = 'all' | 'must' | 'nice'
type MarkFilter = 'all' | 'unmarked' | SkillMark
type Sort = 'jobs' | 'weight'
type ProfileSkill = { name: string; level: keyof typeof LEVEL_LABEL }

const PERIODS = [30, 60, 90, 180] as const
const KINDS: { id: Kind; label: string }[] = [
  { id: 'all', label: 'Todas' },
  { id: 'must', label: 'Obligatorias' },
  { id: 'nice', label: 'Deseables' },
]
const MARK_FILTERS: { id: MarkFilter; label: string }[] = [
  { id: 'all', label: 'Todas' },
  { id: 'unmarked', label: 'Sin decidir' },
  { id: 'gap', label: 'No la tengo' },
  { id: 'have', label: 'La tengo' },
]
const weightFmt = new Intl.NumberFormat('es-ES', { maximumFractionDigits: 2 })

function Segmented<T extends string | number>({
  label,
  options,
  value,
  onChange,
}: {
  label: string
  options: readonly { id: T; label: string }[]
  value: T
  onChange: (id: T) => void
}) {
  return (
    <div role="group" aria-label={label} className="inline-flex rounded-lg border bg-card p-0.5">
      {options.map((o) => (
        <Button
          key={o.id}
          size="sm"
          variant="ghost"
          aria-pressed={value === o.id}
          className={cn('h-7 px-2.5', value === o.id && 'bg-secondary font-medium')}
          onClick={() => onChange(o.id)}
        >
          {o.label}
        </Button>
      ))}
    </div>
  )
}

function countFor(gap: SkillGap, kind: Kind): number {
  if (kind === 'must') return gap.must_have_count
  if (kind === 'nice') return gap.nice_to_have_count
  return gap.jobs_count
}

// --- «Es lo mismo que…» ---------------------------------------------------------------------

function AliasDialog({
  gap,
  profileSkills,
  onClose,
  onDone,
}: {
  gap: SkillGap | null
  profileSkills: ProfileSkill[]
  onClose: () => void
  onDone: (message: string) => void
}) {
  return (
    <Dialog open={gap !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        {gap && <AliasForm gap={gap} profileSkills={profileSkills} onCancel={onClose} onDone={onDone} />}
      </DialogContent>
    </Dialog>
  )
}

function AliasForm({
  gap,
  profileSkills,
  onCancel,
  onDone,
}: {
  gap: SkillGap
  profileSkills: ProfileSkill[]
  onCancel: () => void
  onDone: (message: string) => void
}) {
  const [query, setQuery] = useState('')
  const [chosen, setChosen] = useState<string | null>(null)
  const addAlias = useAddSkillAlias()
  const fold = (s: string) => s.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase()
  const visible = profileSkills.filter((s) => fold(s.name).includes(fold(query.trim())))

  const submit = (e?: FormEvent) => {
    e?.preventDefault()
    if (!chosen || addAlias.isPending) return
    addAlias.mutate(
      { skill: gap.skill, profile_skill: chosen },
      {
        onSuccess: (result) =>
          onDone(
            result.added
              ? `«${result.skill}» cuenta ya como «${result.profile_skill}». El score de las ofertas se recalcula en segundo plano.`
              : `«${result.skill}» ya contaba como «${result.profile_skill}».`,
          ),
      },
    )
  }

  return (
    <form onSubmit={submit} className="grid gap-5">
      <DialogHeader>
        <DialogTitle>«{gap.skill}» es lo mismo que…</DialogTitle>
        <DialogDescription>
          Elige la skill de tu perfil que significa lo mismo. Se añade como sinónimo en{' '}
          <code className="font-mono text-[0.85em]">config/skill_aliases.yaml</code> y se recalcula el score de tus
          ofertas.
        </DialogDescription>
      </DialogHeader>

      <div className="grid gap-2">
        <Input
          aria-label="Buscar en tu perfil"
          placeholder="Buscar en tu perfil"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="bg-background"
        />
        <div role="radiogroup" aria-label="Skills de tu perfil" className="grid max-h-64 gap-1 overflow-y-auto pr-1">
          {visible.map((s) => {
            const selected = chosen === s.name
            return (
              <button
                key={s.name}
                type="button"
                role="radio"
                aria-checked={selected}
                onClick={() => setChosen(s.name)}
                className={cn(
                  'flex items-center justify-between gap-3 rounded-md border px-3 py-2 text-left text-sm transition-colors outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50',
                  selected ? 'border-primary/40 bg-accent text-accent-foreground' : 'border-input hover:bg-foreground/[0.03]',
                )}
              >
                <span>{s.name}</span>
                <span className="text-xs text-muted-foreground">{LEVEL_LABEL[s.level]}</span>
              </button>
            )
          })}
          {visible.length === 0 && <p className="px-1 py-2 text-sm text-muted-foreground">Ninguna skill de tu perfil coincide.</p>}
        </div>
      </div>

      {addAlias.error && (
        <p role="alert" className="text-sm text-destructive">
          {addAlias.error.message}
        </p>
      )}

      <DialogFooter>
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancelar
        </Button>
        <Button type="submit" disabled={!chosen || addAlias.isPending}>
          {addAlias.isPending ? 'Guardando…' : 'Son lo mismo'}
        </Button>
      </DialogFooter>
    </form>
  )
}

// --- Tabla ------------------------------------------------------------------------------------

function MarkButton({
  gap,
  status,
  children,
  icon,
}: {
  gap: SkillGap
  status: SkillMark
  children: string
  icon: ReactNode
}) {
  const setMark = useSetSkillMark()
  const active = gap.mark === status
  return (
    <Button
      type="button"
      size="sm"
      variant="ghost"
      aria-pressed={active}
      disabled={setMark.isPending}
      title={active ? 'Quitar la marca' : undefined}
      className={cn('h-7 px-2', active && 'bg-secondary font-medium text-foreground')}
      onClick={() => setMark.mutate({ skill: gap.skill, status: active ? null : status })}
    >
      {icon}
      {children}
    </Button>
  )
}

function GapRow({ gap, kind, onAlias }: { gap: SkillGap; kind: Kind; onAlias: (gap: SkillGap) => void }) {
  return (
    <tr className="border-t align-top">
      <th scope="row" className="py-3 pr-4 text-left font-medium">
        {gap.skill}
        {gap.jobs_count === 0 && (
          <span className="block text-xs font-normal text-muted-foreground">Ya no la pide ninguna oferta del periodo</span>
        )}
      </th>
      <td className="tabular py-3 pr-4 whitespace-nowrap">
        <span className="font-medium">{countFor(gap, kind)}</span>
        {kind === 'all' && gap.jobs_count > 0 && (
          <span className="block text-xs text-muted-foreground">
            {gap.must_have_count} oblig. · {gap.nice_to_have_count} des.
          </span>
        )}
      </td>
      <td className="tabular py-3 pr-4">{weightFmt.format(gap.weight)}</td>
      <td className="hidden py-3 pr-4 md:table-cell">
        <ul className="space-y-0.5 text-xs text-muted-foreground">
          {gap.examples.map((e) => (
            <li key={e.job_id} className="max-w-64 truncate">
              <Link to={`/jobs/${e.job_id}`} className="hover:text-foreground hover:underline">
                {e.title} · {e.company}
              </Link>
              {e.score != null && <span className="tabular"> · {e.score}</span>}
            </li>
          ))}
        </ul>
      </td>
      <td className="py-2.5">
        <div className="flex flex-wrap gap-1" role="group" aria-label={`Acciones para ${gap.skill}`}>
          <Button type="button" size="sm" variant="outline" className="h-7 px-2" onClick={() => onAlias(gap)}>
            <EqualsIcon />
            Es lo mismo que…
          </Button>
          <MarkButton gap={gap} status="have" icon={<CheckCircleIcon />}>
            La tengo
          </MarkButton>
          <MarkButton gap={gap} status="gap" icon={<ProhibitIcon />}>
            No la tengo
          </MarkButton>
        </div>
      </td>
    </tr>
  )
}

// --- Página -----------------------------------------------------------------------------------

export function SkillsPage() {
  const [days, setDays] = useState<number>(60)
  const [kind, setKind] = useState<Kind>('all')
  const [markFilter, setMarkFilter] = useState<MarkFilter>('all')
  const [sort, setSort] = useState<Sort>('jobs')
  const [aliasFor, setAliasFor] = useState<SkillGap | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const { data, isPending, error, refetch } = useSkillGaps(days)

  const rows = useMemo(() => {
    const gaps = (data?.gaps ?? []).filter((g) => {
      if (kind !== 'all' && countFor(g, kind) === 0 && g.jobs_count > 0) return false
      if (markFilter === 'unmarked') return g.mark === null
      if (markFilter !== 'all') return g.mark === markFilter
      return true
    })
    return [...gaps].sort((a, b) =>
      sort === 'weight'
        ? b.weight - a.weight || countFor(b, kind) - countFor(a, kind)
        : countFor(b, kind) - countFor(a, kind) || b.weight - a.weight,
    )
  }, [data, kind, markFilter, sort])

  const marked = (status: SkillMark) => data?.gaps.filter((g) => g.mark === status).length ?? 0

  if (error instanceof ApiError && error.type === 'not_found') {
    return (
      <EmptyState icon={<UserCircleIcon className="size-6" weight="duotone" />} title="Aún no tienes perfil">
        <InlineCode text="Los huecos se calculan frente a tu perfil. Créalo con el skill `actualizar-perfil`." />
      </EmptyState>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Skills</h1>
          <p className="mt-1 max-w-[68ch] text-sm text-muted-foreground">
            Lo que piden tus ofertas y tu perfil no cubre. Muchas veces es vocabulario: si es lo mismo que una skill tuya,
            dilo y el score se recalcula. Si la tienes, añádela al perfil; si no, va a tu plan de formación.
          </p>
        </div>
        <div className="flex flex-wrap items-start gap-2">
          {marked('have') > 0 && (
            <AgentButton action="anadir-skills">
              Añadir al perfil las que tengo ({marked('have')})
            </AgentButton>
          )}
          <AgentButton action="plan-formacion" variant={marked('gap') > 0 ? 'default' : 'outline'}>
            Plan de formación
          </AgentButton>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Segmented
          label="Periodo"
          options={PERIODS.map((d) => ({ id: d, label: `${d} días` }))}
          value={days}
          onChange={setDays}
        />
        <Segmented label="Tipo" options={KINDS} value={kind} onChange={setKind} />
        <Segmented label="Marca" options={MARK_FILTERS} value={markFilter} onChange={setMarkFilter} />
      </div>

      {notice && (
        <p role="status" className="rounded-lg border border-primary/20 bg-accent/60 px-4 py-2.5 text-sm text-accent-foreground">
          {notice}
        </p>
      )}

      {isPending ? (
        <Skeleton className="h-72 rounded-xl" />
      ) : error ? (
        <ErrorState error={error} onRetry={() => void refetch()} />
      ) : data.gaps.length === 0 ? (
        <EmptyState icon={<PuzzlePieceIcon className="size-6" weight="duotone" />} title="Tu perfil cubre lo que piden tus ofertas">
          Sin skills ausentes en {data.jobs_considered} ofertas (abiertas y aprobadas o enviadas en los últimos {data.days}{' '}
          días).
        </EmptyState>
      ) : (
        <section aria-label="Skills ausentes" className="rounded-xl border bg-card p-5 sm:p-6">
          <p className="text-sm text-muted-foreground">
            {data.gaps.length} skills ausentes en {data.jobs_considered} ofertas: las abiertas y las aprobadas o enviadas en
            los últimos {data.days} días. El peso suma 1 por oferta que la pide como obligatoria y 0,5 como deseable, por
            el score de la oferta.
          </p>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full min-w-[36rem] text-sm" aria-label="Skills ausentes por frecuencia">
              <thead>
                <tr className="text-left text-xs text-muted-foreground">
                  <th scope="col" className="pb-2 pr-4 font-medium">
                    Skill
                  </th>
                  <th scope="col" className="pb-2 pr-4 font-medium" aria-sort={sort === 'jobs' ? 'descending' : 'none'}>
                    <button type="button" className="hover:text-foreground" onClick={() => setSort('jobs')}>
                      Ofertas{sort === 'jobs' && ' ↓'}
                    </button>
                  </th>
                  <th scope="col" className="pb-2 pr-4 font-medium" aria-sort={sort === 'weight' ? 'descending' : 'none'}>
                    <button type="button" className="hover:text-foreground" onClick={() => setSort('weight')}>
                      Peso{sort === 'weight' && ' ↓'}
                    </button>
                  </th>
                  <th scope="col" className="hidden pb-2 pr-4 font-medium md:table-cell">
                    Ejemplos
                  </th>
                  <th scope="col" className="pb-2 font-medium">
                    <span className="sr-only">Acciones</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((gap) => (
                  <GapRow key={gap.key} gap={gap} kind={kind} onAlias={setAliasFor} />
                ))}
              </tbody>
            </table>
            {rows.length === 0 && <p className="py-6 text-center text-sm text-muted-foreground">Ninguna con este filtro.</p>}
          </div>
        </section>
      )}

      <AliasDialog
        gap={aliasFor}
        profileSkills={data?.profile_skills ?? []}
        onClose={() => setAliasFor(null)}
        onDone={(message) => {
          setAliasFor(null)
          setNotice(message)
        }}
      />
    </div>
  )
}
