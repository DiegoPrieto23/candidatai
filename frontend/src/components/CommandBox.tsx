import { useTranslation } from 'react-i18next'
import { CopyButton } from '@/components/CopyButton'
import { cn } from '@/lib/utils'

/**
 * Un texto para pegar en otro sitio (la orden para tu agente, la de instalarlo), entero y legible,
 * con «Copiar». Nunca cortado: quien lo copia a mano tiene que poder verlo todo.
 */
export function CommandBox({ text, label, mono = false, className }: { text: string; label: string; mono?: boolean; className?: string }) {
  const { t } = useTranslation()
  return (
    <div className={cn('flex items-start gap-2 rounded-lg border bg-background p-2.5', className)}>
      <p aria-label={label} className={cn('min-w-0 flex-1 text-sm break-words whitespace-pre-wrap select-all', mono && 'font-mono text-[0.8rem]')}>
        {text}
      </p>
      <CopyButton text={text} ariaLabel={`${t('copy.label')}: ${label}`} />
    </div>
  )
}
