import { useTranslation } from 'react-i18next'
import { UsersThreeIcon } from '@phosphor-icons/react'

/**
 * Insignia «Conoces a N» para listas (bandeja, triaje). En su fichero y no en `NetworkPanel`: la
 * Bandeja la usa y así no se descarga el panel entero.
 */
export function KnownBadge({ count }: { count?: number }) {
  const { t } = useTranslation('network')
  if (!count) return null
  return (
    <span
      className="inline-flex shrink-0 items-center gap-1 rounded-full border border-primary/30 bg-primary/10 px-1.5 py-px text-[0.7rem] leading-4 font-medium whitespace-nowrap text-primary"
      title={t('knownTitle')}
    >
      <UsersThreeIcon className="size-3" weight="bold" />
      {t('knownBadge', { count })}
    </span>
  )
}
