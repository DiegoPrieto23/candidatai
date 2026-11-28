import { useCallback, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ChatsCircleIcon } from '@phosphor-icons/react'
import { useAgentRun } from '@/api/queries'
import { AgentRunPanel } from '@/components/AgentRunPanel'
import { Button } from '@/components/ui/button'

/**
 * «Ver conversación» de una ejecución ya pasada, desde el historial de la ficha (fase 48.1c): el
 * mismo panel que el aviso, donde se le puede seguir escribiendo.
 */
export function RunConversation({ runId, subject }: { runId: number; subject: string | null }) {
  const { t } = useTranslation('nav', { keyPrefix: 'tasks' })
  const [open, setOpen] = useState(false)
  const run = useAgentRun(open ? runId : null)
  const close = useCallback(() => setOpen(false), [])
  const data = run.data
  return (
    <>
      <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" aria-expanded={open} onClick={() => setOpen(!open)}>
        <ChatsCircleIcon />
        {t('conversation')}
      </Button>
      {open && data && (
        <AgentRunPanel
          target={{
            run_id: data.id,
            action: data.action,
            job_id: data.job_id,
            subject,
            agent: data.agent,
            started_at: data.started_at ?? data.created_at,
            finished_at: data.finished_at,
            steps: [],
            asks_permissions: data.asks_permissions,
            status: data.status === 'queued' || data.status === 'running' ? 'running' : 'finished',
            outcome: data.status === 'done' ? 'done' : null,
          }}
          onClose={close}
        />
      )}
    </>
  )
}
