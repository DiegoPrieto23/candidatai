import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { CheckIcon, KeyIcon, LockIcon, PlusIcon } from '@phosphor-icons/react'
import type { SourceView } from '@/api/client'
import { AddPlatformButton } from '@/components/AddPlatformDialog'
import { SiteIcon } from '@/components/SiteIcon'
import { formatRelative } from '@/lib/labels'
import { splitIssues } from '@/lib/runIssues'
import { cn } from '@/lib/utils'

function hostOf(source: SourceView): string | null {
  const url = source.website ?? source.browse?.search_urls[0]
  if (!url) return null
  try {
    return new URL(url).hostname
  } catch {
    return null
  }
}

/** Por qué tu agente no puede buscar en un portal (lo cambias en «Dónde buscar»). */
function unusableReason(source: SourceView): 'off' | 'blocked' | 'noAgent' {
  if (!source.active) return 'off'
  if (source.browse?.access === 'blocked') return 'blocked'
  return 'noAgent'
}

/** Vistas, las que pasan tus filtros y nuevas, en una barra (cada parte, sobre las vistas). */
function RunBar({ found, passed, created }: { found: number; passed: number; created: number }) {
  const pct = (n: number) => `${Math.min(100, Math.round((n / found) * 100))}%`
  return (
    <span className="relative block h-1.5 overflow-hidden rounded-full bg-foreground/10" aria-hidden>
      <span className="absolute inset-y-0 left-0 rounded-full bg-primary/45" style={{ width: pct(passed) }} />
      <span className="absolute inset-y-0 left-0 rounded-full bg-primary" style={{ width: pct(created) }} />
    </span>
  )
}

const CARD = 'relative grid min-h-32 content-start gap-3 rounded-xl border bg-card px-4 pt-3.5 pb-4'

/** Un portal en el que tu agente puede buscar: se marca o se desmarca pulsando la tarjeta. */
export function PortalCard({ source, checked, onChange }: { source: SourceView; checked: boolean; onChange: (checked: boolean) => void }) {
  const { t } = useTranslation('search', { keyPrefix: 'portals' })
  const browse = source.browse!
  const run = source.last_run
  const { problems } = splitIssues(run?.errors ?? [])
  return (
    <li className="contents">
      <label
        className={cn(
          CARD,
          'cursor-pointer transition-[border-color,box-shadow,opacity] has-[input:focus-visible]:ring-[3px] has-[input:focus-visible]:ring-ring/50',
          checked ? 'border-primary/45 shadow-[inset_0_0_0_1px_color-mix(in_oklch,var(--primary)_25%,transparent)]' : 'opacity-75 hover:opacity-90',
        )}
      >
        <input type="checkbox" className="peer sr-only" checked={checked} onChange={(e) => onChange(e.target.checked)} />
        <span
          aria-hidden
          className={cn(
            'absolute top-3 right-3 grid size-5 place-items-center rounded-full',
            checked ? 'bg-primary text-primary-foreground' : 'border-[1.5px] border-input',
          )}
        >
          {checked && <CheckIcon className="size-3" weight="bold" />}
        </span>
        <span className="flex min-w-0 items-center gap-3 pr-7">
          <SiteIcon name={source.name} sourceId={source.id} host={hostOf(source)} />
          <span className="min-w-0">
            <span className="block truncate font-semibold">{source.name}</span>
            {browse.access === 'login' ? (
              <span className="flex items-center gap-1 text-xs text-warning-foreground">
                <KeyIcon className="size-3" aria-hidden />
                {t('login')}
              </span>
            ) : (
              <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <span className="size-1.5 rounded-full bg-primary" aria-hidden />
                {t('ready')}
              </span>
            )}
          </span>
        </span>
        {run && run.found > 0 && <RunBar found={run.found} passed={run.after_filters} created={run.created} />}
        <span className="grid gap-0.5 text-xs text-muted-foreground">
          <span>
            {run ? (
              <>
                {formatRelative(source.last_run_at ?? run.started_at)} ·{' '}
                <strong className="font-semibold text-foreground">{t('created', { count: run.created })}</strong>{' '}
                {t('of', { found: run.found })}
              </>
            ) : (
              t('never')
            )}
          </span>
          <span>
            {t('searches', { count: browse.search_urls.length })}
            {problems.length > 0 && (
              <>
                {' · '}
                <span className="text-warning-foreground" title={problems[0].message}>
                  {t('problems', { count: problems.length })}
                  <span className="sr-only">: {problems[0].message}</span>
                </span>
              </>
            )}
          </span>
        </span>
      </label>
    </li>
  )
}

/** Un portal en el que tu agente no puede buscar ahora, y dónde se cambia. */
export function UnusableCard({ source }: { source: SourceView }) {
  const { t } = useTranslation('search', { keyPrefix: 'portals' })
  return (
    <li className={cn(CARD, 'border-dashed bg-transparent')}>
      <span className="flex min-w-0 items-center gap-3 opacity-70">
        <SiteIcon name={source.name} sourceId={source.id} host={hostOf(source)} />
        <span className="min-w-0">
          <span className="block truncate font-semibold">{source.name}</span>
          <span className="flex items-center gap-1 text-xs text-muted-foreground">
            <LockIcon className="size-3" aria-hidden />
            {t(`unusable.${unusableReason(source)}`)}
          </span>
        </span>
      </span>
      <Link to="/fuentes/plataformas" className="w-fit text-xs text-primary underline-offset-4 hover:underline">
        {t('change')}
      </Link>
    </li>
  )
}

/** La última tarjeta: añadir un portal, con el mismo diálogo de «Dónde buscar». */
export function AddPortalCard() {
  return (
    <li className="contents">
      <AddPlatformButton
        render={(open, label) => (
          <button
            type="button"
            onClick={open}
            className="grid min-h-32 place-content-center justify-items-center gap-1 rounded-xl border border-dashed border-input text-sm text-muted-foreground outline-none transition-colors hover:border-ring hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50"
          >
            <PlusIcon className="size-4" aria-hidden />
            {label}
          </button>
        )}
      />
    </li>
  )
}

/** La leyenda de las barras de las tarjetas. */
export function RunLegend() {
  const { t } = useTranslation('search', { keyPrefix: 'portals.legend' })
  const item = 'inline-flex items-center gap-1.5 before:size-2 before:rounded-[2px]'
  return (
    <p className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
      <span className={cn(item, 'before:bg-foreground/10')}>{t('found')}</span>
      <span className={cn(item, 'before:bg-primary/45')}>{t('passed')}</span>
      <span className={cn(item, 'before:bg-primary')}>{t('created')}</span>
    </p>
  )
}
