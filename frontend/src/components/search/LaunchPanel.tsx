import { Trans, useTranslation } from 'react-i18next'
import { BuildingsIcon, KeyIcon } from '@phosphor-icons/react'
import type { SourceView } from '@/api/client'
import { useStartSearch, type SearchScope } from '@/api/queries'
import { AgentButton } from '@/components/AgentButton'
import { Hint } from '@/components/Hint'
import { SiteIcon } from '@/components/SiteIcon'
import { BusyLabel } from '@/components/StableLabel'
import { Button } from '@/components/ui/button'
import { errorMessage } from '@/lib/errors'
import { hostOf } from '@/lib/siteHost'

/** Los logos que caben apilados; el resto, como «+N». */
const MAX_LOGOS = 4

/**
 * La columna de «Buscar ahora»: en qué portales buscará tu agente (sus logos), cuántas empresas con
 * portal propio se revisan a la vez, cuántas ofertas nuevas como mucho en los portales, el botón y, si
 * algún portal pide sesión, el aviso. El botón abre primero la búsqueda (`POST /search/run`, que
 * encola las empresas) y lanza tu agente ligado a ella; sin portales elegidos, solo revisa las
 * empresas. Qué portales entran se elige en sus tarjetas, debajo.
 */
export function LaunchPanel({
  chosen,
  companies,
  none = false,
  search,
  searching,
}: {
  chosen: SourceView[]
  /** Empresas con portal propio activas: se revisan con el mismo clic, sin tu agente. */
  companies: number
  /** Aún no tienes portales en los que buscar (lo de cómo añadirlos va debajo). */
  none?: boolean
  search: SearchScope
  searching: boolean
}) {
  const { t } = useTranslation('search')
  const start = useStartSearch()
  const offers = chosen.reduce((sum, s) => sum + (s.browse?.max_offers ?? 0), 0)
  const withLogin = chosen.filter((s) => s.browse?.access === 'login')
  const shown = chosen.slice(0, MAX_LOGOS)
  const portalIds = chosen.map((s) => s.id)
  const openSearch = async () => {
    const result = await start.mutateAsync({ portal_ids: portalIds, include_companies: true })
    return result.run_id ?? null
  }
  const companiesOnly = chosen.length === 0 && companies > 0
  return (
    <div className="grid content-center gap-3.5">
      <span className="text-[0.6875rem] font-medium tracking-[0.07em] text-muted-foreground uppercase">{t('launch.eyebrow')}</span>
      {chosen.length === 0 && !companiesOnly ? (
        <p className="text-sm text-muted-foreground">{none ? t('empty.title') : t('noneChosen')}</p>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-2.5">
            {chosen.length > 0 && (
              <span className="flex shrink-0" aria-hidden>
                {shown.map((source, i) => (
                  <SiteIcon
                    key={source.id}
                    size="sm"
                    name={source.name}
                    sourceId={source.id}
                    host={hostOf(source)}
                    className={i > 0 ? '-ml-2 shadow-sm ring-2 ring-card' : 'shadow-sm ring-2 ring-card'}
                  />
                ))}
                {chosen.length > MAX_LOGOS && (
                  <span className="-ml-2 grid size-7 place-items-center rounded-md border bg-muted text-xs font-semibold text-muted-foreground ring-2 ring-card">
                    +{chosen.length - MAX_LOGOS}
                  </span>
                )}
              </span>
            )}
            <strong className="text-sm font-semibold">
              {t('launch.portals', { count: chosen.length })}
              {companies > 0 && <> · {t('launch.companies', { count: companies })}</>}
            </strong>
            {companies > 0 && <Hint text={t('launch.companiesHint')} label={t('launch.companiesHintLabel')} />}
          </div>
          {chosen.length > 0 ? (
            <p className="flex items-baseline gap-1.5 leading-none text-muted-foreground">
              <Trans
                t={t}
                i18nKey="launch.offers"
                count={offers}
                components={{ n: <span className="font-mono text-[2.125rem] font-semibold tracking-tight text-foreground tabular-nums" /> }}
              />
            </p>
          ) : (
            <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
              <BuildingsIcon className="size-4 shrink-0" aria-hidden />
              {t('launch.companiesOnly', { count: companies })}
            </p>
          )}
        </>
      )}
      {/* Sin portales no hay nada que lanzar: cómo añadirlos va debajo de la franja. */}
      {companiesOnly ? (
        <Button
          size="default"
          className="w-full"
          disabled={searching || start.isPending}
          onClick={() => start.mutate({ portal_ids: [], include_companies: true })}
        >
          <BusyLabel busy={searching || start.isPending} busyText={t('searching')} text={t('searchNow')} />
        </Button>
      ) : (
        !none && (
          <AgentButton
            action="search-jobs"
            primary
            size="default"
            search={search}
            prepareSearch={openSearch}
            disabled={searching || chosen.length === 0}
            fill
          >
            <BusyLabel busy={searching} busyText={t('searching')} text={t('searchNow')} />
          </AgentButton>
        )
      )}
      {start.data && start.data.run_id === null && (
        <p role="status" className="text-xs text-muted-foreground">{start.data.message}</p>
      )}
      {start.isError && <p role="alert" className="text-xs text-destructive">{errorMessage(start.error)}</p>}
      {withLogin.length > 0 && (
        <p className="flex w-fit items-center gap-1.5 rounded-full border border-warning-foreground/25 bg-warning-foreground/10 px-2.5 py-0.5 text-xs text-warning-foreground">
          <KeyIcon className="size-3.5 shrink-0" aria-hidden />
          {t('go.login', { names: withLogin.map((s) => s.name).join(', ') })}
          <Hint text={t('go.loginHint')} label={t('go.loginHintLabel')} />
        </p>
      )}
    </div>
  )
}
