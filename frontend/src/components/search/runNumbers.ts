import { useTranslation } from 'react-i18next'
import type { Schemas } from '@/api/client'

/**
 * Las cifras de un recorrido, iguales en las tarjetas de «Buscar», en «Dónde buscar», en el aviso
 * «Buscando…» y en el resumen de tu agente: vistas · pasan tus filtros · ya las tenías · nuevas
 * (de ellas, reabiertas). `known` lo calcula el servidor: las que pasan tus filtros que no son
 * nuevas ni quedaron sin abrir por el límite.
 */
export type RunNumbers = Pick<Schemas['SourceRunView'], 'found' | 'known' | 'created' | 'reopened' | 'left_by_limit'> & {
  passed: number
  stop_reason?: Schemas['SourceRunView']['stop_reason']
}

export function numbersOf(run: Schemas['SourceRunView']): RunNumbers {
  return { ...run, passed: run.after_filters }
}

/** Los textos de esas cifras: el resumen en una línea y por qué paró tu agente. */
export function useRunText() {
  const { t } = useTranslation('search', { keyPrefix: 'run' })
  return {
    summary(n: RunNumbers): string {
      const parts = [
        t('seen', { count: n.found }),
        t('passed', { count: n.passed }),
        t('known', { count: n.known }),
        t('created', { count: n.created }),
      ].join(' · ')
      return n.reopened > 0 ? `${parts} ${t('ofThemReopened', { count: n.reopened })}` : parts
    },
    reopened: (count: number) => t('reopened', { count }),
    /** Sin motivo (las empresas o un recorrido de antes de anotarlo), nada que decir. */
    stop(n: Pick<RunNumbers, 'stop_reason' | 'left_by_limit'>): string | null {
      if (!n.stop_reason) return null
      if (n.stop_reason !== 'limit') return t(`stop.${n.stop_reason}`)
      return n.left_by_limit > 0 ? t('stop.limit', { count: n.left_by_limit }) : t('stop.limitReached')
    },
    /** Lo que queda sin abrir por el límite en toda una búsqueda (el aviso). */
    left: (count: number) => t('left', { count }),
  }
}
