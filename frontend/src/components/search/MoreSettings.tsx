import { useEffect, useId, useState, type ReactNode } from 'react'
import { useIsMutating } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { CheckIcon, LockIcon } from '@phosphor-icons/react'
import { ApiError } from '@/api/client'
import { useSalaryFloor, useSaveProfileSection, useSaveSalaryFloor, type EditableProfile } from '@/api/queries'
import { Hint } from '@/components/Hint'
import { useUnsavedGuard } from '@/components/profile/editor'
import { CodeTagsField, FieldError, TagsField } from '@/components/profile/fields'
import { CONTRACT_TYPES, EMPLOYER_KINDS, EMPLOYMENT_TYPES, type Preferences } from '@/components/profile/types'
import { BusyLabel } from '@/components/StableLabel'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { errorMessage } from '@/lib/errors'
import { activeGroups, clearedMore, readMore, type MoreDraft } from '@/lib/moreSettings'
import { cn } from '@/lib/utils'
import { ChipChoices } from './ChipChoices'

const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b)
const num = (value: string): number | null => (value.trim() === '' ? null : Number(value))

type Snapshot = { more: MoreDraft; salary: number | null }
type Status = { kind: 'saved'; before: Snapshot } | { kind: 'undone' } | { kind: 'error'; message: string; conflict: boolean }

/**
 * «Más ajustes»: experiencia y sueldo, idiomas, contrato y jornada, y lo que no quieres. Se despliega
 * dentro de la franja. A diferencia de las etiquetas de arriba, se cambian varias cosas y se guardan
 * de una vez («Guardar cambios», con «Deshacer» después): así el encaje se recalcula una sola vez. El
 * sueldo mínimo es privado y va por su propio camino, justo después de lo demás.
 *
 * Plegado sigue montado (`hidden`): lo que tengas a medias no se pierde y el aviso de salir sin guardar
 * sigue activo.
 */
export function MoreSettings({
  id,
  state,
  prefs,
  hidden,
  reload,
}: {
  id: string
  state: EditableProfile
  prefs: Preferences
  hidden: boolean
  reload: () => void
}) {
  const { t } = useTranslation('search', { keyPrefix: 'more' })
  const { t: tp } = useTranslation('profileEditor')
  const ids = useId()
  const saveSection = useSaveProfileSection()
  const floor = useSalaryFloor()
  const saveSalary = useSaveSalaryFloor()

  const server = readMore(prefs)
  const serverSalary = floor.data?.salary_floor_eur ?? null
  const [draft, setDraft] = useState<MoreDraft | null>(null)
  const [salaryText, setSalaryText] = useState<string | null>(null)
  const [errors, setErrors] = useState<ReadonlyMap<string, string>>(new Map())
  const [status, setStatus] = useState<Status | null>(null)
  const [saving, setSaving] = useState(false)
  // Tras guardar, se espera al perfil nuevo (con este `file_hash`) antes de soltar el borrador.
  const [waitFor, setWaitFor] = useState<string | null>(null)
  const mutating = useIsMutating() > 0

  // Si el perfil nuevo no llega (falla la recarga), no se queda todo bloqueado.
  useEffect(() => {
    if (waitFor === null) return
    const timer = window.setTimeout(() => setWaitFor(null), 8000)
    return () => window.clearTimeout(timer)
  }, [waitFor])

  // Ya está el perfil guardado: el borrador deja paso a lo que dice el fichero (ajuste durante el render).
  if (waitFor !== null && state.file_hash === waitFor) {
    setDraft(null)
    setSalaryText(null)
    setWaitFor(null)
  }

  const view = draft ?? server
  const salaryValue = salaryText ?? (serverSalary == null ? '' : String(serverSalary))
  const salary = num(salaryValue)
  const salaryInvalid = salary !== null && (!Number.isInteger(salary) || salary <= 0)
  const moreChanged = draft !== null && !same(draft, server)
  const salaryChanged = salaryText !== null && salary !== serverSalary
  const dirty = moreChanged || salaryChanged
  // También mientras se guarda otra cosa (la franja): cada guardado parte del fichero que deja el anterior.
  const busy = saving || waitFor !== null || mutating
  useUnsavedGuard(dirty && !busy, t('unsavedConfirm'))

  const set = (change: Partial<MoreDraft>) => {
    setStatus(null)
    setDraft({ ...view, ...change })
  }
  const err = (path: string) =>
    [...errors].find(([k]) => k === `preferences.${path}` || k.startsWith(`preferences.${path}.`) || k.startsWith(`preferences.${path}[`))?.[1]

  /** Guarda lo que cambia (la sección y luego el sueldo, cada uno con el `file_hash` del anterior). */
  const persist = async (more: MoreDraft | null, floorValue: number | null | undefined): Promise<boolean> => {
    setSaving(true)
    setErrors(new Map())
    setStatus(null)
    let hash = state.file_hash
    let changed = false
    try {
      if (more) {
        const result = await saveSection.mutateAsync({ section: 'preferences', file_hash: hash, content: { ...prefs, ...more } })
        hash = result.file_hash
        changed ||= result.changed
      }
      if (floorValue !== undefined) {
        const result = await saveSalary.mutateAsync({ file_hash: hash, salary_floor_eur: floorValue })
        hash = result.file_hash
        changed ||= result.changed
      }
      if (changed && hash !== state.file_hash) setWaitFor(hash)
      else {
        setDraft(null)
        setSalaryText(null)
      }
      return true
    } catch (error) {
      const map = new Map<string, string>()
      if (error instanceof ApiError && error.type === 'validation_error') for (const d of error.details) map.set(d.field, d.reason)
      setErrors(map)
      const conflict = error instanceof ApiError && error.type === 'conflict'
      const message = conflict ? tp('errors.conflict') : map.size > 0 ? tp('errors.validation') : errorMessage(error)
      setStatus({ kind: 'error', message, conflict })
      // Si una parte ya se guardó, el fichero cambió: se recarga.
      if (hash !== state.file_hash) reload()
      return false
    } finally {
      setSaving(false)
    }
  }

  const save = async () => {
    const before = { more: server, salary: serverSalary }
    if (await persist(moreChanged ? view : null, salaryChanged ? salary : undefined)) setStatus({ kind: 'saved', before })
  }
  const undo = async (before: Snapshot) => {
    const back = !same(before.more, server) ? before.more : null
    if (await persist(back, before.salary !== serverSalary ? before.salary : undefined)) setStatus({ kind: 'undone' })
  }
  const discard = () => {
    setDraft(null)
    setSalaryText(null)
    setErrors(new Map())
    setStatus(null)
  }

  const active = activeGroups(view, salaryInvalid ? null : salary)
  const tolerance = state.policy_years_tolerance ?? 0
  const policyWords = state.policy_discard_title_keywords ?? []
  const signals = view.exclude_signals
  const employer = [...view.excluded_employer_kinds, ...(signals.includes('employer_hidden') ? (['employer_hidden'] as const) : [])]

  return (
    <div id={id} hidden={hidden} role="region" aria-label={t('label')} className="col-span-full rounded-b-xl border-t bg-muted/45 px-5 pt-5 pb-3.5">
      <div className="grid gap-x-8 gap-y-6 lg:grid-cols-3">
        <div className="grid content-start gap-6">
          <SettingsGroup title={t('experience')} active={active.has('experience')}>
            <fieldset className="grid gap-1.5">
              <legend className="mb-1.5 flex items-center gap-1 text-sm">
                {t('years')}
                <Hint text={tolerance > 0 ? tp('fields.yearsHint', { count: tolerance }) : tp('fields.yearsHintExact')} label={t('yearsHintLabel')} />
              </legend>
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <Label htmlFor={`${ids}-min`} className="font-normal">
                  {tp('fields.minYears')}
                </Label>
                <Input
                  id={`${ids}-min`}
                  type="number"
                  min={0}
                  max={40}
                  className="h-8 w-16"
                  disabled={busy}
                  value={view.min_years_required == null ? '' : String(view.min_years_required)}
                  aria-invalid={err('min_years_required') ? true : undefined}
                  aria-describedby={err('min_years_required') ? `${ids}-min-error` : undefined}
                  onChange={(e) => set({ min_years_required: num(e.target.value) })}
                />
                <Label htmlFor={`${ids}-max`} className="font-normal">
                  {tp('fields.maxYearsShort')}
                </Label>
                <Input
                  id={`${ids}-max`}
                  type="number"
                  min={0}
                  max={40}
                  className="h-8 w-16"
                  disabled={busy}
                  value={view.max_years_required == null ? '' : String(view.max_years_required)}
                  aria-invalid={err('max_years_required') ? true : undefined}
                  aria-describedby={err('max_years_required') ? `${ids}-max-error` : undefined}
                  onChange={(e) => set({ max_years_required: num(e.target.value) })}
                />
                <span className="text-muted-foreground">{tp('fields.yearsUnit')}</span>
              </div>
              <FieldError id={`${ids}-min-error`} error={err('min_years_required')} />
              <FieldError id={`${ids}-max-error`} error={err('max_years_required')} />
            </fieldset>
            <div className="grid gap-1.5">
              <Label htmlFor={`${ids}-salary`} className="font-normal">
                {tp('fields.salaryFloor')}
              </Label>
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <Input
                  id={`${ids}-salary`}
                  type="number"
                  min={1}
                  step={1000}
                  inputMode="numeric"
                  className="h-8 w-28"
                  value={salaryValue}
                  disabled={busy || floor.isLoading || floor.isError}
                  aria-invalid={salaryInvalid ? true : undefined}
                  aria-describedby={[`${ids}-salary-note`, (salaryInvalid || floor.isError) && `${ids}-salary-error`].filter(Boolean).join(' ')}
                  onChange={(e) => {
                    setStatus(null)
                    setSalaryText(e.target.value)
                  }}
                />
                <span className="text-muted-foreground">{tp('fields.salaryUnit')}</span>
              </div>
              <p id={`${ids}-salary-note`} className="flex items-center gap-1 text-xs text-muted-foreground">
                <LockIcon className="size-3" aria-hidden />
                {t('salaryPrivate')} <Hint text={tp('fields.salaryHint')} label={t('salaryHintLabel')} />
              </p>
              <FieldError id={`${ids}-salary-error`} error={salaryInvalid ? tp('fields.salaryInvalid') : floor.isError ? tp('fields.salaryLoadError') : undefined} />
            </div>
          </SettingsGroup>

          <SettingsGroup title={t('languages')} active={active.has('languages')}>
            <CodeTagsField
              kind="language"
              className="[&>label]:sr-only"
              label={tp('fields.workLanguages')}
              value={view.languages_for_work}
              error={err('languages_for_work')}
              onChange={(v) => set({ languages_for_work: v })}
            />
          </SettingsGroup>
        </div>

        <SettingsGroup title={t('contract')} active={active.has('contract')}>
          <ChipChoices
            label={tp('fields.contractTypes')}
            value={view.contract_types}
            disabled={busy}
            options={CONTRACT_TYPES.map((c) => ({ value: c, label: tp(`fields.contract.${c}`) }))}
            onChange={(v) => set({ contract_types: v })}
          />
          <ChipChoices
            label={tp('fields.employmentTypes')}
            value={view.employment_types}
            disabled={busy}
            options={EMPLOYMENT_TYPES.map((e) => ({ value: e, label: tp(`fields.employment.${e}`) }))}
            onChange={(v) => set({ employment_types: v })}
          />
          <p className="flex items-center gap-1 text-xs text-muted-foreground">
            {t('anyIfEmpty')} <Hint text={t('ruleHint')} label={t('ruleHintLabel')} />
          </p>
          <FieldError id={`${ids}-contract-error`} error={err('contract_types') ?? err('employment_types')} />
        </SettingsGroup>

        <SettingsGroup title={t('discard')} active={active.has('discard')}>
          <p className="-mb-1.5 flex items-center gap-1 text-sm">
            {t('keywords')}
            <Hint
              text={[tp('fields.discardKeywordsHint'), policyWords.length > 0 ? tp('fields.policyKeywords', { words: policyWords.join(', ') }) : ''].join(' ').trim()}
              label={t('keywordsHintLabel')}
            />
          </p>
          <TagsField
            label={t('keywords')}
            className="[&>label]:sr-only"
            value={view.discard_title_keywords}
            error={err('discard_title_keywords')}
            onChange={(v) => set({ discard_title_keywords: v })}
          />
          <div role="group" aria-label={t('employerLabel')} className="grid gap-1.5">
            {[...EMPLOYER_KINDS, 'employer_hidden' as const].map((kind) => (
              <label key={kind} className="flex items-start gap-2 text-sm">
                <input
                  type="checkbox"
                  className="mt-0.5 accent-primary"
                  disabled={busy}
                  checked={(employer as string[]).includes(kind)}
                  onChange={(e) => {
                    if (kind === 'employer_hidden') {
                      const others = signals.filter((s) => s !== 'employer_hidden')
                      set({ exclude_signals: e.target.checked ? [...others, 'employer_hidden'] : others })
                    } else {
                      const next = e.target.checked ? [...view.excluded_employer_kinds, kind] : view.excluded_employer_kinds.filter((k) => k !== kind)
                      set({ excluded_employer_kinds: EMPLOYER_KINDS.filter((k) => next.includes(k)) })
                    }
                  }}
                />
                {t(`employer.${kind}`)}
              </label>
            ))}
            <FieldError id={`${ids}-employer-error`} error={err('excluded_employer_kinds') ?? err('exclude_signals')} />
          </div>
        </SettingsGroup>
      </div>

      <div className="mt-5 flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-t pt-3">
        <Button type="button" variant="ghost" size="sm" disabled={busy} onClick={() => {
          setStatus(null)
          setDraft(clearedMore(view))
          setSalaryText('')
        }}>
          {t('reset')}
        </Button>
        <div className="flex flex-wrap items-center justify-end gap-x-3 gap-y-2">
          <span className="text-xs text-muted-foreground" aria-live="polite">
            {status?.kind === 'error' ? (
              <span role="alert" className="flex flex-wrap items-center gap-2 text-destructive">
                {status.message}
                {status.conflict && (
                  <Button type="button" size="sm" variant="ghost" onClick={() => {
                    discard()
                    reload()
                    void floor.refetch()
                  }}>
                    {tp('actions.reload')}
                  </Button>
                )}
              </span>
            ) : status?.kind === 'saved' && !dirty ? (
              <span className="inline-flex items-center gap-2 text-primary">
                <CheckIcon className="size-3.5" aria-hidden />
                {t('saved')}
                <button type="button" disabled={busy} className="underline-offset-4 hover:underline disabled:opacity-50" onClick={() => void undo(status.before)}>
                  {t('undo')}
                </button>
              </span>
            ) : status?.kind === 'undone' && !dirty ? (
              t('undone')
            ) : dirty ? (
              t('rescore')
            ) : null}
          </span>
          <Button type="button" variant="outline" size="sm" disabled={!dirty || busy} onClick={discard}>
            {t('discardChanges')}
          </Button>
          <Button type="button" size="sm" disabled={!dirty || busy || salaryInvalid} onClick={() => void save()}>
            <BusyLabel busy={saving} busyText={t('saving')} text={t('save')} />
          </Button>
        </div>
      </div>
    </div>
  )
}

function SettingsGroup({ title, active, children }: { title: string; active: boolean; children: ReactNode }) {
  const id = useId()
  return (
    <section className="grid content-start gap-3" aria-labelledby={id}>
      <h3 id={id} className="flex items-center gap-2 text-sm font-semibold">
        <span aria-hidden className={cn('size-1.5 rounded-full', active ? 'bg-primary' : 'bg-transparent')} />
        {title}
      </h3>
      {children}
    </section>
  )
}
