import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ArrowCounterClockwiseIcon } from '@phosphor-icons/react'
import { useProfileDiff, useUndoProfile } from '@/api/queries'
import { Button } from '@/components/ui/button'
import { errorMessage } from '@/lib/errors'
import { Block } from './fields'
import { useProfileState } from './editor'

/** «Ver cambios» (diff de las dos últimas versiones) y «Deshacer el último cambio». */
export function HistoryBlock() {
  const { t } = useTranslation('profileEditor')
  const { state, dirtyCount } = useProfileState()
  const [showDiff, setShowDiff] = useState(false)
  const diff = useProfileDiff(showDiff)
  const undo = useUndoProfile()
  const [message, setMessage] = useState<string | null>(null)
  return (
    <Block title={t('history.title')} hint={t('history.hint')}>
      <div className="flex flex-wrap items-center gap-2">
        <Button type="button" size="sm" variant="outline" aria-expanded={showDiff} onClick={() => setShowDiff((v) => !v)}>
          {showDiff ? t('history.hideDiff') : t('history.showDiff')}
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={state.undo_available === 0 || undo.isPending || dirtyCount > 0}
          onClick={() => {
            setMessage(null)
            undo.mutate(state.file_hash ?? null, {
              onSuccess: () => setMessage(t('history.undone')),
              onError: (e) => setMessage(errorMessage(e)),
            })
          }}
        >
          <ArrowCounterClockwiseIcon /> {t('history.undo')}
        </Button>
        <span className="text-xs text-muted-foreground">
          {dirtyCount > 0 ? t('history.saveFirst') : t('history.copies', { count: state.undo_available })}
        </span>
      </div>
      {message && (
        <p role="status" className="text-sm">
          {message}
        </p>
      )}
      {showDiff && (
        <pre aria-label={t('history.diffLabel')} className="max-h-96 overflow-auto rounded-md bg-muted/50 p-3 font-mono text-xs leading-relaxed">
          {diff.isPending ? '…' : diff.isError ? errorMessage(diff.error) : diff.data.diff || t('history.noDiff')}
        </pre>
      )}
    </Block>
  )
}
