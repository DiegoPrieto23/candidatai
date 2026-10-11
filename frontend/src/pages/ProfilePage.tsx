import { FileTextIcon, FolderIcon, WarningIcon } from '@phosphor-icons/react'
import type { ContextFileInfo, ContextStatus } from '@/api/client'
import { useContextStatus } from '@/api/queries'
import { OpenFolderButton } from '@/components/OpenFolderButton'
import { ErrorState, InlineCode } from '@/components/States'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

const SECTIONS: Record<ContextFileInfo['section'], { title: string; hint: string }> = {
  'estilo-redaccion': {
    title: 'Estilo de redacción',
    hint: 'Tono, estructura, palabras que usas y que evitas. Lo usan los CVs y las cartas.',
  },
  'perfil-conductual': {
    title: 'Perfil conductual',
    hint: 'Cómo trabajas, fortalezas, tests de personalidad. Para preparar entrevistas.',
  },
  criterios: {
    title: 'Criterios',
    hint: 'Deal-breakers y preferencias en texto libre. La valoración de encaje los cita como riesgo.',
  },
  narrativa: {
    title: 'Narrativa',
    hint: 'Tu historia, motivación y cómo explicas los cambios. Para entrevistas.',
  },
}

const FOLDERS: Record<ContextStatus['folders'][number]['name'], string> = {
  cv: 'Tus CVs anteriores (PDF o Word)',
  linkedin: 'Exportaciones de tu perfil de LinkedIn',
  titulos: 'Títulos y certificados',
  referencias: 'Cartas de referencia',
  candidaturas: 'Lo que enviaste en cada candidatura (se llena solo)',
}

function formatSize(bytes: number): string {
  return bytes < 1024 ? `${bytes} B` : `${(bytes / 1024).toFixed(1).replace('.', ',')} KB`
}

function formatWhen(iso: string): string {
  return new Date(iso).toLocaleString('es-ES', { day: 'numeric', month: 'short', year: 'numeric' })
}

function FileState({ file }: { file: ContextFileInfo }) {
  const [label, tone] = !file.exists
    ? ['No existe', 'text-muted-foreground']
    : file.empty
      ? ['Vacío', 'text-amber-700 dark:text-amber-400']
      : ['Con contenido', 'text-emerald-700 dark:text-emerald-400']
  return <span className={cn('text-xs font-medium', tone)}>{label}</span>
}

function ContextFiles({ files }: { files: ContextFileInfo[] }) {
  return (
    <ul className="divide-y rounded-xl border bg-card">
      {files.map((file) => (
        <li key={file.section} className="grid gap-1 px-4 py-3">
          <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
            <span className="flex items-center gap-2 font-medium">
              <FileTextIcon className="size-4 text-muted-foreground" aria-hidden />
              {SECTIONS[file.section].title}
            </span>
            <FileState file={file} />
          </div>
          <p className="text-sm text-muted-foreground">{SECTIONS[file.section].hint}</p>
          <p className="font-mono text-xs text-muted-foreground">
            data/{file.path}
            {file.exists && (
              <>
                {' · '}
                {formatSize(file.size_bytes)}
                {file.modified_at && ` · ${formatWhen(file.modified_at)}`}
              </>
            )}
          </p>
          {file.warnings.map((warning) => (
            <p key={warning} className="flex items-start gap-1.5 text-xs text-amber-700 dark:text-amber-400">
              <WarningIcon className="mt-0.5 size-3.5 shrink-0" aria-hidden />
              {warning.replace(/^[a-z_]+: /, '')}
            </p>
          ))}
        </li>
      ))}
    </ul>
  )
}

function DocumentFolders({ folders }: { folders: ContextStatus['folders'] }) {
  return (
    <ul className="divide-y rounded-xl border bg-card">
      {folders.map((folder) => (
        <li key={folder.name} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3">
          <span className="grid gap-0.5">
            <span className="flex items-center gap-2 font-mono text-sm">
              <FolderIcon className="size-4 text-muted-foreground" aria-hidden />
              {folder.name}/
            </span>
            <span className="text-sm text-muted-foreground">{FOLDERS[folder.name]}</span>
          </span>
          <span className="text-xs text-muted-foreground">
            {folder.files === 1 ? '1 fichero' : `${folder.files} ficheros`}
          </span>
        </li>
      ))}
    </ul>
  )
}

export function ProfilePage() {
  const status = useContextStatus()

  let body
  if (status.isPending) {
    body = (
      <div className="grid gap-3">
        <Skeleton className="h-48" />
        <Skeleton className="h-40" />
      </div>
    )
  } else if (status.isError) {
    body = <ErrorState error={status.error} onRetry={() => status.refetch()} />
  } else {
    body = (
      <div className="grid gap-10">
        <section aria-labelledby="contexto" className="grid gap-3">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 id="contexto" className="text-lg font-semibold tracking-tight">
                Contexto
              </h2>
              <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                Orienta a tu agente: el tono de tus CVs y cartas, los riesgos de una oferta y la preparación
                de entrevistas. <strong className="font-medium text-foreground">Nunca respalda un hecho</strong>
                : lo que diga un CV o una carta tiene que estar en tu perfil. Edítalos con tu editor o pide a
                tu agente <InlineCode text="`actualizar-perfil`" />.
              </p>
            </div>
            <OpenFolderButton folder="contexto" ariaLabel="Abrir la carpeta del contexto" />
          </div>
          <ContextFiles files={status.data.files} />
        </section>
        <section aria-labelledby="documentos" className="grid gap-3">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 id="documentos" className="text-lg font-semibold tracking-tight">
                Documentos
              </h2>
              <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                Tus documentos fuente. <InlineCode text="`actualizar-perfil`" /> puede leerlos para crear o
                ampliar tu perfil, siempre preguntándote antes de escribir.
              </p>
            </div>
            <OpenFolderButton folder="documentos" ariaLabel="Abrir la carpeta de documentos" />
          </div>
          <DocumentFolders folders={status.data.folders} />
        </section>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-3xl animate-in fade-in duration-300">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold tracking-tight">Mi perfil</h1>
        <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
          Tu perfil (<InlineCode text="`data/profile.yaml`" />) es lo único que puede afirmar un CV, una carta o
          una respuesta. Aquí tienes lo que lo acompaña.
        </p>
      </div>
      {body}
    </div>
  )
}
