import type { TFunction } from 'i18next'
import type { AgentTaskView, PromptView } from '@/api/client'
import type { AgentAction, AgentRunEvent } from '@/api/queries'

/** Los textos del aviso (`nav`, `tasks`). */
export type TasksT = TFunction<'nav', 'tasks'>

/** Dónde se ve el resultado. Lo que es de una oferta va a su ficha, en la pestaña que toca. */
export function resultLink(task: AgentTaskView): string | null {
  const action = task.action as AgentAction
  if (action === 'process-jobs') return '/bandeja'
  if (action === 'assess-fit') return '/bandeja/revision'
  if (action === 'review-replies') return '/respuestas'
  if (task.job_id === null) return null
  if (action === 'research-company') return `/jobs/${task.job_id}?tab=company`
  if (action === 'draft-message' || action === 'draft-follow-up') return `/jobs/${task.job_id}?tab=process`
  return `/jobs/${task.job_id}`
}

/** Las herramientas con nombre propio en el aviso; las demás, «Usando get_x». */
const NAMED_TOOLS = new Set([
  'get_profile',
  'get_context',
  'get_extraction',
  'get_match',
  'get_cv_brief',
  'check_job_open',
  'list_cv_templates',
  'check_cv_fit',
  'save_cv_content',
  'get_cv_content',
  'save_cv_verification',
  'get_cv_correction',
  'get_cover_letter',
  'save_cover_letter',
  'save_cover_letter_verification',
  'save_fit_assessment',
  'save_extraction',
  'list_jobs',
  'get_job',
  'get_status',
  'Skill',
  'Agent',
  'Task',
  'Read',
  'skill',
  'task',
  'command_execution',
  'web_search',
  'file_change',
  'collab_tool_call',
])

/** Lo que hace una herramienta, en palabras: «Leyendo el perfil», «Subagente writer». */
export function toolLabel(t: TasksT, tool: string | null | undefined, detail?: string | null): string {
  if (!tool) return t('tools.unknown' as never)
  if (!NAMED_TOOLS.has(tool)) return t('tools.other' as never, { tool })
  const key = tool.toLowerCase() === 'task' ? 'agent' : tool.toLowerCase()
  return t(`tools.${key}` as never, { detail: detail ?? '?' })
}

/** El paso en curso («3/6 · Redactar») o, si no hay pasos, nada. */
export function stepText(t: TasksT, steps: AgentTaskView['steps']): string | null {
  const index = steps.findIndex((step) => step.state === 'current')
  if (index < 0) return null
  return t('stepOf' as never, { n: index + 1, total: steps.length, step: t(`steps.${steps[index].id}` as never) })
}

/** Una herramienta con su resultado (si ya llegó), o un evento suelto de la conversación. */
export type RunItem =
  | { kind: 'tool'; start: AgentRunEvent; result: AgentRunEvent | null }
  | { kind: 'other'; event: AgentRunEvent }

/** Junta cada `tool_start` con el primer `tool_result` de la misma herramienta que venga detrás. */
export function pairTools(events: AgentRunEvent[]): RunItem[] {
  const items: RunItem[] = []
  const open: Extract<RunItem, { kind: 'tool' }>[] = []
  for (const event of events) {
    if (event.kind === 'tool_start') {
      const item = { kind: 'tool' as const, start: event, result: null }
      items.push(item)
      open.push(item)
    } else if (event.kind === 'tool_result') {
      const index = open.findIndex((item) => item.start.tool === event.tool && item.start.sub === event.sub)
      if (index >= 0) {
        open[index].result = event
        open.splice(index, 1)
      } else {
        // Sin su inicio (algún agente solo avisa al acabar): se ve igual, sobre todo si se denegó.
        items.push({ kind: 'tool', start: { ...event, kind: 'tool_start', text: null }, result: event })
      }
    } else {
      items.push({ kind: 'other', event })
    }
  }
  return items
}


/** Las herramientas con que el agente pregunta o pide permiso: en el panel las sustituye su tarjeta. */
export const PROMPT_TOOLS = new Set(['ask_user', 'wait_user_action', 'request_permission'])

/** Un paso de la conversación o una pregunta/permiso, para pintarlos juntos en orden. */
export type PanelEntry = { kind: 'item'; item: RunItem } | { kind: 'prompt'; prompt: PromptView }

function itemTime(item: RunItem): number {
  return Date.parse(item.kind === 'tool' ? item.start.at : item.event.at)
}

/**
 * Junta la conversación y las preguntas por la hora. Una pregunta va antes que el primer paso
 * guardado después de ella (los pasos se guardan por tandas, unos segundos tarde); con la misma
 * hora, primero el paso.
 */
export function mergeByTime(items: RunItem[], prompts: PromptView[]): PanelEntry[] {
  const merged: PanelEntry[] = []
  const queue = [...prompts].sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at))
  for (const item of items) {
    while (queue.length > 0 && Date.parse(queue[0].created_at) < itemTime(item)) {
      merged.push({ kind: 'prompt', prompt: queue.shift() as PromptView })
    }
    merged.push({ kind: 'item', item })
  }
  for (const prompt of queue) merged.push({ kind: 'prompt', prompt })
  return merged
}
