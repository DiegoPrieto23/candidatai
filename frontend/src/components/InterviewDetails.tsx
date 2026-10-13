import { useTranslation } from 'react-i18next'
import { type MilestoneOut, type Stage } from '@/api/client'
import { AgentButton } from '@/components/AgentButton'
import { OpenFolderButton } from '@/components/OpenFolderButton'
import { interviewPhase, planIsStale } from '@/lib/interviews'
import { dateFormatter } from '@/lib/labels'

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

export function InterviewActions({ milestone, stage }: { milestone: MilestoneOut; stage: Stage | null }) {
  const { t } = useTranslation('status', { keyPrefix: 'interview' })
  const phase = interviewPhase(milestone, stage)
  if (!phase) return null
  return (
    <div className="mt-2 flex flex-wrap items-start gap-2">
      {phase === 'upcoming' ? (
        <>
          <AgentButton action="prepare-interview" milestoneId={milestone.id}>
            {t('prepare')}
          </AgentButton>
          <AgentButton action="mock-interview" milestoneId={milestone.id}>
            {t('mock')}
          </AgentButton>
        </>
      ) : (
        <AgentButton action="debrief-interview" milestoneId={milestone.id}>
          {milestone.debrief_notes ? t('debriefAgain') : t('debrief')}
        </AgentButton>
      )}
    </div>
  )
}

/** Plan de preparación y repaso de una entrevista, si los hay. */
export function InterviewDetails({ milestone }: { milestone: MilestoneOut }) {
  const { t } = useTranslation('status', { keyPrefix: 'interview' })
  const plan = milestone.prep_plan
  if (!plan && !milestone.debrief_notes) return null
  const minutes = plan ? plan.blocks.reduce((sum, b) => sum + b.minutes, 0) : 0
  return (
    <div className="mt-2 space-y-2">
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
