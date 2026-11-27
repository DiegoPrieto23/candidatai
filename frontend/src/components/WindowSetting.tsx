import { useTranslation } from 'react-i18next'
import type { Schemas } from '@/api/client'
import { useAgentLauncher, useSaveWindowPreference } from '@/api/queries'
import { Switch } from '@/components/Switch'
import { errorMessage } from '@/lib/errors'

type WindowStyle = NonNullable<Schemas['WindowPreference']['window_style']>

/**
 * «Abrir en una ventana» (fase 48.1a): por defecto, lo que puede ir sin ventana se sigue en el aviso
 * del portal; con esto, el botón principal abre el agente en su ventana, como antes. En Windows
 * (fase 48.1d), además, cómo se abre esa ventana: minimizada, detrás del navegador o en Windows
 * Terminal.
 */
export function WindowSetting() {
  const { t } = useTranslation('agent', { keyPrefix: 'window' })
  const launcher = useAgentLauncher()
  const save = useSaveWindowPreference()
  if (!launcher.data || launcher.data.no_agent_installed) return null
  const data = launcher.data
  const pending = save.isPending ? save.variables : undefined
  const checked = pending?.open_in_window ?? data.open_in_window
  const style = pending?.window_style ?? data.window_style
  const styles = data.window_styles ?? []
  return (
    <div className="mt-3 rounded-xl border bg-card p-4">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium">{t('title')}</p>
          <p className="mt-0.5 text-sm text-muted-foreground">{checked ? t('on') : t('off')}</p>
        </div>
        <Switch
          checked={checked}
          disabled={save.isPending}
          label={t('title')}
          onChange={(next) => save.mutate({ open_in_window: next })}
        />
      </div>
      {styles.length > 0 && (
        <fieldset className="mt-4 border-t pt-3">
          <legend className="pt-3 text-sm font-medium">{t('style.title')}</legend>
          <p className="mt-0.5 text-sm text-muted-foreground">{t('style.hint')}</p>
          <div className="mt-2 space-y-1.5">
            {styles.map((option: WindowStyle) => (
              <label key={option} className="flex cursor-pointer items-start gap-2 text-sm">
                <input
                  type="radio"
                  name="window-style"
                  className="mt-1 accent-primary"
                  checked={style === option}
                  disabled={save.isPending}
                  onChange={() => save.mutate({ open_in_window: checked, window_style: option })}
                />
                <span>
                  {t(`style.${option}.label`)}
                  <span className="block text-xs text-muted-foreground">{t(`style.${option}.hint`)}</span>
                </span>
              </label>
            ))}
          </div>
        </fieldset>
      )}
      {save.error && (
        <p role="alert" className="mt-2 text-xs text-destructive">
          {errorMessage(save.error)}
        </p>
      )}
    </div>
  )
}
