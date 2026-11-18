/**
 * Preferencias de CV y carta. Son partes de la sección `preferences`: cada bloque cambia la suya y
 * guarda la sección entera con las demás tal cual. Lo que buscas se edita en «Buscar ofertas»
 * (`components/search/`).
 */
import { useTranslation } from 'react-i18next'
import { useTemplates } from '@/api/queries'
import { Block, BlockActions, CheckField, CodeTagsField, SelectField, TagsField, TextField } from './fields'
import { useBlockEditor } from './editor'
import type { CoverLetterPreferences, CvPreferences, Preferences, ProfileData } from './types'
import { useTemplateText } from '@/lib/templateText'

const prefs = (p: ProfileData): Preferences =>
  p.preferences ?? { roles: [], seniority_target: [], remote_modes: [], languages_for_work: [], cv: { photo_policy: { default: true } } }

const num = (value: string): number | null => (value.trim() === '' ? null : Number(value))

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
