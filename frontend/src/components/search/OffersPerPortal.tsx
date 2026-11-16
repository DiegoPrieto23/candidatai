import { Trans, useTranslation } from 'react-i18next'
import type { SourceView } from '@/api/client'
import { useSetBrowseMaxOffers } from '@/api/queries'
import { Hint } from '@/components/Hint'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { errorMessage } from '@/lib/errors'
import { maxOffersOptions } from '@/lib/maxOffers'

/**
 * «Hasta [N] ofertas por portal»: cambia a la vez el límite de los portales elegidos (y el de los que
 * añadas después). Si no tienen todos el mismo, lo dice y elegir un número los iguala. El de cada uno
 * se sigue afinando en «Dónde buscar».
 */
export function OffersPerPortal({ chosen }: { chosen: SourceView[] }) {
  const { t } = useTranslation('search', { keyPrefix: 'plan.perPortal' })
  const save = useSetBrowseMaxOffers()
  const values = [...new Set(chosen.map((s) => s.browse?.max_offers ?? 0).filter((n) => n > 0))].sort((a, b) => a - b)
  // Mientras se guarda, el que acabas de elegir; luego, el que dice el servidor.
  const pending = save.isPending ? save.variables?.max_offers : undefined
  const uniform = pending ?? (values.length === 1 ? values[0] : undefined)
  const varies = pending === undefined && values.length > 1
  const select = (
    <Select
      value={uniform ? String(uniform) : ''}
      onValueChange={(v) => save.mutate({ source_ids: chosen.map((s) => s.id), max_offers: Number(v) })}
      disabled={save.isPending || chosen.length === 0}
    >
      <SelectTrigger
        className="mx-1 inline-flex h-7 w-auto min-w-14 gap-1 px-2 align-middle font-semibold tabular-nums"
        aria-label={varies ? t('ariaVaries') : t('aria', { count: uniform ?? 2 })}
      >
        <SelectValue placeholder={varies ? t('varies') : '–'} />
      </SelectTrigger>
      <SelectContent>
        {maxOffersOptions(...values).map((n) => (
          <SelectItem key={n} value={String(n)}>
            {n}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
  return (
    <div className="grid gap-1">
      <p className="text-sm">
        {/* Con límites distintos no hay número: el plural general («ofertas»). */}
        <Trans t={t} i18nKey="label" count={uniform ?? 2} components={{ n: select }} /> <Hint text={t('hint')} label={t('hintLabel')} />
      </p>
      {varies && <p className="text-xs text-muted-foreground">{t('variesHint', { min: values[0], max: values.at(-1) })}</p>}
      {save.isError && (
        <p role="alert" className="text-xs text-destructive">
          {errorMessage(save.error)}
        </p>
      )}
    </div>
  )
}
