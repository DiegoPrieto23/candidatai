import { useState } from 'react'
import { Trans, useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import {
  ArrowsClockwiseIcon,
  BrowserIcon,
  CaretRightIcon,
  CheckIcon,
  CompassIcon,
  KeyIcon,
} from '@phosphor-icons/react'
import type { SourceView } from '@/api/client'
import { useEditableProfile, usePlatforms, useRunSource, useSearchRun, useSources } from '@/api/queries'
import { AgentButton } from '@/components/AgentButton'
import { SiteIcon } from '@/components/SiteIcon'
import { BusyLabel } from '@/components/StableLabel'
import { EmptyState, ErrorState } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { formatRelative } from '@/lib/labels'
import { splitIssues } from '@/lib/runIssues'
import { cn } from '@/lib/utils'

const MAX_CHIPS = 6
/** Lo mismo que admite el servidor: esto acaba en la orden que abre una terminal. */
const SAFE_TEXT = /^[\p{L}\p{N}_ .,+#/&()-]*$/u
/** Las fuentes que consulta la app sola, por su API, sin navegador ni agente. */
const CONNECTORS = new Set([
  'greenhouse',
  'lever',
  'ashby',
  'personio',
  'teamtailor',
  'workable',
  'smartrecruiters',
  'recruitee',
  'infojobs',
  'adzuna',
  'manfred',
  'freehire',
])

function hostOf(source: SourceView): string | null {
  const url = source.website ?? source.browse?.search_urls[0]
  if (!url) return null
  try {
    return new URL(url).hostname
  } catch {
    return null
  }
}

// --- Portales -------------------------------------------------------------------------------------

function PortalRow({
  source,
  checked,
  onChange,
}: {
  source: SourceView
  checked: boolean
  onChange: (checked: boolean) => void
}) {
  const { t } = useTranslation('search')
  const browse = source.browse!
  const run = source.last_run
  const { problems, notes } = splitIssues(run?.errors ?? [])
  return (
    <li>
      <label className="flex cursor-pointer items-center gap-3 px-4 py-3 transition-colors first:rounded-t-[inherit] hover:bg-foreground/[0.025] focus-within:bg-foreground/[0.025]">
        <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
        <span className={cn('flex min-w-0 flex-1 items-center gap-3 transition-opacity', !checked && 'opacity-55')}>
          <SiteIcon name={source.name} sourceId={source.id} host={hostOf(source)} />
          <span className="min-w-0 flex-1">
            <span className="flex items-center gap-2">
              <span className="truncate font-medium">{source.name}</span>
              {browse.access === 'login' && (
                <span className="inline-flex shrink-0 items-center gap-1 text-xs text-warning-foreground">
                  <KeyIcon className="size-3" aria-hidden />
                  {t('tile.login')}
                </span>
              )}
            </span>
            <span className="block truncate text-xs text-muted-foreground">
              {t('tile.size', { count: browse.search_urls.length, offers: browse.max_offers })}
            </span>
          </span>
          <span className="hidden shrink-0 text-right text-xs text-muted-foreground sm:block">
            <span className="block">
              {run
                ? t('tile.lastRun', {
                    when: formatRelative(source.last_run_at ?? run.started_at),
                    count: run.created,
                    found: run.found,
                  })
                : t('tile.never')}
            </span>
            {(problems.length > 0 || notes.length > 0) && (
              <span className="block">
                {problems.length > 0 && (
                  <span className="text-warning-foreground" title={problems[0].message}>
                    {t('tile.problems', { count: problems.length })}
                  </span>
                )}
                {problems.length > 0 && notes.length > 0 && ' · '}
                {notes.length > 0 && <span title={notes[0].message}>{t('tile.notes', { count: notes.length })}</span>}
              </span>
            )}
          </span>
        </span>
      </label>
    </li>
  )
}

/** Puesto o lugar de esta búsqueda, con lo de tu perfil a un clic. */
function RefineField({
  id,
  label,
  placeholder,
  value,
  chips,
  invalid,
  onChange,
}: {
  id: string
  label: string
  placeholder: string
  value: string
  chips: string[]
  invalid: boolean
  onChange: (value: string) => void
}) {
  return (
    <div className="grid content-start gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Input id={id} value={value} maxLength={80} aria-invalid={invalid} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} />
      {chips.length > 0 && (
        <div className="flex flex-wrap gap-1 pt-0.5">
          {chips.slice(0, MAX_CHIPS).map((chip) => (
            <button
              key={chip}
              type="button"
              aria-pressed={value === chip}
              onClick={() => onChange(value === chip ? '' : chip)}
              className={cn(
                'rounded-full border px-2 py-0.5 text-xs outline-none transition-colors hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring',
                value === chip && 'border-primary/50 bg-primary/10 text-primary',
              )}
            >
              {chip}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

// --- Sin navegador --------------------------------------------------------------------------------

/** Las fuentes con API: no necesitan agente ni navegador, y se pueden consultar ya. */
function WithoutBrowser() {
  const { t } = useTranslation('search')
  const sources = useSources()
  const run = useRunSource()
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null)
  const [outcome, setOutcome] = useState<{ created: number; failed: number } | null>(null)
  const connectors = (sources.data?.sources ?? []).filter((s) => CONNECTORS.has(s.kind) && s.active && !s.keys_missing)
  const latest = connectors
    .map((s) => s.last_run_at)
    .filter((at): at is string => Boolean(at))
    .sort()
    .at(-1)

  const consult = async () => {
    setOutcome(null)
    let created = 0
    let failed = 0
    setProgress({ done: 0, total: connectors.length })
    // De una en una: cada consulta sale a la web de la fuente.
    for (const [index, source] of connectors.entries()) {
      try {
        const result = await run.mutateAsync(source.id)
        created += result.created
        if (result.errors.length > 0) failed += 1
      } catch {
        failed += 1
      }
      setProgress({ done: index + 1, total: connectors.length })
    }
    setProgress(null)
    setOutcome({ created, failed })
  }

  return (
    <section aria-labelledby="search-no-browser" className="grid gap-2 border-t pt-4">
      <h3 id="search-no-browser" className="text-sm font-medium">
        {t('noBrowser.title')}
      </h3>
      {connectors.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          <Trans t={t} i18nKey="noBrowser.none" components={{ to: <Link to="/fuentes/empresas" className="underline underline-offset-4" /> }} />
        </p>
      ) : (
        <>
          <p className="text-sm text-muted-foreground">
            {t('noBrowser.body', { count: connectors.length })}
            {latest && ` ${t('noBrowser.latest', { when: formatRelative(latest) })}`}
          </p>
          <div>
            <Button type="button" variant="outline" size="sm" disabled={progress !== null} onClick={() => void consult()}>
              <ArrowsClockwiseIcon className={cn(progress && 'animate-spin')} />
              <BusyLabel
                busy={progress !== null}
                busyText={t('noBrowser.running', { done: progress?.done ?? 0, total: progress?.total ?? connectors.length })}
                text={t('noBrowser.run')}
              />
            </Button>
          </div>
          <p role="status" className="text-xs text-muted-foreground empty:hidden">
            {outcome &&
              [t('noBrowser.created', { count: outcome.created }), outcome.failed ? t('noBrowser.failed', { count: outcome.failed }) : null]
                .filter(Boolean)
                .join(' · ')}
          </p>
        </>
      )}
      <p className="text-xs text-muted-foreground">
        <Trans t={t} i18nKey="noBrowser.others" components={{ to: <Link to="/fuentes/correo" className="underline underline-offset-4" />, ext: <Link to="/fuentes/extension" className="underline underline-offset-4" /> }} />
      </p>
    </section>
  )
}

// --- Página ---------------------------------------------------------------------------------------

/**
 * «Buscar ofertas»: elegir portales, ver qué va a pasar y lanzar a tu agente, que busca con tu
 * navegador y en su ventana. Si no puede usar el navegador, las fuentes con API se consultan aquí.
 */
export function SearchPage() {
  const { t } = useTranslation('search')
  const platforms = usePlatforms()
  const profile = useEditableProfile()
  const searchRun = useSearchRun().data?.run
  // Dos agentes a la vez se pisarían en tu navegador. Si esa búsqueda se quedó colgada, su aviso te deja
  // dar por terminada la espera.
  const searching = searchRun?.status === 'running'
  // Se guarda lo que quitas, no lo que eliges: un portal nuevo entra marcado.
  const [skipped, setSkipped] = useState<ReadonlySet<number>>(new Set())
  const [role, setRole] = useState('')
  const [location, setLocation] = useState('')

  const sources = platforms.data?.sources ?? []
  const usable = sources.filter((s) => s.active && s.browse?.allow_agent_browsing && s.browse.access !== 'blocked')
  const unusable = sources.length - usable.length
  const chosen = usable.filter((s) => !skipped.has(s.id))
  const withLogin = chosen.filter((s) => s.browse?.access === 'login')
  const badRole = !SAFE_TEXT.test(role)
  const badLocation = !SAFE_TEXT.test(location)
  const oneOff = Boolean(role.trim() || location.trim())
  const searches = oneOff ? chosen.length : chosen.reduce((sum, s) => sum + (s.browse?.search_urls.length ?? 0), 0)
  const offers = chosen.reduce((sum, s) => sum + (s.browse?.max_offers ?? 0), 0)
  const search = {
    // Todos: la orden normal, «las plataformas activas».
    platform_ids: chosen.length === usable.length ? [] : chosen.map((s) => s.id),
    role: role.trim() || undefined,
    location: location.trim() || undefined,
  }
  const preferences = (profile.data?.profile as { preferences?: { roles?: string[]; locations?: { preferred?: string[] } } } | null | undefined)
    ?.preferences
  const allChosen = chosen.length === usable.length
  const looking = [...(preferences?.roles ?? []).slice(0, 3), ...(preferences?.locations?.preferred ?? []).slice(0, 2)].join(' · ')

  let portals
  if (platforms.isPending) {
    portals = <Skeleton className="h-48" />
  } else if (platforms.isError) {
    portals = <ErrorState error={platforms.error} onRetry={() => platforms.refetch()} />
  } else if (usable.length === 0) {
    portals = (
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
    portals = (
      <>
        <ul aria-label={t('platforms')} className="divide-y rounded-xl border bg-card">
          {usable.map((source) => (
            <PortalRow
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
        <Collapsible className="mt-5 rounded-xl border bg-card" defaultOpen={false}>
          <CollapsibleTrigger className="group flex w-full items-center gap-2 rounded-xl px-4 py-3 text-left text-sm font-medium outline-none hover:bg-foreground/[0.03] focus-visible:ring-[3px] focus-visible:ring-ring/50">
            <CaretRightIcon className="size-3.5 transition-transform group-data-[state=open]:rotate-90" aria-hidden />
            {t('refine.toggle')}
          </CollapsibleTrigger>
          <CollapsibleContent className="grid gap-3 px-4 pb-4">
            <p className="text-sm text-muted-foreground">{t('refine.hint')}</p>
            <div className="grid gap-4 sm:grid-cols-2">
              <RefineField
                id="search-role"
                label={t('refine.role')}
                placeholder={t('refine.rolePlaceholder')}
                value={role}
                chips={preferences?.roles ?? []}
                invalid={badRole}
                onChange={setRole}
              />
              <RefineField
                id="search-location"
                label={t('refine.location')}
                placeholder={t('refine.locationPlaceholder')}
                value={location}
                chips={preferences?.locations?.preferred ?? []}
                invalid={badLocation}
                onChange={setLocation}
              />
            </div>
            {(badRole || badLocation) && (
              <p role="alert" className="text-xs text-destructive">
                {t('refine.badText')}
              </p>
            )}
          </CollapsibleContent>
        </Collapsible>
      </>
    )
  }

  return (
    <div className="max-w-6xl animate-in fade-in duration-300">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">{t('title')}</h1>
        <p className="mt-1.5 max-w-[65ch] text-sm leading-relaxed text-muted-foreground">{t('intro')}</p>
      </div>

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <section aria-labelledby="search-where" className="min-w-0">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h2 id="search-where" className="font-medium">
              {t('where')}
            </h2>
            <div className="flex items-center gap-3 text-xs">
              {usable.length > 1 && (
                <button
                  type="button"
                  className="text-muted-foreground underline-offset-4 outline-none hover:text-foreground hover:underline focus-visible:underline"
                  onClick={() => setSkipped(allChosen ? new Set(usable.map((s) => s.id)) : new Set())}
                >
                  {allChosen ? t('selectNone') : t('selectAll')}
                </button>
              )}
              <Link to="/fuentes/plataformas" className="text-muted-foreground underline-offset-4 hover:text-foreground hover:underline">
                {t('manage')}
              </Link>
            </div>
          </div>
          {portals}
        </section>

        <aside aria-labelledby="search-plan" className="grid gap-4 rounded-xl border bg-card p-5 lg:sticky lg:top-6">
          <div>
            <h2 id="search-plan" className="font-medium">
              {t('plan.title')}
            </h2>
            {usable.length > 0 && (
              <>
                <p className="mt-1 text-lg leading-snug font-semibold tracking-tight">
                  {t('plan.summary', { portals: chosen.length, count: searches })}
                </p>
                <p className="text-sm text-muted-foreground">
                  {t('plan.offers', { count: offers })}
                  {' · '}
                  {oneOff ? t('plan.oneOff') : t('plan.saved')}
                </p>
              </>
            )}
          </div>

          {usable.length > 0 && (
            <>
              <p className="flex items-baseline justify-between gap-3 border-y py-2.5 text-xs">
                <span className="min-w-0">
                  <span className="text-muted-foreground">{t('plan.looking')}</span>{' '}
                  <span className="font-medium">{looking || t('plan.lookingNone')}</span>
                </span>
                <Link to="/buscar/ajustes" className="shrink-0 text-primary underline-offset-4 hover:underline">
                  {t('plan.change')}
                </Link>
              </p>
              <div className="grid gap-2">
                <h3 className="text-xs font-medium text-muted-foreground">{t('plan.before')}</h3>
                <ul className="grid gap-2 text-sm">
                  <li className="flex gap-2">
                    <BrowserIcon className="mt-0.5 size-4 shrink-0 text-primary" weight="duotone" aria-hidden />
                    <span>
                      <span className="font-medium">{t('plan.browser')}</span>{' '}
                      <span className="text-muted-foreground">{t('plan.browserHint')}</span>
                    </span>
                  </li>
                  {withLogin.length > 0 && (
                    <li className="flex gap-2">
                      <KeyIcon className="mt-0.5 size-4 shrink-0 text-primary" weight="duotone" aria-hidden />
                      <span>
                        <span className="font-medium">{t('plan.login', { names: withLogin.map((s) => s.name).join(', ') })}</span>{' '}
                        <span className="text-muted-foreground">{t('plan.loginHint')}</span>
                      </span>
                    </li>
                  )}
                  <li className="flex gap-2">
                    <CheckIcon className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
                    <span className="text-muted-foreground">{t('plan.safe')}</span>
                  </li>
                </ul>
              </div>
              <div className="grid gap-1.5">
                <AgentButton
                  action="search-jobs"
                  primary
                  size="default"
                  search={search}
                  disabled={searching || chosen.length === 0 || badRole || badLocation}
                >
                  <BusyLabel busy={searching} busyText={t('searching')} text={t('searchNow')} />
                </AgentButton>
                {chosen.length === 0 && <p className="text-xs text-muted-foreground">{t('noneChosen')}</p>}
              </div>
            </>
          )}

          <WithoutBrowser />
        </aside>
      </div>

    </div>
  )
}
