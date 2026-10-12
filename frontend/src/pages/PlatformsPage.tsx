import { useState } from 'react'
import { ArrowSquareOutIcon, ClockIcon, CompassIcon, WarningIcon } from '@phosphor-icons/react'
import type { AgentBrowseLimits, BrowseAccess, SourceView } from '@/api/client'
import { usePlatforms, useUpdateBrowseSettings } from '@/api/queries'
import { AddPlatformButton } from '@/components/AddPlatformDialog'
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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { iconCandidates, platformHome, searchLabel } from '@/lib/searches'
import { cn } from '@/lib/utils'

const ACCESS: { value: BrowseAccess; label: string; hint: string }[] = [
  { value: 'free', label: 'Libre', hint: 'Se ve sin iniciar sesión' },
  { value: 'login', label: 'Con sesión', hint: 'Inicias sesión tú antes de que busque' },
  { value: 'blocked', label: 'Bloqueada', hint: 'El agente la salta' },
]
const PRIORITIES = Array.from({ length: 10 }, (_, i) => i + 1)

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Algo ha fallado.'
}

function formatWhen(iso: string): string {
  return new Date(iso).toLocaleString('es-ES', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** Lo que busca el agente en esta plataforma, legible; las URLs completas, al desplegar. */
function Searches({ urls, name }: { urls: string[]; name: string }) {
  const [showUrls, setShowUrls] = useState(false)
  if (!urls.length) return null
  return (
    <div className="grid gap-1.5">
      <span className="text-xs text-muted-foreground">
        Qué busca el agente <span className="sr-only">en {name}</span>
      </span>
      <ul className="flex flex-wrap gap-1.5">
        {urls.map((url) => (
          <li key={url}>
            <a
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              title={`Abrir esta búsqueda en ${name}`}
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
        {showUrls ? 'Ocultar las URLs' : 'Ver las URLs'}
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

/**
 * Icono del portal, que tu navegador carga del propio portal (sin referer): prueba las rutas de
 * `iconCandidates` en orden y, si ninguna carga, pone la inicial del nombre.
 */
function PlatformIcon({ name, home }: { name: string; home: { origin: string; host: string } | null }) {
  const [attempt, setAttempt] = useState(0)
  const candidates = home ? iconCandidates(home) : []
  const box = 'grid size-9 shrink-0 place-items-center rounded-lg border bg-white dark:bg-white/95'
  if (attempt >= candidates.length) {
    return (
      <span className={cn(box, 'bg-muted font-semibold text-muted-foreground dark:bg-muted')} aria-hidden>
        {name.trim().charAt(0).toUpperCase()}
      </span>
    )
  }
  return (
    <span className={box} aria-hidden>
      <img
        key={candidates[attempt]}
        src={candidates[attempt]}
        alt=""
        width={20}
        height={20}
        loading="lazy"
        referrerPolicy="no-referrer"
        onError={() => setAttempt((n) => n + 1)}
        className="size-5 object-contain"
      />
    </span>
  )
}

function plural(n: number, one: string, many: string): string {
  return `${n} ${n === 1 ? one : many}`
}

// --- Interruptor y aviso de LinkedIn -------------------------------------------------------------

function Switch({
  checked,
  disabled,
  label,
  onChange,
}: {
  checked: boolean
  disabled?: boolean
  label: string
  onChange: (checked: boolean) => void
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        'relative inline-flex h-6 w-11 shrink-0 items-center rounded-full border transition-colors',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50',
        checked ? 'border-primary bg-primary' : 'border-input bg-muted',
      )}
    >
      <span
        className={cn(
          'inline-block size-4.5 rounded-full bg-background shadow-sm transition-transform',
          checked ? 'translate-x-5.5' : 'translate-x-0.5',
        )}
      />
    </button>
  )
}

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
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <WarningIcon weight="fill" className="size-5 text-amber-600 dark:text-amber-400" />
            ¿Dejar que el agente recorra LinkedIn?
          </DialogTitle>
          <DialogDescription asChild>
            <div className="grid gap-2.5 text-sm leading-relaxed">
              <p>
                Las condiciones de LinkedIn prohíben recorrer su web con herramientas automáticas. Aunque el
                agente usa tu navegador, va despacio y solo lee, <strong>LinkedIn puede restringir o cerrar tu
                cuenta</strong> si lo detecta.
              </p>
              <p>
                Las alternativas sin riesgo son sus alertas por correo (pantalla «Alertas») y el botón «Enviar a
                Job Hunter» mientras ves una oferta.
              </p>
              <p>Puedes desactivarlo cuando quieras. Las candidaturas nunca se envían solas.</p>
            </div>
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button variant="destructive" disabled={pending} onClick={onConfirm}>
            {pending ? 'Activando…' : 'Activar bajo mi responsabilidad'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// --- Una plataforma ------------------------------------------------------------------------------

function LastRun({ source }: { source: SourceView }) {
  const last = source.last_run
  if (!last) {
    return (
      <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <ClockIcon className="size-3.5" />
        El agente aún no la ha recorrido
      </p>
    )
  }
  const existing = Math.max(0, last.after_filters - last.created)
  return (
    <div className="text-xs text-muted-foreground">
      <p className="flex items-center gap-1.5">
        <ClockIcon className="size-3.5" />
        <span>
          {formatWhen(last.finished_at ?? last.started_at)}: {plural(last.found, 'encontrada', 'encontradas')},{' '}
          {plural(last.created, 'nueva', 'nuevas')}, {plural(existing, 'ya conocida', 'ya conocidas')}
          {last.errors.length > 0 && (
            <span className="text-amber-700 dark:text-amber-400">
              {' '}
              · {plural(last.errors.length, 'incidente', 'incidentes')}
            </span>
          )}
        </span>
      </p>
      {last.errors.length > 0 && (
        <ul className="mt-1 space-y-0.5 pl-5">
          {last.errors.slice(0, 3).map((issue, i) => (
            <li key={i}>
              <InlineCode text={issue.message} />
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function PlatformRow({ source }: { source: SourceView }) {
  const update = useUpdateBrowseSettings()
  const [confirming, setConfirming] = useState(false)
  const browse = source.browse

  if (!browse) {
    return (
      <li className="px-4 py-4 sm:px-5">
        <h3 className="font-medium">{source.name}</h3>
        <p className="mt-1 text-sm text-destructive">
          Su configuración no es válida. Pide a tu agente que la vuelva a guardar con{' '}
          <InlineCode text="`buscar-ofertas configurar`" />.
        </p>
      </li>
    )
  }

  const linkedin = browse.platform === 'linkedin'
  const home = platformHome(browse.search_urls)
  const enabled = browse.allow_agent_browsing === true
  const change = (body: { allow_agent_browsing?: boolean; priority?: number; access?: BrowseAccess }) =>
    update.mutate({ sourceId: source.id, ...body })

  const onToggle = (next: boolean) => {
    if (next && linkedin) setConfirming(true)
    else change({ allow_agent_browsing: next })
  }

  return (
    <li className={cn('grid gap-3 px-4 py-4 sm:px-5', !enabled && 'bg-muted/30')}>
      <div className="flex flex-wrap items-start gap-x-4 gap-y-2">
        <PlatformIcon name={source.name} home={home} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-medium">{source.name}</h3>
            <span className="rounded-md border px-1.5 py-0.5 font-mono text-xs text-muted-foreground">
              {browse.platform}
            </span>
            {linkedin && (
              <span className="rounded-md bg-amber-500/10 px-1.5 py-0.5 text-xs text-amber-700 dark:text-amber-400">
                Riesgo para tu cuenta
              </span>
            )}
          </div>
          <p className="mt-1 flex flex-wrap items-center gap-x-2 text-xs text-muted-foreground">
            {home && (
              <>
                <a
                  href={home.origin}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-foreground/80 underline-offset-2 hover:text-foreground hover:underline"
                >
                  {home.host}
                  <ArrowSquareOutIcon className="size-3" aria-hidden />
                </a>
                <span aria-hidden>·</span>
              </>
            )}
            Hasta {plural(browse.max_offers ?? 0, 'oferta', 'ofertas')} por recorrido
          </p>
        </div>
        <label className="flex items-center gap-2.5 text-sm">
          <span className={cn(!enabled && 'text-muted-foreground')}>
            {enabled ? 'El agente la recorre' : 'Desactivada'}
          </span>
          <Switch
            checked={enabled}
            disabled={update.isPending}
            label={`Búsqueda con navegador en ${source.name}`}
            onChange={onToggle}
          />
        </label>
      </div>

      <div className="flex flex-wrap gap-3">
        <div className="grid gap-1">
          <span className="text-xs text-muted-foreground">Prioridad</span>
          <Select
            value={String(browse.priority)}
            onValueChange={(v) => change({ priority: Number(v) })}
            disabled={update.isPending}
          >
            <SelectTrigger className="h-8 w-24" aria-label={`Prioridad de ${source.name}`}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {PRIORITIES.map((p) => (
                <SelectItem key={p} value={String(p)}>
                  {p === 1 ? '1 (primera)' : p}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="grid gap-1">
          <span className="text-xs text-muted-foreground">Acceso</span>
          <Select
            value={browse.access}
            onValueChange={(v) => change({ access: v as BrowseAccess })}
            disabled={update.isPending}
          >
            <SelectTrigger className="h-8 w-36" aria-label={`Acceso a ${source.name}`}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {ACCESS.map((a) => (
                <SelectItem key={a.value} value={a.value}>
                  {a.label}
                  <span className="ml-1.5 text-xs text-muted-foreground">{a.hint}</span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <Searches urls={browse.search_urls} name={source.name} />
      {browse.notes && <p className="text-sm text-muted-foreground">{browse.notes}</p>}
      <LastRun source={source} />
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
  return (
    <p className="mt-2 text-xs text-muted-foreground">
      Límites en <InlineCode text="`config/policies.yaml`" />: como mucho{' '}
      {plural(limits.max_result_pages, 'página', 'páginas')} de resultados por búsqueda, {limits.delay_seconds} s
      de pausa entre páginas y {limits.default_max_offers} ofertas por plataforma si no dice otra cosa.
    </p>
  )
}

function byPriority(a: SourceView, b: SourceView): number {
  const pa = a.browse?.priority ?? 99
  const pb = b.browse?.priority ?? 99
  return pa - pb || a.name.localeCompare(b.name, 'es')
}

export function PlatformsPage() {
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
      <EmptyState icon={<CompassIcon className="size-6" weight="duotone" />} title="Aún no hay plataformas">
        Añádelas con «Añadir plataforma» o pide a tu agente <InlineCode text="`buscar-ofertas configurar`" />:
        te preguntará dónde buscas, te recomendará portales y guardará aquí las búsquedas.
      </EmptyState>
    )
  } else {
    body = (
      <ul className="divide-y rounded-xl border bg-card">
        {[...platforms.data.sources].sort(byPriority).map((source) => (
          <PlatformRow key={source.id} source={source} />
        ))}
      </ul>
    )
  }

  return (
    <div className="mx-auto max-w-3xl animate-in fade-in duration-300">
      <div className="mb-8">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h1 className="text-2xl font-semibold tracking-tight">Plataformas</h1>
          <div className="flex flex-wrap gap-2">
            <AgentButton action="ampliar-busqueda">Ampliar búsqueda</AgentButton>
            <AddPlatformButton />
          </div>
        </div>
        <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
          Portales que tu agente recorre con tu navegador cuando le pides{' '}
          <InlineCode text="`buscar-ofertas`" />, por orden de prioridad. Solo lee: no se postula, no guarda
          ofertas en el portal ni resuelve captchas. Lo que encuentra queda en «Por extraer».
          «Ampliar búsqueda» propone puestos cercanos a los que apruebas; tú decides cuáles añadir.
        </p>
        {platforms.data && <Limits limits={platforms.data.agent_browse} />}
      </div>
      {body}
    </div>
  )
}
