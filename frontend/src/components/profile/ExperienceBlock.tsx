import { useRef, useState } from 'react'
import { BuildingsIcon, PlusIcon } from '@phosphor-icons/react'
import { useTranslation } from 'react-i18next'
import { AgentButton } from '@/components/AgentButton'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { Block, BlockActions, CheckField, ItemControls, MonthField, TagsField, TextField } from './fields'
import { move, removeAt, replaceAt, useBlockEditor, useProfileState } from './editor'
import { FoldAllButton, FoldItem } from './fold'
import { PRESENT, skillNames, type Achievement, type Experience, type ProfileData } from './types'

/**
 * Una empresa (o un logro) del borrador. Los nuevos llevan `_key`, una clave local que no cambia
 * al reordenar y que no se guarda (fase 27.2).
 */
type DraftAchievement = Achievement & { _key?: string }
type DraftExperience = Experience & { _key?: string; achievements?: DraftAchievement[] }

const read = (p: ProfileData): DraftExperience[] => p.experience ?? []
const write = (d: DraftExperience[]) => ({
  experience: d.map(({ _key, ...exp }) => ({
    ...exp,
    achievements: exp.achievements?.map(({ _key: _achievementKey, ...ach }) => ach),
  })),
})

const EMPTY_EXPERIENCE: Experience = { company: '', role: '', start: '', end: 'present', achievements: [] }
const EMPTY_ACHIEVEMENT: Achievement = { text: '', skills: [] }


/**
 * Empresas y sus logros. Los ids los pone el servidor; los que ya existen no cambian.
 *
 * Fase 27.2: cada empresa arranca plegada (solo su cabecera) y se despliega pulsándola. Se abren
 * solas la que acabas de añadir y las que tienen un error de validación. El borrador vive en
 * `useBlockEditor`, así que plegar no pierde cambios.
 */
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

  const counter = useRef(0)
  const nextKey = () => {
    counter.current += 1
    return `new-${counter.current}`
  }
  // Al guardar, el borrador pasa a ser lo que devuelve el servidor: las empresas nuevas ya traen su
  // id y no su clave local. `aliases` (id → clave local) conserva la clave, así que la tarjeta no
  // se vuelve a montar ni se pliega. Guardar no reordena, así que se emparejan por posición.
  const [aliases, setAliases] = useState<ReadonlyMap<string, string>>(new Map())
  const [previous, setPrevious] = useState(list)
  if (previous !== list) {
    setPrevious(list)
    if (previous.length === list.length) {
      // Solo los ids que acaban de aparecer: reordenar también cambia lo que hay en cada posición.
      const known = new Set(previous.map((exp) => exp.id))
      const adopted = list.flatMap((exp, i) =>
        previous[i]._key && !exp._key && exp.id && !known.has(exp.id) ? [[exp.id, previous[i]._key!] as const] : [],
      )
      if (adopted.length > 0) setAliases((prev) => new Map([...prev, ...adopted]))
    }
  }
  /** La clave de una empresa: su clave local o su id. No cambia al reordenar ni al guardar. */
  const keyOf = (exp: DraftExperience, i: number) =>
    exp._key ?? (exp.id ? (aliases.get(exp.id) ?? exp.id) : `index-${i}`)

  const [expanded, setExpanded] = useState<ReadonlySet<string>>(new Set())
  const [focusKey, setFocusKey] = useState<string | null>(null)
  const toggle = (key: string, open: boolean) => {
    setFocusKey(null)
    setExpanded((prev) => {
      const next = new Set(prev)
      if (open) next.add(key)
      else next.delete(key)
      return next
    })
  }
  const add = () => {
    const key = nextKey()
    block.update((d) => [{ ...EMPTY_EXPERIENCE, _key: key }, ...d])
    setExpanded((prev) => new Set(prev).add(key))
    setFocusKey(key)
  }

  // Las empresas con un error en cualquier campo suyo (`experience.<i>…`) se despliegan al llegar
  // los errores, para que no queden escondidos. Se apuntan por su clave: los errores van por
  // posición y dejarían de cuadrar al reordenar.
  const [withErrors, setWithErrors] = useState<readonly string[]>([])
  const [seenErrors, setSeenErrors] = useState(block.errors)
  if (seenErrors !== block.errors) {
    setSeenErrors(block.errors)
    const paths = [...block.errors.keys()]
    const keys = list.flatMap((exp, i) =>
      paths.some((k) => k === `experience.${i}` || k.startsWith(`experience.${i}.`)) ? [keyOf(exp, i)] : [],
    )
    setWithErrors(keys)
    if (keys.length > 0) setExpanded((prev) => new Set([...prev, ...keys]))
  }
  const errorCount = list.filter((exp, i) => withErrors.includes(keyOf(exp, i))).length

  const allOpen = list.length > 0 && list.every((exp, i) => expanded.has(keyOf(exp, i)))
  const period = (exp: Experience) =>
    [exp.start, exp.end === PRESENT ? t('fields.present') : exp.end].filter(Boolean).join(' – ')

  return (
    <Block
      id="experience"
      title={t('blocks.experience.title')}
      hint={t('blocks.experience.hint')}
      actions={
        <div className="flex flex-wrap gap-2">
          {list.length > 0 && (
            <FoldAllButton
              allOpen={allOpen}
              onClick={() => {
                setFocusKey(null)
                setExpanded(allOpen ? new Set() : new Set(list.map(keyOf)))
              }}
            />
          )}
          <Button type="button" size="sm" variant="outline" onClick={add}>
            <PlusIcon /> {t('blocks.experience.add')}
          </Button>
        </div>
      }
    >
      {list.length === 0 && <p className="text-sm text-muted-foreground">{t('blocks.experience.empty')}</p>}
      {errorCount > 0 && <p className="text-sm text-destructive">{t('blocks.experience.errorsIn', { count: errorCount })}</p>}
      {/* Cada empresa, en su tarjeta con borde de color, sin esquinas redondeadas y separada de la siguiente. */}
      <div className="grid gap-6">
      {list.map((exp, i) => {
        const name = exp.company || t('blocks.experience.untitled')
        const path = `experience.${i}`
        const key = keyOf(exp, i)
        const open = expanded.has(key)
        const achievements = exp.achievements ?? []
        const summary = [period(exp), exp.city, t('blocks.experience.achievementCount', { count: achievements.length })]
          .filter(Boolean)
          .join(' · ')
        return (
          <FoldItem
            key={key}
            label={name}
            title={exp.role ? `${exp.role} · ${name}` : name}
            summary={summary}
            icon={<BuildingsIcon weight="duotone" />}
            open={open}
            onOpenChange={(value) => toggle(key, value)}
            controls={
              <ItemControls
                label={name}
                index={i}
                count={list.length}
                onMove={(delta) => block.update((d) => move(d, i, delta))}
                onRemove={() => block.update((d) => removeAt(d, i))}
              />
            }
          >
            <div className="grid gap-3 sm:grid-cols-2">
              <TextField
                label={t('fields.company')}
                value={exp.company}
                autoFocus={focusKey === key}
                error={err(`${path}.company`)}
                onChange={(v) => setItem(i, { company: v })}
              />
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
              {achievements.length > 0 && (
                // Logros separados por una línea fina, con su número y el fondo alterno.
                <div className="divide-y border">
                  {achievements.map((ach, j) => {
                    const apath = `${path}.achievements.${j}`
                    const ref = `${exp.id}/${ach.id}`
                    const label = ach.text || t('blocks.experience.newAchievement')
                    return (
                      <div
                        key={(ach._key as string | undefined) ?? ach.id ?? `index-${j}`}
                        role="group"
                        aria-label={label}
                        className={cn('grid gap-3 p-3', j % 2 === 0 ? 'bg-muted/25' : 'bg-muted')}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-xs font-medium text-muted-foreground">
                            {t('blocks.experience.achievementNumber', { number: j + 1 })}
                          </span>
                          <ItemControls
                            label={label}
                            index={j}
                            count={achievements.length}
                            onMove={(delta) => setItem(i, { achievements: move(achievements, j, delta) })}
                            onRemove={() => setItem(i, { achievements: removeAt(achievements, j) })}
                          />
                        </div>
                        <TextField
                          multiline
                          rows={2}
                          label={t('fields.achievement')}
                          hint={t('fields.achievementHint')}
                          value={ach.text}
                          error={err(`${apath}.text`)}
                          onChange={(v) => setAchievement(i, j, { text: v })}
                        />
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
                            <AgentButton action="improve-profile-item" profileItem={ref}>
                              {t('agent.improve')}
                            </AgentButton>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
              <Button
                type="button"
                size="sm"
                variant="ghost"
                className="justify-self-start"
                onClick={() => setItem(i, { achievements: [...achievements, { ...EMPTY_ACHIEVEMENT, _key: nextKey() }] })}
              >
                <PlusIcon /> {t('blocks.experience.addAchievement')}
              </Button>
            </div>
          </FoldItem>
        )
      })}
      </div>
      <BlockActions block={block} />
    </Block>
  )
}
