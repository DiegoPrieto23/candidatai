import { useTranslation } from 'react-i18next'
import { XIcon } from '@phosphor-icons/react'
import { useDeletePermissionRule, usePermissionRules } from '@/api/queries'
import { Button } from '@/components/ui/button'
import { errorMessage } from '@/lib/errors'

/**
 * Lo permitido «siempre en este proyecto» desde el panel de una ejecución (fase 48.1b). Se guarda
 * en la app, no en la configuración del agente; al quitarlo, la próxima vez se vuelve a preguntar.
 * Sin ninguno, no se enseña nada.
 */
export function PermissionRules() {
  const { t } = useTranslation('agent', { keyPrefix: 'permissions' })
  const { data } = usePermissionRules()
  const remove = useDeletePermissionRule()
  const rules = data?.rules ?? []
  if (rules.length === 0) return null
  return (
    <section aria-labelledby="permission-rules" className="mt-3 rounded-xl border bg-card p-4">
      <h3 id="permission-rules" className="text-sm font-medium">
        {t('title')}
      </h3>
      <p className="mt-0.5 text-sm text-muted-foreground">{t('body')}</p>
      <ul className="mt-3 space-y-2">
        {rules.map((rule) => (
          <li key={rule.id} className="flex items-start gap-2">
            <code className="min-w-0 flex-1 rounded border bg-muted/40 px-2 py-1 font-mono text-xs break-all">
              <span className="font-semibold">{rule.tool}</span> {rule.detail}
            </code>
            <Button
              variant="ghost"
              size="sm"
              disabled={remove.isPending}
              aria-label={t('remove', { tool: rule.tool, detail: rule.detail })}
              onClick={() => remove.mutate(rule.id)}
            >
              <XIcon />
              {t('removeShort')}
            </Button>
          </li>
        ))}
      </ul>
      {remove.error && (
        <p role="alert" className="mt-2 text-xs text-destructive">
          {errorMessage(remove.error)}
        </p>
      )}
    </section>
  )
}
