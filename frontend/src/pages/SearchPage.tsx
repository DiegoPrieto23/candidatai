import { useState } from 'react'
import { Trans, useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { ArrowRightIcon, CaretRightIcon, CompassIcon, MagnifyingGlassIcon } from '@phosphor-icons/react'
import type { SourceView } from '@/api/client'
import { useJobs, usePlatforms } from '@/api/queries'
import { AgentButton } from '@/components/AgentButton'
import { ScoreBadge } from '@/components/MatchDetails'
import { EmptyState, ErrorState } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { formatWhen } from '@/lib/time'

const RECENT = 8
/** Lo mismo que admite el servidor: esto acaba en la orden que abre una terminal. */
const SAFE_TEXT = /^[\p{L}\p{N}_ .,+#/&()-]*$/u

function PlatformChoice({
  source,
  checked,
  onChange,
}: {
  source: SourceView
  checked: boolean
  onChange: (checked: boolean) => void
}) {
  const { t } = useTranslation('search')
  const run = source.last_run
  return (
    <li>
      <label className="flex cursor-pointer items-center gap-3 px-4 py-3 hover:bg-foreground/[0.03]">
        <input
          type="checkbox"
          className="size-4 shrink-0 accent-primary"
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
        />
        <span className="min-w-0 flex-1 truncate text-sm font-medium">{source.name}</span>
        <span className="shrink-0 text-xs text-muted-foreground">
          {source.last_run_at ? formatWhen(source.last_run_at, false) : t('never')}
        </span>
        <span className="tabular w-20 shrink-0 text-right text-xs text-muted-foreground">
          {run ? t('created', { count: run.created }) : ''}
        </span>
      </label>
    </li>
  )
}

/** Lo último que ha dado de alta tu agente desde los portales. */
function Recent() {
  const { t } = useTranslation('search')
  const jobs = useJobs({ page: 1, sort: 'date', dir: 'desc', source_kind: 'agent_browse' }, { refetchInterval: 30_000 })
  const rows = jobs.data?.items.slice(0, RECENT) ?? []
  return (
    <section aria-labelledby="search-recent" className="mt-10">
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <h2 id="search-recent" className="font-medium">
          {t('recent.title')}
        </h2>
        <Link to="/bandeja" className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
          {t('recent.all')}
          <ArrowRightIcon className="size-3" />
        </Link>
      </div>
      {jobs.isPending ? (
        <Skeleton className="h-24" />
      ) : jobs.isError ? (
        <ErrorState error={jobs.error} onRetry={() => jobs.refetch()} />
      ) : rows.length === 0 ? (
        <p className="rounded-xl border border-dashed px-4 py-6 text-center text-sm text-muted-foreground">{t('recent.empty')}</p>
      ) : (
        <ul className="divide-y rounded-xl border bg-card">
          {rows.map((job) => (
            <li key={job.id}>
              <Link to={`/jobs/${job.id}`} className="flex items-center gap-3 px-4 py-2.5 text-sm hover:bg-foreground/[0.03]">
                <span className="min-w-0 flex-1 truncate">
                  <span className="font-medium">{job.title}</span>
                  <span className="text-muted-foreground"> · {job.company}</span>
                </span>
                {job.score != null && <ScoreBadge score={job.score} className="shrink-0" />}
                <CaretRightIcon className="size-3.5 shrink-0 text-muted-foreground" aria-hidden />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

/**
 * «Buscar ofertas»: elegir portales, afinar si hace falta y lanzar a tu agente. La búsqueda la hace
 * él, con tu navegador y en su ventana: aquí solo se lanza y se ve qué va entrando.
 */
export function SearchPage() {
  const { t } = useTranslation('search')
  const platforms = usePlatforms()
  // Se guarda lo que quitas, no lo que eliges: un portal nuevo entra marcado.
  const [skipped, setSkipped] = useState<ReadonlySet<number>>(new Set())
  const [role, setRole] = useState('')
  const [location, setLocation] = useState('')

  const sources = platforms.data?.sources ?? []
  const usable = sources.filter((s) => s.active && s.browse?.allow_agent_browsing)
  const unusable = sources.length - usable.length
  const chosen = usable.filter((s) => !skipped.has(s.id))
  const badRole = !SAFE_TEXT.test(role)
  const badLocation = !SAFE_TEXT.test(location)
  const search = {
    // Todos: la orden normal, «las plataformas activas».
    platform_ids: chosen.length === usable.length ? [] : chosen.map((s) => s.id),
    role: role.trim() || undefined,
    location: location.trim() || undefined,
  }

  let body
  if (platforms.isPending) {
    body = <Skeleton className="h-40" />
  } else if (platforms.isError) {
    body = <ErrorState error={platforms.error} onRetry={() => platforms.refetch()} />
  } else if (usable.length === 0) {
    body = (
      <EmptyState
        icon={<CompassIcon className="size-6" weight="duotone" />}
        title={t('empty.title')}
        action={
          <div className="flex flex-wrap justify-center gap-2">
            <AgentButton action="configure-platforms" primary>
              {t('empty.configure')}
            </AgentButton>
            <Button asChild variant="outline" size="sm">
              <Link to="/fuentes/plataformas">{t('empty.manage')}</Link>
            </Button>
          </div>
        }
      >
        {t('empty.body')}
      </EmptyState>
    )
  } else {
    body = (
      <>
        <ul aria-label={t('platforms')} className="divide-y rounded-xl border bg-card">
          {usable.map((source) => (
            <PlatformChoice
              key={source.id}
              source={source}
              checked={!skipped.has(source.id)}
              onChange={(checked) =>
                setSkipped((current) => {
                  const next = new Set(current)
                  if (checked) next.delete(source.id)
                  else next.add(source.id)
                  return next
                })
              }
            />
          ))}
        </ul>
        {unusable > 0 && (
          <p className="mt-2 text-xs text-muted-foreground">
            <Trans
              t={t}
              i18nKey="unusable"
              count={unusable}
              components={{ to: <Link to="/fuentes/plataformas" className="underline underline-offset-4" /> }}
            />
          </p>
        )}

        <Collapsible className="mt-4">
          <CollapsibleTrigger className="group inline-flex items-center gap-1.5 rounded-sm text-sm font-medium text-muted-foreground outline-none hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50">
            <CaretRightIcon className="size-3.5 transition-transform group-data-[state=open]:rotate-90" aria-hidden />
            {t('refine.toggle')}
          </CollapsibleTrigger>
          <CollapsibleContent className="mt-3 grid gap-3 rounded-xl border bg-card p-4">
            <p className="text-sm text-muted-foreground">{t('refine.hint')}</p>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="grid content-start gap-1.5">
                <Label htmlFor="search-role">{t('refine.role')}</Label>
                <Input
                  id="search-role"
                  value={role}
                  maxLength={80}
                  aria-invalid={badRole}
                  placeholder={t('refine.rolePlaceholder')}
                  onChange={(e) => setRole(e.target.value)}
                />
              </div>
              <div className="grid content-start gap-1.5">
                <Label htmlFor="search-location">{t('refine.location')}</Label>
                <Input
                  id="search-location"
                  value={location}
                  maxLength={80}
                  aria-invalid={badLocation}
                  placeholder={t('refine.locationPlaceholder')}
                  onChange={(e) => setLocation(e.target.value)}
                />
              </div>
            </div>
            {(badRole || badLocation) && (
              <p role="alert" className="text-xs text-destructive">
                {t('refine.badText')}
              </p>
            )}
          </CollapsibleContent>
        </Collapsible>

        <div className="mt-5 flex flex-wrap items-center justify-end gap-3">
          {chosen.length === 0 && <p className="text-xs text-muted-foreground">{t('noneChosen')}</p>}
          <AgentButton
            action="search-jobs"
            primary
            size="default"
            search={search}
            disabled={chosen.length === 0 || badRole || badLocation}
          >
            {t('searchNow')}
          </AgentButton>
        </div>
      </>
    )
  }

  return (
    <div className="mx-auto max-w-3xl animate-in fade-in duration-300">
      <div className="mb-6">
        <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
          <MagnifyingGlassIcon className="size-6 text-muted-foreground" aria-hidden />
          {t('title')}
        </h1>
        <p className="mt-1.5 max-w-[65ch] text-sm leading-relaxed text-muted-foreground">{t('intro')}</p>
      </div>
      {body}
      <Recent />
      <p className="mt-6 text-xs text-muted-foreground">
        <Trans t={t} i18nKey="others" components={{ to: <Link to="/fuentes" className="underline underline-offset-4" /> }} />
      </p>
    </div>
  )
}
