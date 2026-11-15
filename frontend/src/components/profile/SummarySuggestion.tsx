import { useEffect, useState } from 'react'
import { ArrowDownIcon, RobotIcon, WarningIcon, XIcon } from '@phosphor-icons/react'
import { useTranslation } from 'react-i18next'
import { useProfileSuggestions, useResolveProfileSuggestion } from '@/api/queries'
import { Hint } from '@/components/Hint'
import { AgentButton } from '@/components/AgentButton'
import { Button } from '@/components/ui/button'
import { errorMessage } from '@/lib/errors'

/**
 * «Generar resumen en inglés» y, cuando tu agente lo deja, su propuesta junto al campo. Usarla la
 * pasa al formulario, donde se edita y se guarda como cualquier cambio: el agente nunca escribe en
 * el perfil.
 */
const WAIT_MINUTES = 10

export function SummarySuggestion({
  spanish,
  saved,
  onUse,
}: {
  spanish: string | null | undefined
  /** El resumen en español del perfil guardado, que es el que lee tu agente. */
  saved: string | null | undefined
  onUse: (text: string) => void
}) {
  const { t } = useTranslation('profileEditor', { keyPrefix: 'summarySuggestion' })
  // Hasta cuándo se espera la propuesta (ms): el agente puede fallar o cerrarse sin dejarla.
  const [waitUntil, setWaitUntil] = useState<number | null>(null)
  const suggestions = useProfileSuggestions(waitUntil !== null)
  const resolve = useResolveProfileSuggestion()
  const suggestion = suggestions.data?.suggestions.find((s) => s.field === 'summary.en')
  // Con la propuesta ya aquí (o pasado el tope, abajo), se deja de preguntar.
  if (waitUntil !== null && suggestion) setWaitUntil(null)
  useEffect(() => {
    if (waitUntil === null) return
    const timer = setTimeout(() => setWaitUntil(null), Math.max(0, waitUntil - Date.now()))
    return () => clearTimeout(timer)
  }, [waitUntil])
  const source = (spanish ?? '').trim()
  // El agente traduce el resumen guardado: con el español a medio editar, primero se guarda.
  const unsaved = source !== (saved ?? '').trim()
  const outdated = suggestion != null && (suggestion.source ?? '') !== source

  return (
    <div className="grid gap-2 sm:col-start-2">
      {!suggestion && (
        <span className="inline-flex items-center gap-1 justify-self-start">
          <AgentButton
            action="translate-summary"
            disabled={!source || unsaved}
            onStarted={() => setWaitUntil(Date.now() + WAIT_MINUTES * 60_000)}
          >
            {t('generate')}
          </AgentButton>
          {source && unsaved && <Hint text={t('saveFirst')} label={t('saveFirstLabel')} />}
        </span>
      )}
      {suggestion && (
        <section aria-label={t('label')} className="grid gap-2 rounded-lg border border-primary/20 bg-accent/40 p-3 text-sm">
          <p className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
            <RobotIcon aria-hidden /> {t('label')}
          </p>
          <p className="whitespace-pre-line">{suggestion.text}</p>
          {outdated && (
            <p className="flex items-start gap-1.5 text-xs text-warning-foreground">
              <WarningIcon className="mt-0.5 shrink-0" aria-hidden /> {t('outdated')}
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              size="xs"
              disabled={resolve.isPending}
              onClick={() =>
                resolve.mutate({ id: suggestion.id, outcome: 'used' }, { onSuccess: () => onUse(suggestion.text) })
              }
            >
              <ArrowDownIcon /> {t('use')}
            </Button>
            <Button
              type="button"
              size="xs"
              variant="ghost"
              disabled={resolve.isPending}
              onClick={() => resolve.mutate({ id: suggestion.id, outcome: 'discarded' })}
            >
              <XIcon /> {t('discard')}
            </Button>
          </div>
          {resolve.isError && (
            <p role="alert" className="text-xs text-destructive">
              {errorMessage(resolve.error)}
            </p>
          )}
        </section>
      )}
    </div>
  )
}
