/**
 * «Qué quieres corregir» de un CV ya generado. El texto se guarda al pulsar el botón del agente,
 * que abre `correct-cv` con solo el `job_id`: tu agente lo lee después, como dato. Mientras siga
 * pendiente se pregunta cada pocos segundos, y al cerrarse se refresca el CV.
 */
import { useEffect, useRef, useState } from 'react'
import { InfoIcon, XIcon } from '@phosphor-icons/react'
import { useTranslation } from 'react-i18next'
import { useCancelCvCorrection, useCvHistory, useRequestCvCorrection, useRefreshCv } from '@/api/queries'
import { AgentButton } from '@/components/AgentButton'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { errorMessage } from '@/lib/errors'

const MAX_INSTRUCTION = 2000

/** Las keywords de la oferta que faltan en el CV, para las sugerencias. Muy largas no caben. */
const MAX_SUGGESTED_KEYWORDS = 2
const MAX_KEYWORD = 40

export function CvCorrection({ jobId, missingKeywords = [] }: { jobId: number; missingKeywords?: string[] }) {
  const { t } = useTranslation('cv', { keyPrefix: 'correction' })
  const history = useCvHistory(jobId)
  const request = useRequestCvCorrection(jobId)
  const cancel = useCancelCvCorrection(jobId)
  const refresh = useRefreshCv(jobId)
  const [text, setText] = useState('')
  const id = `cv-correction-${jobId}`

  const correction = history.data?.correction ?? null
  const pending = correction?.status === 'pending' ? correction : null
  const wasPending = useRef(false)
  useEffect(() => {
    if (wasPending.current && !pending) refresh()
    wasPending.current = pending !== null
  }, [pending, refresh])

  const instruction = text.trim()
  // Solo rellenan la caja: lo envías tú, y lo que tu perfil no respalde tu agente no lo añade.
  const suggestions = [
    t('suggest.shorter'),
    t('suggest.focus'),
    ...missingKeywords
      .filter((keyword) => keyword.length <= MAX_KEYWORD)
      .slice(0, MAX_SUGGESTED_KEYWORDS)
      .map((keyword) => t('suggest.keyword', { keyword })),
  ]
  const prepare = async () => {
    if (!instruction) return
    await request.mutateAsync(instruction)
    setText('')
  }

  return (
    <div className="grid w-full max-w-xl gap-3">
      <div className="flex flex-wrap gap-1.5">
        {suggestions.map((suggestion) => (
          <Button
            key={suggestion}
            type="button"
            variant="outline"
            size="xs"
            className="h-auto rounded-full py-1 text-left whitespace-normal"
            onClick={() => setText((current) => (current.trim() ? `${current.trimEnd()}\n${suggestion}` : suggestion))}
          >
            {suggestion}
          </Button>
        ))}
      </div>
      <div className="grid gap-1.5">
        <Label htmlFor={id}>{t('label')}</Label>
        <Textarea
          id={id}
          value={text}
          onChange={(e) => setText(e.target.value)}
          maxLength={MAX_INSTRUCTION}
          rows={3}
          placeholder={t('placeholder')}
        />
        <p className="text-xs text-muted-foreground">{t('hint')}</p>
      </div>
      {pending && (
        <div role="status" className="flex items-start gap-2 rounded-md bg-muted/70 px-3 py-2 text-sm">
          <InfoIcon className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
          <span className="min-w-0 flex-1 break-words">
            <span className="block font-medium">{t('pending')}</span>
            <span className="block text-foreground/85">{pending.instruction}</span>
          </span>
          <Button
            type="button"
            variant="ghost"
            size="xs"
            disabled={cancel.isPending}
            onClick={() => cancel.mutate(pending.id)}
          >
            <XIcon /> {t('cancel')}
          </Button>
        </div>
      )}
      {correction?.status === 'declined' && (
        <div role="status" className="rounded-md border border-warning-border bg-warning/40 px-3 py-2 text-sm">
          <span className="block font-medium">{t('declined')}</span>
          <span className="block break-words text-foreground/85">{correction.instruction}</span>
          {correction.note && <span className="mt-1 block break-words text-muted-foreground">{correction.note}</span>}
        </div>
      )}
      {(request.error || cancel.error) && (
        <p role="alert" className="text-sm text-destructive">
          {errorMessage(request.error ?? cancel.error)}
        </p>
      )}
      <AgentButton
        action="correct-cv"
        jobId={jobId}
        prepare={prepare}
        disabled={request.isPending || (!instruction && !pending)}
      >
        {t('submit')}
      </AgentButton>
    </div>
  )
}
