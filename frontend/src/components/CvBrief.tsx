/**
 * Indicaciones para el CV de una oferta («destaca el proyecto de Airflow», «en inglés»…), junto a
 * «Generar CV». Se guardan solas al salir de la caja (también al pulsar el botón del agente justo
 * después) y tu agente las lee cada vez que redacta o rehace ese CV.
 */
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { CheckIcon } from '@phosphor-icons/react'
import { useCvBrief, useSaveCvBrief } from '@/api/queries'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { errorMessage } from '@/lib/errors'

const MAX_INSTRUCTIONS = 4000

function BriefForm({ jobId, saved }: { jobId: number; saved: string }) {
  const { t } = useTranslation('cv', { keyPrefix: 'brief' })
  const save = useSaveCvBrief(jobId)
  const [text, setText] = useState(saved)
  const id = `cv-brief-${jobId}`
  const dirty = text.trim() !== saved
  return (
    <div className="grid w-full gap-1.5">
      <Label htmlFor={id}>{t('label')}</Label>
      <Textarea
        id={id}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onBlur={() => dirty && save.mutate(text)}
        maxLength={MAX_INSTRUCTIONS}
        rows={3}
        placeholder={t('placeholder')}
      />
      <p className="text-xs text-muted-foreground" role="status">
        {save.isPending ? (
          t('saving')
        ) : save.isSuccess && !dirty ? (
          <span className="inline-flex items-center gap-1 text-emerald-700 dark:text-emerald-400">
            <CheckIcon className="size-3.5" aria-hidden />
            {t('saved')}
          </span>
        ) : (
          t('hint')
        )}
      </p>
      {save.error && (
        <p role="alert" className="text-sm text-destructive">
          {errorMessage(save.error)}
        </p>
      )}
    </div>
  )
}

export function CvBrief({ jobId }: { jobId: number }) {
  const brief = useCvBrief(jobId)
  if (!brief.isSuccess) return null
  return <BriefForm jobId={jobId} saved={brief.data.instructions} />
}
