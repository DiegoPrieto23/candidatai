/**
 * Edición directa del CV, sin agente: guarda una versión nueva con el mismo diseño, sin verificar.
 * Se cambian textos, se quitan o reordenan logros y se organizan las skills en grupos; añadir un logro
 * va por una corrección, porque necesita su evidencia del perfil. Lo que el perfil no respalde se
 * avisa después de guardar, porque lo decide quien lo escribe.
 */
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent, type ReactNode } from 'react'
import { ArrowDownIcon, ArrowUpIcon, FloppyDiskIcon, PlusIcon, TrashIcon, XIcon } from '@phosphor-icons/react'
import { useTranslation } from 'react-i18next'
import type { CvContent, CvView, EditWarning } from '@/api/client'
import { useEditCv } from '@/api/queries'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { errorMessage } from '@/lib/errors'
import { BusyLabel } from '@/components/StableLabel'

// Los límites de `CvContent`.
const MAX_SUBTITLE = 200
const MAX_SUMMARY = 1200
const MAX_BULLET = 400
const MAX_GROUP = 60
const MAX_SKILLS = 20

type Bullet = CvContent['experience'][number]['bullets'][number]
type Group = CvContent['skills'][number]
/** Un grupo con su clave: al reordenar o quitar, cada uno conserva lo que se está escribiendo. */
type KeyedGroup = Group & { key: number }

/** Mueve el elemento `from` una posición arriba (-1) o abajo (+1). */
function move<T>(list: T[], from: number, step: -1 | 1): T[] {
  const to = from + step
  if (to < 0 || to >= list.length) return list
  const next = [...list]
  ;[next[from], next[to]] = [next[to], next[from]]
  return next
}

// El mismo criterio que el servidor.
const sameSkill = (a: string, b: string) => a.trim().toLowerCase() === b.trim().toLowerCase()

/** Pide el foco, tras el siguiente render, para el primero de estos `data-focus` que esté activo:
 * al mover o quitar, el botón pulsado se desactiva o desaparece y el foco caería a la página. */
type FocusRequest = (ids: string[]) => void

function IconButton({
  label,
  onClick,
  disabled,
  focusId,
  children,
}: {
  label: string
  onClick: () => void
  disabled?: boolean
  focusId: string
  children: ReactNode
}) {
  return (
    <Button
      type="button"
      data-focus={focusId}
      variant="ghost"
      size="icon"
      className="size-7 shrink-0 text-muted-foreground hover:text-foreground"
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={onClick}
    >
      {children}
    </Button>
  )
}

function BulletFields({
  title,
  bullets,
  onChange,
  focusPrefix,
  requestFocus,
}: {
  title: string
  bullets: Bullet[]
  onChange: (bullets: Bullet[]) => void
  focusPrefix: string
  requestFocus: FocusRequest
}) {
  const { t } = useTranslation('cv', { keyPrefix: 'edit' })
  // Cada logro, por sus evidencias: así el campo sigue al logro al subirlo o bajarlo.
  const seen = new Map<string, number>()
  return (
    <fieldset className="grid gap-2">
      <legend className="mb-1 text-sm font-medium">{title}</legend>
      {bullets.map((bullet, i) => {
        const evidence = bullet.evidence.join('|')
        const repeat = seen.get(evidence) ?? 0
        seen.set(evidence, repeat + 1)
        const position = i + 1
        const at = (index: number, part: string) => `${focusPrefix}-${index}-${part}`
        return (
          <div key={`${evidence}#${repeat}`} className="flex items-start gap-1">
            <Textarea
              data-focus={at(i, 'text')}
              aria-label={t('bulletAria', { title, position })}
              value={bullet.text}
              onChange={(e) => onChange(bullets.map((row, j) => (j === i ? { ...row, text: e.target.value } : row)))}
              maxLength={MAX_BULLET}
              rows={2}
            />
            <div className="flex flex-col">
              <IconButton
                label={t('bulletUp', { title, position })}
                focusId={at(i, 'up')}
                disabled={i === 0}
                onClick={() => {
                  requestFocus([at(i - 1, 'up'), at(i - 1, 'down')])
                  onChange(move(bullets, i, -1))
                }}
              >
                <ArrowUpIcon />
              </IconButton>
              <IconButton
                label={t('bulletDown', { title, position })}
                focusId={at(i, 'down')}
                disabled={i === bullets.length - 1}
                onClick={() => {
                  requestFocus([at(i + 1, 'down'), at(i + 1, 'up')])
                  onChange(move(bullets, i, 1))
                }}
              >
                <ArrowDownIcon />
              </IconButton>
              {/* El último no se quita: cada experiencia del CV lleva al menos un logro. */}
              <IconButton
                label={t('bulletRemove', { title, position })}
                focusId={at(i, 'remove')}
                disabled={bullets.length === 1}
                onClick={() => {
                  requestFocus([at(Math.min(i, bullets.length - 2), 'text')])
                  onChange(bullets.filter((_, j) => j !== i))
                }}
              >
                <TrashIcon />
              </IconButton>
            </div>
          </div>
        )
      })}
    </fieldset>
  )
}

function SkillGroup({
  group,
  position,
  total,
  onChange,
  onMove,
  onRemove,
  nameRef,
  requestFocus,
}: {
  group: KeyedGroup
  position: number
  total: number
  onChange: (group: KeyedGroup) => void
  onMove: (step: -1 | 1) => void
  onRemove: () => void
  nameRef?: (node: HTMLInputElement | null) => void
  requestFocus: FocusRequest
}) {
  const { t } = useTranslation('cv', { keyPrefix: 'edit' })
  const [draft, setDraft] = useState('')
  const [problem, setProblem] = useState<string | null>(null)
  const [confirming, setConfirming] = useState(false)
  const name = group.group.trim() || t('unnamed', { position })
  const nameId = `cv-edit-group-${group.key}`
  const problemId = `${nameId}-problem`
  const at = (index: number, part: string) => `group-${index}-${part}`
  const here = position - 1
  const pending = draft.trim()

  const add = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key !== 'Enter') return
    // Intro añade la skill; no envía el formulario.
    event.preventDefault()
    const skill = draft.trim()
    if (!skill) return
    if (group.items.some((item) => sameSkill(item, skill))) {
      setProblem(t('skillRepeated', { skill }))
      return
    }
    if (group.items.length >= MAX_SKILLS) {
      setProblem(t('skillsFull', { max: MAX_SKILLS }))
      return
    }
    onChange({ ...group, items: [...group.items, skill] })
    setDraft('')
    setProblem(null)
  }

  return (
    <li className="grid gap-2 rounded-lg border bg-card p-3">
      <div className="flex items-center gap-1">
        <Input
          id={nameId}
          ref={nameRef}
          data-focus={at(here, 'name')}
          aria-label={t('groupName', { position })}
          placeholder={t('groupPlaceholder')}
          value={group.group}
          onChange={(e) => onChange({ ...group, group: e.target.value })}
          // Intro en el nombre no guarda la versión: se guarda con el botón.
          onKeyDown={(e) => e.key === 'Enter' && e.preventDefault()}
          maxLength={MAX_GROUP}
          className="h-8 font-medium"
        />
        <IconButton
          label={t('groupUp', { group: name })}
          focusId={at(here, 'up')}
          disabled={position === 1}
          onClick={() => {
            requestFocus([at(here - 1, 'up'), at(here - 1, 'down')])
            onMove(-1)
          }}
        >
          <ArrowUpIcon />
        </IconButton>
        <IconButton
          label={t('groupDown', { group: name })}
          focusId={at(here, 'down')}
          disabled={position === total}
          onClick={() => {
            requestFocus([at(here + 1, 'down'), at(here + 1, 'up')])
            onMove(1)
          }}
        >
          <ArrowDownIcon />
        </IconButton>
        <IconButton
          label={t('groupRemove', { group: name })}
          focusId={at(here, 'remove')}
          onClick={() => (group.items.length > 0 ? setConfirming(true) : onRemove())}
        >
          <TrashIcon />
        </IconButton>
      </div>
      {confirming && (
        <div
          role="group"
          aria-label={t('groupRemove', { group: name })}
          className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm"
          onKeyDown={(event) => {
            if (event.key !== 'Escape') return
            event.stopPropagation()
            setConfirming(false)
          }}
        >
          <p>{t('confirmRemoveGroup', { group: name, count: group.items.length })}</p>
          <div className="mt-2 flex gap-2">
            <Button type="button" size="sm" variant="destructive" onClick={onRemove}>
              {t('removeGroup')}
            </Button>
            {/* El foco, en lo que no quita nada. */}
            <Button type="button" size="sm" variant="ghost" onClick={() => setConfirming(false)} autoFocus>
              {t('cancel')}
            </Button>
          </div>
        </div>
      )}
      {group.items.length > 0 ? (
        <ul aria-label={t('skillsOf', { group: name })} className="flex flex-wrap gap-1.5">
          {group.items.map((skill, i) => (
            <li
              key={`${i}-${skill}`}
              className="inline-flex items-center gap-0.5 rounded-md bg-secondary py-0.5 pr-0.5 pl-2 text-sm text-secondary-foreground"
            >
              {skill}
              <button
                type="button"
                aria-label={t('skillRemove', { skill, group: name })}
                title={t('skillRemove', { skill, group: name })}
                className="rounded p-0.5 text-muted-foreground hover:bg-background hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                onClick={() => {
                  // La etiqueta desaparece: el foco pasa al campo de añadir de su grupo.
                  requestFocus([at(here, 'add')])
                  onChange({ ...group, items: group.items.filter((_, j) => j !== i) })
                }}
              >
                <XIcon className="size-3.5" />
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-warning-foreground">{t('groupEmpty')}</p>
      )}
      <Input
        data-focus={at(here, 'add')}
        aria-label={t('addSkill', { group: name })}
        aria-describedby={problem ? problemId : undefined}
        aria-invalid={problem ? true : undefined}
        placeholder={t('addSkillPlaceholder')}
        value={draft}
        onChange={(e) => {
          setDraft(e.target.value)
          setProblem(null)
        }}
        onKeyDown={add}
        className="h-8"
      />
      {problem ? (
        <p id={problemId} className="text-xs text-destructive">
          {problem}
        </p>
      ) : (
        // Lo escrito sin Intro no se guarda: que no se pierda sin avisar.
        pending && <p className="text-xs text-muted-foreground">{t('pendingSkill', { skill: pending })}</p>
      )}
    </li>
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
  const [texts, setTexts] = useState<CvContent>(cv.content)
  const [groups, setGroups] = useState<KeyedGroup[]>(() => cv.content.skills.map((g, key) => ({ ...g, key })))
  const nextKey = useRef(cv.content.skills.length)
  const focusKey = useRef<number | null>(null)
  const form = useRef<HTMLFormElement>(null)
  const focusAfter = useRef<string[] | null>(null)
  const requestFocus: FocusRequest = (ids) => {
    focusAfter.current = ids
  }
  // Tras mover o quitar, el foco va al primero de los pedidos que siga activo.
  useEffect(() => {
    const ids = focusAfter.current
    if (!ids) return
    focusAfter.current = null
    for (const id of ids) {
      const node = form.current?.querySelector<HTMLElement>(`[data-focus="${id}"]`)
      if (node && !node.hasAttribute('disabled')) {
        node.focus()
        return
      }
    }
  })
  const content: CvContent = { ...texts, skills: groups.map(({ key: _key, ...group }) => group) }
  const dirty = JSON.stringify(content) !== JSON.stringify(cv.content)
  const incomplete = groups.some((g) => !g.group.trim() || g.items.length === 0)
  const prefix = `cv-edit-${cv.document_id}`
  const labels = cv.labels

  const setBullets = (kind: 'experience' | 'projects', block: number, bullets: Bullet[]) =>
    setTexts({ ...texts, [kind]: texts[kind].map((item, b) => (b === block ? { ...item, bullets } : item)) })
  const addGroup = () => {
    const key = nextKey.current++
    focusKey.current = key
    setGroups([...groups, { key, group: '', items: [] }])
  }

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (incomplete) return
    // Con la promesa, no con `onSuccess` de `mutate`: la versión nueva desmonta este formulario
    // (`key`) antes de que termine, y React Query descartaría ese callback. El error lo enseña `edit`.
    edit.mutateAsync({ base_document_id: cv.document_id, content }).then(
      (result) => onSaved(result.warnings),
      () => undefined,
    )
  }

  return (
    <form ref={form} onSubmit={submit} aria-label={t('form')} className="space-y-5">
      <p className="text-xs text-muted-foreground">{t('hint')}</p>
      <div className="grid gap-1.5">
        <Label htmlFor={`${prefix}-subtitle`}>{t('subtitle')}</Label>
        <Input
          id={`${prefix}-subtitle`}
          value={texts.subtitle}
          onChange={(e) => setTexts({ ...texts, subtitle: e.target.value })}
          maxLength={MAX_SUBTITLE}
        />
      </div>
      <div className="grid gap-1.5">
        <Label htmlFor={`${prefix}-summary`}>{t('summary')}</Label>
        <Textarea
          id={`${prefix}-summary`}
          value={texts.summary}
          onChange={(e) => setTexts({ ...texts, summary: e.target.value })}
          maxLength={MAX_SUMMARY}
          rows={4}
        />
      </div>
      {texts.experience.map((item, b) => (
        <BulletFields
          key={item.experience_id}
          title={labels[item.experience_id] ?? item.experience_id}
          bullets={item.bullets}
          onChange={(bullets) => setBullets('experience', b, bullets)}
          focusPrefix={`experience-${b}`}
          requestFocus={requestFocus}
        />
      ))}
      {texts.projects.map((item, b) => (
        <BulletFields
          key={item.project_id}
          title={labels[item.project_id] ?? item.project_id}
          bullets={item.bullets}
          onChange={(bullets) => setBullets('projects', b, bullets)}
          focusPrefix={`projects-${b}`}
          requestFocus={requestFocus}
        />
      ))}
      <section aria-labelledby={`${prefix}-skills`} className="grid gap-2">
        <h3 id={`${prefix}-skills`} className="text-sm font-medium">
          {t('skillsTitle')}
        </h3>
        <p className="text-xs text-muted-foreground">{t('skillsHint')}</p>
        {groups.length > 0 && (
          <ul className="grid gap-2">
            {groups.map((group, g) => (
              <SkillGroup
                key={group.key}
                group={group}
                position={g + 1}
                total={groups.length}
                onChange={(changed) => setGroups(groups.map((old) => (old.key === group.key ? changed : old)))}
                onMove={(step) => setGroups(move(groups, g, step))}
                onRemove={() => {
                  // Al siguiente grupo, al anterior o, si no queda ninguno, a «Añadir grupo».
                  requestFocus([`group-${g}-name`, `group-${g - 1}-name`, 'add-group'])
                  setGroups(groups.filter((old) => old.key !== group.key))
                }}
                requestFocus={requestFocus}
                nameRef={(node) => {
                  // El grupo recién añadido se estrena con el foco en su nombre.
                  if (node && focusKey.current === group.key) {
                    focusKey.current = null
                    node.focus()
                  }
                }}
              />
            ))}
          </ul>
        )}
        <div>
          <Button type="button" variant="outline" size="sm" data-focus="add-group" onClick={addGroup}>
            <PlusIcon />
            {t('addGroup')}
          </Button>
        </div>
      </section>
      {edit.error && (
        <p role="alert" className="text-sm text-destructive">
          {errorMessage(edit.error)}
        </p>
      )}
      {incomplete && <p className="text-sm text-muted-foreground">{t('incomplete')}</p>}
      <Button type="submit" disabled={!dirty || incomplete || edit.isPending} className="active:translate-y-px">
        <FloppyDiskIcon />
        <BusyLabel busy={edit.isPending} busyText={t('saving')} text={t('save')} />
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
