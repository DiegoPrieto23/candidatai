import { Link } from 'react-router'
import { useTranslation } from 'react-i18next'
import type { SourceView } from '@/api/client'
import { SiteIcon } from '@/components/SiteIcon'
import { whenLabel } from '@/lib/labels'
import { platformHome } from '@/lib/searches'
import { cn } from '@/lib/utils'

const COMPANIES_ID = 'search-companies'
/** Las que caben sin alargar la página; el resto, en «Dónde buscar». */
export const COMPANIES_SHOWN = 8

/**
 * Las empresas con portal propio, bajo los portales de «Buscar»: entran en la búsqueda las activas, y la
 * app las revisa sola, sin agente. Solo se ven; se gestionan en «Dónde buscar».
 */
export function CompanyCards({ companies, failed = false }: { companies: SourceView[]; failed?: boolean }) {
  const { t } = useTranslation('search', { keyPrefix: 'companies' })
  const { t: tRow } = useTranslation('sources', { keyPrefix: 'row' })
  // Primero las activas, que son las que se revisan al buscar.
  const activeOnes = companies.filter((c) => c.active)
  const sorted = [...activeOnes, ...companies.filter((c) => !c.active)]
  const active = activeOnes.length
  const manage = (
    <Link to="/fuentes/empresas" className="text-sm text-primary underline-offset-4 hover:underline">
      {companies.length > COMPANIES_SHOWN ? t('more', { count: companies.length }) : t('manage')}
    </Link>
  )

  return (
    <section aria-labelledby={COMPANIES_ID} className="grid gap-3">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-2">
        <h3 id={COMPANIES_ID} className="font-semibold">
          {t('title')}
          {companies.length > 0 && (
            <span className="font-normal text-muted-foreground"> · {t('active', { active, total: companies.length })}</span>
          )}
        </h3>
        {manage}
      </div>
      {failed ? (
        <p className="text-sm text-muted-foreground">{t('error')}</p>
      ) : companies.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t('empty')}</p>
      ) : (
        <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
          {sorted.slice(0, COMPANIES_SHOWN).map((company) => (
            <li key={company.id} className="flex items-center gap-3 rounded-lg border bg-card px-3 py-2">
              {/* Su `key`: con otra web, el logo empieza de cero. */}
              <SiteIcon
                key={company.website ?? ''}
                name={company.name}
                sourceId={company.id}
                host={company.website ? (platformHome([company.website])?.host ?? null) : null}
                size="sm"
              />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="truncate text-sm font-medium">{company.name}</span>
                  <span
                    className={cn(
                      'shrink-0 rounded-md px-1.5 py-0.5 text-[0.7rem]',
                      company.active ? 'bg-primary/10 text-primary' : 'bg-muted text-muted-foreground',
                    )}
                  >
                    {company.active ? tRow('active') : tRow('paused')}
                  </span>
                </div>
                <p className="truncate text-xs text-muted-foreground">
                  {company.last_run
                    ? tRow('last', { when: whenLabel(company.last_run.started_at), count: company.last_run.created })
                    : tRow('notRun')}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
