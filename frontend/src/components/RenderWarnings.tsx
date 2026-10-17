import { WarningIcon } from '@phosphor-icons/react'
import { useTranslation } from 'react-i18next'
import type { Schemas } from '@/api/client'
import { InlineCode } from '@/components/States'
import { codeLabel, serverText } from '@/lib/i18n'

type Warning = Schemas['RenderWarning']

/**
 * Avisos de un render del CV o de la carta. Los de maquetación (fase 25.5) dicen además la página
 * y cómo arreglarlo: con una opción de render, sin agente, o recortando con tu agente.
 */
export function RenderWarnings({ warnings, className }: { warnings: Warning[]; className?: string }) {
  const { t } = useTranslation('cv', { keyPrefix: 'layout' })
  if (warnings.length === 0) return null
  return (
    <ul className={className ?? 'mt-3 space-y-1.5'}>
      {warnings.map((warning, i) => (
        <li key={i} className="flex items-start gap-2 text-sm text-warning-foreground">
          <WarningIcon className="mt-0.5 size-4 shrink-0" weight="duotone" />
          <span>
            <InlineCode text={serverText(codeLabel(`cv:warnings.${warning.code}`), warning.message)} />
            {(warning.page != null || warning.fix) && (
              <span className="block text-xs text-muted-foreground">
                {warning.page != null && t('page', { page: warning.page })}
                {warning.page != null && warning.fix && ' · '}
                {warning.fix && t(`fix.${warning.fix}`)}
              </span>
            )}
          </span>
        </li>
      ))}
    </ul>
  )
}
