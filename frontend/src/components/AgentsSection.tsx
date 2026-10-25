import { useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { CheckIcon, CopyIcon } from '@phosphor-icons/react'
import type {
  AgentEntry,
  AgentPreferences,
  AgentResolution,
  AgentsOverview,
  LocalModelsStatus,
} from '@/api/client'
import { useAgentsOverview, useLocalModels, useSaveAgentPreferences, type AgentAction } from '@/api/queries'
import { LocalModels } from '@/components/LocalModels'
import { SpendTiers } from '@/components/SpendTiers'
import { ErrorState, InlineCode } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { blockedText, modelText, reasonText, warningText } from '@/lib/agentText'
import { errorMessage } from '@/lib/errors'
import { i18n, SOURCE_LANGUAGE } from '@/lib/i18n'
import { cn } from '@/lib/utils'

/**
 * Sección «Agentes» de la página «Agente» (fase 24.4): qué agentes hay y qué sabe hacer
 * cada uno, el agente por defecto, el modelo de cada agente y el agente y el modelo de cada acción.
 * Las preferencias se guardan enteras (`PUT /agent/preferences`) en la base de datos de `data/`.
 * Fase 24.6: niveles de gasto y, en los agentes con modelos locales, el Ollama de este equipo.
 */

type Save = (change: (prefs: AgentPreferences) => void) => void

/** Mientras se guarda, los controles se bloquean: cada guardado sustituye todas las preferencias y
 * parte de las últimas leídas, así que dos seguidos se pisarían. */

const SELECT = 'h-9 rounded-md border border-input bg-background px-3 text-sm'

function clone(prefs: AgentPreferences): AgentPreferences {
  return {
    default_agent: prefs.default_agent ?? null,
    agents: { ...(prefs.agents ?? {}) },
    actions: { ...(prefs.actions ?? {}) },
  }
}

function Badge({ children, unchecked }: { children: ReactNode; unchecked?: boolean }) {
  const { t } = useTranslation('agents')
  return (
    <span
      className={cn(
        'inline-flex h-5 items-center rounded-full px-2 text-[0.7rem] font-medium whitespace-nowrap',
        unchecked ? 'border border-dashed text-muted-foreground' : 'bg-foreground/[0.06] text-foreground/80',
      )}
      title={unchecked ? t('unchecked') : undefined}
    >
      {children}
      {unchecked && '?'}
    </span>
  )
}

function Badges({ entry }: { entry: AgentEntry }) {
  const { t } = useTranslation('agents')
  const caps = entry.capabilities
  const optional: [boolean | null | undefined, string][] = [
    [caps.vision, t('badges.vision')],
    [caps.web, t('badges.web')],
    [caps.browser, t('badges.browser')],
  ]
  return (
    <div className="flex flex-wrap gap-1.5">
      {entry.info.open_source && <Badge>{t('badges.openSource')}</Badge>}
      {caps.local_models && <Badge>{t('badges.localModels')}</Badge>}
      {caps.mcp && <Badge>{t('badges.mcp')}</Badge>}
      {caps.subagents === 'isolated' && <Badge>{t('badges.isolation', { level: caps.isolation_level })}</Badge>}
      {caps.headless && <Badge>{t('badges.headless')}</Badge>}
      {optional.map(([value, label]) =>
        value === false ? null : (
          <Badge key={label} unchecked={value == null}>
            {label}
          </Badge>
        ),
      )}
    </div>
  )
}

function CopyCommand({ command }: { command: string }) {
  const { t } = useTranslation('agents')
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard?.writeText(command)
      setCopied(true)
    } catch {
      setCopied(false)
    }
  }
  return (
    <div className="mt-2 flex items-center gap-2 text-xs">
      <span className="text-muted-foreground">{t('installWith')}</span>
      <code className="min-w-0 flex-1 truncate rounded bg-muted px-1.5 py-0.5 font-mono">{command}</code>
      <Button type="button" variant="ghost" size="sm" onClick={() => void copy()} aria-label={t('copy')}>
        {copied ? <CheckIcon /> : <CopyIcon />}
        {copied ? t('copied') : t('copy')}
      </Button>
    </div>
  )
}

function subagentModels(entry: AgentEntry): string | null {
  const models = [entry.models.fast, entry.models.capable].filter(Boolean)
  return models.length ? [...new Set(models)].join(' / ') : null
}

function ModelControls({
  entry,
  prefs,
  save,
  busy,
}: {
  entry: AgentEntry
  prefs: AgentPreferences
  save: Save
  busy: boolean
}) {
  const { t } = useTranslation('agents')
  const current = prefs.agents?.[entry.name] ?? {}
  const [model, setModel] = useState(current.model ?? '')
  const id = `model-${entry.name}`
  const commit = (next: { model?: string | null; preset?: string | null }) =>
    save((p) => {
      p.agents = { ...p.agents, [entry.name]: { model: next.model || null, preset: next.preset || null } }
    })
  const fixed = subagentModels(entry)
  return (
    <div className="mt-3 space-y-1.5 border-t pt-3">
      {entry.models.by_name || entry.models.presets.length > 0 ? (
        <div className="flex flex-wrap items-end gap-2">
          {entry.models.by_name && (
            <div className="grid min-w-40 flex-1 gap-1">
              <Label htmlFor={id} className="text-xs">
                {t('model')}
              </Label>
              <Input
                id={id}
                value={model}
                maxLength={100}
                placeholder={entry.models.example ? t('modelExample', { example: entry.models.example }) : t('modelDefault')}
                disabled={busy || Boolean(current.preset)}
                onChange={(e) => setModel(e.target.value)}
                onBlur={() => model.trim() !== (current.model ?? '') && commit({ model: model.trim() })}
                onKeyDown={(e) => e.key === 'Enter' && e.currentTarget.blur()}
              />
            </div>
          )}
          {entry.models.presets.length > 0 && (
            <div className="grid gap-1">
              <Label htmlFor={`${id}-preset`} className="text-xs">
                {t('preset')}
              </Label>
              <select
                id={`${id}-preset`}
                className={SELECT}
                disabled={busy}
                value={current.preset ?? ''}
                onChange={(e) => {
                  setModel('')
                  commit({ preset: e.target.value })
                }}
              >
                <option value="">{t('noPreset')}</option>
                {entry.models.presets.map((preset) => (
                  <option key={preset} value={preset}>
                    {preset}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">{t('noModelChoice')}</p>
      )}
      <p className="text-xs text-muted-foreground">
        {fixed ? t('subagentsFixed', { models: fixed }) : t('subagentsInherit')}
        {entry.models.by_name && ` ${t('modelHelp')}`}
      </p>
    </div>
  )
}

function AgentCard({
  entry,
  launchable,
  prefs,
  save,
  busy,
  local,
}: {
  entry: AgentEntry
  launchable: boolean
  prefs: AgentPreferences
  save: Save
  busy: boolean
  local?: LocalModelsStatus
}) {
  const { t } = useTranslation('agents')
  const platform = navigator.userAgent.includes('Mac') ? 'macos' : navigator.userAgent.includes('Linux') ? 'linux' : 'windows'
  const install = entry.info.install[platform]
  return (
    <li className="rounded-xl border bg-card p-4" aria-label={entry.info.display_name}>
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
        <h3 className="font-medium">{entry.info.display_name}</h3>
        <span className={cn('text-xs tabular', entry.installed ? 'text-muted-foreground' : 'text-destructive')}>
          {entry.installed ? (entry.version ?? '') : t('notInstalled')}
        </span>
        <span className="ml-auto text-xs text-muted-foreground">
          {entry.info.vendor} · {entry.info.license}
        </span>
      </div>
      <div className="mt-2">
        <Badges entry={entry} />
      </div>
      {entry.info.note && <p className="mt-2 text-xs text-warning-foreground">{entry.info.note}</p>}
      {!entry.installed && install && <CopyCommand command={install} />}
      {!entry.enabled && <p className="mt-2 text-xs text-muted-foreground">{t('onlyCompatible')}</p>}
      {entry.enabled && !launchable && <p className="mt-2 text-xs text-muted-foreground">{t('notLaunchable')}</p>}
      {launchable && <ModelControls entry={entry} prefs={prefs} save={save} busy={busy} />}
      {entry.enabled && entry.capabilities.local_models && <LocalModels status={local} />}
    </li>
  )
}

function actionLabel(action: AgentAction, label: string): string {
  return i18n.language === SOURCE_LANGUAGE ? label : i18n.t(`agent:actions.${action}`)
}

function Effective({ res }: { res: AgentResolution }) {
  const { t } = useTranslation('agents')
  const blocked = blockedText(res)
  const warning = warningText(res)
  const model = modelText(res)
  return (
    <div className="text-xs">
      <span className="font-medium text-foreground">{res.display_name ?? t('none')}</span>
      {model && <span className="text-muted-foreground"> · {model}</span>}
      <span className="text-muted-foreground"> · {reasonText(res)}</span>
      {blocked && <p className="text-destructive">{blocked}</p>}
      {!blocked && warning && <p className="text-warning-foreground">{warning}</p>}
    </div>
  )
}

function ActionRow({
  row,
  overview,
  save,
  busy,
}: {
  row: AgentsOverview['effective'][number]
  overview: AgentsOverview
  save: Save
  busy: boolean
}) {
  const { t } = useTranslation('agents')
  const pref = overview.preferences.actions?.[row.action]
  const [model, setModel] = useState(pref?.model ?? '')
  const label = actionLabel(row.action, row.label)
  const names = new Map(overview.agents.map((a) => [a.name, a.info.display_name]))
  const setAgent = (agent: string) =>
    save((p) => {
      const actions = { ...p.actions }
      if (agent) actions[row.action] = { agent, model: null, preset: null }
      else delete actions[row.action]
      p.actions = actions
    })
  const commitModel = () => {
    if (!pref || model.trim() === (pref.model ?? '')) return
    save((p) => {
      p.actions = { ...p.actions, [row.action]: { ...pref, model: model.trim() || null, preset: null } }
    })
  }
  return (
    <tr className="border-t align-top">
      <th scope="row" className="py-2 pr-3 text-left text-sm font-normal">
        {label}
      </th>
      <td className="py-2 pr-3">
        <select
          aria-label={t('agent')}
          className={cn(SELECT, 'h-8 w-full min-w-32')}
          disabled={busy}
          value={pref?.agent ?? ''}
          onChange={(e) => {
            setModel('')
            setAgent(e.target.value)
          }}
        >
          <option value="">{t('inherit')}</option>
          {overview.launchable.map((name) => (
            <option key={name} value={name}>
              {names.get(name) ?? name}
            </option>
          ))}
        </select>
        {pref && (
          <Input
            aria-label={t('model')}
            className="mt-1 h-8"
            value={model}
            maxLength={100}
            placeholder={pref.preset ? `${t('preset')} ${pref.preset}` : t('modelPlaceholder')}
            disabled={busy || Boolean(pref.preset)}
            onChange={(e) => setModel(e.target.value)}
            onBlur={commitModel}
            onKeyDown={(e) => e.key === 'Enter' && e.currentTarget.blur()}
          />
        )}
      </td>
      <td className="py-2">
        <Effective res={row.terminal} />
      </td>
    </tr>
  )
}

export function AgentsSection() {
  const { t } = useTranslation('agents')
  const { data, isPending, isError, error, refetch } = useAgentsOverview()
  const mutation = useSaveAgentPreferences()
  const local = useLocalModels(Boolean(data?.agents.some((a) => a.enabled && a.capabilities.local_models)))
  if (isPending) return <Skeleton className="h-48" />
  if (isError) return <ErrorState error={error} onRetry={() => void refetch()} />

  const save: Save = (change) => {
    const next = clone(data.preferences)
    change(next)
    mutation.mutate(next)
  }
  const launchable = new Set(data.launchable)
  const names = new Map(data.agents.map((a) => [a.name, a]))
  return (
    <div className="space-y-6">
      <p className="max-w-prose text-sm text-muted-foreground">{t('intro')}</p>
      <div className="grid max-w-md gap-1.5">
        <Label htmlFor="default-agent">{t('defaultAgent')}</Label>
        <select
          id="default-agent"
          className={SELECT}
          disabled={mutation.isPending}
          value={data.preferences.default_agent ?? ''}
          onChange={(e) => save((p) => void (p.default_agent = e.target.value || null))}
        >
          <option value="">{t('defaultAuto')}</option>
          {data.launchable.map((name) => {
            const entry = names.get(name)
            return (
              <option key={name} value={name}>
                {entry?.info.display_name ?? name}
                {entry && !entry.installed ? ` (${t('notInstalled')})` : ''}
              </option>
            )
          })}
        </select>
      </div>
      {mutation.isError && (
        <p role="alert" className="text-sm text-destructive">
          <InlineCode text={errorMessage(mutation.error)} />
        </p>
      )}
      {mutation.isSuccess && !mutation.isPending && (
        <p role="status" className="text-xs text-muted-foreground">
          {t('saved')}
        </p>
      )}

      <ul className="grid gap-3 md:grid-cols-2">
        {data.agents.map((entry) => (
          <AgentCard
            key={`${entry.name}-${JSON.stringify(data.preferences.agents?.[entry.name] ?? {})}`}
            entry={entry}
            launchable={launchable.has(entry.name)}
            prefs={data.preferences}
            save={save}
            busy={mutation.isPending}
            local={local.data}
          />
        ))}
      </ul>

      <SpendTiers overview={data} />

      <section aria-labelledby="by-action-title">
        <h3 id="by-action-title" className="text-base font-semibold tracking-tight">
          {t('byAction')}
        </h3>
        <p className="mb-2 text-sm text-muted-foreground">{t('byActionIntro')}</p>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[36rem]">
            <thead>
              <tr className="text-left text-xs font-medium tracking-wide text-muted-foreground uppercase">
                <th scope="col" className="pb-1">
                  {t('action')}
                </th>
                <th scope="col" className="pb-1">
                  {t('agent')}
                </th>
                <th scope="col" className="pb-1">
                  {t('effective')}
                </th>
              </tr>
            </thead>
            <tbody>
              {data.effective.map((row) => (
                <ActionRow
                  key={`${row.action}-${JSON.stringify(data.preferences.actions?.[row.action] ?? {})}`}
                  row={row}
                  overview={data}
                  save={save}
                  busy={mutation.isPending}
                />
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
