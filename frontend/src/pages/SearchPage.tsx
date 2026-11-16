import { useState } from 'react'
import { Trans, useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { CompassIcon, KeyIcon } from '@phosphor-icons/react'
import { usePlatforms, useSearchRun } from '@/api/queries'
import { AgentButton } from '@/components/AgentButton'
import { Hint } from '@/components/Hint'
import { BusyLabel } from '@/components/StableLabel'
import { EmptyState, ErrorState } from '@/components/States'
import { OffersPerPortal } from '@/components/search/OffersPerPortal'
import { AddPortalCard, PortalCard, RunLegend, UnusableCard } from '@/components/search/PortalCard'
import { SearchFooter } from '@/components/search/SearchFooter'
import { SearchStrip } from '@/components/search/SearchStrip'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'

/** Lo mismo que admite el servidor: esto acaba en la orden que abre una terminal. */
const SAFE_TEXT = /^[\p{L}\p{N}_ .,+#/&()-]*$/u

/**
 * La sección «Buscar» de «Buscar ofertas». Arriba, una franja con qué buscas, dónde y cuántas (cada
 * cosa se cambia ahí mismo) y el botón para empezar; debajo, tus portales como tarjetas que se marcan
 * y lo que dio cada uno la última vez; al pie, la última búsqueda y lo que se consulta sin navegador.
 * Tu agente busca con tu navegador y en su ventana. El título y la intro son de la página.
 */
export function SearchPage() {
  const { t } = useTranslation('search')
  const platforms = usePlatforms()
  const searchRun = useSearchRun().data?.run
  // Dos agentes a la vez se pisarían en tu navegador. Si esa búsqueda se quedó colgada, su aviso te deja
  // dar por terminada la espera.
  const searching = searchRun?.status === 'running'
  // Se guarda lo que quitas, no lo que eliges: un portal nuevo entra marcado.
  const [skipped, setSkipped] = useState<ReadonlySet<number>>(new Set())
  const [oneOff, setOneOff] = useState(false)
  const [role, setRole] = useState('')
  const [location, setLocation] = useState('')

  const sources = platforms.data?.sources ?? []
  const usable = sources.filter((s) => s.active && s.browse?.allow_agent_browsing && s.browse.access !== 'blocked')
  const unusable = sources.filter((s) => !usable.includes(s))
  const chosen = usable.filter((s) => !skipped.has(s.id))
  const allChosen = chosen.length === usable.length
  const withLogin = chosen.filter((s) => s.browse?.access === 'login')
  // Lo de «solo esta vez» solo cuenta mientras está abierto.
  const once = { role: oneOff ? role.trim() : '', location: oneOff ? location.trim() : '' }
  const invalid = { role: oneOff && !SAFE_TEXT.test(role), location: oneOff && !SAFE_TEXT.test(location) }
  const offers = chosen.reduce((sum, s) => sum + (s.browse?.max_offers ?? 0), 0)
  const search = {
    // Todos: la orden normal, «las plataformas activas».
    platform_ids: allChosen ? [] : chosen.map((s) => s.id),
    role: once.role || undefined,
    location: once.location || undefined,
  }

  if (platforms.isPending) return <Skeleton className="h-96" />
  if (platforms.isError) return <ErrorState error={platforms.error} onRetry={() => platforms.refetch()} />

  if (usable.length === 0) {
    return (
      <div className="grid gap-6">
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
        <SearchFooter portals={[]} />
      </div>
    )
  }

  const action = (
    <>
      <AgentButton
        action="search-jobs"
        primary
        size="default"
        search={search}
        disabled={searching || chosen.length === 0 || invalid.role || invalid.location}
        fill
      >
        <BusyLabel busy={searching} busyText={t('searching')} text={t('searchNow')} />
      </AgentButton>
      <p className="text-center text-xs text-muted-foreground">
        {chosen.length === 0 ? (
          t('noneChosen')
        ) : (
          <Trans t={t} i18nKey="go.summary" count={offers} values={{ portals: chosen.length }} components={{ b: <strong className="font-semibold text-foreground" /> }} />
        )}
      </p>
      {withLogin.length > 0 && (
        <p className="flex items-center justify-center gap-1.5 text-center text-xs text-warning-foreground">
          <KeyIcon className="size-3.5 shrink-0" aria-hidden />
          {t('go.login', { names: withLogin.map((s) => s.name).join(', ') })}
          <Hint text={t('go.loginHint')} label={t('go.loginHintLabel')} />
        </p>
      )}
    </>
  )

  // Casilla maestra: marcada con todos, a medias con algunos.
  const someChosen = chosen.length > 0 && !allChosen

  return (
    <div className="grid gap-7">
      <SearchStrip
        oneOff={oneOff}
        onOneOff={setOneOff}
        role={role}
        location={location}
        invalid={invalid}
        onRole={setRole}
        onLocation={setLocation}
        count={<OffersPerPortal chosen={chosen} />}
        action={action}
      />

      <section aria-labelledby="search-where" className="grid gap-3">
        <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-2">
          <h3 id="search-where" className="font-semibold">
            {t('portals.title')} <span className="font-normal text-muted-foreground">· {t('portals.chosen', { chosen: chosen.length, total: usable.length })}</span>
          </h3>
          {usable.length > 1 && (
            <label className="flex cursor-pointer items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
              <input
                type="checkbox"
                checked={allChosen}
                ref={(el) => {
                  if (el) el.indeterminate = someChosen
                }}
                onChange={() => setSkipped(allChosen ? new Set(usable.map((s) => s.id)) : new Set())}
              />
              {allChosen ? t('selectNone') : t('selectAll')}
            </label>
          )}
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
          <ul aria-label={t('platforms')} className="contents">
            {usable.map((source) => (
              <PortalCard
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
          {unusable.length > 0 && (
            <ul aria-label={t('portals.unusableList')} className="contents">
              {unusable.map((source) => (
                <UnusableCard key={source.id} source={source} />
              ))}
            </ul>
          )}
          <ul className="contents">
            <AddPortalCard />
          </ul>
        </div>
        {usable.some((s) => s.last_run && s.last_run.found > 0) && <RunLegend />}
      </section>

      <SearchFooter portals={usable} />
    </div>
  )
}
