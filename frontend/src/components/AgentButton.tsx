import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { Link } from 'react-router'
import {
  ArrowsLeftRightIcon,
  CaretDownIcon,
  ClockCountdownIcon,
  GearSixIcon,
  SparkleIcon,
  TerminalWindowIcon,
  XIcon,
} from '@phosphor-icons/react'
import { useTranslation } from 'react-i18next'
import { ApiError } from '@/api/client'
import {
  useAgentLauncher,
  useCreateAgentRequest,
  useLaunchAgent,
  useStartAgentRun,
  type AgentAction,
  type SearchScope,
} from '@/api/queries'
import { CommandBox } from '@/components/CommandBox'
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
import { WATCHED_ACTIONS, watchFor } from '@/lib/readyWatch'
import { cn } from '@/lib/utils'

type Feedback = {
  tone: 'ok' | 'info' | 'error'
  text: string
  link?: boolean
} | null

/**
 * Botón que abre tu agente en una terminal con la orden de un skill ya escrita. Lo que
 * haga el agente lo ves y lo apruebas tú en esa terminal. Si no se puede abrir (otro sistema,
 * agente no instalado), enseña la orden entera, con «Copiar», y dónde pegarla; sin ningún agente
 * instalado, enlaza a cómo instalar uno. Ese recuadro no se va solo: se cierra con su botón.
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
 * Lo que lanza tu agente se reconoce por el icono de destellos. Solo la acción principal de cada
 * pantalla va rellena (`primary`); las demás, con borde, para que no compitan entre sí. El agente
 * con el que se abre no ocupa sitio en el botón: va en el globo y en el desplegable.
 */
export function AgentButton({
  action,
  jobId,
  milestoneId,
  profileItem,
  upload,
  search,
  children,
  size = 'sm',
  primary = false,
  prepare,
  disabled = false,
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
  /** «Buscar ofertas»: en qué portales y, si quieres, una búsqueda puntual. */
  search?: SearchScope
  children: ReactNode
  size?: 'sm' | 'default'
  /** La acción principal de la pantalla: rellena. Una como mucho por pantalla. */
  primary?: boolean
  /** Lo que hay que guardar antes de lanzar (p. ej. el texto de una corrección), en cualquier modo. */
  prepare?: () => Promise<unknown>
  disabled?: boolean
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
  // La orden que no se pudo abrir: se queda a la vista hasta cerrarla.
  const [prompt, setPrompt] = useState<string | null>(null)
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined)
  useEffect(() => () => clearTimeout(timer.current), [])

  const show = (next: Feedback) => {
    setPrompt(null)
    setFeedback(next)
    clearTimeout(timer.current)
    timer.current = setTimeout(() => setFeedback(null), 8000)
  }
  const target = { action, job_id: jobId, milestone_id: milestoneId, profile_item: profileItem, upload, search }
  const failed = (error: unknown, fallback: string) =>
    show({ tone: 'error', text: error instanceof Error ? errorMessage(error) : fallback })

  /** Primero `prepare`; si falla, se queda en el error de quien lo pasa y no se lanza nada. */
  const prepared = (go: () => void) => {
    if (!prepare) return go()
    prepare().then(go, () => undefined)
  }

  const run = (agentName?: string) => prepared(() =>
    launch.mutate(agentName ? { ...target, agent: agentName } : target, {
      onSuccess: (result) => {
        const opened = t('opened', { agent: result.agent })
        const warning = result.warning ? warningText(result) : null
        const watched = WATCHED_ACTIONS[action] ? ` ${t('ready.watching')}` : ''
        show({ tone: 'ok', text: (warning ? `${opened} ${t('warning', { warning })}` : opened) + watched })
        watchFor(action, result.job_id ?? jobId, milestoneId)
      },
      onError: (error) => {
        const order = error instanceof ApiError ? error.details.find((d) => d.field === 'prompt')?.received : null
        if (order) {
          clearTimeout(timer.current)
          setFeedback(null)
          setPrompt(order)
        } else {
          failed(error, t('openFailed'))
        }
      },
    }))

  const runInBackground = (agentName?: string) => prepared(() =>
    startRun.mutate(agentName ? { ...target, agent: agentName } : target, {
      onSuccess: (result) => {
        show({
          tone: 'ok',
          text: result.status === 'running' ? t('alreadyRunning') : t('queued'),
          link: true,
        })
        watchFor(action, result.job_id ?? jobId, milestoneId)
      },
      onError: (error) => failed(error, t('backgroundFailed')),
    }))

  const leaveForLater = () => prepared(() =>
    leave.mutate(target, {
      onSuccess: () => show({ tone: 'ok', text: t('requestSaved'), link: true }),
      onError: (error) => failed(error, t('requestFailed')),
    }))

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
  const variant = primary ? 'default' : 'outline'
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
              variant={variant}
              size={size}
              onClick={() => run()}
              disabled={busy || disabled || blocked !== null}
              className="rounded-r-none"
              aria-describedby={hintId}
            >
              <SparkleIcon weight="duotone" className={cn(!primary && 'text-primary')} />
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
              variant={variant}
              size={size}
              disabled={busy || disabled}
              aria-label={shownAgent ? t('moreWith', { agent: shownAgent }) : t('more')}
              className={cn(
                'rounded-l-none px-2',
                primary ? 'border-l border-l-primary-foreground/25' : '-ml-px',
              )}
            >
              <CaretDownIcon weight="bold" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-72">
            {/* Sin ratón no hay globo: la ayuda abre el menú. */}
            <DropdownMenuLabel className="text-xs font-normal text-muted-foreground">
              {hint}
              {shownAgent && <span className="mt-1 block font-medium text-foreground/80">{t('with', { agent: shownAgent })}</span>}
            </DropdownMenuLabel>
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
      {prompt && (
        <span role="group" aria-labelledby={`${hintId}-prompt`} className="grid w-full max-w-md gap-2 rounded-lg border border-warning-border bg-warning/40 p-3 text-sm">
          <span className="flex items-start justify-between gap-2">
            <span id={`${hintId}-prompt`} aria-live="polite" className="font-medium">{launcher.data?.no_agent_installed ? t('noAgent') : t('cantOpen')}</span>
            <Button type="button" size="icon-sm" variant="ghost" className="-mt-1 -mr-1" aria-label={t('closePrompt')} onClick={() => setPrompt(null)}>
              <XIcon />
            </Button>
          </span>
          <span className="text-muted-foreground">{t('pasteWhere')}</span>
          <CommandBox text={prompt} label={t('promptLabel')} />
          {launcher.data?.no_agent_installed && (
            <Link to="/agente" className="text-primary underline underline-offset-4">
              {t('howToInstall')}
            </Link>
          )}
        </span>
      )}
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
