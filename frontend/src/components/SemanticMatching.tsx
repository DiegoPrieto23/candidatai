import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { CheckCircleIcon, CircleNotchIcon, SparkleIcon, WarningCircleIcon } from '@phosphor-icons/react'
import type { MatchView } from '@/api/client'
import { useInstallSemanticMatching, useSemanticMatching } from '@/api/queries'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { errorMessage } from '@/lib/errors'
import { cn } from '@/lib/utils'

const BENEFITS = ['synonyms', 'languages', 'fewSkills', 'weight'] as const

type State = 'off' | 'installing' | 'failed' | 'installed' | 'disabled' | 'docker'

function useSemanticState(): State | undefined {
  const { data } = useSemanticMatching()
  if (!data) return undefined
  if (data.installing) return 'installing'
  if (data.disabled) return 'disabled'
  if (data.installed) return 'installed'
  if (data.in_docker) return 'docker'
  return data.error ? 'failed' : 'off'
}

/**
 * Lo que está pasando, bien a la vista: instalándose (con el aviso de que tarda y se puede seguir
 * usando la app), instalada, fallida o sin activar. Con el botón para ver qué aporta e instalarla.
 */
function SemanticStatus({ state, compact, prefix = 'semantic.state' }: { state: State; compact?: boolean; prefix?: string }) {
  const { t } = useTranslation('match')
  const [open, setOpen] = useState(false)
  const tone = {
    installing: 'border-primary/40 bg-primary/5',
    failed: 'border-destructive/40 bg-destructive/5',
    installed: 'border-emerald-500/40 bg-emerald-500/5',
  }[state as string] ?? 'border-dashed'
  const icon =
    state === 'installing' ? (
      <CircleNotchIcon className="size-5 shrink-0 animate-spin text-primary" aria-hidden />
    ) : state === 'failed' ? (
      <WarningCircleIcon className="size-5 shrink-0 text-destructive" weight="duotone" aria-hidden />
    ) : state === 'installed' ? (
      <CheckCircleIcon className="size-5 shrink-0 text-emerald-600 dark:text-emerald-400" weight="duotone" aria-hidden />
    ) : (
      <SparkleIcon className="size-5 shrink-0 text-primary" weight="duotone" aria-hidden />
    )
  const action =
    state === 'off' ? t('semantic.learnMore') : state === 'failed' ? t('semantic.retry') : null

  return (
    <div
      role={state === 'failed' ? 'alert' : 'status'}
      className={cn('flex gap-3 rounded-lg border text-sm', compact ? 'p-3' : 'p-4', tone)}
    >
      {icon}
      <div className="min-w-0 flex-1 space-y-1">
        <p className="font-medium text-foreground">{t(`${prefix}.${state}.title` as never)}</p>
        <p className="text-muted-foreground">{t(`${prefix}.${state}.body` as never)}</p>
        {action && (
          <Button type="button" variant="outline" size="sm" className="mt-2" onClick={() => setOpen(true)}>
            <SparkleIcon weight="duotone" className="text-primary" />
            {action}
          </Button>
        )}
      </div>
      <SemanticMatchingDialog open={open} onOpenChange={setOpen} />
    </div>
  )
}

/**
 * Junto al score de una oferta: si se calculó con la comparación por significado, cuánto se
 * parecen tu perfil y la oferta (así se ve que está activa y leyendo tu perfil); si no, el aviso
 * de que instalándola el encaje sale más fino, o que se está instalando.
 */
export function SemanticScoreHint({ match }: { match: MatchView }) {
  const { t } = useTranslation('match')
  const state = useSemanticState()
  const semantic = match.breakdown.semantic
  if (semantic) {
    return (
      <p className="flex items-start gap-2 text-sm text-muted-foreground">
        <SparkleIcon className="mt-0.5 size-4 shrink-0 text-primary" weight="duotone" aria-hidden />
        <span>{t('semantic.score.active', { pct: Math.round(semantic.value * 100) })}</span>
      </p>
    )
  }
  if (state === 'off' || state === 'failed') return <SemanticStatus state={state} compact prefix="semantic.score" />
  if (state === 'installing') return <SemanticStatus state={state} compact />
  return null
}

/** En la página «Agente»: la opción siempre a mano, esté como esté. */
export function SemanticMatchingCard() {
  const state = useSemanticState()
  if (!state) return null
  return <SemanticStatus state={state} />
}

function SemanticMatchingDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const { t } = useTranslation('match')
  const { data } = useSemanticMatching(open)
  const install = useInstallSemanticMatching()
  const docker = data?.in_docker ?? false
  const error = install.error ? errorMessage(install.error) : data?.error

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <SparkleIcon weight="duotone" className="size-5 text-primary" aria-hidden />
            {t('semantic.title')}
          </DialogTitle>
          <DialogDescription>{t('semantic.intro')}</DialogDescription>
        </DialogHeader>
        <ul className="list-disc space-y-1.5 pl-5 text-sm">
          {BENEFITS.map((key) => (
            <li key={key}>{t(`semantic.benefits.${key}`)}</li>
          ))}
        </ul>
        <div className="space-y-1.5 rounded-lg border border-dashed p-3 text-xs text-muted-foreground">
          <p>{t('semantic.local')}</p>
          <p>{t('semantic.permanent')}</p>
          <p>{t('semantic.size')}</p>
        </div>
        {docker && <p className="text-sm text-muted-foreground">{t('semantic.docker')}</p>}
        {error && (
          <p role="alert" className="text-sm break-words text-destructive">
            {error}
          </p>
        )}
        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            {t('semantic.notNow')}
          </Button>
          {!docker && (
            <Button
              type="button"
              disabled={install.isPending}
              onClick={() => install.mutate(undefined, { onSuccess: () => onOpenChange(false) })}
            >
              <SparkleIcon weight="duotone" />
              {install.isPending ? t('semantic.starting') : t('semantic.install')}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
