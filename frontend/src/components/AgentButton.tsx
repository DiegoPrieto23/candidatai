import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { Link } from 'react-router'
import {
  ArrowsLeftRightIcon,
  CaretDownIcon,
  ClockCountdownIcon,
  GearSixIcon,
  TerminalWindowIcon,
} from '@phosphor-icons/react'
import { useTranslation } from 'react-i18next'
import { ApiError } from '@/api/client'
import {
  useAgentLauncher,
  useCreateAgentRequest,
  useLaunchAgent,
  useStartAgentRun,
  type AgentAction,
} from '@/api/queries'
import { Hint } from '@/components/Hint'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { blockedText, COPY_PROMPT_CODES, warningText } from '@/lib/agentText'
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
 *
 * Fase 24.4: el desplegable dice con qué agente iría («con Claude Code ▾», según tus preferencias)
 * y deja abrirlo con otro solo esta vez. Si el agente no sirve para la acción (le falta una
 * capacidad, p. ej.), el botón se deshabilita y el desplegable dice por qué.
 *
 * Fase 27.1: un globo dice qué hace el skill (`agentActions.json`), por qué está bloqueado y cómo se
 * abre. El disparador es el `<span>` que envuelve el botón, porque un `<button disabled>` no dispara
 * eventos; sin ratón, la ayuda va también en el desplegable y, para lectores de pantalla, en
 * `aria-describedby`.
 *
 * Siempre en verde (el color primario): así se distingue de un vistazo lo que lanza tu agente.
 */
export function AgentButton({
  action,
  jobId,
  milestoneId,
  profileItem,
  upload,
  children,
  size = 'sm',
  className,
}: {
  action: AgentAction
  jobId?: number
  /** Acciones de una entrevista (fase 17): la oferta sale del hito. */
  milestoneId?: number
  /** «Mi perfil» (fase 25.7b): el id de un logro o una historia. Solo en terminal. */
  profileItem?: string
  /** Plantillas: el nombre de un CV subido (`data/uploads/<nombre>`). Solo en terminal. */
  upload?: string
  children: ReactNode
  size?: 'sm' | 'default'
  className?: string
}) {
  const { t } = useTranslation('agentButton')
  const { t: tAgent } = useTranslation('agent')
  const { t: tHint } = useTranslation('agentActions')
  const buttonId = useId()
  const hintId = useId()
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
  const target = { action, job_id: jobId, milestone_id: milestoneId, profile_item: profileItem, upload }
  const failed = (error: unknown, fallback: string) =>
    show({ tone: 'error', text: error instanceof Error ? errorMessage(error) : fallback })

  const run = (agentName?: string) =>
    launch.mutate(agentName ? { ...target, agent: agentName } : target, {
      onSuccess: (result) => {
        const opened = t('opened', { agent: result.agent })
        const warning = result.warning ? warningText(result) : null
        show({ tone: 'ok', text: warning ? `${opened} ${t('warning', { warning })}` : opened })
      },
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

  const runInBackground = (agentName?: string) =>
    startRun.mutate(agentName ? { ...target, agent: agentName } : target, {
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

  const spec = launcher.data?.actions.find((a) => a.id === action)
  const agent = launcher.data?.available ? launcher.data.agent : null
  const canBackground = spec?.background ?? false
  const background = spec?.background_agent ?? launcher.data?.background
  // Fase 24.4: el agente de esta acción y los demás, para elegir solo esta vez.
  const effective = spec?.agent
  const shownAgent = effective?.display_name ?? null
  const blocked = effective?.blocked && !COPY_PROMPT_CODES.has(effective.blocked_code ?? '') ? blockedText(effective) : null
  const alternatives = spec?.alternatives ?? []
  const busy = launch.isPending || startRun.isPending || leave.isPending
  const hint = tHint(action)
  const mechanism = agent ? t('titleAgent', { agent: shownAgent ?? agent }) : t('titleCopy')
  return (
    <span data-slot="agent-button" className={cn('inline-flex flex-col items-start gap-1.5', className)}>
      <span className="inline-flex">
        <Hint
          text={
            <span className="grid gap-1.5">
              <span className="font-semibold">{tAgent(`actions.${action}`)}</span>
              <span>{hint}</span>
              {blocked ? (
                <span className="rounded-sm border border-warning-border bg-warning px-1.5 py-1 text-warning-foreground">
                  {blocked}
                </span>
              ) : (
                <span className="text-background/70">{mechanism}</span>
              )}
            </span>
          }
        >
          {/* Bloqueado, el botón no recibe el foco: lo recibe el envoltorio (con el nombre del botón) para que el globo salga con el teclado. */}
          <span
            className="inline-flex"
            {...(blocked ? { tabIndex: 0, role: 'group', 'aria-labelledby': buttonId } : {})}
          >
            <Button
              id={buttonId}
              type="button"
              variant="default"
              size={size}
              onClick={() => run()}
              disabled={busy || blocked !== null}
              className="rounded-r-none"
              aria-describedby={hintId}
            >
              <TerminalWindowIcon weight="duotone" />
              {children}
            </Button>
          </span>
        </Hint>
        <span id={hintId} className="sr-only">
          {`${hint} ${blocked ?? mechanism}`}
        </span>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              type="button"
              variant="default"
              size={size}
              disabled={busy}
              aria-label={shownAgent ? t('moreWith', { agent: shownAgent }) : t('more')}
              className="rounded-l-none border-l border-l-primary-foreground/25 px-2"
            >
              {shownAgent && (
                <span className="hidden max-w-32 truncate text-xs font-normal sm:inline">
                  {t('with', { agent: shownAgent })}
                </span>
              )}
              <CaretDownIcon weight="bold" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-72">
            {/* Sin ratón no hay globo: la ayuda abre el menú. */}
            <DropdownMenuLabel className="text-xs font-normal text-muted-foreground">{hint}</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onSelect={() => run()} disabled={blocked !== null}>
              <TerminalWindowIcon weight="duotone" />
              <span>
                <span className="block font-medium">{t('terminal')}</span>
                <span className={cn('block text-xs', blocked ? 'text-destructive' : 'text-muted-foreground')}>
                  {blocked ?? (effective && warningText(effective)) ?? t('terminalHint')}
                </span>
              </span>
            </DropdownMenuItem>
            {canBackground && (
              <DropdownMenuItem onSelect={() => runInBackground()} disabled={!background?.available}>
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
            {canBackground && !background?.available && background?.suggested && (
              // Fase 24.5: el agente de esta acción no puede en segundo plano; otro sí.
              <DropdownMenuItem onSelect={() => runInBackground(background.suggested ?? undefined)}>
                <GearSixIcon weight="duotone" />
                <span>
                  <span className="block font-medium">
                    {t('backgroundWith', { agent: background.suggested_name ?? background.suggested })}
                  </span>
                  <span className="block text-xs text-muted-foreground">{t('backgroundHint')}</span>
                </span>
              </DropdownMenuItem>
            )}
            {alternatives.length > 0 && (
              <>
                <DropdownMenuSeparator />
                <DropdownMenuLabel className="text-xs font-normal text-muted-foreground">{t('onceWith')}</DropdownMenuLabel>
                {alternatives.map((alt) => {
                  const altBlocked = blockedText(alt)
                  const altWarning = warningText(alt)
                  return (
                    <DropdownMenuItem key={alt.agent} onSelect={() => run(alt.agent ?? undefined)} disabled={altBlocked !== null}>
                      <ArrowsLeftRightIcon weight="duotone" />
                      <span>
                        <span className="block font-medium">{t('openWith', { agent: alt.display_name ?? alt.agent })}</span>
                        {(altBlocked ?? altWarning) && (
                          <span className="block text-xs text-muted-foreground">{altBlocked ?? altWarning}</span>
                        )}
                      </span>
                    </DropdownMenuItem>
                  )
                })}
                <DropdownMenuSeparator />
              </>
            )}
            {/* La cola de encargos no guarda el id de un elemento del perfil ni el CV subido. */}
            {action !== 'handle-requests' && !profileItem && !upload && (
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
