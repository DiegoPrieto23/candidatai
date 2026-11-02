/**
 * Edición directa del texto de un CV, sin agente: guarda una versión nueva con el mismo diseño, sin
 * verificar. Solo textos; añadir, quitar o reordenar va por una corrección. Lo que el perfil no
 * respalde se avisa después de guardar, porque lo decide quien lo escribe.
 */
import { useState, type FormEvent } from 'react'
import { FloppyDiskIcon } from '@phosphor-icons/react'
import { useTranslation } from 'react-i18next'
import type { CvContent, CvView, EditWarning } from '@/api/client'
import { useEditCv } from '@/api/queries'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { errorMessage } from '@/lib/errors'

// Los límites de `CvContent`.
const MAX_SUBTITLE = 200
const MAX_SUMMARY = 1200
const MAX_BULLET = 400
const MAX_GROUP = 60

type Bullets = { text: string }[]

function BulletFields({
  title,
  bullets,
  onChange,
}: {
  title: string
  bullets: Bullets
  onChange: (index: number, text: string) => void
}) {
  const { t } = useTranslation('cv', { keyPrefix: 'edit' })
  return (
    <fieldset className="grid gap-2">
      <legend className="mb-1 text-sm font-medium">{title}</legend>
      {bullets.map((bullet, i) => (
        <Textarea
          key={i}
          aria-label={t('bulletAria', { title, position: i + 1 })}
          value={bullet.text}
          onChange={(e) => onChange(i, e.target.value)}
          maxLength={MAX_BULLET}
          rows={2}
        />
      ))}
    </fieldset>
  )
}

function Warnings({ warnings }: { warnings: EditWarning[] }) {
  const { t } = useTranslation('cv', { keyPrefix: 'edit' })
  return (
    <div role="status" className="rounded-md border border-warning-border bg-warning/40 px-3 py-2 text-sm">
      <p className="font-medium">{t('warningsTitle')}</p>
      <ul className="mt-1 list-disc space-y-0.5 pl-5">
        {warnings.map((warning, i) => (
          <li key={i} className="break-words">
            {t(`warning.${warning.code}`, { value: warning.value })}
          </li>
        ))}
      </ul>
    </div>
  )
}

function EditForm({ cv, jobId, onSaved }: { cv: CvView; jobId: number; onSaved: (warnings: EditWarning[]) => void }) {
  const { t } = useTranslation('cv', { keyPrefix: 'edit' })
  const edit = useEditCv(jobId)
  const [content, setContent] = useState<CvContent>(cv.content)
  const dirty = JSON.stringify(content) !== JSON.stringify(cv.content)
  const prefix = `cv-edit-${cv.document_id}`
  const labels = cv.labels
  const experience = content.experience
  const projects = content.projects
  const skills = content.skills

  const setExperience = (block: number, bullet: number, text: string) =>
    setContent({
      ...content,
      experience: experience.map((item, b) =>
        b === block
          ? { ...item, bullets: item.bullets.map((row, i) => (i === bullet ? { ...row, text } : row)) }
          : item,
      ),
    })
  const setProject = (block: number, bullet: number, text: string) =>
    setContent({
      ...content,
      projects: projects.map((item, b) =>
        b === block
          ? { ...item, bullets: item.bullets.map((row, i) => (i === bullet ? { ...row, text } : row)) }
          : item,
      ),
    })
  const setGroup = (block: number, group: string) =>
    setContent({ ...content, skills: skills.map((item, b) => (b === block ? { ...item, group } : item)) })
  const setSkill = (block: number, position: number, value: string) =>
    setContent({
      ...content,
      skills: skills.map((item, b) =>
        b === block ? { ...item, items: item.items.map((old, i) => (i === position ? value : old)) } : item,
      ),
    })

  const submit = (e: FormEvent) => {
    e.preventDefault()
    // Con la promesa, no con `onSuccess` de `mutate`: la versión nueva desmonta este formulario
    // (`key`) antes de que termine, y React Query descartaría ese callback. El error lo enseña `edit`.
    edit.mutateAsync({ base_document_id: cv.document_id, content }).then(
      (result) => onSaved(result.warnings),
      () => undefined,
    )
  }

  return (
    <form onSubmit={submit} aria-label={t('form')} className="space-y-5">
      <p className="text-xs text-muted-foreground">{t('hint')}</p>
      <div className="grid gap-1.5">
        <Label htmlFor={`${prefix}-subtitle`}>{t('subtitle')}</Label>
        <Input
          id={`${prefix}-subtitle`}
          value={content.subtitle}
          onChange={(e) => setContent({ ...content, subtitle: e.target.value })}
          maxLength={MAX_SUBTITLE}
        />
      </div>
      <div className="grid gap-1.5">
        <Label htmlFor={`${prefix}-summary`}>{t('summary')}</Label>
        <Textarea
          id={`${prefix}-summary`}
          value={content.summary}
          onChange={(e) => setContent({ ...content, summary: e.target.value })}
          maxLength={MAX_SUMMARY}
          rows={4}
        />
      </div>
      {experience.map((item, b) => (
        <BulletFields
          key={item.experience_id}
          title={labels[item.experience_id] ?? item.experience_id}
          bullets={item.bullets}
          onChange={(i, text) => setExperience(b, i, text)}
        />
      ))}
      {projects.map((item, b) => (
        <BulletFields
          key={item.project_id}
          title={labels[item.project_id] ?? item.project_id}
          bullets={item.bullets}
          onChange={(i, text) => setProject(b, i, text)}
        />
      ))}
      {skills.map((group, b) => (
        <fieldset key={b} className="grid gap-2">
          <legend className="mb-1 text-sm font-medium">{t('skillGroup', { position: b + 1 })}</legend>
          <Input
            aria-label={t('groupName', { position: b + 1 })}
            value={group.group}
            onChange={(e) => setGroup(b, e.target.value)}
            maxLength={MAX_GROUP}
          />
          <div className="grid gap-2 sm:grid-cols-2">
            {group.items.map((skill, i) => (
              <Input
                key={i}
                aria-label={t('skillAria', { group: group.group, position: i + 1 })}
                value={skill}
                onChange={(e) => setSkill(b, i, e.target.value)}
              />
            ))}
          </div>
        </fieldset>
      ))}
      {edit.error && (
        <p role="alert" className="text-sm text-destructive">
          {errorMessage(edit.error)}
        </p>
      )}
      <Button type="submit" disabled={!dirty || edit.isPending} className="active:translate-y-px">
        <FloppyDiskIcon />
        {edit.isPending ? t('saving') : t('save')}
      </Button>
    </form>
  )
}

export function CvInlineEditor({ cv, jobId }: { cv: CvView; jobId: number }) {
  const [warnings, setWarnings] = useState<EditWarning[]>([])
  return (
    <div className="space-y-4">
      {warnings.length > 0 && <Warnings warnings={warnings} />}
      {/* Con otra versión vigente, el formulario empieza de nuevo: no se edita sobre lo viejo. */}
      <EditForm key={cv.document_id} cv={cv} jobId={jobId} onSaved={setWarnings} />
    </div>
  )
}
