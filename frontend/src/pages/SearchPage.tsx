import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { CompassIcon } from '@phosphor-icons/react'
import { usePlatforms, useSearchRun, useSources } from '@/api/queries'
import { AgentButton } from '@/components/AgentButton'
import { EmptyState, ErrorState } from '@/components/States'
import { LaunchPanel } from '@/components/search/LaunchPanel'
import { OffersPerPortal } from '@/components/search/OffersPerPortal'
import { AddPortalCard, PortalCard, RunLegend, UnusableCard } from '@/components/search/PortalCard'
import { SearchFooter } from '@/components/search/SearchFooter'
import { SearchStrip } from '@/components/search/SearchStrip'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { COMPANY_KINDS } from '@/lib/sourceKinds'

const PORTALS_ID = 'search-where'

/**
 * La sección «Buscar» de «Buscar ofertas». Arriba, una franja con lo que buscas (cada cosa se cambia ahí
 * mismo, y el resto en «Más ajustes») y la columna para empezar; debajo, tus portales como tarjetas que
 * se marcan y lo que dio cada uno la última vez; al pie, la última búsqueda y lo que se consulta sin
 * navegador. Tu agente busca con tu navegador y en su ventana. El título y la intro son de la página;
 * si «Más ajustes» está abierto lo dice la ruta (`moreOpen`, `onMore`).
 */
export function SearchPage({ moreOpen = false, onMore = () => {} }: { moreOpen?: boolean; onMore?: (open: boolean) => void }) {
  const { t } = useTranslation('search')
  const platforms = usePlatforms()
  const allSources = useSources()
  const searchRun = useSearchRun().data?.run
  // Dos agentes a la vez se pisarían en tu navegador. Si esa búsqueda se quedó colgada, su aviso te deja
  // dar por terminada la espera.
  const searching = searchRun?.status === 'running'
  // Se guarda lo que quitas, no lo que eliges: un portal nuevo entra marcado.
  const [skipped, setSkipped] = useState<ReadonlySet<number>>(new Set())

  const sources = platforms.data?.sources ?? []
  const usable = sources.filter((s) => s.active && s.browse?.allow_agent_browsing && s.browse.access !== 'blocked')
  const unusable = sources.filter((s) => !usable.includes(s))
  const chosen = usable.filter((s) => !skipped.has(s.id))
  const allChosen = chosen.length === usable.length
  const companies = (allSources.data?.sources ?? []).filter((s) => s.active && COMPANY_KINDS.has(s.kind)).length
  // Todos: la orden normal, «las plataformas activas».
  const search = { platform_ids: allChosen ? [] : chosen.map((s) => s.id) }

  // La franja depende de tu perfil, no de tus portales: se ve siempre, también sin portales.
  const strip = (
    <SearchStrip
      count={<OffersPerPortal chosen={chosen} />}
      action={
        platforms.isPending ? (
          <Skeleton className="h-44" />
        ) : (
          <LaunchPanel chosen={chosen} companies={companies} none={usable.length === 0} search={search} searching={searching} />
        )
      }
      moreOpen={moreOpen}
      onMore={onMore}
    />
  )

  if (platforms.isPending || platforms.isError) {
    return (
      <div className="grid gap-7">
        {strip}
        {platforms.isPending ? <Skeleton className="h-48" /> : <ErrorState error={platforms.error} onRetry={() => platforms.refetch()} />}
      </div>
    )
  }

  if (usable.length === 0) {
    return (
      <div className="grid gap-7">
        {strip}
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

  // Casilla maestra: marcada con todos, a medias con algunos.
  const someChosen = chosen.length > 0 && !allChosen

  return (
    <div className="grid gap-7">
      {strip}

      <section aria-labelledby={PORTALS_ID} className="grid gap-3">
        <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-2">
          <h3 id={PORTALS_ID} tabIndex={-1} className="scroll-mt-24 font-semibold outline-none">
            {t('portals.title')} <span className="font-normal text-muted-foreground">· {t('portals.chosen', { chosen: chosen.length, total: usable.length })}</span>
          </h3>
          <span className="flex flex-wrap items-center gap-x-5 gap-y-2">
            <Link to="/fuentes/empresas" className="text-sm text-primary underline-offset-4 hover:underline">
              {t('portals.companies')}
            </Link>
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
          </span>
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
