import { useState } from 'react'
import { Trans, useTranslation } from 'react-i18next'
import { ArrowSquareOutIcon, ClockIcon, CompassIcon, GlobeIcon, WarningIcon } from '@phosphor-icons/react'
import type { AgentBrowseLimits, BrowseAccess, LinkedInPublicView, SourceView } from '@/api/client'
import {
  useLinkedInPublic,
  usePlatforms,
  useRunLinkedInPublic,
  useUpdateBrowseSettings,
  useUpdateLinkedInPublic,
} from '@/api/queries'
import { AddPlatformButton, EditPlatformButton } from '@/components/AddPlatformDialog'
import { AgentButton } from '@/components/AgentButton'
import { Hint } from '@/components/Hint'
import { Reveal } from '@/components/Reveal'
import { SiteIcon } from '@/components/SiteIcon'
import { Switch } from '@/components/Switch'
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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { errorMessage } from '@/lib/errors'
import { i18n } from '@/lib/i18n'
import { dateFormatter } from '@/lib/labels'
import { platformHome, searchLabel } from '@/lib/searches'
import { cn } from '@/lib/utils'

const ACCESS: readonly BrowseAccess[] = ['free', 'login', 'blocked']
// Ofertas que abre el agente en cada recorrido (el servidor acepta de 1 a 100).
const MAX_OFFERS = [5, 10, 15, 20, 25, 30, 40, 50, 75, 100]

function formatWhen(iso: string): string {
  return dateFormatter({ day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }).format(new Date(iso))
}

/** Lo que busca el agente en esta plataforma, legible; las URLs completas, al desplegar. */
function Searches({ urls, name }: { urls: string[]; name: string }) {
  const { t } = useTranslation('platforms', { keyPrefix: 'searches' })
  const [showUrls, setShowUrls] = useState(false)
  if (!urls.length) return null
  return (
    <div className="grid gap-1.5">
      <span className="text-xs text-muted-foreground">
        {t('what')}
        <span className="sr-only">{t('whatSr', { name })}</span>
      </span>
      <ul className="flex flex-wrap gap-1.5">
        {urls.map((url) => (
          <li key={url}>
            <a
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              title={t('open', { name })}
              className="inline-flex items-center gap-1 rounded-md border bg-background px-2 py-1 text-xs transition-colors hover:border-foreground/25 hover:bg-foreground/[0.03]"
            >
              {searchLabel(url)}
              <ArrowSquareOutIcon className="size-3 text-muted-foreground" aria-hidden />
            </a>
          </li>
        ))}
      </ul>
      <button
        type="button"
        onClick={() => setShowUrls((v) => !v)}
        aria-expanded={showUrls}
        className="justify-self-start text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
      >
        {showUrls ? t('hideUrls') : t('showUrls')}
      </button>
      {showUrls && (
        <ul className="grid gap-0.5">
          {urls.map((url) => (
            <li key={url} className="truncate font-mono text-xs text-muted-foreground">
              {url}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

type CountKey = 'found' | 'new' | 'known' | 'issues' | 'offers' | 'pages' | 'afterFilters'

function plural(key: CountKey, count: number): string {
  return i18n.t(`platforms:counts.${key}`, { count })
}

// --- Interruptor y aviso de LinkedIn -------------------------------------------------------------

function LinkedInRiskDialog({
  open,
  onOpenChange,
  onConfirm,
  pending,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onConfirm: () => void
  pending: boolean
}) {
  const { t } = useTranslation('platforms', { keyPrefix: 'linkedinRisk' })
  const strong = { strong: <strong /> }
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <WarningIcon weight="fill" className="size-5 text-amber-600 dark:text-amber-400" />
            {t('title')}
          </DialogTitle>
          <DialogDescription asChild>
            <div className="grid gap-2.5 text-sm leading-relaxed">
              <p>
                <Trans t={t} i18nKey="p1" components={strong} />
              </p>
              <p>{t('p2')}</p>
              <p>{t('p3')}</p>
            </div>
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {t('cancel')}
          </Button>
          <Button variant="destructive" disabled={pending} onClick={onConfirm}>
            {pending ? t('activating') : t('activate')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// --- Búsqueda pública de LinkedIn sin sesión (fase 22) ------------------------------------------

type PublicConfirm = 'enabled' | 'fetch_detail' | null

function PublicRiskDialog({
  what,
  onOpenChange,
  onConfirm,
  pending,
}: {
  what: PublicConfirm
  onOpenChange: (open: boolean) => void
  onConfirm: () => void
  pending: boolean
}) {
  const { t } = useTranslation('platforms', { keyPrefix: 'publicRisk' })
  const strong = { strong: <strong /> }
  const detail = what === 'fetch_detail'
  return (
    <Dialog open={what !== null} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <WarningIcon weight="fill" className="size-5 text-amber-600 dark:text-amber-400" />
            {detail ? t('detailTitle') : t('enableTitle')}
          </DialogTitle>
          <DialogDescription asChild>
            <div className="grid gap-2.5 text-sm leading-relaxed">
              {detail ? (
                <p>
                  <Trans t={t} i18nKey="detail" components={strong} />
                </p>
              ) : (
                <>
                  <p>
                    <Trans t={t} i18nKey="p1" components={strong} />
                  </p>
                  <p>
                    <Trans t={t} i18nKey="p2" components={strong} />
                  </p>
                  <p>{t('p3')}</p>
                </>
              )}
            </div>
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {t('cancel')}
          </Button>
          <Button variant="destructive" disabled={pending} onClick={onConfirm}>
            {pending ? t('activating') : detail ? t('download') : t('activate')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function PublicLastRun({ view }: { view: LinkedInPublicView }) {
  const { t } = useTranslation('platforms')
  const last = view.last_run
  if (!last) {
    return <p className="text-xs text-muted-foreground">{t('public.notRun')}</p>
  }
  const existing = Math.max(0, last.after_filters - last.created)
  const warnings = last.errors.filter((e) => e.code !== 'blocked')
  return (
    <div className="text-xs text-muted-foreground">
      <p className="flex items-center gap-1.5">
        <ClockIcon className="size-3.5" />
        <span>
          {formatWhen(last.finished_at ?? last.started_at)}: {plural('found', last.found)},{' '}
          {plural('afterFilters', last.after_filters)}, {plural('new', last.created)}, {plural('known', existing)}
        </span>
      </p>
      {warnings.length > 0 && (
        <ul className="mt-1 space-y-0.5 pl-5">
          {warnings.slice(0, 3).map((issue, i) => (
            <li key={i}>
              <InlineCode text={issue.message} />
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

/** Si la espera hasta la próxima ejecución es por un bloqueo de LinkedIn (y no por el límite diario). */
function isBlocked(view: LinkedInPublicView, now: number): boolean {
  if (!view.blocked_at || !view.next_run_at) return false
  const until = new Date(view.next_run_at).getTime()
  const cooldownEnd = new Date(view.blocked_at).getTime() + view.limits.block_cooldown_days * 86_400_000
  return until > now && cooldownEnd >= until
}

function LinkedInPublicPanel() {
  const { t } = useTranslation('platforms', { keyPrefix: 'public' })
  const query = useLinkedInPublic()
  const update = useUpdateLinkedInPublic()
  const runNow = useRunLinkedInPublic()
  const [confirming, setConfirming] = useState<PublicConfirm>(null)
  // Hora de referencia al montar: los datos se refrescan cada minuto y el servidor vuelve a
  // comprobar los límites al ejecutar.
  const [now] = useState(() => Date.now())

  if (query.isPending) return <Skeleton className="h-16" />
  if (query.isError) return <ErrorState error={query.error} onRetry={() => query.refetch()} />
  const view = query.data
  const waiting = view.next_run_at !== null && new Date(view.next_run_at).getTime() > now
  const blocked = isBlocked(view, now)

  const toggle = (key: 'enabled' | 'fetch_detail', next: boolean) => {
    if (next) setConfirming(key)
    else update.mutate({ [key]: false })
  }

  return (
    <section className="grid gap-3 rounded-lg border border-dashed p-3" aria-label={t('label')}>
      <div className="flex flex-wrap items-start gap-x-4 gap-y-2">
        <GlobeIcon className="mt-0.5 size-5 shrink-0 text-muted-foreground" aria-hidden />
        <div className="min-w-0 flex-1">
          <h4 className="text-sm font-medium">{t('title')}</h4>
          <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">
            {t('intro')}
          </p>
        </div>
        <label className="flex items-center gap-2.5 text-sm">
          <span className={cn(!view.enabled && 'text-muted-foreground')}>
            {view.enabled ? t('enabled') : t('disabled')}
          </span>
          <Switch
            checked={view.enabled}
            disabled={update.isPending}
            label={t('switch')}
            onChange={(next) => toggle('enabled', next)}
          />
        </label>
      </div>

      {view.enabled && (
        <label className="flex items-center justify-between gap-3 text-sm">
          <span>
            {t('detail')}
            <span className="block text-xs text-muted-foreground">
              {t('detailHint', { offers: plural('offers', view.limits.max_details_per_run) })}
            </span>
          </span>
          <Switch
            checked={view.fetch_detail}
            disabled={update.isPending}
            label={t('detail')}
            onChange={(next) => toggle('fetch_detail', next)}
          />
        </label>
      )}

      {view.searches.length > 0 ? (
        <div className="grid gap-1">
          <span className="text-xs text-muted-foreground">{t('what')}</span>
          <ul className="flex flex-wrap gap-1.5">
            {view.searches.map((s) => (
              <li key={s.url} className="rounded-md border bg-background px-2 py-1 text-xs">
                {[s.keywords, s.location].filter(Boolean).join(' · ') || searchLabel(s.url)}
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">
          <InlineCode text={t('noSearch')} />
        </p>
      )}
      {view.ignored.length > 0 && (
        <p className="text-xs text-amber-700 dark:text-amber-400">
          {t('ignored', { count: view.ignored.length, list: view.ignored.map((i) => i.message).join(' ') })}
        </p>
      )}

      {blocked && view.next_run_at && (
        <p role="status" className="flex items-start gap-1.5 text-sm text-amber-700 dark:text-amber-400">
          <WarningIcon weight="fill" className="mt-0.5 size-4 shrink-0" />
          {t('blocked', { date: formatWhen(view.next_run_at) })}
        </p>
      )}
      <PublicLastRun view={view} />

      {view.enabled && (
        <div className="flex flex-wrap items-center gap-3">
          <Button
            size="sm"
            variant="outline"
            disabled={runNow.isPending || waiting || view.searches.length === 0}
            onClick={() => runNow.mutate()}
          >
            {runNow.isPending ? t('searching') : t('searchNow')}
          </Button>
          {waiting && !blocked && view.next_run_at && (
            <span className="text-xs text-muted-foreground">
              {t('daily', { date: formatWhen(view.next_run_at) })}
            </span>
          )}
          {runNow.data && <span className="text-xs text-muted-foreground">{runNow.data.message}</span>}
        </div>
      )}
      {(update.error || runNow.error) && (
        <p role="alert" className="text-sm text-destructive">
          {errorMessage(update.error ?? runNow.error)}
        </p>
      )}

      <PublicRiskDialog
        what={confirming}
        pending={update.isPending}
        onOpenChange={(open) => {
          if (!open) setConfirming(null)
        }}
        onConfirm={() => {
          if (confirming) {
            update.mutate({ [confirming]: true, confirm_risk: true }, { onSettled: () => setConfirming(null) })
          }
        }}
      />
    </section>
  )
}

// --- Una plataforma ------------------------------------------------------------------------------

/** El último recorrido en una línea («11 oct · 34 encontradas, 15 nuevas · 2 incidentes»). */
function LastRun({ source }: { source: SourceView }) {
  const { t } = useTranslation('platforms', { keyPrefix: 'row' })
  const last = source.last_run
  if (!last) {
    return (
      <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <ClockIcon className="size-3.5 shrink-0" />
        {t('notRun')}
      </p>
    )
  }
  return (
    <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
      <ClockIcon className="size-3.5 shrink-0" />
      <span>
        {formatWhen(last.finished_at ?? last.started_at)} · {plural('found', last.found)}, {plural('new', last.created)}
        {last.errors.length > 0 && (
          <span className="text-amber-700 dark:text-amber-400"> · {plural('issues', last.errors.length)}</span>
        )}
      </span>
    </p>
  )
}

/** El registro del último recorrido: cuántas ya conocía y sus incidentes. */
function RunLog({ source }: { source: SourceView }) {
  const { t } = useTranslation('platforms', { keyPrefix: 'row' })
  const last = source.last_run
  if (!last) return null
  const existing = Math.max(0, last.after_filters - last.created)
  return (
    <div className="grid gap-1 text-xs text-muted-foreground">
      <span>{t('log')}</span>
      <p className="text-foreground/80">
        {plural('found', last.found)}, {plural('new', last.created)}, {plural('known', existing)}
      </p>
      {last.errors.length > 0 && (
        <ul className="space-y-0.5 pl-4">
          {last.errors.map((issue, i) => (
            <li key={i} className="list-disc">
              <InlineCode text={issue.message} />
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

/** Un puesto del orden de recorrido y la plataforma que lo tiene (fase 27.3: sin empates). */
interface Slot {
  id: number
  name: string
  priority: number
}

function PlatformRow({ source, order, limits }: { source: SourceView; order: Slot[]; limits: AgentBrowseLimits }) {
  const { t } = useTranslation('platforms')
  const update = useUpdateBrowseSettings()
  const linkedinPublic = useLinkedInPublic()
  const [confirming, setConfirming] = useState(false)
  const browse = source.browse

  if (!browse) {
    return (
      <li className="px-4 py-4 sm:px-5">
        <h3 className="font-medium">{source.name}</h3>
        <p className="mt-1 text-sm text-destructive">
          <InlineCode text={t('row.invalid')} />
        </p>
      </li>
    )
  }

  const linkedin = browse.platform === 'linkedin'
  const publicEnabled = linkedinPublic.data?.enabled === true
  const current = browse.priority ?? order.findIndex((slot) => slot.id === source.id) + 1
  const home = platformHome(browse.search_urls)
  const enabled = browse.allow_agent_browsing === true
  const change = (body: {
    allow_agent_browsing?: boolean
    priority?: number
    expected_priority?: number
    access?: BrowseAccess
    max_offers?: number
  }) => update.mutate({ sourceId: source.id, ...body })
  const maxOffers = browse.max_offers ?? 0
  const maxOffersOptions = MAX_OFFERS.includes(maxOffers)
    ? MAX_OFFERS
    : [...MAX_OFFERS, maxOffers].filter((n) => n > 0).sort((a, b) => a - b)

  const onToggle = (next: boolean) => {
    if (next && linkedin) setConfirming(true)
    else change({ allow_agent_browsing: next })
  }

  return (
    <li className={cn('grid gap-3 px-4 py-4 sm:px-5', !enabled && 'bg-muted/30')}>
      <div className="flex flex-wrap items-start gap-x-4 gap-y-2">
        <SiteIcon name={source.name} home={home} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-medium">{source.name}</h3>
            {linkedin && (
              <span className="rounded-md bg-amber-500/10 px-1.5 py-0.5 text-xs text-amber-700 dark:text-amber-400">
                {t('row.risk')}
              </span>
            )}
          </div>
          {home && (
            <a
              href={home.origin}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-0.5 inline-flex items-center gap-1 text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
            >
              {home.host}
              <ArrowSquareOutIcon className="size-3" aria-hidden />
            </a>
          )}
          <div className="mt-1">
            <LastRun source={source} />
          </div>
        </div>
        <div className="flex items-center gap-3">
          <EditPlatformButton source={source} />
          <label className="flex items-center gap-2.5 text-sm">
            <span className={cn(!enabled && 'text-muted-foreground')}>
              {enabled ? t('row.browsing') : t('row.disabled')}
            </span>
            <Switch
              checked={enabled}
              disabled={update.isPending}
              label={t('row.switch', { name: source.name })}
              onChange={onToggle}
            />
          </label>
        </div>
      </div>

      {/* La búsqueda pública de LinkedIn, a la vista solo si está activada: es otra forma de buscar. */}
      {linkedin && publicEnabled && <LinkedInPublicPanel />}
      <Reveal label={t('row.settings')} className="space-y-3" defaultOpen={(source.last_run?.errors.length ?? 0) > 0}>
        <div className="flex flex-wrap gap-3">
          <div className="grid gap-1">
            <span className="flex items-center gap-1 text-xs text-muted-foreground">
              {t('row.priority')}
              <Hint text={t('row.priorityHint')} label={t('row.priorityHintAria')} />
            </span>
            <Select
              value={String(current)}
              // Un puesto ocupado se intercambia; el servidor comprueba que `current` sigue siendo el
              // suyo (si otra pestaña cambió el orden, responde 409 y la lista se recarga).
              onValueChange={(v) => change({ priority: Number(v), expected_priority: current })}
              disabled={update.isPending}
            >
              <SelectTrigger className="h-8 w-32" aria-label={t('row.priorityAria', { name: source.name })}>
                {/* Solo el número: quién ocupa cada puesto va en el menú. */}
                <SelectValue>{current === 1 ? t('row.first') : current}</SelectValue>
              </SelectTrigger>
              <SelectContent>
                {order.map((slot) => (
                  <SelectItem key={slot.id} value={String(slot.priority)}>
                    {t('row.slot', { position: slot.priority, name: slot.name })}
                    <span className="ml-1.5 text-xs text-muted-foreground">
                      {slot.id === source.id ? t('row.slotCurrent') : t('row.slotSwap', { position: current })}
                    </span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-1">
            <span className="flex items-center gap-1 text-xs text-muted-foreground">
              {t('row.access')}
              <Hint text={t('row.accessHint')} label={t('row.accessHintAria')} />
            </span>
            <Select
              value={browse.access}
              onValueChange={(v) => change({ access: v as BrowseAccess })}
              disabled={update.isPending}
            >
              <SelectTrigger className="h-8 w-36" aria-label={t('row.accessAria', { name: source.name })}>
                {/* Solo el nombre: la pista de cada opción va en el menú. */}
                <SelectValue>{t(`access.${browse.access}`)}</SelectValue>
              </SelectTrigger>
              <SelectContent>
                {ACCESS.map((a) => (
                  <SelectItem key={a} value={a}>
                    {t(`access.${a}`)}
                    <span className="ml-1.5 text-xs text-muted-foreground">{t(`access.${a}Hint`)}</span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-1">
            <span className="flex items-center gap-1 text-xs text-muted-foreground">
              {t('row.maxOffers')}
              <Hint text={t('row.maxOffersHint')} label={t('row.maxOffersHintAria')} />
            </span>
            <Select
              value={String(maxOffers)}
              onValueChange={(v) => change({ max_offers: Number(v) })}
              disabled={update.isPending}
            >
              <SelectTrigger className="h-8 w-28" aria-label={t('row.maxOffersAria', { name: source.name })}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {maxOffersOptions.map((n) => (
                  <SelectItem key={n} value={String(n)}>
                    {n}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <Searches urls={browse.search_urls} name={source.name} />
        {browse.notes && <p className="text-sm text-muted-foreground">{browse.notes}</p>}
        <RunLog source={source} />
        {linkedin && !publicEnabled && <LinkedInPublicPanel />}
        <Limits limits={limits} />
      </Reveal>
      {update.error && (
        <p role="alert" className="text-sm text-destructive">
          {errorMessage(update.error)}
        </p>
      )}

      {linkedin && (
        <LinkedInRiskDialog
          open={confirming}
          onOpenChange={setConfirming}
          pending={update.isPending}
          onConfirm={() =>
            update.mutate(
              { sourceId: source.id, allow_agent_browsing: true, confirm_risk: true },
              { onSettled: () => setConfirming(false) },
            )
          }
        />
      )}
    </li>
  )
}

// --- Página --------------------------------------------------------------------------------------

function Limits({ limits }: { limits: AgentBrowseLimits }) {
  const { t } = useTranslation('platforms')
  return (
    <p className="text-xs text-muted-foreground">
      <InlineCode
        text={t('limits', {
          pages: plural('pages', limits.max_result_pages),
          delay: limits.delay_seconds,
          offers: limits.default_max_offers,
        })}
      />
    </p>
  )
}

function byPriority(a: SourceView, b: SourceView): number {
  const pa = a.browse?.priority ?? 99
  const pb = b.browse?.priority ?? 99
  return pa - pb || a.name.localeCompare(b.name, i18n.language)
}

export function PlatformsPage() {
  const { t } = useTranslation('platforms')
  const { t: tAgent } = useTranslation('agent')
  const platforms = usePlatforms()

  let body
  if (platforms.isPending) {
    body = (
      <div className="grid gap-3">
        <Skeleton className="h-32" />
        <Skeleton className="h-32" />
      </div>
    )
  } else if (platforms.isError) {
    body = <ErrorState error={platforms.error} onRetry={() => platforms.refetch()} />
  } else if (platforms.data.sources.length === 0) {
    body = (
      <EmptyState
        icon={<CompassIcon className="size-6" weight="duotone" />}
        title={t('empty.title')}
        action={
          <div className="flex flex-wrap justify-center gap-2">
            <AgentButton action="configure-platforms" primary>
              {tAgent('actions.configure-platforms')}
            </AgentButton>
            <AddPlatformButton />
          </div>
        }
      >
        <InlineCode text={t('empty.body')} />
      </EmptyState>
    )
  } else {
    const sorted = [...platforms.data.sources].sort(byPriority)
    const order = sorted
      .filter((source) => source.browse)
      .map((source, i) => ({ id: source.id, name: source.name, priority: source.browse?.priority ?? i + 1 }))
    body = (
      <ul className="divide-y rounded-xl border bg-card">
        {sorted.map((source) => (
          <PlatformRow key={source.id} source={source} order={order} limits={platforms.data.agent_browse} />
        ))}
      </ul>
    )
  }

  // Con plataformas, lo destacado es buscar; sin ninguna, añadir la primera (en el estado vacío).
  const any = (platforms.data?.sources.length ?? 0) > 0
  return (
    <div className="mx-auto max-w-3xl animate-in fade-in duration-300">
      <div className="mb-8">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h1 className="text-2xl font-semibold tracking-tight">{t('title')}</h1>
          {any && (
            <div className="flex flex-wrap gap-2">
              <AddPlatformButton />
              <AgentButton action="configure-platforms">{tAgent('actions.configure-platforms')}</AgentButton>
              <AgentButton action="broaden-search">{t('broaden')}</AgentButton>
              <AgentButton action="search-jobs" primary>
                {t('search')}
              </AgentButton>
            </div>
          )}
        </div>
        <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
          <InlineCode text={t('intro')} />
        </p>
      </div>
      {body}
    </div>
  )
}
