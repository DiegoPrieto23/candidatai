import { PlusIcon } from '@phosphor-icons/react'
import { useTranslation } from 'react-i18next'
import { AgentButton } from '@/components/AgentButton'
import { Button } from '@/components/ui/button'
import { Block, BlockActions, ItemControls, TextField } from './fields'
import { move, removeAt, replaceAt, useBlockEditor, useProfileState } from './editor'
import { evidenceOptions, type ProfileData, type Story } from './types'

const read = (p: ProfileData): Story[] => p.stories ?? []
const write = (d: Story[]) => ({ stories: d })

const STAR = ['situation', 'task', 'action', 'result'] as const
const EMPTY: Story = { title: '', situation: '', task: '', action: '', result: '', evidence: [] }

/** Historias STAR: cada una cita al menos un logro o proyecto del perfil (sin eso no se guarda). */
export function StoriesBlock() {
  const { t } = useTranslation('profileEditor')
  const { profile } = useProfileState()
  const block = useBlockEditor('stories', read, write)
  const options = evidenceOptions(profile)
  const savedIds = new Set((profile.stories ?? []).map((s) => s.id))
  const missingEvidence = block.draft.some((s) => s.evidence.length === 0)
  const err = (path: string) => block.errors.get(path)
  const set = (i: number, change: Partial<Story>) => block.update((d) => replaceAt(d, i, { ...d[i], ...change }))
  return (
    <Block
      title={t('blocks.stories.title')}
      hint={t('blocks.stories.hint')}
      actions={
        <div className="flex flex-wrap gap-2">
          <AgentButton action="propose-stories">{t('agent.propose')}</AgentButton>
          <Button type="button" size="sm" variant="outline" onClick={() => block.update((d) => [...d, { ...EMPTY }])}>
            <PlusIcon /> {t('blocks.stories.add')}
          </Button>
        </div>
      }
    >
      {block.draft.map((story, i) => {
        const label = story.title || t('blocks.stories.untitled')
        const path = `stories.${i}`
        return (
          <article key={story.id ?? `new-${i}`} aria-label={label} className="grid gap-3 rounded-lg border p-3">
            <div className="flex items-center justify-between gap-2">
              <TextField className="flex-1" label={t('fields.storyTitle')} value={story.title} error={err(`${path}.title`)} onChange={(v) => set(i, { title: v })} />
              <ItemControls
                label={label}
                index={i}
                count={block.draft.length}
                onMove={(delta) => block.update((d) => move(d, i, delta))}
                onRemove={() => block.update((d) => removeAt(d, i))}
              />
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              {STAR.map((part) => (
                <TextField
                  key={part}
                  multiline
                  rows={3}
                  label={t(`star.${part}.label`)}
                  hint={t(`star.${part}.hint`)}
                  value={story[part]}
                  error={err(`${path}.${part}`)}
                  onChange={(v) => set(i, { [part]: v })}
                />
              ))}
            </div>
            <fieldset className="grid gap-1.5">
              <legend className="mb-1 text-sm font-medium">{t('fields.evidence')}</legend>
              <p className="text-xs text-muted-foreground">{t('fields.evidenceHint')}</p>
              {options.length === 0 && <p className="text-sm text-muted-foreground">{t('fields.noEvidence')}</p>}
              <div className="grid max-h-56 gap-1 overflow-auto rounded-md border p-2">
                {options.map((o) => (
                  <label key={o.ref} className="flex items-start gap-2 text-sm">
                    <input
                      type="checkbox"
                      className="mt-1"
                      checked={story.evidence.includes(o.ref)}
                      onChange={(e) =>
                        set(i, { evidence: e.target.checked ? [...story.evidence, o.ref] : story.evidence.filter((r) => r !== o.ref) })
                      }
                    />
                    <span>
                      {o.label}
                      <span className="ml-1.5 text-xs text-muted-foreground">
                        {['projects', 'education', 'certifications'].includes(o.group) ? t(`groups.${o.group as 'projects'}`) : o.group}
                      </span>
                    </span>
                  </label>
                ))}
              </div>
              {(story.evidence.length === 0 || err(`${path}.evidence`)) && (
                <p className="text-xs text-destructive">{err(`${path}.evidence`) ?? t('fields.evidenceRequired')}</p>
              )}
            </fieldset>
            {story.id && savedIds.has(story.id) && (
              <AgentButton action="improve-profile-item" profileItem={story.id} className="justify-self-start">
                {t('agent.improve')}
              </AgentButton>
            )}
          </article>
        )
      })}
      {missingEvidence && <p className="text-sm text-muted-foreground">{t('blocks.stories.needEvidence')}</p>}
      <BlockActions block={block} blocked={missingEvidence} />
    </Block>
  )
}

