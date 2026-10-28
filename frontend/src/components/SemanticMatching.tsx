import { useState } from 'react'
import { useTranslation } from 'react-i18next'
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

const BENEFITS = ['synonyms', 'languages', 'fewSkills', 'weight'] as const

/**
 * En el desglose del score, en lugar de «sin activar»: qué aporta la comparación por significado
 * y, si la quieres, instalarla. La instala el worker; la elección es permanente.
 */
export function SemanticMatchingNote() {
  const { t } = useTranslation('match')
  const [open, setOpen] = useState(false)
  const { data } = useSemanticMatching()

  if (data?.installing) return <span role="status">{t('semantic.installing')}</span>
  if (data?.error && !open) {
    return (
      <span role="alert">
        {t('semantic.failed')}{' '}
        <button type="button" onClick={() => setOpen(true)} className="underline underline-offset-2 hover:text-foreground">
          {t('semantic.retry')}
        </button>
      </span>
    )
  }
  return (
    <>
      {t('semantic.off')}{' '}
      <button type="button" onClick={() => setOpen(true)} className="underline underline-offset-2 hover:text-foreground">
        {t('semantic.learnMore')}
      </button>
      <SemanticMatchingDialog open={open} onOpenChange={setOpen} />
    </>
  )
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
          <DialogTitle>{t('semantic.title')}</DialogTitle>
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
              {install.isPending ? t('semantic.starting') : t('semantic.install')}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
