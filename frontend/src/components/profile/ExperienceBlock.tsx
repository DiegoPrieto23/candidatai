import { PlusIcon } from '@phosphor-icons/react'
import { useTranslation } from 'react-i18next'
import { AgentButton } from '@/components/AgentButton'
import { Button } from '@/components/ui/button'
import { Block, BlockActions, CheckField, ItemControls, MonthField, TagsField, TextField } from './fields'
import { move, removeAt, replaceAt, useBlockEditor, useProfileState } from './editor'
import { skillNames, type Achievement, type Experience, type ProfileData } from './types'

const read = (p: ProfileData): Experience[] => p.experience ?? []
const write = (d: Experience[]) => ({ experience: d })

const EMPTY_EXPERIENCE: Experience = { company: '', role: '', start: '', end: 'present', achievements: [] }
const EMPTY_ACHIEVEMENT: Achievement = { text: '', skills: [] }

/** Empresas y sus logros. Los ids los pone el servidor; los que ya existen no cambian. */
export function ExperienceBlock() {
  const { t } = useTranslation('profileEditor')
  const { profile } = useProfileState()
  const block = useBlockEditor('experience', read, write)
  const list = block.draft
  const err = (path: string) => block.errors.get(path)
  const saved = new Set(
    (profile.experience ?? []).flatMap((e) => (e.achievements ?? []).map((a) => `${e.id}/${a.id}`)),
  )
  const suggestions = skillNames(profile)
  const setItem = (i: number, change: Partial<Experience>) => block.update((d) => replaceAt(d, i, { ...d[i], ...change }))
  const setAchievement = (i: number, j: number, change: Partial<Achievement>) =>
    block.update((d) => {
      const achievements = d[i].achievements ?? []
      return replaceAt(d, i, { ...d[i], achievements: replaceAt(achievements, j, { ...achievements[j], ...change }) })
    })

  return (
    <Block
      title={t('blocks.experience.title')}
      hint={t('blocks.experience.hint')}
      actions={
        <Button type="button" size="sm" variant="outline" onClick={() => block.update((d) => [{ ...EMPTY_EXPERIENCE }, ...d])}>
          <PlusIcon /> {t('blocks.experience.add')}
        </Button>
      }
    >
      {list.length === 0 && <p className="text-sm text-muted-foreground">{t('blocks.experience.empty')}</p>}
      {list.map((exp, i) => {
        const name = exp.company || t('blocks.experience.untitled')
        const path = `experience.${i}`
        return (
          <article key={exp.id ?? `new-${i}`} aria-label={name} className="grid gap-3 rounded-lg border p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-sm font-medium">
                {exp.role ? `${exp.role} · ${name}` : name}
              </h3>
              <ItemControls
                label={name}
                index={i}
                count={list.length}
                onMove={(delta) => block.update((d) => move(d, i, delta))}
                onRemove={() => block.update((d) => removeAt(d, i))}
              />
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <TextField label={t('fields.company')} value={exp.company} error={err(`${path}.company`)} onChange={(v) => setItem(i, { company: v })} />
              <TextField label={t('fields.role')} value={exp.role} error={err(`${path}.role`)} onChange={(v) => setItem(i, { role: v })} />
              <TextField label={t('fields.city')} value={exp.city} error={err(`${path}.city`)} onChange={(v) => setItem(i, { city: v })} />
              <div className="grid grid-cols-2 gap-3">
                <MonthField label={t('fields.start')} value={exp.start} error={err(`${path}.start`) ?? err(path)} onChange={(v) => setItem(i, { start: v })} />
                <MonthField label={t('fields.end')} allowPresent value={exp.end} error={err(`${path}.end`)} onChange={(v) => setItem(i, { end: v })} />
              </div>
              <TextField
                className="sm:col-span-2"
                multiline
                rows={2}
                label={t('fields.context')}
                hint={t('fields.contextHint')}
                value={exp.context}
                onChange={(v) => setItem(i, { context: v })}
              />
            </div>
            <div className="grid gap-2">
              <h4 className="text-sm font-medium">{t('blocks.experience.achievements')}</h4>
              {(exp.achievements ?? []).map((ach, j) => {
                const apath = `${path}.achievements.${j}`
                const ref = `${exp.id}/${ach.id}`
                const label = ach.text || t('blocks.experience.newAchievement')
                return (
                  <div key={ach.id ?? `new-${j}`} role="group" aria-label={label} className="grid gap-3 rounded-md bg-muted/40 p-3">
                    <div className="flex items-start justify-between gap-2">
                      <TextField
                        className="flex-1"
                        multiline
                        rows={2}
                        label={t('fields.achievement')}
                        hint={t('fields.achievementHint')}
                        value={ach.text}
                        error={err(`${apath}.text`)}
                        onChange={(v) => setAchievement(i, j, { text: v })}
                      />
                      <ItemControls
                        label={label}
                        index={j}
                        count={(exp.achievements ?? []).length}
                        onMove={(delta) => setItem(i, { achievements: move(exp.achievements ?? [], j, delta) })}
                        onRemove={() => setItem(i, { achievements: removeAt(exp.achievements ?? [], j) })}
                      />
                    </div>
                    <div className="grid gap-3 sm:grid-cols-2">
                      <TextField
                        label={t('fields.metrics')}
                        hint={t('fields.metricsHint')}
                        value={ach.metrics}
                        onChange={(v) => setAchievement(i, j, { metrics: v })}
                      />
                      <TextField
                        label={t('fields.source')}
                        hint={t('fields.sourceHint')}
                        type="url"
                        value={ach.source}
                        error={err(`${apath}.source`)}
                        onChange={(v) => setAchievement(i, j, { source: v })}
                      />
                      <TagsField
                        className="sm:col-span-2"
                        label={t('fields.skills')}
                        hint={t('fields.skillsHint')}
                        value={ach.skills}
                        suggestions={suggestions}
                        error={[...block.errors].find(([k]) => k.startsWith(`${apath}.skills`))?.[1]}
                        onChange={(v) => setAchievement(i, j, { skills: v })}
                      />
                    </div>
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <CheckField label={t('fields.nda')} checked={Boolean(ach.nda)} onChange={(v) => setAchievement(i, j, { nda: v })} />
                      {saved.has(ref) && (
                        <AgentButton action="improve-profile-item" profileItem={ref} variant="ghost">
                          {t('agent.improve')}
                        </AgentButton>
                      )}
                    </div>
                  </div>
                )
              })}
              <Button
                type="button"
                size="sm"
                variant="ghost"
                className="justify-self-start"
                onClick={() => setItem(i, { achievements: [...(exp.achievements ?? []), { ...EMPTY_ACHIEVEMENT }] })}
              >
                <PlusIcon /> {t('blocks.experience.addAchievement')}
              </Button>
            </div>
          </article>
        )
      })}
      <BlockActions block={block} />
    </Block>
  )
}
