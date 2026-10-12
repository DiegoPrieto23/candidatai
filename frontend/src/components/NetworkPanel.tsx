import { useState } from 'react'
import { ArrowSquareOutIcon, DownloadSimpleIcon, PlusIcon, UsersThreeIcon } from '@phosphor-icons/react'
import type { ContactRelation, JobView, NetworkPerson, Stage } from '@/api/client'
import { useAddContactFromNetwork, useImportNetwork, useJobNetwork, useNetworkStatus } from '@/api/queries'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { CONTACT_RELATION_LABEL, formatDate } from '@/lib/labels'

/** Etapas con ficha de proceso: solo ahí se puede añadir a alguien como contacto. */
const PROCESS_STAGES: ReadonlySet<Stage> = new Set(['approved', 'cv_ready', 'applied', 'in_process'])
const RELATIONS: ContactRelation[] = ['referral', 'recruiter', 'hiring_manager']

function isUrl(value: string): boolean {
  return /^https?:\/\//i.test(value)
}

function AddToProcess({ jobId, person }: { jobId: number; person: NetworkPerson }) {
  const [open, setOpen] = useState(false)
  const [relation, setRelation] = useState<ContactRelation>('referral')
  const add = useAddContactFromNetwork(jobId)
  if (!open) {
    return (
      <Button variant="outline" size="sm" className="h-7 px-2 text-xs" onClick={() => setOpen(true)}>
        <PlusIcon />
        Añadir al proceso
      </Button>
    )
  }
  const id = `relation-${person.id}`
  return (
    <form
      className="flex flex-wrap items-center gap-2"
      onSubmit={(e) => {
        e.preventDefault()
        add.mutate({ network_contact_id: person.id, relation }, { onSuccess: () => setOpen(false) })
      }}
    >
      <label htmlFor={id} className="sr-only">
        Papel de {person.name} en el proceso
      </label>
      <select
        id={id}
        value={relation}
        onChange={(e) => setRelation(e.target.value as ContactRelation)}
        className="h-7 rounded-md border border-input bg-background px-2 text-xs"
      >
        {RELATIONS.map((r) => (
          <option key={r} value={r}>
            {CONTACT_RELATION_LABEL[r]}
          </option>
        ))}
      </select>
      <Button type="submit" size="sm" className="h-7 px-2 text-xs" disabled={add.isPending}>
        Añadir
      </Button>
      <Button type="button" variant="ghost" size="sm" className="h-7 px-2 text-xs" onClick={() => setOpen(false)}>
        Cancelar
      </Button>
      {add.error && (
        <p role="alert" className="w-full text-xs text-destructive">
          {add.error.message}
        </p>
      )}
    </form>
  )
}

function Person({ person, jobId, canAdd }: { person: NetworkPerson; jobId: number; canAdd: boolean }) {
  return (
    <li className="space-y-1.5 py-2.5 text-sm">
      <p>
        {person.linkedin_url && isUrl(person.linkedin_url) ? (
          <a
            href={person.linkedin_url}
            target="_blank"
            rel="noopener noreferrer nofollow"
            className="inline-flex items-center gap-1 font-medium underline-offset-4 hover:underline"
          >
            {person.name}
            <ArrowSquareOutIcon className="size-3.5 text-muted-foreground" />
          </a>
        ) : (
          <span className="font-medium">{person.name}</span>
        )}
        {person.position && <span className="text-muted-foreground"> · {person.position}</span>}
      </p>
      {person.match === 'probable' && person.company && (
        <p className="text-xs text-muted-foreground">En LinkedIn pone «{person.company}»: comprueba que es la misma.</p>
      )}
      {person.contact_id != null ? (
        <p className="text-xs font-medium text-primary">Ya es contacto del proceso</p>
      ) : (
        canAdd && <AddToProcess jobId={jobId} person={person} />
      )}
    </li>
  )
}

function ImportNetwork() {
  const { data } = useNetworkStatus()
  const run = useImportNetwork()
  return (
    <div className="space-y-3 text-sm">
      <p className="text-muted-foreground">
        Importa tus contactos de LinkedIn para ver a quién conoces en cada empresa. En LinkedIn: Ajustes → Privacidad
        de los datos → Obtener una copia de tus datos → Contactos. Deja el fichero en{' '}
        <code className="font-mono text-xs">data/{data?.default_file ?? 'documentos/linkedin/Connections.csv'}</code>.
      </p>
      <Button
        variant="outline"
        size="sm"
        disabled={!data?.default_file_exists || run.isPending}
        onClick={() => run.mutate()}
      >
        <DownloadSimpleIcon />
        {run.isPending ? 'Importando…' : 'Importar Connections.csv'}
      </Button>
      {data && !data.default_file_exists && (
        <p className="text-xs text-muted-foreground">Aún no está el fichero en esa carpeta.</p>
      )}
      {run.error && (
        <p role="alert" className="text-xs text-destructive">
          {run.error.message}
        </p>
      )}
    </div>
  )
}

/**
 * Ficha (fase 18): las personas de tu red de LinkedIn que trabajan en la empresa de la oferta. La app
 * no navega LinkedIn ni envía nada: solo cruza tu exportación con tus ofertas.
 */
export function NetworkPanel({ job }: { job: JobView }) {
  const { data, isPending, isError, error } = useJobNetwork(job.id)
  const canAdd = job.stage !== null && PROCESS_STAGES.has(job.stage)
  const count = data?.people.length ?? 0
  return (
    <section aria-label="Tu red" className="rounded-xl border bg-card p-5 sm:p-6">
      <h2 className="mb-4 flex items-center gap-2 text-base font-semibold tracking-tight">
        <UsersThreeIcon className="size-[18px] text-primary" weight="duotone" />
        Tu red
      </h2>
      {isPending ? (
        <Skeleton className="h-16" />
      ) : isError ? (
        // Panel secundario: el fallo se dice sin `alert`, para no tapar los avisos de la ficha.
        <p className="text-sm text-muted-foreground">No se pudo cargar tu red: {error.message}</p>
      ) : data.network_size === 0 ? (
        <ImportNetwork />
      ) : count === 0 ? (
        <p className="text-sm text-muted-foreground">Nadie de tu red trabaja en {data.company}.</p>
      ) : (
        <>
          <p className="text-sm">
            Conoces a {count === 1 ? '1 persona' : `${count} personas`} en {data.company}.
          </p>
          <ul className="mt-1 divide-y">
            {data.people.map((person) => (
              <Person key={person.id} person={person} jobId={job.id} canAdd={canAdd} />
            ))}
          </ul>
          {!canAdd && job.stage !== 'closed' && (
            <p className="mt-2 text-xs text-muted-foreground">Apruébala para añadirlos como contactos del proceso.</p>
          )}
        </>
      )}
      {data && data.network_size > 0 && data.imported_at && (
        <p className="mt-3 text-xs text-muted-foreground">
          Red importada el {formatDate(data.imported_at)} ({data.network_size} personas).
        </p>
      )}
    </section>
  )
}

/** Insignia «Conoces a N» para listas (bandeja, triaje). */
export function KnownBadge({ count }: { count?: number }) {
  if (!count) return null
  return (
    <span
      className="inline-flex shrink-0 items-center gap-1 rounded-full border border-primary/30 bg-primary/10 px-1.5 py-px text-[0.7rem] leading-4 font-medium whitespace-nowrap text-primary"
      title="Personas de tu red de LinkedIn en esta empresa"
    >
      <UsersThreeIcon className="size-3" weight="bold" />
      Conoces a {count}
    </span>
  )
}

/** Triaje: «Conoces a 2 personas en Acme: Ana (CTO) y Luis (Recruiter)». Solo si hay alguien. */
export function KnownPeople({ jobId, count }: { jobId: number; count?: number }) {
  const { data } = useJobNetwork(jobId, Boolean(count))
  if (!count || !data?.people.length) return null
  const names = data.people.map((p) => (p.position ? `${p.name} (${p.position})` : p.name))
  const list = names.length < 2 ? names.join('') : `${names.slice(0, -1).join(', ')} y ${names[names.length - 1]}`
  return (
    <p className="mt-3 flex items-start gap-1.5 text-sm">
      <UsersThreeIcon className="mt-0.5 size-4 shrink-0 text-primary" weight="duotone" />
      <span>
        Conoces a {data.people.length === 1 ? '1 persona' : `${data.people.length} personas`} en {data.company}:{' '}
        {list}.
      </span>
    </p>
  )
}
