import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { AgentsOverview, SpendTier } from '@/api/client'
import { useSpendTierActions, useSpendTiers, type AgentAction } from '@/api/queries'
import { ErrorState, InlineCode } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { errorMessage } from '@/lib/errors'
import { i18n } from '@/lib/i18n'
import { cn } from '@/lib/utils'

/**
 * «Niveles de gasto» (fase 24.6): «Económico», «Equilibrado» y «Máximo», conjuntos de agente y modelo
 * por acción que se rellenan una vez y se aplican con un clic. Aplicar cambia tus preferencias por
 * acción (las de la tabla «Por acción») y se puede deshacer.
 */

const SELECT = 'h-8 w-full min-w-28 rounded-md border border-input bg-background px-2 text-sm'

type Pref = SpendTier['actions'][string]

function actionName(action: string): string {
  return i18n.t(`agent:actions.${action as AgentAction}`)
}

function prefText(pref: Pref, names: Map<string, string>): string {
  const agent = names.get(pref.agent) ?? pref.agent
  const model = pref.model ?? (pref.preset ? `preset ${pref.preset}` : null)
  return model ? `${agent} · ${model}` : agent
}

function TierEditor({
  tier,
  overview,
  busy,
  onSave,
  onCancel,
}: {
  tier: SpendTier
  overview: AgentsOverview
  busy: boolean
  onSave: (actions: Record<string, Pref>) => void
  onCancel: () => void
}) {
  const { t } = useTranslation('agents')
  const [draft, setDraft] = useState<Record<string, Pref>>({ ...tier.actions })
  const names = new Map(overview.agents.map((a) => [a.name, a.info.display_name]))
  const set = (action: string, change: Partial<Pref>) =>
    setDraft((d) => ({ ...d, [action]: { ...d[action], ...change } as Pref }))
  return (
    <form
      className="mt-2 space-y-2"
      onSubmit={(e) => {
        e.preventDefault()
        onSave(draft)
      }}
    >
      {Object.entries(draft).map(([action, pref]) => (
        <fieldset key={action} className="grid gap-1">
          <legend className="text-xs text-muted-foreground">{actionName(action)}</legend>
          <select
            aria-label={t('tiers.agentFor', { action: actionName(action) })}
            className={SELECT}
            disabled={busy}
            value={pref.agent}
            onChange={(e) => set(action, { agent: e.target.value, model: null, preset: null })}
          >
            {overview.launchable.map((name) => (
              <option key={name} value={name}>
                {names.get(name) ?? name}
              </option>
            ))}
          </select>
          <Input
            aria-label={t('tiers.modelFor', { action: actionName(action) })}
            className="h-8"
            value={pref.model ?? ''}
            maxLength={100}
            placeholder={pref.preset ? `${t('preset')} ${pref.preset}` : t('modelPlaceholder')}
            disabled={busy || Boolean(pref.preset)}
            onChange={(e) => set(action, { model: e.target.value || null })}
          />
        </fieldset>
      ))}
      <div className="flex gap-2">
        <Button type="submit" size="sm" disabled={busy}>
          {t('save')}
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={onCancel} disabled={busy}>
          {t('tiers.cancel')}
        </Button>
      </div>
    </form>
  )
}

export function SpendTiers({ overview }: { overview: AgentsOverview }) {
  const { t } = useTranslation('agents')
  const { data, isPending, isError, error, refetch } = useSpendTiers()
  const actions = useSpendTierActions()
  const [editing, setEditing] = useState<string | null>(null)
  if (isPending) return <Skeleton className="h-40" />
  if (isError) return <ErrorState error={error} onRetry={() => void refetch()} />

  const busy = Object.values(actions).some((m) => m.isPending)
  const failed = Object.values(actions).find((m) => m.isError)
  const names = new Map(overview.agents.map((a) => [a.name, a.info.display_name]))
  return (
    <section aria-labelledby="tiers-title" className="space-y-3">
      <div className="flex flex-wrap items-baseline gap-2">
        <h3 id="tiers-title" className="text-base font-semibold tracking-tight">
          {t('tiers.title')}
        </h3>
        {data.can_undo && (
          <Button type="button" size="sm" variant="outline" className="ml-auto" disabled={busy} onClick={() => actions.undo.mutate()}>
            {t('tiers.undo')}
          </Button>
        )}
      </div>
      <p className="max-w-prose text-sm text-muted-foreground">{t('tiers.intro')}</p>
      {failed?.error && (
        <p role="alert" className="text-sm text-destructive">
          <InlineCode text={errorMessage(failed.error)} />
        </p>
      )}
      <ul className="grid gap-3 md:grid-cols-3">
        {data.tiers.map((tier) => (
          <li
            key={tier.id}
            aria-label={t(`tiers.${tier.id}.label`)}
            className={cn('rounded-xl border bg-card p-4', tier.active && 'border-foreground/40')}
          >
            <div className="flex items-baseline gap-2">
              <h4 className="font-medium">{t(`tiers.${tier.id}.label`)}</h4>
              {tier.active && <span className="text-xs text-muted-foreground">{t('tiers.active')}</span>}
              {tier.custom && <span className="ml-auto text-xs text-muted-foreground">{t('tiers.custom')}</span>}
            </div>
            <p className="mt-1 text-xs text-muted-foreground">{t(`tiers.${tier.id}.help`)}</p>
            {editing === tier.id ? (
              <TierEditor
                tier={tier}
                overview={overview}
                busy={busy}
                onCancel={() => setEditing(null)}
                onSave={(draft) =>
                  actions.save.mutate(
                    { tier: tier.id, body: { actions: draft } },
                    { onSuccess: () => setEditing(null) },
                  )
                }
              />
            ) : (
              <>
                <dl className="mt-2 space-y-0.5 text-xs">
                  {Object.entries(tier.actions).map(([action, pref]) => (
                    <div key={action} className="flex flex-wrap gap-x-1">
                      <dt className="text-muted-foreground">{actionName(action)}:</dt>
                      <dd>{prefText(pref, names)}</dd>
                    </div>
                  ))}
                </dl>
                {tier.notes.map((note) => (
                  <p key={note} className="mt-1 text-xs text-warning-foreground">
                    {t(`tiers.notes.${note}`)}
                  </p>
                ))}
                <div className="mt-3 flex flex-wrap gap-2">
                  <Button
                    type="button"
                    size="sm"
                    disabled={
                      busy ||
                      tier.active ||
                      Object.keys(tier.actions).length === 0 ||
                      tier.notes.includes('needs_local_model')
                    }
                    onClick={() => actions.apply.mutate(tier.id)}
                  >
                    {t('tiers.apply')}
                  </Button>
                  <Button type="button" size="sm" variant="ghost" disabled={busy} onClick={() => setEditing(tier.id)}>
                    {t('tiers.edit')}
                  </Button>
                  {tier.custom && (
                    <Button type="button" size="sm" variant="ghost" disabled={busy} onClick={() => actions.reset.mutate(tier.id)}>
                      {t('tiers.reset')}
                    </Button>
                  )}
                </div>
              </>
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}
