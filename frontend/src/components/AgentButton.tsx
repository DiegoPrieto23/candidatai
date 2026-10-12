import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Link } from 'react-router'
import { CaretDownIcon, ClockCountdownIcon, GearSixIcon, TerminalWindowIcon } from '@phosphor-icons/react'
import { ApiError } from '@/api/client'
import {
  useAgentLauncher,
  useCreateAgentRequest,
  useLaunchAgent,
  useStartAgentRun,
  type AgentAction,
} from '@/api/queries'
import { Button } from '@/components/ui/button'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { cn } from '@/lib/utils'

type Feedback = {
  tone: 'ok' | 'info' | 'error'
  text: string
  link?: boolean
} | null

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
 *
 * El desplegable de al lado (fase 19) ofrece «En segundo plano» (sin ventana, desde el worker, solo
 * en los skills que no preguntan) y «Dejar para mi próxima sesión» (cola de encargos).
 */
export function AgentButton({
  action,
  jobId,
  milestoneId,
  children,
  variant = 'outline',
  size = 'sm',
  className,
}: {
  action: AgentAction
  jobId?: number
  /** Acciones de una entrevista (fase 17): la oferta sale del hito. */
  milestoneId?: number
  children: ReactNode
  variant?: 'default' | 'outline' | 'secondary' | 'ghost'
  size?: 'sm' | 'default'
  className?: string
}) {
  const launcher = useAgentLauncher()
  const launch = useLaunchAgent()
  const startRun = useStartAgentRun()
  const leave = useCreateAgentRequest()
  const [feedback, setFeedback] = useState<Feedback>(null)
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined)
  useEffect(() => () => clearTimeout(timer.current), [])

  const show = (next: Feedback) => {
    setFeedback(next)
    clearTimeout(timer.current)
    timer.current = setTimeout(() => setFeedback(null), 8000)
  }
  const target = { action, job_id: jobId, milestone_id: milestoneId }
  const failed = (error: unknown, fallback: string) =>
    show({ tone: 'error', text: error instanceof Error ? error.message : fallback })

  const run = () =>
    launch.mutate(target, {
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
          failed(error, 'No se pudo abrir tu agente.')
        }
      },
    })

  const runInBackground = () =>
    startRun.mutate(target, {
      onSuccess: (result) =>
        show({
          tone: 'ok',
          text: result.status === 'running' ? 'Ya se está ejecutando en segundo plano.' : 'En cola en segundo plano.',
          link: true,
        }),
      onError: (error) => failed(error, 'No se pudo lanzar en segundo plano.'),
    })

  const leaveForLater = () =>
    leave.mutate(target, {
      onSuccess: () => show({ tone: 'ok', text: 'Encargo guardado: tu agente lo verá en tu próxima sesión.', link: true }),
      onError: (error) => failed(error, 'No se pudo guardar el encargo.'),
    })

  const agent = launcher.data?.available ? launcher.data.agent : null
  const canBackground = launcher.data?.actions.find((a) => a.id === action)?.background ?? false
  const background = launcher.data?.background
  const busy = launch.isPending || startRun.isPending || leave.isPending
  return (
    <span className={cn('inline-flex flex-col items-start gap-1.5', className)}>
      <span className="inline-flex">
        <Button
          type="button"
          variant={variant}
          size={size}
          onClick={run}
          disabled={busy}
          className="rounded-r-none"
          title={agent ? `Abre ${agent} en una terminal con la orden ya escrita` : 'Copia la orden para tu agente'}
        >
          <TerminalWindowIcon weight="duotone" />
          {children}
        </Button>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              type="button"
              variant={variant}
              size={size}
              disabled={busy}
              aria-label="Más formas de lanzarlo"
              className={cn('rounded-l-none border-l px-2', variant === 'default' && 'border-l-primary-foreground/25')}
            >
              <CaretDownIcon weight="bold" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-72">
            <DropdownMenuItem onSelect={run}>
              <TerminalWindowIcon weight="duotone" />
              <span>
                <span className="block font-medium">En terminal</span>
                <span className="block text-xs text-muted-foreground">Lo ves, contestas y apruebas tú.</span>
              </span>
            </DropdownMenuItem>
            {canBackground && (
              <DropdownMenuItem onSelect={runInBackground} disabled={!background?.available}>
                <GearSixIcon weight="duotone" />
                <span>
                  <span className="block font-medium">En segundo plano</span>
                  <span className="block text-xs text-muted-foreground">
                    {background?.available
                      ? 'Sin ventana y solo con las herramientas de la app. Síguelo en «Agente».'
                      : (background?.reason ?? 'No disponible.')}
                  </span>
                </span>
              </DropdownMenuItem>
            )}
            {action !== 'handle-requests' && (
              <DropdownMenuItem onSelect={leaveForLater}>
                <ClockCountdownIcon weight="duotone" />
                <span>
                  <span className="block font-medium">Dejar para mi próxima sesión</span>
                  <span className="block text-xs text-muted-foreground">
                    Tu agente lo verá con el skill handle-requests.
                  </span>
                </span>
              </DropdownMenuItem>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      </span>
      <span
        role="status"
        className={cn(
          'max-w-sm text-xs empty:hidden',
          feedback?.tone === 'error' ? 'text-destructive' : 'text-muted-foreground',
        )}
      >
        {feedback?.text}
        {feedback?.link && (
          <>
            {' '}
            <Link to="/agente" className="underline underline-offset-4">
              Ver en «Agente»
            </Link>
          </>
        )}
      </span>
    </span>
  )
}
