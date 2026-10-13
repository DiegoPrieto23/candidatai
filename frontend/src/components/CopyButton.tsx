import { useEffect, useRef, useState } from 'react'
import { CheckIcon, CopyIcon } from '@phosphor-icons/react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'

/** Copia un texto al portapapeles y lo confirma durante un momento. */
export function CopyButton({
  text,
  label,
  ariaLabel,
  disabled = false,
}: {
  text: string
  label?: string
  ariaLabel?: string
  disabled?: boolean
}) {
  const { t } = useTranslation()
  const [state, setState] = useState<'idle' | 'copied' | 'failed'>('idle')
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined)
  useEffect(() => () => clearTimeout(timer.current), [])
  const show = (next: 'copied' | 'failed') => {
    setState(next)
    clearTimeout(timer.current)
    timer.current = setTimeout(() => setState('idle'), next === 'copied' ? 1500 : 4000)
  }
  const copy = () => {
    // El portapapeles solo existe en contexto seguro (127.0.0.1 o localhost).
    if (!navigator.clipboard) return show('failed')
    navigator.clipboard.writeText(text).then(
      () => show('copied'),
      () => show('failed'),
    )
  }
  return (
    <>
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={disabled}
        aria-label={state === 'idle' ? ariaLabel : undefined}
        onClick={copy}
      >
        {state === 'copied' ? <CheckIcon /> : <CopyIcon />}
        {state === 'copied' ? t('copy.copied') : state === 'failed' ? t('copy.failed') : (label ?? t('copy.label'))}
      </Button>
      <span role="status" className="sr-only">
        {state === 'copied' ? t('copy.copiedStatus') : state === 'failed' ? t('copy.failed') : ''}
      </span>
    </>
  )
}
