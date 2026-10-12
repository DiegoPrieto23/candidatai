import { type MilestoneOut, type Stage } from '@/api/client'
import { AgentButton } from '@/components/AgentButton'
import { OpenFolderButton } from '@/components/OpenFolderButton'
import { interviewPhase, planIsStale } from '@/lib/interviews'

type PrepBlock = NonNullable<MilestoneOut['prep_plan']>['blocks'][number]

const dayFmt = new Intl.DateTimeFormat('es-ES', { weekday: 'short', day: 'numeric', month: 'short' })

/** «lun, 13 oct» de una fecha `AAAA-MM-DD` (sin pasar por UTC, que la movería de día). */
function formatDay(iso: string): string {
  const [y, m, d] = iso.split('-').map(Number)
  return dayFmt.format(new Date(y, m - 1, d))
}

function byDay(blocks: PrepBlock[]): [string, PrepBlock[]][] {
  const days = new Map<string, PrepBlock[]>()
  for (const block of blocks) days.set(block.date, [...(days.get(block.date) ?? []), block])
  return [...days.entries()]
}

export function InterviewActions({ milestone, stage }: { milestone: MilestoneOut; stage: Stage | null }) {
  const phase = interviewPhase(milestone, stage)
  if (!phase) return null
  return (
    <div className="mt-2 flex flex-wrap items-start gap-2">
      {phase === 'upcoming' ? (
        <>
          <AgentButton action="preparar-entrevista" milestoneId={milestone.id}>
            Preparar
          </AgentButton>
          <AgentButton action="simular-entrevista" milestoneId={milestone.id}>
            Simulacro
          </AgentButton>
        </>
      ) : (
        <AgentButton action="repasar-entrevista" milestoneId={milestone.id}>
          {milestone.debrief_notes ? 'Repasar otra vez' : 'Repasar'}
        </AgentButton>
      )}
    </div>
  )
}

/** Plan de preparación y repaso de una entrevista, si los hay. */
export function InterviewDetails({ milestone }: { milestone: MilestoneOut }) {
  const plan = milestone.prep_plan
  if (!plan && !milestone.debrief_notes) return null
  const minutes = plan ? plan.blocks.reduce((sum, b) => sum + b.minutes, 0) : 0
  return (
    <div className="mt-2 space-y-2">
      {plan && (
        <details className="rounded-md border bg-muted/30 px-3 py-2 text-xs">
          <summary className="cursor-pointer font-medium">
            Plan de preparación · {plan.blocks.length} {plan.blocks.length === 1 ? 'bloque' : 'bloques'},{' '}
            {minutes} min
          </summary>
          <div className="mt-2 space-y-2">
            {planIsStale(milestone) && (
              <p className="text-amber-700 dark:text-amber-400">
                La entrevista se ha movido antes de algunos bloques: pulsa «Preparar» para rehacer el plan.
              </p>
            )}
            {byDay(plan.blocks).map(([day, blocks]) => (
              <div key={day}>
                <p className="font-medium capitalize">{formatDay(day)}</p>
                <ul className="mt-0.5 space-y-0.5 text-muted-foreground">
                  {blocks.map((b, i) => (
                    <li key={i}>
                      <span className="tabular-nums">{b.minutes} min</span> · {b.topic}
                      {b.detail && <span> — {b.detail}</span>}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
            {plan.dossier && (
              <div className="space-y-1.5 border-t pt-2">
                <p>
                  Dosier: <code className="rounded bg-muted px-1 py-0.5 font-mono">{plan.dossier}</code>
                </p>
                <OpenFolderButton folder="entrevistas" label="Abrir carpeta de dosieres" />
              </div>
            )}
          </div>
        </details>
      )}
      {milestone.debrief_notes && (
        <div className="rounded-md border bg-muted/30 px-3 py-2 text-xs" aria-label="Repaso de la entrevista">
          <p className="font-medium">Repaso</p>
          <p className="mt-0.5 whitespace-pre-line text-muted-foreground">{milestone.debrief_notes}</p>
          {milestone.next_steps && (
            <>
              <p className="mt-2 font-medium">Próximos pasos</p>
              <p className="mt-0.5 whitespace-pre-line text-muted-foreground">{milestone.next_steps}</p>
            </>
          )}
        </div>
      )}
    </div>
  )
}
