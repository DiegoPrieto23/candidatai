/**
 * Preferencias (fase 25.7b): búsqueda, CV y carta. Las tres son partes de la misma sección
 * (`preferences`): cada bloque cambia la suya y guarda la sección entera con las demás tal cual.
 */
import { useTranslation } from 'react-i18next'
import { useTemplates } from '@/api/queries'
import { Block, BlockActions, CheckField, ChoicesField, SelectField, TagsField, TextField } from './fields'
import { useBlockEditor } from './editor'
import {
  REMOTE_MODES,
  SENIORITIES,
  type CoverLetterPreferences,
  type CvPreferences,
  type Preferences,
  type ProfileData,
} from './types'

// Lo de `preferences` menos `cv` y `cover_letter` (también lo que la UI no edita, como
// `exclude_signals`, que vuelve tal cual).
type Search = Pick<Preferences, 'roles' | 'seniority_target' | 'max_years_required' | 'remote_modes' | 'locations' | 'languages_for_work'> & {
  [key: string]: unknown
}

const prefs = (p: ProfileData): Preferences =>
  p.preferences ?? { roles: [], seniority_target: [], remote_modes: [], languages_for_work: [], cv: { photo_policy: { default: true } } }

const readSearch = (p: ProfileData): Search => {
  const { cv: _cv, cover_letter: _letter, ...search } = prefs(p)
  return search as Search
}
const writeSearch = (d: Search, p: ProfileData) => ({ preferences: { ...prefs(p), ...d } })

const num = (value: string): number | null => (value.trim() === '' ? null : Number(value))

/** Puestos, seniority, años, modalidad, ubicaciones e idiomas: son los filtros duros y el score. */
export function SearchPreferencesBlock() {
  const { t } = useTranslation('profileEditor')
  const block = useBlockEditor('search', readSearch, writeSearch, { preview: true })
  const d = block.draft
  const err = (path: string) => block.errors.get(`preferences.${path}`) ?? [...block.errors].find(([k]) => k.startsWith(`preferences.${path}.`))?.[1]
  const set = (change: Partial<Search>) => block.update((current) => ({ ...current, ...change }))
  const locations = d.locations ?? {}
  return (
    <Block title={t('blocks.search.title')} hint={t('blocks.search.hint')}>
      <TagsField label={t('fields.roles')} hint={t('fields.rolesHint')} value={d.roles} error={err('roles')} onChange={(v) => set({ roles: v })} />
      <ChoicesField
        label={t('fields.seniority')}
        value={d.seniority_target}
        error={err('seniority_target')}
        options={SENIORITIES.map((s) => ({ value: s, label: t(`seniority.${s}`) }))}
        onChange={(v) => set({ seniority_target: v })}
      />
      <div className="grid gap-4 sm:grid-cols-2">
        <TextField
          label={t('fields.maxYears')}
          hint={t('fields.maxYearsHint')}
          type="number"
          value={d.max_years_required == null ? '' : String(d.max_years_required)}
          error={err('max_years_required')}
          onChange={(v) => set({ max_years_required: num(v) })}
        />
        <TagsField
          label={t('fields.workLanguages')}
          hint={t('fields.workLanguagesHint')}
          value={d.languages_for_work}
          error={err('languages_for_work')}
          onChange={(v) => set({ languages_for_work: v.map((x) => x.toLowerCase()) })}
        />
      </div>
      <ChoicesField
        label={t('fields.remoteModes')}
        value={d.remote_modes}
        error={err('remote_modes')}
        options={REMOTE_MODES.map((m) => ({ value: m, label: t(`remote.${m}`) }))}
        onChange={(v) => set({ remote_modes: v })}
      />
      <div className="grid gap-4 sm:grid-cols-3">
        {(['preferred', 'allowed', 'excluded'] as const).map((kind) => (
          <TagsField
            key={kind}
            label={t(`fields.locations.${kind}`)}
            hint={t(`fields.locations.${kind}Hint`)}
            value={locations[kind]}
            onChange={(v) => set({ locations: { ...locations, [kind]: v } })}
          />
        ))}
      </div>
      <BlockActions block={block} />
    </Block>
  )
}

const readCv = (p: ProfileData): CvPreferences => prefs(p).cv
const writeCv = (d: CvPreferences, p: ProfileData) => ({ preferences: { ...prefs(p), cv: d } })

/** Plantilla por defecto, páginas, foto por país, indicaciones y lo que no quieres que diga. */
export function CvPreferencesBlock() {
  const { t } = useTranslation('profileEditor')
  const templates = useTemplates()
  const block = useBlockEditor('cv', readCv, writeCv)
  const d = block.draft
  const err = (path: string) => block.errors.get(`preferences.cv.${path}`)
  const set = (change: Partial<CvPreferences>) => block.update((current) => ({ ...current, ...change }))
  const byCountry = d.photo_policy.by_country ?? {}
  const options = [
    { value: '', label: t('fields.templateAuto') },
    ...(templates.data?.templates ?? []).map((tpl) => ({ value: tpl.id, label: tpl.name })),
  ]
  if (d.default_template && !options.some((o) => o.value === d.default_template)) {
    options.push({ value: d.default_template, label: d.default_template })
  }
  return (
    <Block title={t('blocks.cv.title')} hint={t('blocks.cv.hint')}>
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
        <TagsField
          label={t('fields.photoNo')}
          hint={t('fields.photoNoHint')}
          value={Object.entries(byCountry).filter(([, v]) => !v).map(([k]) => k)}
          error={[...block.errors].find(([k]) => k.startsWith('preferences.cv.photo_policy'))?.[1]}
          onChange={(v) =>
            set({
              photo_policy: {
                ...d.photo_policy,
                by_country: {
                  ...Object.fromEntries(Object.entries(byCountry).filter(([, on]) => on)),
                  ...Object.fromEntries(v.map((c) => [c.toUpperCase(), false])),
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
    <Block title={t('blocks.letter.title')} hint={t('blocks.letter.hint')}>
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
