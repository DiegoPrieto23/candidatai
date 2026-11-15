/**
 * Preferencias (fase 25.7b): búsqueda, CV y carta. Todas son partes de la misma sección
 * (`preferences`): cada bloque cambia la suya y guarda la sección entera con las demás tal cual.
 * «Búsqueda» va en cuatro bloques (fase 27.5): puesto, experiencia y sueldo, dónde y cómo, y
 * contrato y empresa. El sueldo mínimo vive en `private` y se guarda aparte, sin diff.
 */
import { useEffect, useId, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { LockIcon, XIcon } from '@phosphor-icons/react'
import { ApiError } from '@/api/client'
import { Hint } from '@/components/Hint'
import { useSalaryFloor, useSaveSalaryFloor, useTemplates } from '@/api/queries'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { errorMessage } from '@/lib/errors'
import { Block, BlockActions, CheckField, ChoicesField, CodeTagsField, FieldError, SelectField, TagsField, TextField } from './fields'
import { useBlockEditor, useProfileState } from './editor'
import {
  CONTRACT_TYPES,
  EMPLOYER_KINDS,
  EMPLOYMENT_TYPES,
  REMOTE_MODES,
  SENIORITIES,
  type ContractType,
  type CoverLetterPreferences,
  type CvPreferences,
  type Preferences,
  type ProfileData,
} from './types'
import { useTemplateText } from '@/lib/templateText'
import { BusyLabel } from '@/components/StableLabel'

const prefs = (p: ProfileData): Preferences =>
  p.preferences ?? { roles: [], seniority_target: [], remote_modes: [], languages_for_work: [], cv: { photo_policy: { default: true } } }

// Cada bloque de «Búsqueda» edita unas claves de `preferences`; las demás (también lo que la UI no
// edita) vuelven tal cual.
const writeSearch = <T extends Partial<Preferences>>(d: T, p: ProfileData) => ({ preferences: { ...prefs(p), ...d } })

const num = (value: string): number | null => (value.trim() === '' ? null : Number(value))

type Role = Pick<Preferences, 'roles' | 'seniority_target' | 'discard_title_keywords'>
const readRole = (p: ProfileData): Role => {
  const { roles, seniority_target, discard_title_keywords } = prefs(p)
  return { roles, seniority_target, discard_title_keywords: discard_title_keywords ?? [] }
}

/** Puestos, niveles y palabras que descartan. */
export function SearchRoleBlock() {
  const { t } = useTranslation('profileEditor')
  const { state } = useProfileState()
  const block = useBlockEditor('search-role', readRole, writeSearch, { preview: true })
  const d = block.draft
  const err = (path: string) => [...block.errors].find(([k]) => k === `preferences.${path}` || k.startsWith(`preferences.${path}.`) || k.startsWith(`preferences.${path}[`))?.[1]
  const set = (change: Partial<Role>) => block.update((current) => ({ ...current, ...change }))
  const policyWords = state.policy_discard_title_keywords ?? []
  return (
    <Block id="search-role" title={t('blocks.searchRole.title')} hint={t('blocks.searchRole.hint')}>
      <TagsField label={t('fields.roles')} hint={t('fields.rolesHint')} value={d.roles} error={err('roles')} onChange={(v) => set({ roles: v })} />
      <ChoicesField
        label={t('fields.seniority')}
        value={d.seniority_target}
        error={err('seniority_target')}
        options={SENIORITIES.map((s) => ({ value: s, label: t(`seniority.${s}`) }))}
        onChange={(v) => set({ seniority_target: v })}
      />
      <TagsField
        label={t('fields.discardKeywords')}
        hint={
          <>
            {t('fields.discardKeywordsHint')}
            {policyWords.length > 0 && <> {t('fields.policyKeywords', { words: policyWords.join(', ') })}</>}
          </>
        }
        value={d.discard_title_keywords}
        error={err('discard_title_keywords')}
        onChange={(v) => set({ discard_title_keywords: v })}
      />
      <BlockActions block={block} />
    </Block>
  )
}

type Experience = Pick<Preferences, 'min_years_required' | 'max_years_required'>
const readExperience = (p: ProfileData): Experience => {
  const { min_years_required, max_years_required } = prefs(p)
  return { min_years_required: min_years_required ?? null, max_years_required: max_years_required ?? null }
}

/** Años que pide la oferta (como un rango) y el sueldo mínimo, que se guarda aparte. */
export function SearchExperienceBlock() {
  const { t } = useTranslation('profileEditor')
  const { state } = useProfileState()
  const block = useBlockEditor('search-experience', readExperience, writeSearch, { preview: true })
  const d = block.draft
  const id = useId()
  const set = (change: Partial<Experience>) => block.update((current) => ({ ...current, ...change }))
  const tolerance = state.policy_years_tolerance ?? 0
  const minError = block.errors.get('preferences.min_years_required')
  const maxError = block.errors.get('preferences.max_years_required')
  return (
    <Block id="search-experience" title={t('blocks.searchExperience.title')} hint={t('blocks.searchExperience.hint')}>
      <fieldset className="grid content-start gap-1.5" aria-describedby={`${id}-hint`}>
        <legend className="mb-1 text-sm font-medium">{t('fields.years')}</legend>
        <div className="flex flex-wrap items-center gap-2">
          <Label htmlFor={`${id}-min`} className="font-normal">
            {t('fields.minYears')}
          </Label>
          <Input
            id={`${id}-min`}
            type="number"
            min={0}
            max={40}
            className="w-20"
            value={d.min_years_required == null ? '' : String(d.min_years_required)}
            aria-invalid={minError ? true : undefined}
            aria-describedby={minError ? `${id}-min-error` : undefined}
            onChange={(e) => set({ min_years_required: num(e.target.value) })}
          />
          <Label htmlFor={`${id}-max`} className="font-normal">
            {t('fields.maxYearsShort')}
          </Label>
          <Input
            id={`${id}-max`}
            type="number"
            min={0}
            max={40}
            className="w-20"
            value={d.max_years_required == null ? '' : String(d.max_years_required)}
            aria-invalid={maxError ? true : undefined}
            aria-describedby={maxError ? `${id}-max-error` : undefined}
            onChange={(e) => set({ max_years_required: num(e.target.value) })}
          />
          <span className="text-sm text-muted-foreground">{t('fields.yearsUnit')}</span>
        </div>
        <p id={`${id}-hint`} className="text-xs text-muted-foreground">
          {tolerance > 0 ? t('fields.yearsHint', { count: tolerance }) : t('fields.yearsHintExact')}
        </p>
        <FieldError id={`${id}-min-error`} error={minError} />
        <FieldError id={`${id}-max-error`} error={maxError} />
      </fieldset>
      <BlockActions block={block} />
      <SalaryFloorField />
    </Block>
  )
}

/** El sueldo mínimo (`private.salary_floor_eur`): privado, con su propio botón y sin diff. */
function SalaryFloorField() {
  const { t } = useTranslation('profileEditor')
  const { state, setDirty, reload } = useProfileState()
  const floor = useSalaryFloor()
  const save = useSaveSalaryFloor()
  const id = useId()
  const [text, setText] = useState<string | null>(null) // `null`: sin tocar, se ve el guardado
  const [saved, setSaved] = useState(false)
  const server = floor.data?.salary_floor_eur ?? null
  const value = text ?? (server == null ? '' : String(server))
  const parsed = num(value)
  const invalid = parsed !== null && (!Number.isInteger(parsed) || parsed <= 0)
  const dirty = text !== null && parsed !== server
  useEffect(() => setDirty('salary-floor', dirty), [dirty, setDirty])
  useEffect(() => () => setDirty('salary-floor', false), [setDirty])
  const error = save.error
  const conflict = error instanceof ApiError && error.type === 'conflict'
  const message = conflict ? t('errors.conflict') : error ? errorMessage(error) : floor.isError ? t('fields.salaryLoadError') : null
  const describedBy = [`${id}-unit`, `${id}-hint`, invalid && `${id}-error`].filter(Boolean).join(' ')
  return (
    <div className="grid gap-2 rounded-lg border border-dashed p-3">
      <Label htmlFor={id} className="flex items-center gap-1.5">
        <LockIcon aria-hidden /> {t('fields.salaryFloor')}
      </Label>
      <div className="flex flex-wrap items-center gap-2">
        <Input
          id={id}
          type="number"
          min={1}
          step={1000}
          inputMode="numeric"
          className="w-36"
          value={value}
          disabled={floor.isLoading || floor.isError}
          aria-invalid={invalid ? true : undefined}
          aria-describedby={describedBy}
          onChange={(e) => {
            setText(e.target.value)
            setSaved(false)
            save.reset()
          }}
        />
        <span id={`${id}-unit`} className="text-sm text-muted-foreground">
          {t('fields.salaryUnit')}
        </span>
        <Button
          type="button"
          size="sm"
          disabled={!dirty || invalid || save.isPending}
          onClick={() =>
            save.mutate(
              { file_hash: state.file_hash, salary_floor_eur: parsed },
              {
                onSuccess: () => {
                  setText(null)
                  setSaved(true)
                },
              },
            )
          }
        >
          <BusyLabel busy={save.isPending} busyText={t('actions.saving')} text={t('fields.salarySave')} />
        </Button>
        <span role="status" className="text-xs text-emerald-700 dark:text-emerald-400">
          {saved && !dirty ? t('fields.salarySaved') : null}
        </span>
      </div>
      <p id={`${id}-hint`} className="text-xs text-muted-foreground">
        {t('fields.salaryHint')}
      </p>
      <FieldError id={`${id}-error`} error={invalid ? t('fields.salaryInvalid') : undefined} />
      {message && (
        <div className="flex flex-wrap items-center gap-2">
          <p role="alert" className="text-sm text-destructive">
            {message}
          </p>
          {conflict && (
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={() => {
                save.reset()
                reload()
              }}
            >
              {t('actions.reload')}
            </Button>
          )}
        </div>
      )}
    </div>
  )
}

type Where = Pick<Preferences, 'remote_modes' | 'locations' | 'languages_for_work'>
const readWhere = (p: ProfileData): Where => {
  const { remote_modes, locations, languages_for_work } = prefs(p)
  return { remote_modes, locations, languages_for_work }
}

/** Modalidad, ubicaciones e idiomas. */
export function SearchWhereBlock() {
  const { t } = useTranslation('profileEditor')
  const block = useBlockEditor('search-where', readWhere, writeSearch, { preview: true })
  const d = block.draft
  const err = (path: string) => [...block.errors].find(([k]) => k === `preferences.${path}` || k.startsWith(`preferences.${path}.`) || k.startsWith(`preferences.${path}[`))?.[1]
  const set = (change: Partial<Where>) => block.update((current) => ({ ...current, ...change }))
  const locations = d.locations ?? {}
  return (
    <Block id="search-where" title={t('blocks.searchWhere.title')} hint={t('blocks.searchWhere.hint')}>
      <ChoicesField
        label={t('fields.remoteModes')}
        value={d.remote_modes}
        error={err('remote_modes')}
        options={REMOTE_MODES.map((m) => ({ value: m, label: t(`remote.${m}`) }))}
        onChange={(v) => set({ remote_modes: v })}
      />
      <LocationsField
        value={locations}
        error={err('locations')}
        onChange={(v) => set({ locations: v })}
      />
      <CodeTagsField
        kind="language"
        label={t('fields.workLanguages')}
        value={d.languages_for_work}
        error={err('languages_for_work')}
        onChange={(v) => set({ languages_for_work: v })}
      />
      <BlockActions block={block} />
    </Block>
  )
}

const LOCATION_KINDS = ['preferred', 'allowed', 'excluded'] as const
type LocationKind = (typeof LOCATION_KINDS)[number]
type Locations = NonNullable<Preferences['locations']>

/**
 * Ubicaciones con un selector por fila (fase 41.4): «Cualquier modalidad» (`preferred`), «Solo
 * híbrido o remoto» (`allowed`) o «Descartar» (`excluded`). Se guardan las mismas tres listas de
 * siempre. Las filas no cambian de sitio al cambiar el selector: el orden se recuerda aquí (al
 * recargar, vuelven al orden de las listas). La clave es el sitio, así el selector no pierde el foco.
 */
function LocationsField({ value, error, onChange }: { value: Locations; error?: string; onChange: (v: Locations) => void }) {
  const { t } = useTranslation('profileEditor')
  const id = useId()
  const [text, setText] = useState('')
  const [order, setOrder] = useState<string[]>([])
  // Un sitio, una fila (si un perfil antiguo lo tiene en dos listas, manda la primera).
  const rows = LOCATION_KINDS.flatMap((kind) => (value[kind] ?? []).map((place) => ({ kind, place }))).filter(
    (row, i, all) => all.findIndex((r) => r.place.toLowerCase() === row.place.toLowerCase()) === i,
  )
  const rank = (place: string) => {
    const i = order.indexOf(place.toLowerCase())
    return i === -1 ? Number.MAX_SAFE_INTEGER : i
  }
  // `sort` es estable: las que aún no tienen sitio en `order` quedan en el orden de las listas.
  const sorted = [...rows].sort((a, b) => rank(a.place) - rank(b.place))
  const remember = (places: string[]) => setOrder((current) => [...current, ...places.map((p) => p.toLowerCase()).filter((p) => !current.includes(p))])
  const without = (place: string): Locations =>
    Object.fromEntries(
      Object.entries(value).map(([k, v]) => [k, LOCATION_KINDS.includes(k as LocationKind) && Array.isArray(v) ? v.filter((p) => p.toLowerCase() !== place.toLowerCase()) : v]),
    )
  const move = (place: string, kind: LocationKind) => {
    remember(sorted.map((r) => r.place))
    const rest = without(place)
    onChange({ ...rest, [kind]: [...(rest[kind] ?? []), place] })
  }
  const add = () => {
    const place = text.trim()
    setText('')
    if (!place || rows.some((r) => r.place.toLowerCase() === place.toLowerCase())) return
    remember([...sorted.map((r) => r.place), place])
    onChange({ ...value, preferred: [...(value.preferred ?? []), place] })
  }
  return (
    <fieldset className="grid content-start gap-2" aria-describedby={error ? `${id}-error` : undefined}>
      <legend className="mb-1 flex items-center gap-1 text-sm font-medium">
        {t('fields.locations.label')} <Hint text={t('fields.locations.hint')} label={t('fields.locations.hintLabel')} />
      </legend>
      {sorted.length > 0 && (
        <ul className="grid gap-2">
          {sorted.map(({ kind, place }) => (
            <li key={place.toLowerCase()} className="flex flex-wrap items-center gap-2">
              <span className="min-w-0 flex-1 truncate text-sm">{place}</span>
              <select
                className="h-9 w-56 rounded-md border border-input bg-background px-3 text-sm"
                aria-label={t('fields.locations.modeFor', { place })}
                value={kind}
                onChange={(e) => move(place, e.target.value as LocationKind)}
              >
                {LOCATION_KINDS.map((k) => (
                  <option key={k} value={k}>
                    {t(`fields.locations.${k}`)}
                  </option>
                ))}
              </select>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="size-8"
                aria-label={t('fields.removeTag', { item: place })}
                onClick={() => onChange(without(place))}
              >
                <XIcon aria-hidden />
              </Button>
            </li>
          ))}
        </ul>
      )}
      <div className="flex gap-2">
        <Input
          className="min-w-0"
          value={text}
          aria-label={t('fields.locations.add')}
          placeholder={t('fields.locations.add')}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              add()
            }
          }}
        />
        <Button type="button" variant="outline" size="sm" onClick={add} disabled={!text.trim()}>
          {t('fields.add')}
        </Button>
      </div>
      <FieldError id={`${id}-error`} error={error} />
    </fieldset>
  )
}

type Contract = Required<Pick<Preferences, 'contract_types' | 'employment_types' | 'excluded_employer_kinds' | 'exclude_signals'>>

/** `exclude_signals: [fixed_term]` es lo mismo que no aceptar `fixed_term`: la pantalla
 *  lo enseña como la casilla «Temporal» sin marcar y al guardar escribe solo `contract_types`. */
export const readContract = (p: ProfileData): Contract => {
  const pr = prefs(p)
  const signals = pr.exclude_signals ?? []
  const accepted = pr.contract_types ?? []
  const contract_types = signals.includes('fixed_term')
    ? (accepted.length ? accepted : [...CONTRACT_TYPES]).filter((c: ContractType) => c !== 'fixed_term')
    : accepted
  return {
    contract_types,
    employment_types: pr.employment_types ?? [],
    excluded_employer_kinds: pr.excluded_employer_kinds ?? [],
    exclude_signals: signals.filter((s) => s !== 'fixed_term'),
  }
}

type EmployerChoice = (typeof EMPLOYER_KINDS)[number] | 'employer_hidden'

/** Tipo de contrato, jornada y tipo de empresa. */
export function SearchContractBlock() {
  const { t } = useTranslation('profileEditor')
  const block = useBlockEditor('search-contract', readContract, writeSearch, { preview: true })
  const d = block.draft
  const err = (path: string) => [...block.errors].find(([k]) => k.startsWith(`preferences.${path}`))?.[1]
  const set = (change: Partial<Contract>) => block.update((current) => ({ ...current, ...change }))
  return (
    <Block id="search-contract" title={t('blocks.searchContract.title')} hint={t('blocks.searchContract.hint')}>
      <div className="grid gap-4 sm:grid-cols-2">
        <ChoicesField
          label={t('fields.contractTypes')}
          value={d.contract_types}
          error={err('contract_types')}
          options={CONTRACT_TYPES.map((c) => ({ value: c, label: t(`fields.contract.${c}`) }))}
          onChange={(v) => set({ contract_types: CONTRACT_TYPES.filter((c) => v.includes(c)) })}
        />
        <ChoicesField
          label={t('fields.employmentTypes')}
          value={d.employment_types}
          error={err('employment_types')}
          options={EMPLOYMENT_TYPES.map((e) => ({ value: e, label: t(`fields.employment.${e}`) }))}
          onChange={(v) => set({ employment_types: EMPLOYMENT_TYPES.filter((e) => v.includes(e)) })}
        />
      </div>
      {/* «No dice qué empresa contrata» es una señal (`exclude_signals`), pero se marca con los
          tipos de empresa: es de lo que trata. Las demás señales que haya se quedan como estaban. */}
      <ChoicesField
        vertical
        label={t('fields.employerKinds')}
        hint={t('fields.employerKindsHint')}
        value={[...d.excluded_employer_kinds, ...(d.exclude_signals.includes('employer_hidden') ? (['employer_hidden'] as const) : [])]}
        error={err('excluded_employer_kinds') ?? err('exclude_signals')}
        options={[
          ...EMPLOYER_KINDS.map((k) => ({ value: k as EmployerChoice, label: t(`fields.employer.${k}`) })),
          { value: 'employer_hidden' as EmployerChoice, label: t('fields.employerHidden') },
        ]}
        onChange={(v) => {
          const others = d.exclude_signals.filter((s) => s !== 'employer_hidden')
          set({
            excluded_employer_kinds: EMPLOYER_KINDS.filter((k) => v.includes(k)),
            exclude_signals: v.includes('employer_hidden') ? [...others, 'employer_hidden'] : others,
          })
        }}
      />
      <BlockActions block={block} />
    </Block>
  )
}

const readCv = (p: ProfileData): CvPreferences => prefs(p).cv
const writeCv = (d: CvPreferences, p: ProfileData) => ({ preferences: { ...prefs(p), cv: d } })

/** Plantilla por defecto, páginas, foto por país, indicaciones y lo que no quieres que diga. */
export function CvPreferencesBlock() {
  const { t } = useTranslation('profileEditor')
  const text = useTemplateText()
  const templates = useTemplates()
  const block = useBlockEditor('cv', readCv, writeCv)
  const d = block.draft
  const err = (path: string) => block.errors.get(`preferences.cv.${path}`)
  const set = (change: Partial<CvPreferences>) => block.update((current) => ({ ...current, ...change }))
  const byCountry = d.photo_policy.by_country ?? {}
  const options = [
    { value: '', label: t('fields.templateAuto') },
    ...(templates.data?.templates ?? []).map((tpl) => ({ value: tpl.id, label: text.name(tpl) })),
  ]
  if (d.default_template && !options.some((o) => o.value === d.default_template)) {
    options.push({ value: d.default_template, label: d.default_template })
  }
  return (
    <Block id="cv" title={t('blocks.cv.title')} hint={t('blocks.cv.hint')}>
      <div className="grid gap-4 sm:grid-cols-2">
        <SelectField
          label={t('fields.defaultTemplate')}
          value={d.default_template ?? ''}
          options={options}
          error={err('default_template')}
          onChange={(v) => set({ default_template: v || null })}
        />
        <SelectField
          label={t('fields.maxPages')}
          value={d.max_pages == null ? '' : String(d.max_pages)}
          options={[{ value: '', label: t('fields.maxPagesAuto') }, ...['1', '2', '3'].map((v) => ({ value: v, label: v }))]}
          onChange={(v) => set({ max_pages: num(v) })}
        />
      </div>
      <div className="grid gap-2">
        <CheckField
          label={t('fields.photoDefault')}
          checked={d.photo_policy.default}
          onChange={(v) => set({ photo_policy: { ...d.photo_policy, default: v } })}
        />
        <CodeTagsField
          kind="region"
          label={t('fields.photoNo')}
          value={Object.entries(byCountry).filter(([, v]) => !v).map(([k]) => k)}
          error={[...block.errors].find(([k]) => k.startsWith('preferences.cv.photo_policy'))?.[1]}
          onChange={(v) =>
            set({
              photo_policy: {
                ...d.photo_policy,
                by_country: {
                  ...Object.fromEntries(Object.entries(byCountry).filter(([, on]) => on)),
                  ...Object.fromEntries(v.map((c) => [c, false])),
                },
              },
            })
          }
        />
      </div>
      <TextField multiline label={t('fields.cvInstructions')} hint={t('fields.instructionsHint')} value={d.instructions} onChange={(v) => set({ instructions: v })} />
      <TagsField label={t('fields.avoid')} hint={t('fields.avoidHint')} value={d.avoid} onChange={(v) => set({ avoid: v })} />
      {(d.template_rules ?? []).length > 0 && (
        <p className="text-xs text-muted-foreground">{t('blocks.cv.rules', { count: (d.template_rules ?? []).length })}</p>
      )}
      <BlockActions block={block} />
    </Block>
  )
}

const readLetter = (p: ProfileData): CoverLetterPreferences => prefs(p).cover_letter ?? {}
const writeLetter = (d: CoverLetterPreferences, p: ProfileData) => ({ preferences: { ...prefs(p), cover_letter: d } })

/** Indicaciones generales de la carta. Las de cada oferta siguen en su ficha. */
export function LetterPreferencesBlock() {
  const { t } = useTranslation('profileEditor')
  const block = useBlockEditor('letter', readLetter, writeLetter)
  const d = block.draft
  const err = (path: string) => block.errors.get(`preferences.cover_letter.${path}`)
  const set = (change: Partial<CoverLetterPreferences>) => block.update((current) => ({ ...current, ...change }))
  const signOff = d.sign_off ?? {}
  return (
    <Block id="letter" title={t('blocks.letter.title')} hint={t('blocks.letter.hint')}>
      <div className="grid gap-4 sm:grid-cols-2">
        <TextField label={t('fields.tone')} value={d.tone} onChange={(v) => set({ tone: v })} />
        <TextField
          label={t('fields.maxWords')}
          hint={t('fields.maxWordsHint')}
          type="number"
          value={d.max_words == null ? '' : String(d.max_words)}
          error={err('max_words')}
          onChange={(v) => set({ max_words: num(v) })}
        />
        <TextField label={t('fields.signOffEs')} value={signOff.es} onChange={(v) => set({ sign_off: { ...signOff, es: v } })} />
        <TextField label={t('fields.signOffEn')} value={signOff.en} onChange={(v) => set({ sign_off: { ...signOff, en: v } })} />
        <SelectField
          label={t('fields.defaultFormat')}
          value={d.default_format ?? ''}
          options={[
            { value: '', label: t('fields.formatNone') },
            { value: 'text', label: t('fields.formatText') },
            { value: 'pdf', label: 'PDF' },
          ]}
          onChange={(v) => set({ default_format: (v || null) as CoverLetterPreferences['default_format'] })}
        />
      </div>
      <TextField multiline label={t('fields.letterInstructions')} hint={t('fields.letterInstructionsHint')} value={d.instructions} onChange={(v) => set({ instructions: v })} />
      <TagsField label={t('fields.avoid')} hint={t('fields.avoidHint')} value={d.avoid} onChange={(v) => set({ avoid: v })} />
      <BlockActions block={block} />
    </Block>
  )
}
