import { useId, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import {
  CheckCircleIcon,
  ClockCountdownIcon,
  RobotIcon,
  SparkleIcon,
  TerminalWindowIcon,
  XIcon,
  GearSixIcon,
} from '@phosphor-icons/react'
import type { AgentRequestView } from '@/api/client'
import {
  useAgentLauncher,
  useAgentsOverview,
  useAgentRequests,
  useCancelAgentRequest,
} from '@/api/queries'
import { AgentButton } from '@/components/AgentButton'
import { AgentLogo } from '@/components/AgentLogo'
import { AgentsSection } from '@/components/AgentsSection'
import { CostsSection } from '@/components/CostsSection'
import { GetAnAgent } from '@/components/GetAnAgent'
import { Reveal } from '@/components/Reveal'
import { SemanticMatchingCard } from '@/components/SemanticMatching'
import { ErrorState } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { i18n, SOURCE_LANGUAGE } from '@/lib/i18n'
import { formatWhen } from '@/lib/time'
import { errorMessage } from '@/lib/errors'

/** El nombre de un encargo: el del servidor en español; en otro idioma, el de su acción. */
function actionLabel(item: { action: AgentRequestView['action']; label: string }): string {
  return i18n.language === SOURCE_LANGUAGE ? item.label : i18n.t(`agent:actions.${item.action}`)
}

function Target({ jobId }: { jobId: number | null }) {
  const { t } = useTranslation('agent')
  if (!jobId) return null
  return (
    <Link to={`/jobs/${jobId}`} className="text-sm text-muted-foreground underline-offset-4 hover:underline">
      {t('job', { id: jobId })}
    </Link>
  )
}

function RequestRow({ request }: { request: AgentRequestView }) {
  const { t } = useTranslation('agent')
  const cancel = useCancelAgentRequest()
  const pending = request.status === 'pending'
  return (
    <li className="flex flex-wrap items-start gap-x-3 gap-y-1 rounded-lg border bg-card px-4 py-3">
      <div className="min-w-0 flex-1">
        <p className="flex flex-wrap items-center gap-x-3">
          <span className="font-medium">{actionLabel(request)}</span>
          <Target jobId={request.job_id} />
          <span className="text-xs text-muted-foreground tabular">{formatWhen(request.created_at)}</span>
        </p>
        {pending ? (
          // La orden que recibe el agente es técnica (nombra el skill): plegada.
          <Reveal label={t('technicalDetails', { ns: 'common' })} className="mt-1 space-y-1">
            <p className="text-xs text-muted-foreground">{request.prompt}</p>
          </Reveal>
        ) : (
          <p className="mt-0.5 text-sm text-muted-foreground">
            {request.status === 'done' ? (request.summary ?? t('done')) : t('cancelled')}
            {request.agent_name && ` · ${request.agent_name}`}
          </p>
        )}
        {cancel.error && <p className="mt-1 text-xs text-destructive">{errorMessage(cancel.error)}</p>}
      </div>
      {pending && (
        <Button variant="ghost" size="sm" onClick={() => cancel.mutate(request.id)} disabled={cancel.isPending}>
          <XIcon />
          {t('remove')}
        </Button>
      )}
    </li>
  )
}

function Requests() {
  const { t } = useTranslation('agent')
  const { data, isPending, isError, error, refetch } = useAgentRequests()
  if (isPending) return <Skeleton className="h-24" />
  if (isError) return <ErrorState error={error} onRetry={() => void refetch()} />
  const pending = data.requests.filter((r) => r.status === 'pending').reverse()
  const closed = data.requests.filter((r) => r.status !== 'pending').slice(0, 10)
  return (
    <div className="space-y-4">
      {pending.length === 0 ? (
        <p className="rounded-xl border border-dashed px-4 py-6 text-center text-sm text-muted-foreground">
          {t('noRequests')}
        </p>
      ) : (
        <>
          <ul className="space-y-2" aria-label={t('pendingRequests')}>
            {pending.map((r) => (
              <RequestRow key={r.id} request={r} />
            ))}
          </ul>
          <AgentButton action="handle-requests" primary>
            {t('handle')}
          </AgentButton>
        </>
      )}
      {closed.length > 0 && (
        <details>
          <summary className="cursor-pointer text-xs font-medium tracking-wide text-muted-foreground uppercase">
            {t('recentlyClosed')}
          </summary>
          <ul className="mt-2 space-y-2">
            {closed.map((r) => (
              <RequestRow key={r.id} request={r} />
            ))}
          </ul>
        </details>
      )}
    </div>
  )
}

/**
 * Lo primero de «Agente»: si tienes un agente listo, si no puedo abrirlo desde aquí o, sin ninguno,
 * cómo instalar uno.
 */
function AgentSummary() {
  const { t } = useTranslation('agent', { keyPrefix: 'summary' })
  const launcher = useAgentLauncher()
  const overview = useAgentsOverview()
  if (launcher.isPending) return <Skeleton className="h-24 rounded-xl" />
  if (launcher.isError) return <ErrorState error={launcher.error} onRetry={() => void launcher.refetch()} />
  if (launcher.data.no_agent_installed) return <GetAnAgent linkToAgentPage={false} />
  const { available, agent, reason } = launcher.data
  const name = overview.data?.agents.find((a) => a.name === agent)?.info.display_name ?? agent
  return (
    <section aria-labelledby="your-agent" className="rounded-xl border bg-card p-5 text-sm sm:p-6">
      <h2 id="your-agent" className="flex flex-wrap items-center gap-2 text-lg font-semibold tracking-tight">
        {available ? (
          <>
            <AgentLogo name={agent} />
            {t('ready', { agent: name })}
            <CheckCircleIcon className="size-5 text-emerald-600 dark:text-emerald-400" weight="fill" aria-hidden />
          </>
        ) : (
          <>
            <TerminalWindowIcon className="size-6 text-muted-foreground" weight="duotone" aria-hidden />
            {t('cantOpen')}
          </>
        )}
      </h2>
      <p className="mt-2 max-w-prose text-muted-foreground">
        {available ? t('readyHint') : t('cantOpenHint', { reason: reason ?? '' })}
      </p>
    </section>
  )
}

/**
 * La configuración de los agentes, tras un botón que dice lo que hay dentro. El botón va en la
 * columna de «Tus agentes»; lo que despliega, debajo de las dos columnas y a todo lo ancho, para que
 * las tarjetas de los agentes quepan de tres en tres.
 */
function useAgentsSettings(noAgent: boolean | undefined) {
  const { t } = useTranslation('agents', { keyPrefix: 'configure' })
  const defaultOpen = noAgent ?? false
  const [open, setOpen] = useState(defaultOpen)
  const [mounted, setMounted] = useState(defaultOpen)
  // Cuando se sabe si hay agente, vuelve a su estado de partida: abierto si aún no tienes ninguno.
  const [known, setKnown] = useState(noAgent)
  if (known !== noAgent) {
    setKnown(noAgent)
    setOpen(defaultOpen)
    setMounted(defaultOpen)
  }
  const id = useId()
  const panelRef = useRef<HTMLDivElement>(null)
  const toggle = (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-card p-4">
      <div className="min-w-0 flex-1 basis-56">
        <p className="text-sm font-medium">{t('title')}</p>
        <p className="mt-0.5 text-sm text-muted-foreground">{t('body')}</p>
      </div>
      <Button
        type="button"
        variant="outline"
        size="sm"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => {
          setOpen(!open)
          setMounted(true)
          // Si la columna de al lado es larga, lo desplegado queda fuera de la vista: se lleva a ella.
          if (!open) requestAnimationFrame(() => panelRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }))
        }}
      >
        <GearSixIcon />
        {open ? t('close') : t('open')}
      </Button>
    </div>
  )
  const panel = (
    <div ref={panelRef} id={id} hidden={!open} className="mt-8 min-w-0 scroll-mt-4">
      {mounted && <AgentsSection />}
    </div>
  )
  return { toggle, panel }
}

export function AgentPage() {
  const { t } = useTranslation('agent')
  const { t: tAgents } = useTranslation('agents')
  const launcher = useAgentLauncher()
  const settings = useAgentsSettings(launcher.data?.no_agent_installed)
  // Arriba lo que más se usa (tus agentes y lo que les has dejado); después, la
  // comparación por significado del score, y el coste y el umbral, plegados al final como ajustes.
  return (
    <div className="animate-in fade-in duration-300">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">{t('title')}</h1>
        <p className="max-w-prose text-sm text-muted-foreground">
          {t('intro')}
        </p>
      </div>
      <div className="mb-8 max-w-3xl">
        <AgentSummary />
      </div>
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <section aria-labelledby="agents-title" className="min-w-0">
          <h2 id="agents-title" className="mb-3 flex items-center gap-2 text-lg font-semibold tracking-tight">
            <RobotIcon className="size-5 text-muted-foreground" weight="duotone" />
            {tAgents('title')}
          </h2>
          {/* Versiones, licencias, niveles y modelos: plegado salvo si aún no tienes ninguno (las
              tarjetas dicen cómo instalar cada uno). */}
          {settings.toggle}
        </section>
        <section aria-labelledby="requests-title" className="min-w-0">
          <h2 id="requests-title" className="mb-3 flex items-center gap-2 text-lg font-semibold tracking-tight">
            <ClockCountdownIcon className="size-5 text-muted-foreground" weight="duotone" />
            {t('nextSession')}
          </h2>
          <Requests />
        </section>
      </div>
      {settings.panel}
      <section aria-labelledby="semantic-title" className="mt-10 min-w-0 max-w-3xl">
        <h2 id="semantic-title" className="mb-3 flex items-center gap-2 text-lg font-semibold tracking-tight">
          <SparkleIcon className="size-5 text-primary" weight="duotone" />
          {t('semantic')}
        </h2>
        <SemanticMatchingCard />
      </section>
      <Reveal label={t('costs.settings')} className="mt-10 min-w-0">
        <CostsSection />
      </Reveal>
    </div>
  )
}
