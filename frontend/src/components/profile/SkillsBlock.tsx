import { useId, useState, type ReactNode } from 'react'
import { PlusIcon, XIcon } from '@phosphor-icons/react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Combobox } from '@/components/ui/combobox'
import { Input } from '@/components/ui/input'
import { ALL, CATEGORY_CHIPS_MAX, NO_CATEGORY, NO_FILTER, categoriesOf, countWith, isFiltered, matches, type SkillFilter } from '@/lib/skillFilters'
import { Block, BlockActions, FieldError, ItemControls, SELECT, TagsField } from './fields'
import { move, removeAt, replaceAt, useBlockEditor } from './editor'
import { LANGUAGE_LEVELS, SKILL_LEVELS, type Language, type ProfileData, type Skill } from './types'

interface Draft {
  skills: Skill[]
  basic_skills: string[]
}

const read = (p: ProfileData): Draft => ({ skills: p.skills ?? [], basic_skills: p.basic_skills ?? [] })
const write = (d: Draft) => ({ skills: d.skills, basic_skills: d.basic_skills })

const readLanguages = (p: ProfileData): Language[] => p.languages ?? []
const writeLanguages = (d: Language[]) => ({ languages: d })

const OTHER = '__other__'

/** Idioma, nivel y botones: una sola rejilla para la cabecera y las filas (cada fila, una subrejilla),
 *  así las columnas casan aunque una fila tenga «Otro (escríbelo)» abierto. */
const LANGUAGE_GRID = 'grid grid-cols-[minmax(0,1fr)_12rem_auto] gap-x-3 gap-y-1.5'
const LANGUAGE_ROW = 'col-span-full grid grid-cols-subgrid items-start'

/** Nivel de idioma: un desplegable (A1–C2, Nativo) que conserva un valor libre que ya tuvieras. */
function LanguageLevel({ value, onChange, error, errorId }: { value: string; onChange: (value: string) => void; error?: string; errorId: string }) {
  const { t } = useTranslation('profileEditor')
  const known = (LANGUAGE_LEVELS as readonly string[]).includes(value)
  const [other, setOther] = useState(!known && value !== '')
  return (
    <div className="grid content-start gap-1.5">
      <select
        aria-label={t('fields.level')}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : undefined}
        className={`${SELECT} font-normal`}
        value={other ? OTHER : known ? value : ''}
        onChange={(e) => {
          const picked = e.target.value
          setOther(picked === OTHER)
          if (picked !== OTHER) onChange(picked)
          else if (known) onChange('')
        }}
      >
        <option value="" disabled>
          {t('fields.choose')}
        </option>
        {LANGUAGE_LEVELS.map((level) => (
          <option key={level} value={level}>
            {level === 'Nativo' ? t('fields.native') : level}
          </option>
        ))}
        <option value={OTHER}>{t('fields.otherLevel')}</option>
      </select>
      {other && <Input aria-label={t('fields.otherLevelText')} value={value} onChange={(e) => onChange(e.target.value)} />}
      <FieldError id={errorId} error={error} />
    </div>
  )
}

function LanguageRow({
  lang,
  index,
  count,
  errors,
  onChange,
  onMove,
  onRemove,
}: {
  lang: Language
  index: number
  count: number
  errors: ReadonlyMap<string, string>
  onChange: (change: Partial<Language>) => void
  onMove: (delta: number) => void
  onRemove: () => void
}) {
  const { t } = useTranslation('profileEditor')
  const id = useId()
  const languageError = errors.get(`languages.${index}.language`)
  const label = lang.language || t('fields.language')
  return (
    <div role="group" aria-label={label} className={`${LANGUAGE_ROW} rounded-md bg-muted/40 p-2`}>
      <div className="grid content-start gap-1.5">
        <Input
          aria-label={t('fields.language')}
          aria-invalid={languageError ? true : undefined}
          aria-describedby={languageError ? `${id}-language` : undefined}
          value={lang.language}
          onChange={(e) => onChange({ language: e.target.value })}
        />
        <FieldError id={`${id}-language`} error={languageError} />
      </div>
      <LanguageLevel key={lang.language} value={lang.level} errorId={`${id}-level`} error={errors.get(`languages.${index}.level`)} onChange={(level) => onChange({ level })} />
      <ItemControls label={label} index={index} count={count} onMove={onMove} onRemove={onRemove} />
    </div>
  )
}

/** Idiomas con su nivel. Pueden cambiar el encaje con las ofertas que piden uno, así que se ve el diff.
 *  `regional` sigue en el YAML (lo usa el CV si está relleno), pero ya no se edita aquí. */
export function LanguagesBlock() {
  const { t } = useTranslation('profileEditor')
  const block = useBlockEditor('languages', readLanguages, writeLanguages, { preview: true })
  const languages = block.draft
  const setLanguage = (i: number, change: Partial<Language>) =>
    block.update((d) => replaceAt(d, i, { ...d[i], ...change }))
  return (
    <Block id="languages" title={t('blocks.languages.title')} hint={t('blocks.languages.hint')}>
      <div className={LANGUAGE_GRID}>
        {languages.length > 0 && (
          <div className={`${LANGUAGE_ROW} px-2 text-sm font-medium`} aria-hidden="true">
            <span>{t('fields.language')}</span>
            <span>{t('fields.level')}</span>
            <span />
          </div>
        )}
        {languages.map((lang, i) => (
          <LanguageRow
            // Por posición: con el nombre en la clave, la fila se montaba de nuevo (y perdía el foco) a cada letra.
            key={i}
            lang={lang}
            index={i}
            count={languages.length}
            errors={block.errors}
            onChange={(change) => setLanguage(i, change)}
            onMove={(delta) => block.update((d) => move(d, i, delta))}
            onRemove={() => block.update((d) => removeAt(d, i))}
          />
        ))}
        <Button
          type="button"
          size="sm"
          variant="ghost"
          className="col-span-full justify-self-start"
          onClick={() => block.update((d) => [...d, { language: '', level: '' }])}
        >
          <PlusIcon /> {t('blocks.languages.add')}
        </Button>
      </div>
      <BlockActions block={block} />
    </Block>
  )
}

/** Una skill en una sola línea: con muchas, la lista tiene que caber sin tanto scroll. */
function SkillRow({
  skill,
  error,
  index,
  count,
  canMove,
  onChange,
  onMove,
  onRemove,
}: {
  skill: Skill
  error?: string
  index: number
  count: number
  canMove: boolean
  onChange: (change: Partial<Skill>) => void
  onMove: (delta: number) => void
  onRemove: () => void
}) {
  const { t } = useTranslation('profileEditor')
  const label = skill.name || t('fields.skill')
  return (
    <div role="group" aria-label={label} className="grid gap-1 rounded-md bg-muted/40 px-2 py-1">
      <div className="grid grid-cols-[minmax(0,1.4fr)_4.25rem_minmax(0,1fr)_auto] items-center gap-1.5">
        <Input
          aria-label={t('fields.skill')}
          aria-invalid={Boolean(error)}
          className="h-8 px-2"
          value={skill.name}
          onChange={(e) => onChange({ name: e.target.value })}
        />
        <select
          aria-label={t('fields.level')}
          title={t(`levels.${skill.level}`)}
          className={`${SELECT} h-8 px-1.5 font-normal`}
          value={skill.level}
          onChange={(e) => onChange({ level: e.target.value as Skill['level'] })}
        >
          {SKILL_LEVELS.map((level) => (
            <option key={level} value={level} title={t(`levels.${level}`)}>
              {level}
            </option>
          ))}
        </select>
        <Input
          aria-label={t('fields.category')}
          placeholder={t('fields.category')}
          className="h-8 px-2"
          value={skill.category ?? ''}
          onChange={(e) => onChange({ category: e.target.value })}
        />
        <ItemControls label={label} index={index} count={canMove ? count : 1} onMove={onMove} onRemove={onRemove} />
      </div>
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  )
}

/** Un chip de filtro con su recuento; si dejaría la lista vacía, atenuado (salvo el elegido). */
function FilterChip({ label, title, count, active, onClick }: { label: string; title?: string; count: number; active: boolean; onClick: () => void }) {
  return (
    <Button
      type="button"
      size="sm"
      variant={active ? 'default' : 'outline'}
      aria-pressed={active}
      title={title}
      disabled={count === 0 && !active}
      onClick={onClick}
    >
      {label}
      <span className="tabular text-xs opacity-70">{count}</span>
    </Button>
  )
}

/** Sin `label`, no es un grupo: el desplegable ya lleva su nombre y no hace falta repetirlo. */
function FilterRow({ heading, label, children }: { heading: string; label?: string; children: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
      <span className="w-20 shrink-0 text-xs text-muted-foreground" aria-hidden="true">
        {heading}
      </span>
      <div role={label ? 'group' : undefined} aria-label={label} className="flex flex-wrap items-center gap-1">
        {children}
      </div>
    </div>
  )
}

/** Skills con su nivel privado y skills básicas. Cambiarlas recalcula los scores. */
export function SkillsBlock() {
  const { t } = useTranslation('profileEditor')
  const block = useBlockEditor('skills', read, write, { preview: true })
  const { skills, basic_skills } = block.draft
  const [filter, setChosen] = useState<SkillFilter>(NO_FILTER)
  // Cómo se llamaba la categoría elegida: si la renombras o la vacías, el filtro sigue (a 0) hasta que lo cambies.
  const [chosenLabel, setChosenLabel] = useState('')
  // Las filas que editas con un filtro puesto siguen a la vista aunque ya no casen (p. ej. al
  // cambiarles el nivel), para que no desaparezcan mientras escribes. Se olvidan al cambiar el filtro.
  const [kept, setKept] = useState<ReadonlySet<number>>(new Set())
  const present = categoriesOf(skills)
  const categories =
    filter.category === ALL || present.some((c) => c.key === filter.category)
      ? present
      : [...present, { key: filter.category, label: chosenLabel }]
  const filtered = isFiltered(filter)
  const setFilter = (next: SkillFilter) => {
    setChosen(next)
    setChosenLabel(categories.find((c) => c.key === next.category)?.label ?? '')
    setKept(new Set())
  }
  // Descartar devuelve otra lista: los índices de `kept` ya no serían los de las filas que tocaste.
  const actions = {
    ...block,
    discard: () => {
      setKept(new Set())
      block.discard()
    },
  }
  const err = (path: string) => block.errors.get(path)
  const setSkill = (i: number, change: Partial<Skill>) => {
    if (filtered && !kept.has(i)) setKept(new Set(kept).add(i))
    block.update((d) => ({ ...d, skills: replaceAt(d.skills, i, { ...d.skills[i], ...change }) }))
  }
  const removeSkill = (i: number) => {
    // Los índices de detrás se corren uno.
    setKept(new Set([...kept].filter((k) => k !== i).map((k) => (k > i ? k - 1 : k))))
    block.update((d) => ({ ...d, skills: removeAt(d.skills, i) }))
  }
  const shown = skills.flatMap((skill, index) => (matches(skill, filter) || kept.has(index) ? [{ skill, index }] : []))
  const categoryName = (key: string, label: string) => (key === NO_CATEGORY ? t('blocks.skills.noCategory') : label)
  const levelCount = (level: string) => countWith(skills, { ...filter, level })
  const categoryCount = (category: string) => countWith(skills, { ...filter, category })
  return (
    <Block id="skills" title={t('blocks.skills.title')} hint={t('blocks.skills.hint')}>
      <div className="grid gap-2">
        <p className="text-xs text-muted-foreground">{t('blocks.skills.levels')}</p>
        <div className="grid gap-1.5">
          <FilterRow heading={t('blocks.skills.levelHeading')} label={t('blocks.skills.filterLabel')}>
            {[ALL, ...SKILL_LEVELS].map((level) => (
              <FilterChip
                key={level}
                label={level === ALL ? t('blocks.skills.all') : level}
                title={level === ALL ? undefined : t(`levels.${level as Skill['level']}`)}
                count={levelCount(level)}
                active={filter.level === level}
                onClick={() => setFilter({ ...filter, level })}
              />
            ))}
          </FilterRow>
          {categories.length > 0 && (
            <FilterRow
              heading={t('blocks.skills.categoryHeading')}
              label={categories.length > CATEGORY_CHIPS_MAX ? undefined : t('blocks.skills.categoryFilterLabel')}
            >
              {categories.length > CATEGORY_CHIPS_MAX ? (
                <Combobox
                  className="w-64"
                  value={filter.category}
                  onChange={(category) => setFilter({ ...filter, category })}
                  label={t('blocks.skills.categoryFilterLabel')}
                  aria-label={t('blocks.skills.categoryFilterLabel')}
                  placeholder={t('blocks.skills.allCategories')}
                  searchLabel={t('blocks.skills.searchCategory')}
                  noMatch={(query) => t('blocks.skills.noCategoryMatch', { query })}
                  options={[
                    { value: ALL, label: t('blocks.skills.allCategories'), meta: String(categoryCount(ALL)) },
                    ...categories.map((c) => {
                      const count = categoryCount(c.key)
                      return {
                        value: c.key,
                        label: categoryName(c.key, c.label),
                        meta: String(count),
                        disabled: count === 0 && filter.category !== c.key,
                      }
                    }),
                  ]}
                />
              ) : (
                [{ key: ALL, label: t('blocks.skills.all') }, ...categories].map((c) => (
                  <FilterChip
                    key={c.key}
                    label={c.key === ALL ? c.label : categoryName(c.key, c.label)}
                    count={categoryCount(c.key)}
                    active={filter.category === c.key}
                    onClick={() => setFilter({ ...filter, category: c.key })}
                  />
                ))
              )}
            </FilterRow>
          )}
          {filtered && (
            <Button type="button" size="sm" variant="ghost" className="justify-self-start" onClick={() => setFilter(NO_FILTER)}>
              <XIcon /> {t('blocks.skills.clearFilters')}
            </Button>
          )}
        </div>
        {shown.length === 0 && skills.length > 0 && <p className="py-2 text-sm text-muted-foreground">{t('blocks.skills.noneMatch')}</p>}
        <div className="grid gap-1 2xl:grid-cols-2">
          {shown.map(({ skill, index }) => (
            <SkillRow
              key={index}
              skill={skill}
              index={index}
              count={skills.length}
              canMove={!filtered}
              error={err(`skills.${index}.name`)}
              onChange={(change) => setSkill(index, change)}
              onMove={(delta) => block.update((d) => ({ ...d, skills: move(d.skills, index, delta) }))}
              onRemove={() => removeSkill(index)}
            />
          ))}
        </div>
        {filtered && shown.length > 1 && <p className="text-xs text-muted-foreground">{t('blocks.skills.reorderHint')}</p>}
        <Button
          type="button"
          size="sm"
          variant="ghost"
          className="justify-self-start"
          onClick={() => {
            // Una nueva nace en C y sin categoría: con un filtro puesto, desaparecería nada más añadirla.
            setFilter(NO_FILTER)
            block.update((d) => ({ ...d, skills: [...d.skills, { name: '', level: 'C' }] }))
          }}
        >
          <PlusIcon /> {t('blocks.skills.addSkill')}
        </Button>
      </div>
      <TagsField
        label={t('fields.basicSkills')}
        hint={t('fields.basicSkillsHint')}
        value={basic_skills}
        error={[...block.errors].find(([k]) => k.startsWith('basic_skills'))?.[1]}
        onChange={(v) => block.update((d) => ({ ...d, basic_skills: v }))}
      />
      <BlockActions block={actions} />
    </Block>
  )
}
