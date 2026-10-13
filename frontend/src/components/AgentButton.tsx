import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Link } from 'react-router'
import { CaretDownIcon, ClockCountdownIcon, GearSixIcon, TerminalWindowIcon } from '@phosphor-icons/react'
import { useTranslation } from 'react-i18next'
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
import { errorMessage } from '@/lib/errors'
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
  const { t } = useTranslation('agentButton')
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
    show({ tone: 'error', text: error instanceof Error ? errorMessage(error) : fallback })

  const run = () =>
    launch.mutate(target, {
      onSuccess: (result) => show({ tone: 'ok', text: t('opened', { agent: result.agent }) }),
      onError: async (error) => {
        const prompt = error instanceof ApiError ? error.details.find((d) => d.field === 'prompt')?.received : null
        if (prompt) {
          const copied = await copy(prompt)
          show({
            tone: 'info',
            text: copied
              ? t('copiedPrompt', { error: errorMessage(error) })
              : t('pastePrompt', { prompt }),
          })
        } else {
          failed(error, t('openFailed'))
        }
      },
    })

  const runInBackground = () =>
    startRun.mutate(target, {
      onSuccess: (result) =>
        show({
          tone: 'ok',
          text: result.status === 'running' ? t('alreadyRunning') : t('queued'),
          link: true,
        }),
      onError: (error) => failed(error, t('backgroundFailed')),
    })

  const leaveForLater = () =>
    leave.mutate(target, {
      onSuccess: () => show({ tone: 'ok', text: t('requestSaved'), link: true }),
      onError: (error) => failed(error, t('requestFailed')),
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
          title={agent ? t('titleAgent', { agent }) : t('titleCopy')}
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
              aria-label={t('more')}
              className={cn('rounded-l-none border-l px-2', variant === 'default' && 'border-l-primary-foreground/25')}
            >
              <CaretDownIcon weight="bold" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-72">
            <DropdownMenuItem onSelect={run}>
              <TerminalWindowIcon weight="duotone" />
              <span>
                <span className="block font-medium">{t('terminal')}</span>
                <span className="block text-xs text-muted-foreground">{t('terminalHint')}</span>
              </span>
            </DropdownMenuItem>
            {canBackground && (
              <DropdownMenuItem onSelect={runInBackground} disabled={!background?.available}>
                <GearSixIcon weight="duotone" />
                <span>
                  <span className="block font-medium">{t('background')}</span>
                  <span className="block text-xs text-muted-foreground">
                    {background?.available
                      ? t('backgroundHint')
                      : (background?.reason ?? t('unavailable'))}
                  </span>
                </span>
              </DropdownMenuItem>
            )}
            {action !== 'handle-requests' && (
              <DropdownMenuItem onSelect={leaveForLater}>
                <ClockCountdownIcon weight="duotone" />
                <span>
                  <span className="block font-medium">{t('later')}</span>
                  <span className="block text-xs text-muted-foreground">
                    {t('laterHint')}
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
              {t('seeInAgent')}
            </Link>
          </>
        )}
      </span>
    </span>
  )
}
