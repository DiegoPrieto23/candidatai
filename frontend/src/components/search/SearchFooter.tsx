import { useState } from 'react'
import { Trans, useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { ArrowRightIcon, ArrowsClockwiseIcon } from '@phosphor-icons/react'
import type { SourceView } from '@/api/client'
import { useRunSource, useSources } from '@/api/queries'
import { Hint } from '@/components/Hint'
import { BusyLabel } from '@/components/StableLabel'
import { Button } from '@/components/ui/button'
import { formatRelative } from '@/lib/labels'
import { lastSearchOf } from '@/lib/searchStrip'
import { cn } from '@/lib/utils'

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

/** «Última búsqueda»: cuándo, cuántas nuevas de cuántas vistas, y la bandeja. */
function LastSearch({ portals }: { portals: readonly SourceView[] }) {
  const { t } = useTranslation('search', { keyPrefix: 'last' })
  const last = lastSearchOf(portals)
  return (
    <p className="text-sm">
      <strong className="font-semibold">{t('title')}</strong>{' '}
      {last ? (
        <>
          <span className="text-muted-foreground">
            {formatRelative(last.at)} · {t('summary', { count: last.created, found: last.found })}
          </span>{' '}
          <Link to="/bandeja" className="inline-flex items-center gap-1 text-primary underline-offset-4 hover:underline">
            {t('inbox')}
            <ArrowRightIcon className="size-3" aria-hidden />
          </Link>
        </>
      ) : (
        <span className="text-muted-foreground">{t('never')}</span>
      )}
    </p>
  )
}

/** Las fuentes con API: no necesitan agente ni navegador, y se pueden consultar ya. */
function WithoutBrowser() {
  const { t } = useTranslation('search', { keyPrefix: 'noBrowser' })
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

  const others = t('othersHint')

  return (
    <section aria-labelledby="search-no-browser" className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-sm">
      <h3 id="search-no-browser" className="font-semibold">
        {t('title')}
      </h3>
      {connectors.length === 0 ? (
        <span className="text-muted-foreground">
          <Trans t={t} i18nKey="none" components={{ to: <Link to="/fuentes/empresas" className="underline underline-offset-4" /> }} />{' '}
          <Hint text={others} label={t('othersLabel')} />
        </span>
      ) : (
        <>
          <span className="text-muted-foreground">
            {t('body', { count: connectors.length })} <Hint text={latest ? `${t('latest', { when: formatRelative(latest) })} ${others}` : others} label={t('othersLabel')} />
          </span>
          <Button type="button" variant="outline" size="sm" disabled={progress !== null} onClick={() => void consult()}>
            <ArrowsClockwiseIcon className={cn(progress && 'animate-spin')} />
            <BusyLabel
              busy={progress !== null}
              busyText={t('running', { done: progress?.done ?? 0, total: progress?.total ?? connectors.length })}
              text={t('run')}
            />
          </Button>
          <span role="status" className="text-xs text-muted-foreground empty:hidden">
            {outcome &&
              [t('created', { count: outcome.created }), outcome.failed ? t('failed', { count: outcome.failed }) : null].filter(Boolean).join(' · ')}
          </span>
        </>
      )}
    </section>
  )
}

/** El pie de «Buscar»: la última búsqueda a la izquierda y lo que se consulta sin navegador a la derecha. */
export function SearchFooter({ portals }: { portals: readonly SourceView[] }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-x-8 gap-y-3 border-t pt-4">
      <LastSearch portals={portals} />
      <WithoutBrowser />
    </div>
  )
}
