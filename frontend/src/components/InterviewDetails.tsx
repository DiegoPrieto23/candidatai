import { useId, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { FilePdfIcon } from '@phosphor-icons/react'
import { fileUrls, type MilestoneOut, type Stage } from '@/api/client'
import { useSavePrepInstructions } from '@/api/queries'
import { AgentButton } from '@/components/AgentButton'
import { OpenFolderButton } from '@/components/OpenFolderButton'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { errorMessage } from '@/lib/errors'
import { interviewPhase, planIsStale } from '@/lib/interviews'
import { dateFormatter, formatDateTime } from '@/lib/labels'

type PrepBlock = NonNullable<MilestoneOut['prep_plan']>['blocks'][number]


/** «lun, 13 oct» de una fecha `AAAA-MM-DD` (sin pasar por UTC, que la movería de día). */
function formatDay(iso: string): string {
  const [y, m, d] = iso.split('-').map(Number)
  return dateFormatter({ weekday: 'short', day: 'numeric', month: 'short' }).format(new Date(y, m - 1, d))
}

function byDay(blocks: PrepBlock[]): [string, PrepBlock[]][] {
  const days = new Map<string, PrepBlock[]>()
  for (const block of blocks) days.set(block.date, [...(days.get(block.date) ?? []), block])
  return [...days.entries()]
}

const MAX_INSTRUCTIONS = 4000

/**
 * Lo que quieres que tengan en cuenta la guía y el simulacro de esta entrevista. Se guarda en el
 * hito (la orden que abre tu agente solo lleva ids) y el skill lo lee con `get_interviews`. Se
 * guarda también al salir de la caja, que es lo que pasa al pulsar «Preparar» o «Simulacro».
 */
function PrepInstructions({ milestone }: { milestone: MilestoneOut }) {
  const { t } = useTranslation('status', { keyPrefix: 'interview.instructions' })
  const id = useId()
  const save = useSavePrepInstructions(milestone.job_id)
  const saved = milestone.prep_instructions ?? ''
  const [text, setText] = useState(saved)
  const [justSaved, setJustSaved] = useState(false)
  const dirty = text.trim() !== saved

  const submit = () => {
    if (!dirty || save.isPending) return
    save.mutate(
      { milestoneId: milestone.id, instructions: text.trim() },
      { onSuccess: () => setJustSaved(true) },
    )
  }

  return (
    <div className="mt-2 space-y-1.5">
      <Label htmlFor={id} className="text-xs">
        {t('label')}
      </Label>
      <Textarea
        id={id}
        rows={2}
        maxLength={MAX_INSTRUCTIONS}
        value={text}
        placeholder={t('placeholder')}
        onChange={(e) => {
          setText(e.target.value)
          setJustSaved(false)
        }}
        onBlur={submit}
        className="resize-y text-sm"
      />
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <span>{t('hint')}</span>
        {dirty && (
          <Button type="button" variant="outline" size="sm" className="h-7" disabled={save.isPending} onClick={submit}>
            {save.isPending ? t('saving') : t('save')}
          </Button>
        )}
        {!dirty && justSaved && <span role="status">{t('saved')}</span>}
      </div>
      {save.error && (
        <p role="alert" className="text-xs text-destructive">
          {errorMessage(save.error)}
        </p>
      )}
    </div>
  )
}

export function InterviewActions({ milestone, stage }: { milestone: MilestoneOut; stage: Stage | null }) {
  const { t } = useTranslation('status', { keyPrefix: 'interview' })
  const phase = interviewPhase(milestone, stage)
  if (!phase) return null
  if (phase === 'past') {
    return (
      <div className="mt-2">
        <AgentButton action="debrief-interview" milestoneId={milestone.id}>
          {milestone.debrief_notes ? t('debriefAgain') : t('debrief')}
        </AgentButton>
      </div>
    )
  }
  return (
    <>
      <PrepInstructions milestone={milestone} />
      <div className="mt-2 flex flex-wrap items-start gap-2">
        <AgentButton action="prepare-interview" milestoneId={milestone.id}>
          {t('prepare')}
        </AgentButton>
        <AgentButton action="mock-interview" milestoneId={milestone.id}>
          {t('mock')}
        </AgentButton>
      </div>
    </>
  )
}

/** Guía en PDF, plan de preparación y repaso de una entrevista, si los hay. */
export function InterviewDetails({ milestone }: { milestone: MilestoneOut }) {
  const { t } = useTranslation('status', { keyPrefix: 'interview' })
  const plan = milestone.prep_plan
  const guide = milestone.guide
  if (!plan && !milestone.debrief_notes && !guide) return null
  const minutes = plan ? plan.blocks.reduce((sum, b) => sum + b.minutes, 0) : 0
  return (
    <div className="mt-2 space-y-2">
      {guide && (
        // La guía que redactó tu agente y maquetó la app. Se abre en otra pestaña.
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 rounded-md border bg-muted/30 px-3 py-2 text-xs">
          <FilePdfIcon className="size-4 shrink-0 text-primary" weight="duotone" aria-hidden />
          <a
            href={fileUrls.interviewGuide(milestone.id)}
            target="_blank"
            rel="noreferrer"
            className="font-medium underline-offset-4 hover:underline"
          >
            {t('guide')}
          </a>
          <span className="text-muted-foreground">{t('guideSaved', { date: formatDateTime(guide.saved_at) })}</span>
        </div>
      )}
      {plan && (
        <details className="rounded-md border bg-muted/30 px-3 py-2 text-xs">
          <summary className="cursor-pointer font-medium">
            {t('plan', { count: plan.blocks.length, minutes })}
          </summary>
          <div className="mt-2 space-y-2">
            {planIsStale(milestone) && (
              <p className="text-amber-700 dark:text-amber-400">
                {t('stale')}
              </p>
            )}
            {byDay(plan.blocks).map(([day, blocks]) => (
              <div key={day}>
                <p className="font-medium capitalize">{formatDay(day)}</p>
                <ul className="mt-0.5 space-y-0.5 text-muted-foreground">
                  {blocks.map((b, i) => (
                    <li key={i}>
                      <span className="tabular-nums">{t('minutes', { count: b.minutes })}</span> · {b.topic}
                      {b.detail && <span> — {b.detail}</span>}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
            {plan.dossier && (
              <div className="space-y-1.5 border-t pt-2">
                <p>
                  {t('dossier')} <code className="rounded bg-muted px-1 py-0.5 font-mono">{plan.dossier}</code>
                </p>
                <OpenFolderButton folder="entrevistas" label={t('openDossiers')} />
              </div>
            )}
          </div>
        </details>
      )}
      {milestone.debrief_notes && (
        <div className="rounded-md border bg-muted/30 px-3 py-2 text-xs" aria-label={t('debriefLabel')}>
          <p className="font-medium">{t('debriefTitle')}</p>
          <p className="mt-0.5 whitespace-pre-line text-muted-foreground">{milestone.debrief_notes}</p>
          {milestone.next_steps && (
            <>
              <p className="mt-2 font-medium">{t('nextSteps')}</p>
              <p className="mt-0.5 whitespace-pre-line text-muted-foreground">{milestone.next_steps}</p>
            </>
          )}
        </div>
      )}
    </div>
  )
}
