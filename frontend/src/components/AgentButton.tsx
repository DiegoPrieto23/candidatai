import { useEffect, useRef, useState, type ReactNode } from 'react'
import { TerminalWindowIcon } from '@phosphor-icons/react'
import { ApiError } from '@/api/client'
import { useAgentLauncher, useLaunchAgent, type AgentAction } from '@/api/queries'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

type Feedback = { tone: 'ok' | 'info' | 'error'; text: string } | null

async function copy(text: string): Promise<boolean> {
  if (!navigator.clipboard) return false
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    return false
  }
}

/**
 * Botón que abre tu agente en una terminal con la orden de un skill ya escrita (ADR-024). Lo que
 * haga el agente lo ves y lo apruebas tú en esa terminal. Si no se puede abrir (otro sistema,
 * agente no instalado), copia la orden para que la pegues en tu agente.
 */
export function AgentButton({
  action,
  jobId,
  children,
  variant = 'outline',
  size = 'sm',
  className,
}: {
  action: AgentAction
  jobId?: number
  children: ReactNode
  variant?: 'default' | 'outline' | 'secondary' | 'ghost'
  size?: 'sm' | 'default'
  className?: string
}) {
  const launcher = useAgentLauncher()
  const launch = useLaunchAgent()
  const [feedback, setFeedback] = useState<Feedback>(null)
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined)
  useEffect(() => () => clearTimeout(timer.current), [])

  const show = (next: Feedback) => {
    setFeedback(next)
    clearTimeout(timer.current)
    timer.current = setTimeout(() => setFeedback(null), 8000)
  }

  const run = () =>
    launch.mutate(
      { action, job_id: jobId },
      {
        onSuccess: (result) => show({ tone: 'ok', text: `Abierto en ${result.agent}: sigue en la terminal.` }),
        onError: async (error) => {
          const prompt = error instanceof ApiError ? error.details.find((d) => d.field === 'prompt')?.received : null
          if (prompt) {
            const copied = await copy(prompt)
            show({
              tone: 'info',
              text: copied
                ? `No puedo abrir tu agente desde aquí (${error.message}). He copiado la orden: pégala en tu agente.`
                : `No puedo abrir tu agente desde aquí. Pégale esta orden: «${prompt}»`,
            })
          } else {
            show({ tone: 'error', text: error instanceof Error ? error.message : 'No se pudo abrir tu agente.' })
          }
        },
      },
    )

  const agent = launcher.data?.available ? launcher.data.agent : null
  return (
    <span className={cn('inline-flex flex-col items-start gap-1.5', className)}>
      <Button
        type="button"
        variant={variant}
        size={size}
        onClick={run}
        disabled={launch.isPending}
        title={agent ? `Abre ${agent} en una terminal con la orden ya escrita` : 'Copia la orden para tu agente'}
      >
        <TerminalWindowIcon weight="duotone" />
        {children}
      </Button>
      <span
        role="status"
        className={cn(
          'max-w-sm text-xs empty:hidden',
          feedback?.tone === 'error' ? 'text-destructive' : 'text-muted-foreground',
        )}
      >
        {feedback?.text}
      </span>
    </span>
  )
}
