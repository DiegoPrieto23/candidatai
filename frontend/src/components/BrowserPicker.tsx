import { useTranslation } from 'react-i18next'
import { BROWSERS, type BrowserId } from '@/lib/browser'
import { useRadioGroup } from '@/lib/radioGroup'
import { cn } from '@/lib/utils'

/** «¿Qué navegador usas?»: una fila de opciones, con el detectado marcado. */
export function BrowserPicker({
  browser,
  detected,
  onChoose,
}: {
  browser: BrowserId
  detected: BrowserId
  onChoose: (browser: BrowserId) => void
}) {
  const { t } = useTranslation('extension', { keyPrefix: 'browser' })
  const radio = useRadioGroup(BROWSERS, browser, (value) => onChoose(value))
  return (
    <div className="grid gap-2">
      <p id="browser-picker" className="text-sm font-medium">
        {t('question')}
      </p>
      <div {...radio.group} aria-labelledby="browser-picker" className="flex flex-wrap gap-1.5">
        {BROWSERS.map((id, index) => (
          <button
            key={id}
            type="button"
            {...radio.item(id, index)}
            className={cn(
              'rounded-full border px-3 py-1 text-sm outline-none transition-colors hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring',
              browser === id && 'border-primary/50 bg-primary/10 font-medium text-primary',
            )}
          >
            {id === detected ? `${t(`names.${id}`)} ` : t(`names.${id}`)}
            {id === detected && <span className="text-xs text-muted-foreground">{t('detected')}</span>}
          </button>
        ))}
      </div>
    </div>
  )
}
