/** Proyectos, formación, certificaciones y secciones extra (fase 25.7b): listas con el mismo patrón. */
import { PlusIcon } from '@phosphor-icons/react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Block, BlockActions, CheckField, ItemControls, MonthField, TagsField, TextField } from './fields'
import { move, removeAt, replaceAt, useBlockEditor, useProfileState, type BlockEditor } from './editor'
import { skillNames, type Certification, type Education, type ExtraItem, type ExtraSection, type ProfileData, type Project } from './types'

function AddButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <Button type="button" size="sm" variant="outline" onClick={onClick}>
      <PlusIcon /> {label}
    </Button>
  )
}

function Item<T>({
  block,
  index,
  label,
  children,
}: {
  block: BlockEditor<T[]>
  index: number
  label: string
  children: React.ReactNode
}) {
  return (
    <article aria-label={label} className="grid gap-3 rounded-lg border p-3">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-medium">{label}</h3>
        <ItemControls
          label={label}
          index={index}
          count={block.draft.length}
          onMove={(delta) => block.update((d) => move(d, index, delta))}
          onRemove={() => block.update((d) => removeAt(d, index))}
        />
      </div>
      <div className="grid gap-3 sm:grid-cols-2">{children}</div>
    </article>
  )
}

const readProjects = (p: ProfileData): Project[] => p.projects ?? []
const writeProjects = (d: Project[]) => ({ projects: d })

export function ProjectsBlock() {
  const { t } = useTranslation('profileEditor')
  const { profile } = useProfileState()
  const block = useBlockEditor('projects', readProjects, writeProjects)
  const err = (path: string) => block.errors.get(path)
  const set = (i: number, change: Partial<Project>) => block.update((d) => replaceAt(d, i, { ...d[i], ...change }))
  return (
    <Block
      title={t('blocks.projects.title')}
      hint={t('blocks.projects.hint')}
      actions={<AddButton label={t('blocks.projects.add')} onClick={() => block.update((d) => [...d, { name: '', text: '', skills: [] }])} />}
    >
      {block.draft.map((prj, i) => (
        <Item key={prj.id ?? `new-${i}`} block={block} index={i} label={prj.name || t('blocks.projects.untitled')}>
          <TextField label={t('fields.projectName')} value={prj.name} error={err(`projects.${i}.name`)} onChange={(v) => set(i, { name: v })} />
          <MonthField label={t('fields.date')} value={prj.date} error={err(`projects.${i}.date`)} onChange={(v) => set(i, { date: v })} />
          <TextField className="sm:col-span-2" multiline label={t('fields.description')} value={prj.text} error={err(`projects.${i}.text`)} onChange={(v) => set(i, { text: v })} />
          <TextField label={t('fields.url')} type="url" value={prj.url} error={err(`projects.${i}.url`)} onChange={(v) => set(i, { url: v })} />
          <TextField label={t('fields.source')} type="url" value={prj.source} error={err(`projects.${i}.source`)} onChange={(v) => set(i, { source: v })} />
          <TagsField
            className="sm:col-span-2"
            label={t('fields.skills')}
            hint={t('fields.skillsHint')}
            value={prj.skills}
            suggestions={skillNames(profile)}
            error={[...block.errors].find(([k]) => k.startsWith(`projects.${i}.skills`))?.[1]}
            onChange={(v) => set(i, { skills: v })}
          />
          <CheckField label={t('fields.nda')} checked={Boolean(prj.nda)} onChange={(v) => set(i, { nda: v })} />
        </Item>
      ))}
      <BlockActions block={block} />
    </Block>
  )
}

const readEducation = (p: ProfileData): Education[] => p.education ?? []
const writeEducation = (d: Education[]) => ({ education: d })

export function EducationBlock() {
  const { t } = useTranslation('profileEditor')
  const block = useBlockEditor('education', readEducation, writeEducation)
  const err = (path: string) => block.errors.get(path)
  const set = (i: number, change: Partial<Education>) => block.update((d) => replaceAt(d, i, { ...d[i], ...change }))
  return (
    <Block
      title={t('blocks.education.title')}
      actions={<AddButton label={t('blocks.education.add')} onClick={() => block.update((d) => [...d, { title: '', center: '' }])} />}
    >
      {block.draft.map((edu, i) => (
        <Item key={edu.id ?? `new-${i}`} block={block} index={i} label={edu.title || t('blocks.education.untitled')}>
          <TextField label={t('fields.degree')} value={edu.title} error={err(`education.${i}.title`)} onChange={(v) => set(i, { title: v })} />
          <TextField label={t('fields.center')} value={edu.center} error={err(`education.${i}.center`)} onChange={(v) => set(i, { center: v })} />
          <MonthField label={t('fields.start')} value={edu.start} error={err(`education.${i}.start`)} onChange={(v) => set(i, { start: v })} />
          <MonthField label={t('fields.end')} allowPresent value={edu.end} error={err(`education.${i}.end`) ?? err(`education.${i}`)} onChange={(v) => set(i, { end: v })} />
        </Item>
      ))}
      <BlockActions block={block} />
    </Block>
  )
}

const readCertifications = (p: ProfileData): Certification[] => p.certifications ?? []
const writeCertifications = (d: Certification[]) => ({ certifications: d })

export function CertificationsBlock() {
  const { t } = useTranslation('profileEditor')
  const block = useBlockEditor('certifications', readCertifications, writeCertifications)
  const err = (path: string) => block.errors.get(path)
  const set = (i: number, change: Partial<Certification>) => block.update((d) => replaceAt(d, i, { ...d[i], ...change }))
  return (
    <Block
      title={t('blocks.certifications.title')}
      actions={<AddButton label={t('blocks.certifications.add')} onClick={() => block.update((d) => [...d, { name: '' }])} />}
    >
      {block.draft.map((cert, i) => (
        <Item key={cert.id ?? `new-${i}`} block={block} index={i} label={cert.name || t('blocks.certifications.untitled')}>
          <TextField label={t('fields.certName')} value={cert.name} error={err(`certifications.${i}.name`)} onChange={(v) => set(i, { name: v })} />
          <TextField label={t('fields.issuer')} value={cert.issuer} onChange={(v) => set(i, { issuer: v })} />
          <MonthField label={t('fields.date')} value={cert.date} error={err(`certifications.${i}.date`)} onChange={(v) => set(i, { date: v })} />
          <TextField label={t('fields.verifyUrl')} type="url" value={cert.source} error={err(`certifications.${i}.source`)} onChange={(v) => set(i, { source: v })} />
        </Item>
      ))}
      <BlockActions block={block} />
    </Block>
  )
}

const readExtras = (p: ProfileData): ExtraSection[] => p.extra_sections ?? []
const writeExtras = (d: ExtraSection[]) => ({ extra_sections: d })

export function ExtraSectionsBlock() {
  const { t } = useTranslation('profileEditor')
  const block = useBlockEditor('extra_sections', readExtras, writeExtras)
  const err = (path: string) => block.errors.get(path)
  const set = (i: number, change: Partial<ExtraSection>) => block.update((d) => replaceAt(d, i, { ...d[i], ...change }))
  const setItem = (i: number, j: number, change: Partial<ExtraItem>) =>
    block.update((d) => replaceAt(d, i, { ...d[i], items: replaceAt(d[i].items, j, { ...d[i].items[j], ...change }) }))
  return (
    <Block
      title={t('blocks.extra.title')}
      hint={t('blocks.extra.hint')}
      actions={
        <AddButton label={t('blocks.extra.add')} onClick={() => block.update((d) => [...d, { title: { es: '', en: '' }, items: [{ text: '' }] }])} />
      }
    >
      {block.draft.map((sec, i) => (
        <Item key={sec.id ?? `new-${i}`} block={block} index={i} label={sec.title.es || sec.title.en || t('blocks.extra.untitled')}>
          <TextField label={t('fields.titleEs')} value={sec.title.es} error={err(`extra_sections.${i}.title`)} onChange={(v) => set(i, { title: { ...sec.title, es: v } })} />
          <TextField label={t('fields.titleEn')} value={sec.title.en} onChange={(v) => set(i, { title: { ...sec.title, en: v } })} />
          {sec.items.map((item, j) => (
            <div key={item.id ?? `new-${j}`} className="grid gap-3 rounded-md bg-muted/40 p-3 sm:col-span-2 sm:grid-cols-[1fr_auto_auto]">
              <TextField label={t('fields.item')} value={item.text} error={err(`extra_sections.${i}.items.${j}.text`)} onChange={(v) => setItem(i, j, { text: v })} />
              <MonthField label={t('fields.date')} value={item.date} onChange={(v) => setItem(i, j, { date: v })} />
              <ItemControls
                label={item.text || t('fields.item')}
                index={j}
                count={sec.items.length}
                onMove={(delta) => set(i, { items: move(sec.items, j, delta) })}
                onRemove={() => set(i, { items: removeAt(sec.items, j) })}
              />
            </div>
          ))}
          <Button type="button" size="sm" variant="ghost" className="justify-self-start" onClick={() => set(i, { items: [...sec.items, { text: '' }] })}>
            <PlusIcon /> {t('blocks.extra.addItem')}
          </Button>
        </Item>
      ))}
      <BlockActions block={block} />
    </Block>
  )
}
