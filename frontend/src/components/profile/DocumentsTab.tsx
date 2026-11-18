/**
 * «Mi perfil › Documentos» en tres tarjetas: cómo quieres tus CVs y cartas, notas para tu agente y
 * tus archivos. Cada cosa es una fila de una línea que se despliega al pulsarla; lo de dentro es el
 * mismo bloque de siempre (`BlockInRow`), sin su cabecera. Sin perfil se usan las dos últimas.
 */
import { useRef, useState, type ReactNode } from 'react'
import { CaretRightIcon, UploadSimpleIcon, WarningIcon } from '@phosphor-icons/react'
import { useTranslation } from 'react-i18next'
import type { ContextFileInfo, ContextStatus } from '@/api/client'
import { useContextStatus, useStyleSamples, useTemplates, useUploadSourceDocument, type SourceDocumentFolder } from '@/api/queries'
import { Hint } from '@/components/Hint'
import { OpenFolderButton } from '@/components/OpenFolderButton'
import { ErrorState } from '@/components/States'
import { BusyLabel } from '@/components/StableLabel'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Skeleton } from '@/components/ui/skeleton'
import { codeName } from '@/lib/codes'
import { cvSummary, letterSummary } from '@/lib/docSummaries'
import { errorMessage } from '@/lib/errors'
import { useTemplateText } from '@/lib/templateText'
import { cn } from '@/lib/utils'
import { CONTEXT_SECTIONS, ContextFileEditor, StyleSamplesBlock } from './ContextBlocks'
import { ImportFromCv } from './ImportFromCv'
import { blockAnchor, useOptionalProfileState, useProfileState } from './editor'
import { BlockInRow } from './headingLevel'
import { CvPreferencesBlock, LetterPreferencesBlock } from './PreferencesBlocks'
import type { ProfileData } from './types'

/**
 * Una fila plegable. Lo de dentro se monta la primera vez que se abre y ya no se desmonta (plegar no
 * pierde lo escrito). Con cambios sin guardar (`id` en «Sin guardar») se abre sola y no se pliega, así
 * el aviso de cambios sin guardar siempre lleva a algo visible.
 */
export function DocRow({
  id,
  title,
  about,
  summary,
  status,
  action = 'edit',
  below,
  children,
}: {
  id?: string
  title: string
  about?: string
  summary?: string
  status?: ReactNode
  action?: 'edit' | 'create' | 'view'
  below?: ReactNode
  children: ReactNode
}) {
  const { t } = useTranslation('profile')
  const dirty = useOptionalProfileState()?.dirtyBlocks.has(id ?? '') ?? false
  const [chosen, setChosen] = useState(false)
  const [mounted, setMounted] = useState(false)
  const open = chosen || dirty
  const toggle = (next: boolean) => {
    if (!next && dirty) return
    setChosen(next)
    if (next) setMounted(true)
  }
  const verb = open ? 'fold' : action
  const labels = { fold: t('docs.foldNamed', { name: title }), edit: t('contextFile.editNamed', { name: title }), create: t('contextFile.createNamed', { name: title }), view: t('docs.viewNamed', { name: title }) }
  const texts = { fold: t('docs.fold'), edit: t('contextFile.edit'), create: t('contextFile.create'), view: t('docs.view') }
  return (
    <Collapsible open={open} onOpenChange={toggle} asChild>
      <section
        id={id && blockAnchor(id)}
        tabIndex={id ? -1 : undefined}
        aria-label={title}
        className="scroll-mt-20 outline-none lg:scroll-mt-6"
      >
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-2.5">
          {/* Pulsar en el nombre también despliega; el botón de la derecha es el que llega con teclado. */}
          <div className="flex min-w-0 flex-1 cursor-pointer items-start gap-2" onClick={() => toggle(!open)}>
            <CaretRightIcon
              className={cn('mt-1 size-3.5 shrink-0 text-muted-foreground transition-transform', open && 'rotate-90')}
              weight="bold"
              aria-hidden
            />
            <span className="grid min-w-0">
              <span className="flex items-center gap-1.5 font-medium">
                {title}
                {about && (
                  <span onClick={(event) => event.stopPropagation()}>
                    <Hint text={about} label={t('docs.about', { name: title })} />
                  </span>
                )}
              </span>
              {summary && (
                <span className="truncate text-xs text-muted-foreground" title={summary}>
                  {summary}
                </span>
              )}
            </span>
          </div>
          {status}
          {/* Con cambios sin guardar no se pliega: en vez del botón, se dice por qué, a la vista. */}
          {open && dirty ? (
            <span className="text-xs font-medium text-amber-700 dark:text-amber-400">{t('docs.unsavedOpen')}</span>
          ) : (
            <CollapsibleTrigger asChild>
              <Button type="button" size="sm" variant="ghost" aria-label={labels[verb]}>
                {texts[verb]}
              </Button>
            </CollapsibleTrigger>
          )}
        </div>
        {below}
        {/* Con `forceMount`, Radix no oculta lo plegado: se oculta aquí. */}
        <CollapsibleContent forceMount hidden={!open} className="border-t bg-muted/30 p-4">
          {(mounted || open) && <BlockInRow.Provider value>{children}</BlockInRow.Provider>}
        </CollapsibleContent>
      </section>
    </Collapsible>
  )
}

function Rows({ children }: { children: ReactNode }) {
  return <div className="divide-y overflow-hidden rounded-lg border">{children}</div>
}

/** Una tarjeta de la pestaña: título (con su pista), una línea y sus botones a la derecha. */
function Card({ id, title, lead, about, actions, children }: { id: string; title: string; lead?: string; about?: string; actions?: ReactNode; children: ReactNode }) {
  const { t } = useTranslation('profile')
  return (
    <section aria-labelledby={id} className="grid gap-3 rounded-xl border bg-card p-4 sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id={id} className="flex items-center gap-1.5 font-semibold">
            {title}
            {about && <Hint text={about} label={t('docs.about', { name: title })} />}
          </h2>
          {lead && <p className="mt-0.5 text-sm text-muted-foreground">{lead}</p>}
        </div>
        {actions && <div className="flex flex-wrap items-start gap-2">{actions}</div>}
      </div>
      {children}
    </section>
  )
}

function FileState({ file }: { file: ContextFileInfo }) {
  const { t } = useTranslation('profile', { keyPrefix: 'state' })
  const [label, tone] = !file.exists
    ? [t('missing'), 'text-muted-foreground']
    : file.empty
      ? [t('empty'), 'text-amber-700 dark:text-amber-400']
      : [t('filled'), 'text-emerald-700 dark:text-emerald-400']
  return <span className={cn('text-xs font-medium', tone)}>{label}</span>
}

function PreferencesCard() {
  const { t, i18n } = useTranslation('profile')
  const { profile } = useProfileState()
  const templates = useTemplates()
  const text = useTemplateText()
  const prefs = (profile as ProfileData).preferences
  const say = (key: string, values?: Record<string, unknown>) => String(t(`summary.${key}` as never, values as never))
  const template = (id: string) => {
    const found = templates.data?.templates.find((tpl) => tpl.id === id)
    return found ? text.name(found) : id
  }
  // El YAML se edita a mano: sin `photo_policy`, como si no hubiera nada elegido.
  const cv = { ...prefs?.cv, photo_policy: { default: true, ...prefs?.cv?.photo_policy } }
  return (
    <Card id="docs-prefs" title={t('docs.prefsTitle')}>
      <Rows>
        <DocRow id="cv" title={t('docs.cv')} summary={cvSummary(cv, say, { template, region: (code) => codeName('region', code, i18n.language) })}>
          <CvPreferencesBlock />
        </DocRow>
        <DocRow id="letter" title={t('docs.letter')} summary={letterSummary(prefs?.cover_letter, say, i18n.language)}>
          <LetterPreferencesBlock />
        </DocRow>
      </Rows>
    </Card>
  )
}

/** Las cuatro notas de `data/contexto/` y las muestras de estilo. */
export function NotesCard() {
  const { t } = useTranslation('profile')
  const { t: te } = useTranslation('profileEditor')
  const status = useContextStatus()
  const samples = useStyleSamples()
  const files = new Map((status.data?.files ?? []).map((file) => [file.section, file]))
  return (
    <Card
      id="docs-notes"
      title={t('docs.notesTitle')}
      lead={t('docs.notesLead')}
      about={t('docs.notesHint')}
      actions={<OpenFolderButton folder="contexto" ariaLabel={t('openContext')} />}
    >
      {/* El estado solo pone la etiqueta de cada nota: si no carga, las notas se siguen editando. */}
      {status.isError && !status.data && <ErrorState error={status.error} onRetry={() => status.refetch()} />}
      <Rows>
        {CONTEXT_SECTIONS.map((section) => {
          const file = files.get(section)
          const title = t(`sections.${section}.title`)
          return (
            <DocRow
              key={section}
              id={`context-${section}`}
              title={title}
              about={t(`sections.${section}.hint`)}
              summary={t(`short.${section}`)}
              status={file && <FileState file={file} />}
              action={file && !file.exists ? 'create' : 'edit'}
              below={file?.warnings.map((warning) => (
                <p key={warning} className="flex items-start gap-1.5 px-4 pb-2 text-xs text-amber-700 dark:text-amber-400">
                  <WarningIcon className="mt-0.5 size-3.5 shrink-0" aria-hidden />
                  {warning.replace(/^[a-z_]+: /, '')}
                </p>
              ))}
            >
              <ContextFileEditor section={section} />
            </DocRow>
          )
        })}
        <DocRow
          title={te('style.title')}
          about={t('folders.estilo')}
          summary={t('short.samples')}
          status={
            <span className="text-xs text-muted-foreground">
              {samples.data?.length ? t('docs.samples', { count: samples.data.length }) : t('docs.noSamples')}
            </span>
          }
          action="view"
        >
          <StyleSamplesBlock />
        </DocRow>
      </Rows>
    </Card>
  )
}

const UPLOADS: Record<SourceDocumentFolder, string> = { cv: '.pdf,.docx,.txt,.md', linkedin: '.pdf,.zip,.csv' }

/** Tu CV y tu exportación de LinkedIn se suben desde aquí, a su carpeta, para que tu agente los lea. */
function UploadDocument({ folder }: { folder: SourceDocumentFolder }) {
  const { t } = useTranslation('profile')
  const upload = useUploadSourceDocument(folder)
  const input = useRef<HTMLInputElement>(null)
  const [error, setError] = useState<string | null>(null)
  return (
    <>
      <input
        ref={input}
        type="file"
        accept={UPLOADS[folder]}
        className="sr-only"
        aria-label={t(`upload.fileLabel.${folder}`)}
        onChange={(e) => {
          const file = e.target.files?.[0]
          e.target.value = ''
          if (!file) return
          setError(null)
          upload.mutate(file, { onError: (err) => setError(errorMessage(err)) })
        }}
      />
      <Button type="button" size="sm" variant="outline" disabled={upload.isPending} onClick={() => input.current?.click()}>
        <UploadSimpleIcon /> <BusyLabel busy={upload.isPending} busyText={t('upload.uploading')} text={t(`upload.${folder}`)} />
      </Button>
      {error && (
        <p role="alert" className="basis-full text-sm text-destructive">
          {error}
        </p>
      )}
    </>
  )
}

/** Las carpetas de `data/documentos/`, salvo la de las muestras de estilo (ya en «Notas para tu agente»). */
export function FilesCard({ withImport = false }: { withImport?: boolean }) {
  const { t } = useTranslation('profile')
  const status = useContextStatus()
  return (
    <Card
      id="docs-files"
      title={t('docs.filesTitle')}
      lead={t('docs.filesLead')}
      about={t('docs.filesHint')}
      actions={
        <>
          {withImport && <ImportFromCv />}
          <OpenFolderButton folder="documentos" ariaLabel={t('openDocuments')} />
        </>
      }
    >
      {status.isPending ? (
        <Skeleton className="h-40" />
      ) : status.isError ? (
        <ErrorState error={status.error} onRetry={() => status.refetch()} />
      ) : (
        <Folders folders={status.data.folders.filter((folder) => folder.name !== 'estilo')} />
      )}
    </Card>
  )
}

function Folders({ folders }: { folders: ContextStatus['folders'] }) {
  const { t } = useTranslation('profile')
  return (
    <ul className="divide-y rounded-lg border">
      {folders.map((folder) => {
        const name = t(`folderNames.${folder.name}`)
        return (
          <li key={folder.name} className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5">
            <span className="flex items-center gap-1.5 text-sm font-medium">
              {name}
              <Hint text={t(`folders.${folder.name}`)} label={t('docs.about', { name })} />
            </span>
            <span className="flex flex-wrap items-center gap-3">
              <span className="text-xs text-muted-foreground">{folder.files ? t('files', { count: folder.files }) : t('docs.emptyFolder')}</span>
              {(folder.name === 'cv' || folder.name === 'linkedin') && <UploadDocument folder={folder.name} />}
            </span>
          </li>
        )
      })}
    </ul>
  )
}

/** La pestaña «Documentos», con perfil. */
export function DocumentsTab() {
  const { t } = useTranslation('profile')
  return (
    <div className="grid gap-4">
      <p className="text-sm text-muted-foreground">{t('docs.lead')}</p>
      <PreferencesCard />
      <NotesCard />
      <FilesCard withImport />
    </div>
  )
}
