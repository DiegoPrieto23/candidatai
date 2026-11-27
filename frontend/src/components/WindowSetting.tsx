import { useTranslation } from 'react-i18next'
import { useAgentLauncher, useSaveWindowPreference } from '@/api/queries'
import { Switch } from '@/components/Switch'
import { errorMessage } from '@/lib/errors'

/**
 * «Abrir en una ventana» (fase 48.1a): por defecto, lo que puede ir sin ventana se sigue en el aviso
 * del portal; con esto, el botón principal abre el agente en su ventana, como antes.
 */
export function WindowSetting() {
  const { t } = useTranslation('agent', { keyPrefix: 'window' })
  const launcher = useAgentLauncher()
  const save = useSaveWindowPreference()
  if (!launcher.data || launcher.data.no_agent_installed) return null
  const checked = save.isPending ? save.variables : launcher.data.open_in_window
  return (
    <div className="mt-3 flex items-start justify-between gap-4 rounded-xl border bg-card p-4">
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium">{t('title')}</p>
        <p className="mt-0.5 text-sm text-muted-foreground">{checked ? t('on') : t('off')}</p>
        {save.error && (
          <p role="alert" className="mt-1 text-xs text-destructive">
            {errorMessage(save.error)}
          </p>
        )}
      </div>
      <Switch checked={checked} disabled={save.isPending} label={t('title')} onChange={(next) => save.mutate(next)} />
    </div>
  )
}
