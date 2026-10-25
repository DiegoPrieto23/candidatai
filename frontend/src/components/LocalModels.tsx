import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'
import type { LocalModelsStatus } from '@/api/client'

/**
 * Bloque «Modelos locales» de la tarjeta de un agente que los admite (fase 24.6): si Ollama responde
 * en este equipo, qué modelos tiene y con qué contexto. La app solo lee sus metadatos; no hace
 * inferencia. Los avisos llegan con un código y se traducen aquí.
 */

type Warning = LocalModelsStatus['warnings'][number]

function warningText(t: TFunction<'agents'>, warning: Warning, status: LocalModelsStatus): string {
  const model = status.models.find((m) => m.name === warning.model)
  switch (warning.code) {
    case 'context_low':
      return t('local.contextLow', { model: warning.model, tokens: model?.context ?? '?', min: status.min_context })
    case 'small_model':
      return t('local.smallModel', { model: warning.model, action: warning.action })
    case 'no_models':
      return t('local.noModels')
    default:
      return warning.text
  }
}

export function LocalModels({ status }: { status: LocalModelsStatus | undefined }) {
  const { t } = useTranslation('agents')
  if (!status) return null
  return (
    <div className="mt-3 space-y-1.5 border-t pt-3 text-xs" aria-label={t('local.title')}>
      <p className="font-medium text-foreground">{t('local.title')}</p>
      {!status.running ? (
        <p className="text-muted-foreground">{t('local.down', { url: status.url || '127.0.0.1:11434' })}</p>
      ) : (
        <>
          <p className="text-muted-foreground">
            {t('local.running', { version: status.version ?? '?' })} ·{' '}
            {status.env_context
              ? t('local.envContext', { tokens: status.env_context })
              : t('local.noEnvContext', { tokens: status.default_context })}
          </p>
          {status.models.length > 0 && (
            <ul className="space-y-0.5">
              {status.models.map((model) => (
                <li key={model.name} className="flex flex-wrap gap-x-2">
                  <span className="font-mono">{model.name}</span>
                  <span className="text-muted-foreground tabular">
                    {model.parameter_size ?? '?'} · {t('local.context', { tokens: model.context })}
                    {model.tools === false && ` · ${t('local.noTools')}`}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
      {status.warnings.map((warning, index) => (
        <p key={index} className="text-warning-foreground">
          {warningText(t, warning, status)}
        </p>
      ))}
      <p className="text-muted-foreground">{t('local.guide')}</p>
    </div>
  )
}
