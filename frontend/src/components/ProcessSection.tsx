import { useState, type FormEvent, type ReactNode } from 'react'
import {
  BellRingingIcon,
  CalendarBlankIcon,
  CheckIcon,
  DownloadSimpleIcon,
  FilePdfIcon,
  PencilSimpleIcon,
  PlusIcon,
  TrashIcon,
  XIcon,
} from '@phosphor-icons/react'
import {
  fileUrls,
  type ContactOut,
  type ContactRelation,
  type JobView,
  type MilestoneKind,
  type MilestoneOut,
  type ProcessView,
  type ReferralStatus,
  type Stage,
} from '@/api/client'
import {
  useCreateMilestone,
  useDeleteContact,
  useJobEvent,
  useJobProcess,
  useMilestoneStatus,
  useSaveContact,
  useSetReferral,
  useUpdateMilestone,
  type ContactFields,
} from '@/api/queries'
import { AgentButton } from '@/components/AgentButton'
import { InterviewActions, InterviewDetails } from '@/components/InterviewDetails'
import { ErrorState } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import {
  channelLabel,
  CONTACT_RELATION_LABEL,
  formatDate,
  MILESTONE_KIND_LABEL,
  MILESTONE_STATUS_LABEL,
  REFERRAL_LABEL,
} from '@/lib/labels'
import { formatWhen, fromLocalInput, toLocalDateInput, toLocalInput } from '@/lib/time'
import { cn } from '@/lib/utils'

/** Etapas con ficha de proceso: desde que se aprueba la oferta. */
const PROCESS_STAGES = new Set<Stage>(['approved', 'cv_ready', 'applied', 'in_process', 'closed'])
/** Entrevistas y pruebas registran su evento: solo tras enviar la candidatura. */
const AFTER_APPLIED = new Set<Stage>(['applied', 'in_process'])

function Block({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-medium">{title}</h3>
        {action}
      </div>
      {children}
    </div>
  )
}

function isUrl(value: string): boolean {
  return /^https?:\/\//i.test(value)
}

// --- Hitos ----------------------------------------------------------------------------------

interface MilestoneDraft {
  kind: MilestoneKind
  title: string
  date: string // datetime-local o date
  allDay: boolean
  location: string
  notes: string
}

function draftFrom(m?: MilestoneOut): MilestoneDraft {
  if (!m) return { kind: 'interview', title: '', date: '', allDay: false, location: '', notes: '' }
  return {
    kind: m.kind,
    title: m.title,
    date: m.all_day ? toLocalDateInput(m.starts_at) : toLocalInput(m.starts_at),
    allDay: m.all_day,
    location: m.location ?? '',
    notes: m.notes ?? '',
  }
}

function MilestoneForm({
  stage,
  initial,
  pending,
  error,
  onSubmit,
  onCancel,
}: {
  stage: Stage | null
  initial?: MilestoneOut
  pending: boolean
  error: Error | null
  onSubmit: (draft: MilestoneDraft, startsAt: string) => void
  onCancel: () => void
}) {
  const [draft, setDraft] = useState<MilestoneDraft>(() => draftFrom(initial))
  const set = (changes: Partial<MilestoneDraft>) => setDraft((d) => ({ ...d, ...changes }))
  const startsAt = draft.date ? fromLocalInput(draft.date) : null
  const eventKind = draft.kind === 'interview' || draft.kind === 'test'
  const blocked = !initial && eventKind && (!stage || !AFTER_APPLIED.has(stage))

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (startsAt && !blocked) onSubmit(draft, startsAt)
  }

  return (
    <form onSubmit={submit} className="grid gap-3 rounded-lg border bg-background p-3">
      <div className="grid gap-3 sm:grid-cols-2">
        {!initial && (
          <div className="space-y-1.5">
            <Label htmlFor="ms-kind">Tipo</Label>
            <select
              id="ms-kind"
              value={draft.kind}
              onChange={(e) => set({ kind: e.target.value as MilestoneKind })}
              className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
            >
              {Object.entries(MILESTONE_KIND_LABEL).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
        )}
        <div className="space-y-1.5">
          <Label htmlFor="ms-title">Título (opcional)</Label>
          <Input
            id="ms-title"
            value={draft.title}
            maxLength={200}
            placeholder={MILESTONE_KIND_LABEL[draft.kind]}
            onChange={(e) => set({ title: e.target.value })}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="ms-date">{draft.allDay ? 'Día' : 'Fecha y hora (Madrid)'}</Label>
          <Input
            id="ms-date"
            type={draft.allDay ? 'date' : 'datetime-local'}
            required
            value={draft.date}
            onChange={(e) => set({ date: e.target.value })}
          />
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            <input
              type="checkbox"
              checked={draft.allDay}
              onChange={(e) =>
                set({ allDay: e.target.checked, date: e.target.checked ? draft.date.slice(0, 10) : '' })
              }
            />
            Todo el día
          </label>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="ms-location">Lugar o enlace</Label>
          <Input
            id="ms-location"
            value={draft.location}
            maxLength={500}
            onChange={(e) => set({ location: e.target.value })}
          />
        </div>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="ms-notes">Notas</Label>
        <Textarea
          id="ms-notes"
          rows={2}
          maxLength={4000}
          value={draft.notes}
          onChange={(e) => set({ notes: e.target.value })}
          className="resize-y"
        />
      </div>
      {blocked && (
        <p className="text-xs text-muted-foreground">
          Las entrevistas y las pruebas se anotan cuando la candidatura ya está enviada (registran su evento y
          mueven la oferta a «En proceso»). Antes, usa «Plazo» u «Otro hito».
        </p>
      )}
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error.message}
        </p>
      )}
      <div className="flex justify-end gap-2">
        <Button type="button" variant="outline" size="sm" onClick={onCancel}>
          Cancelar
        </Button>
        <Button type="submit" size="sm" disabled={!startsAt || blocked || pending}>
          {pending ? 'Guardando…' : 'Guardar hito'}
        </Button>
      </div>
    </form>
  )
}

function MilestoneRow({ milestone, stage }: { milestone: MilestoneOut; stage: Stage | null }) {
  const [editing, setEditing] = useState(false)
  const update = useUpdateMilestone(milestone.job_id)
  const status = useMilestoneStatus(milestone.job_id)
  const scheduled = milestone.status === 'scheduled'

  if (editing) {
    return (
      <li>
        <MilestoneForm
          stage={stage}
          initial={milestone}
          pending={update.isPending}
          error={update.error}
          onCancel={() => setEditing(false)}
          onSubmit={(draft, startsAt) =>
            update.mutate(
              {
                milestoneId: milestone.id,
                body: {
                  title: draft.title.trim() || undefined,
                  starts_at: startsAt,
                  all_day: draft.allDay,
                  location: draft.location.trim() || undefined,
                  notes: draft.notes.trim() || undefined,
                },
              },
              { onSuccess: () => setEditing(false) },
            )
          }
        />
      </li>
    )
  }

  return (
    <li className={cn('flex items-start gap-3 py-2.5', !scheduled && 'opacity-60')}>
      <CalendarBlankIcon className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
      <div className="min-w-0 flex-1 text-sm">
        <p>
          <span className="font-medium">{milestone.title}</span>
          <span className="text-muted-foreground"> · {formatWhen(milestone.starts_at, milestone.all_day)}</span>
          {!scheduled && (
            <span className="ml-2 rounded bg-muted px-1.5 py-0.5 text-xs">
              {MILESTONE_STATUS_LABEL[milestone.status]}
            </span>
          )}
        </p>
        {milestone.location && (
          <p className="truncate text-xs text-muted-foreground">
            {isUrl(milestone.location) ? (
              <a href={milestone.location} target="_blank" rel="noopener noreferrer" className="underline underline-offset-2">
                {milestone.location}
              </a>
            ) : (
              milestone.location
            )}
          </p>
        )}
        {milestone.notes && <p className="mt-0.5 text-xs whitespace-pre-line text-muted-foreground">{milestone.notes}</p>}
        <InterviewDetails milestone={milestone} />
        <InterviewActions milestone={milestone} stage={stage} />
        {status.error && (
          <p role="alert" className="mt-1 text-xs text-destructive">
            {status.error.message}
          </p>
        )}
      </div>
      <div className="flex shrink-0 items-center gap-0.5">
        <Button asChild variant="ghost" size="icon" className="size-8" aria-label={`Descargar .ics de «${milestone.title}»`}>
          <a href={fileUrls.milestoneIcs(milestone.id)} download>
            <DownloadSimpleIcon />
          </a>
        </Button>
        {scheduled && (
          <>
            <Button
              variant="ghost"
              size="icon"
              className="size-8"
              aria-label={`Editar «${milestone.title}»`}
              onClick={() => setEditing(true)}
            >
              <PencilSimpleIcon />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="size-8"
              aria-label={`Marcar «${milestone.title}» como hecho`}
              disabled={status.isPending}
              onClick={() => status.mutate({ milestoneId: milestone.id, body: { status: 'done' } })}
            >
              <CheckIcon />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="size-8"
              aria-label={`Cancelar «${milestone.title}»`}
              disabled={status.isPending}
              onClick={() => status.mutate({ milestoneId: milestone.id, body: { status: 'cancelled' } })}
            >
              <XIcon />
            </Button>
          </>
        )}
      </div>
    </li>
  )
}

function Milestones({ process }: { process: ProcessView }) {
  const [adding, setAdding] = useState(false)
  const create = useCreateMilestone()
  return (
    <Block
      title="Hitos"
      action={
        !adding && (
          <Button variant="outline" size="sm" onClick={() => setAdding(true)}>
            <PlusIcon />
            Añadir
          </Button>
        )
      }
    >
      {adding && (
        <MilestoneForm
          stage={process.stage}
          pending={create.isPending}
          error={create.error}
          onCancel={() => setAdding(false)}
          onSubmit={(draft, startsAt) =>
            create.mutate(
              {
                jobId: process.job_id,
                body: {
                  kind: draft.kind,
                  title: draft.title.trim() || undefined,
                  starts_at: startsAt,
                  all_day: draft.allDay,
                  location: draft.location.trim() || undefined,
                  notes: draft.notes.trim() || undefined,
                },
              },
              { onSuccess: () => setAdding(false) },
            )
          }
        />
      )}
      {process.milestones.length === 0 ? (
        !adding && <p className="text-sm text-muted-foreground">Sin entrevistas, pruebas ni plazos anotados.</p>
      ) : (
        <ul className="divide-y">
          {process.milestones.map((m) => (
            <MilestoneRow key={m.id} milestone={m} stage={process.stage} />
          ))}
        </ul>
      )}
    </Block>
  )
}

// --- Contactos ------------------------------------------------------------------------------

const EMPTY_CONTACT: ContactFields = {
  name: '',
  role: '',
  email: '',
  phone: '',
  linkedin: '',
  notes: '',
  relation: null,
}
const RELATIONS: ContactRelation[] = ['referral', 'recruiter', 'hiring_manager']
const REFERRALS: ReferralStatus[] = ['requested', 'given']

function ContactForm({
  jobId,
  initial,
  onDone,
}: {
  jobId: number
  initial?: ContactOut
  onDone: () => void
}) {
  const [fields, setFields] = useState<ContactFields>(() =>
    initial
      ? {
          name: initial.name,
          role: initial.role ?? '',
          email: initial.email ?? '',
          phone: initial.phone ?? '',
          linkedin: initial.linkedin ?? '',
          notes: initial.notes ?? '',
          relation: initial.relation ?? null,
        }
      : EMPTY_CONTACT,
  )
  const save = useSaveContact(jobId)
  const field = (key: Exclude<keyof ContactFields, 'relation'>, label: string, type = 'text') => (
    <div className="space-y-1.5">
      <Label htmlFor={`contact-${key}`}>{label}</Label>
      <Input
        id={`contact-${key}`}
        type={type}
        value={fields[key] ?? ''}
        required={key === 'name'}
        onChange={(e) => setFields((f) => ({ ...f, [key]: e.target.value }))}
      />
    </div>
  )
  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!fields.name.trim()) return
    save.mutate({ contactId: initial?.id, body: fields }, { onSuccess: onDone })
  }
  return (
    <form onSubmit={submit} className="grid gap-3 rounded-lg border bg-background p-3">
      <div className="grid gap-3 sm:grid-cols-2">
        {field('name', 'Nombre')}
        {field('role', 'Cargo')}
        {field('email', 'Correo', 'email')}
        {field('phone', 'Teléfono', 'tel')}
        {field('linkedin', 'LinkedIn')}
        {field('notes', 'Notas')}
        <div className="space-y-1.5">
          <Label htmlFor="contact-relation">Papel en el proceso</Label>
          <select
            id="contact-relation"
            value={fields.relation ?? ''}
            onChange={(e) => setFields((f) => ({ ...f, relation: (e.target.value || null) as ContactRelation | null }))}
            className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
          >
            <option value="">Sin indicar</option>
            {RELATIONS.map((r) => (
              <option key={r} value={r}>
                {CONTACT_RELATION_LABEL[r]}
              </option>
            ))}
          </select>
        </div>
      </div>
      {save.error && (
        <p role="alert" className="text-sm text-destructive">
          {save.error.message}
        </p>
      )}
      <div className="flex justify-end gap-2">
        <Button type="button" variant="outline" size="sm" onClick={onDone}>
          Cancelar
        </Button>
        <Button type="submit" size="sm" disabled={!fields.name.trim() || save.isPending}>
          {save.isPending ? 'Guardando…' : 'Guardar contacto'}
        </Button>
      </div>
    </form>
  )
}

function ReferralSelect({ contact }: { contact: ContactOut }) {
  const set = useSetReferral(contact.job_id)
  const id = `referral-${contact.id}`
  return (
    <span className="inline-flex items-center gap-1.5">
      <label htmlFor={id} className="sr-only">
        Referencia de {contact.name}
      </label>
      <select
        id={id}
        value={contact.referral ?? ''}
        disabled={set.isPending}
        onChange={(e) => set.mutate({ contactId: contact.id, referral: (e.target.value || null) as ReferralStatus | null })}
        className="h-7 rounded-md border border-input bg-background px-1.5 text-xs"
      >
        <option value="">Sin referencia</option>
        {REFERRALS.map((r) => (
          <option key={r} value={r}>
            {REFERRAL_LABEL[r]}
          </option>
        ))}
      </select>
      {set.error && (
        <span role="alert" className="text-xs text-destructive">
          {set.error.message}
        </span>
      )}
    </span>
  )
}

function ContactRow({ contact }: { contact: ContactOut }) {
  const [editing, setEditing] = useState(false)
  const remove = useDeleteContact(contact.job_id)
  if (editing) {
    return (
      <li>
        <ContactForm jobId={contact.job_id} initial={contact} onDone={() => setEditing(false)} />
      </li>
    )
  }
  const links = [
    contact.email && { href: `mailto:${contact.email}`, text: contact.email },
    contact.phone && { href: `tel:${contact.phone}`, text: contact.phone },
    contact.linkedin && isUrl(contact.linkedin) && { href: contact.linkedin, text: 'LinkedIn' },
  ].filter(Boolean) as { href: string; text: string }[]
  return (
    <li className="flex items-start gap-3 py-2.5 text-sm">
      <div className="min-w-0 flex-1">
        <p>
          <span className="font-medium">{contact.name}</span>
          {contact.role && <span className="text-muted-foreground"> · {contact.role}</span>}
          {contact.relation && (
            <span className="ml-2 rounded-full border px-1.5 py-px text-[0.7rem] font-medium text-muted-foreground">
              {CONTACT_RELATION_LABEL[contact.relation]}
            </span>
          )}
        </p>
        {links.length > 0 && (
          <p className="flex flex-wrap gap-x-3 text-xs">
            {links.map((link) => (
              <a key={link.href} href={link.href} className="text-muted-foreground underline underline-offset-2 hover:text-foreground">
                {link.text}
              </a>
            ))}
          </p>
        )}
        {contact.notes && <p className="text-xs text-muted-foreground">{contact.notes}</p>}
        <div className="mt-1.5">
          <ReferralSelect contact={contact} />
        </div>
      </div>
      <Button variant="ghost" size="icon" className="size-8" aria-label={`Editar a ${contact.name}`} onClick={() => setEditing(true)}>
        <PencilSimpleIcon />
      </Button>
      <Button
        variant="ghost"
        size="icon"
        className="size-8"
        aria-label={`Quitar a ${contact.name}`}
        disabled={remove.isPending}
        onClick={() => remove.mutate(contact.id)}
      >
        <TrashIcon />
      </Button>
    </li>
  )
}

function Contacts({ process }: { process: ProcessView }) {
  const [adding, setAdding] = useState(false)
  return (
    <Block
      title="Contactos"
      action={
        !adding && (
          <Button variant="outline" size="sm" onClick={() => setAdding(true)}>
            <PlusIcon />
            Añadir
          </Button>
        )
      }
    >
      {adding && <ContactForm jobId={process.job_id} onDone={() => setAdding(false)} />}
      {process.contacts.length === 0 ? (
        !adding && <p className="text-sm text-muted-foreground">Nadie anotado todavía.</p>
      ) : (
        <ul className="divide-y">
          {process.contacts.map((c) => (
            <ContactRow key={c.id} contact={c} />
          ))}
        </ul>
      )}
    </Block>
  )
}

// --- Envío y seguimiento --------------------------------------------------------------------

function Sending({ process }: { process: ProcessView }) {
  const event = useJobEvent()
  const canFollowUp = process.stage === 'applied' || process.stage === 'in_process'
  const followup = process.followup
  return (
    <Block title="Envío">
      {process.applied_at ? (
        <p className="text-sm">
          Enviada el {formatDate(process.applied_at)}
          {channelLabel(process.channel) && <span className="text-muted-foreground"> · {channelLabel(process.channel)}</span>}
        </p>
      ) : (
        <p className="text-sm text-muted-foreground">Aún sin enviar. Regístralo en Procesos cuando la envíes.</p>
      )}
      {followup?.due && (
        <p className="inline-flex items-center gap-1.5 rounded-md bg-primary/10 px-2.5 py-1.5 text-sm font-medium text-primary">
          <BellRingingIcon className="size-4" weight="duotone" />
          {followup.days_waiting} días sin respuesta: toca un seguimiento.
        </p>
      )}
      {process.documents.cv_render_id != null && (
        <a
          href={fileUrls.renderPdf(process.documents.cv_render_id)}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1.5 text-sm text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
        >
          <FilePdfIcon className="size-4" />
          {process.documents.cv_sent ? 'CV enviado' : 'CV seleccionado para enviar'}
        </a>
      )}
      {process.offer_received && process.stage === 'in_process' && (
        <div className="space-y-1.5">
          <p className="text-sm">Tienes una propuesta: antes de aceptar, revisa qué conviene aclarar.</p>
          <AgentButton action="offer-questions" jobId={process.job_id}>
            Dudas antes de aceptar
          </AgentButton>
        </div>
      )}
      {canFollowUp && (
        <div>
          <Button
            variant="outline"
            size="sm"
            disabled={event.isPending}
            onClick={() => event.mutate({ jobId: process.job_id, body: { type: 'followup_sent' } })}
          >
            Seguimiento enviado
          </Button>
          {event.error && (
            <p role="alert" className="mt-1 text-xs text-destructive">
              {event.error.message}
            </p>
          )}
        </div>
      )}
    </Block>
  )
}

export function ProcessSection({ job }: { job: JobView }) {
  const visible = job.stage !== null && PROCESS_STAGES.has(job.stage)
  const { data, isPending, isError, error, refetch } = useJobProcess(job.id, visible)
  if (!visible) return null
  return (
    <section className="rounded-xl border bg-card p-5 sm:p-6" aria-label="Proceso">
      <h2 className="mb-5 font-semibold">Proceso</h2>
      {isPending ? (
        <Skeleton className="h-32" />
      ) : isError ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : (
        <div className="space-y-7">
          <Sending process={data} />
          <Milestones process={data} />
          <Contacts process={data} />
        </div>
      )}
    </section>
  )
}
