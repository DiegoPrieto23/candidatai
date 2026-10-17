import { useState } from 'react'
import { PlusIcon } from '@phosphor-icons/react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Block, BlockActions, ItemControls, SELECT, TagsField, TextField } from './fields'
import { move, removeAt, replaceAt, useBlockEditor } from './editor'
import { LANGUAGE_LEVELS, SKILL_LEVELS, type Language, type ProfileData, type Skill } from './types'

interface Draft {
  languages: Language[]
  skills: Skill[]
  basic_skills: string[]
}

const read = (p: ProfileData): Draft => ({ languages: p.languages ?? [], skills: p.skills ?? [], basic_skills: p.basic_skills ?? [] })
const write = (d: Draft) => ({ languages: d.languages, skills: d.skills, basic_skills: d.basic_skills })

const OTHER = '__other__'

/** Nivel de idioma: un desplegable (A1–C2, Nativo) que conserva un valor libre que ya tuvieras. */
function LanguageLevel({ value, onChange, error }: { value: string; onChange: (value: string) => void; error?: string }) {
  const { t } = useTranslation('profileEditor')
  const known = (LANGUAGE_LEVELS as readonly string[]).includes(value)
  const [other, setOther] = useState(!known && value !== '')
  return (
    <div className="grid content-start gap-1.5">
      <Label>
        {t('fields.level')}
        <select
          className={`${SELECT} mt-1.5 font-normal`}
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
      </Label>
      {other && <Input aria-label={t('fields.otherLevelText')} value={value} onChange={(e) => onChange(e.target.value)} />}
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  )
}

/** Idiomas, skills con su nivel privado y skills básicas. Cambiar skills recalcula los scores. */
export function SkillsBlock() {
  const { t } = useTranslation('profileEditor')
  const block = useBlockEditor('skills', read, write, { preview: true })
  const { languages, skills, basic_skills } = block.draft
  const err = (path: string) => block.errors.get(path)
  const setLanguage = (i: number, change: Partial<Language>) =>
    block.update((d) => ({ ...d, languages: replaceAt(d.languages, i, { ...d.languages[i], ...change }) }))
  const setSkill = (i: number, change: Partial<Skill>) =>
    block.update((d) => ({ ...d, skills: replaceAt(d.skills, i, { ...d.skills[i], ...change }) }))
  return (
    <Block title={t('blocks.skills.title')} hint={t('blocks.skills.hint')}>
      <div className="grid gap-2">
        <h3 className="text-sm font-medium">{t('blocks.skills.languages')}</h3>
        {languages.map((lang, i) => (
          <div key={`${i}-${lang.language}`} role="group" aria-label={lang.language || t('fields.language')} className="grid gap-3 rounded-md bg-muted/40 p-3 sm:grid-cols-[1fr_12rem_1fr_auto]">
            <TextField label={t('fields.language')} value={lang.language} error={err(`languages.${i}.language`)} onChange={(v) => setLanguage(i, { language: v })} />
            <LanguageLevel value={lang.level} error={err(`languages.${i}.level`)} onChange={(v) => setLanguage(i, { level: v })} />
            <TextField label={t('fields.regional')} hint={t('fields.regionalHint')} value={lang.regional} onChange={(v) => setLanguage(i, { regional: v })} />
            <ItemControls
              label={lang.language || t('fields.language')}
              index={i}
              count={languages.length}
              onMove={(delta) => block.update((d) => ({ ...d, languages: move(d.languages, i, delta) }))}
              onRemove={() => block.update((d) => ({ ...d, languages: removeAt(d.languages, i) }))}
            />
          </div>
        ))}
        <Button
          type="button"
          size="sm"
          variant="ghost"
          className="justify-self-start"
          onClick={() => block.update((d) => ({ ...d, languages: [...d.languages, { language: '', level: '' }] }))}
        >
          <PlusIcon /> {t('blocks.skills.addLanguage')}
        </Button>
      </div>
      <div className="grid gap-2">
        <h3 className="text-sm font-medium">{t('blocks.skills.skills')}</h3>
        <p className="text-xs text-muted-foreground">{t('blocks.skills.levels')}</p>
        {skills.map((skill, i) => (
          <div key={`${i}-${skill.name}`} role="group" aria-label={skill.name || t('fields.skill')} className="grid gap-3 rounded-md bg-muted/40 p-3 sm:grid-cols-[1fr_8rem_1fr_auto]">
            <TextField label={t('fields.skill')} value={skill.name} error={err(`skills.${i}.name`)} onChange={(v) => setSkill(i, { name: v })} />
            <Label className="grid content-start gap-1.5">
              {t('fields.level')}
              <select className={`${SELECT} font-normal`} value={skill.level} onChange={(e) => setSkill(i, { level: e.target.value as Skill['level'] })}>
                {SKILL_LEVELS.map((level) => (
                  <option key={level} value={level}>
                    {t(`levels.${level}`)}
                  </option>
                ))}
              </select>
            </Label>
            <TextField label={t('fields.category')} value={skill.category} onChange={(v) => setSkill(i, { category: v })} />
            <ItemControls
              label={skill.name || t('fields.skill')}
              index={i}
              count={skills.length}
              onMove={(delta) => block.update((d) => ({ ...d, skills: move(d.skills, i, delta) }))}
              onRemove={() => block.update((d) => ({ ...d, skills: removeAt(d.skills, i) }))}
            />
          </div>
        ))}
        <Button
          type="button"
          size="sm"
          variant="ghost"
          className="justify-self-start"
          onClick={() => block.update((d) => ({ ...d, skills: [...d.skills, { name: '', level: 'C' }] }))}
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
      <BlockActions block={block} />
    </Block>
  )
}
