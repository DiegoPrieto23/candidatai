import { useRef, useState } from 'react'
import { FileTextIcon, FolderIcon, UploadSimpleIcon, UserCircleIcon, WarningIcon } from '@phosphor-icons/react'
import { Trans, useTranslation } from 'react-i18next'
import type { ContextFileInfo, ContextStatus } from '@/api/client'
import {
  useContextStatus,
  useEditableProfile,
  useUploadSourceDocument,
  type ContextSectionName,
  type SourceDocumentFolder,
} from '@/api/queries'
import { AgentButton } from '@/components/AgentButton'
import { OpenFolderButton } from '@/components/OpenFolderButton'
import { EmptyState, ErrorState } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { CONTEXT_SECTIONS, ContextFileEditor, StyleSamplesBlock } from '@/components/profile/ContextBlocks'
import { ProfileEditorProvider, useProfileState } from '@/components/profile/editor'
import { ExperienceBlock } from '@/components/profile/ExperienceBlock'
import { HistoryBlock } from '@/components/profile/HistoryBlock'
import { blockAnchor } from '@/components/profile/editor'
import { CertificationsBlock, EducationBlock, ExtraSectionsBlock, ProjectsBlock } from '@/components/profile/ItemsBlocks'
import { PersonalBlock } from '@/components/profile/PersonalBlock'
import {
  CvPreferencesBlock,
  LetterPreferencesBlock,
  SearchContractBlock,
  SearchExperienceBlock,
  SearchRoleBlock,
  SearchWhereBlock,
} from '@/components/profile/PreferencesBlocks'
import { LanguagesBlock, SkillsBlock } from '@/components/profile/SkillsBlock'
import { StartByHand } from '@/components/profile/StartByHand'
import { StartFromCv } from '@/components/profile/StartFromCv'
import { StoriesBlock } from '@/components/profile/StoriesBlock'
import { errorMessage } from '@/lib/errors'
import { dateFormatter, formatNumber } from '@/lib/labels'
import { cn } from '@/lib/utils'

function formatSize(bytes: number): string {
  return bytes < 1024 ? `${bytes} B` : `${formatNumber(bytes / 1024, { minimumFractionDigits: 1, maximumFractionDigits: 1 })} KB`
}

function formatWhen(iso: string): string {
  return dateFormatter({ day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(iso))
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

/** Lleva al bloque del fichero (en «Documentos», con perfil) y le da el foco. */
function goToEditor(section: ContextSectionName) {
  const block = document.getElementById(blockAnchor(`context-${section}`))
  block?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  block?.focus({ preventScroll: true })
}

/**
 * Los cuatro ficheros de contexto. Con perfil, sus editores están más arriba y cada fila lleva hasta
 * el suyo; sin perfil, se crean y se editan aquí mismo, desplegados bajo su fila.
 */
function ContextFiles({ files, editorsAbove }: { files: ContextFileInfo[]; editorsAbove: boolean }) {
  const { t } = useTranslation('profile')
  const [open, setOpen] = useState<ContextSectionName | null>(null)
  return (
    <ul className="divide-y rounded-xl border bg-card">
      {files.map((file) => {
        const name = t(`sections.${file.section}.title`)
        const expanded = open === file.section
        // Sin perfil, se crea o se edita aquí; con perfil, lleva a su bloque.
        const action = expanded ? 'close' : editorsAbove || file.exists ? 'edit' : 'create'
        return (
          <li key={file.section} className="grid gap-1 px-4 py-3">
            <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
              <span className="flex items-center gap-2 font-medium">
                <FileTextIcon className="size-4 text-muted-foreground" aria-hidden />
                {name}
              </span>
              <span className="flex items-center gap-3">
                <FileState file={file} />
                <Button
                  type="button"
                  size="sm"
                  variant={editorsAbove ? 'ghost' : 'outline'}
                  aria-label={t(`contextFile.${action}Named`, { name })}
                  aria-expanded={editorsAbove ? undefined : expanded}
                  onClick={() => (editorsAbove ? goToEditor(file.section) : setOpen(expanded ? null : file.section))}
                >
                  {t(`contextFile.${action}`)}
                </Button>
              </span>
            </div>
            <p className="text-sm text-muted-foreground">{t(`sections.${file.section}.hint`)}</p>
            {file.exists && (
              <p className="text-xs text-muted-foreground">
                {formatSize(file.size_bytes)}
                {file.modified_at && ` · ${formatWhen(file.modified_at)}`}
              </p>
            )}
            {file.warnings.map((warning) => (
              <p key={warning} className="flex items-start gap-1.5 text-xs text-amber-700 dark:text-amber-400">
                <WarningIcon className="mt-0.5 size-3.5 shrink-0" aria-hidden />
                {warning.replace(/^[a-z_]+: /, '')}
              </p>
            ))}
            {!editorsAbove && expanded && (
              <div className="mt-2">
                <ContextFileEditor section={file.section} />
              </div>
            )}
          </li>
        )
      })}
    </ul>
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
        <UploadSimpleIcon /> {upload.isPending ? t('upload.uploading') : t(`upload.${folder}`)}
      </Button>
      {error && (
        <p role="alert" className="basis-full text-sm text-destructive">
          {error}
        </p>
      )}
    </>
  )
}

function DocumentFolders({ folders }: { folders: ContextStatus['folders'] }) {
  const { t } = useTranslation('profile')
  return (
    <ul className="divide-y rounded-xl border bg-card">
      {folders.map((folder) => (
        <li key={folder.name} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3">
          <span className="grid gap-0.5">
            <span className="flex items-center gap-2 text-sm font-medium">
              <FolderIcon className="size-4 text-muted-foreground" aria-hidden />
              {t(`folderNames.${folder.name}`)}
            </span>
            <span className="text-sm text-muted-foreground">{t(`folders.${folder.name}`)}</span>
          </span>
          <span className="flex flex-wrap items-center gap-3">
            <span className="text-xs text-muted-foreground">{t('files', { count: folder.files })}</span>
            {(folder.name === 'cv' || folder.name === 'linkedin') && <UploadDocument folder={folder.name} />}
          </span>
        </li>
      ))}
    </ul>
  )
}

/** El estilo de `InlineCode`, como componente para `Trans`. */
function InlineCodeTag({ children }: { children?: React.ReactNode }) {
  return <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em] text-foreground">{children}</code>
}

/** Estado de los ficheros de contexto y de las carpetas de documentos (fase 13). `editorsAbove`:
 * con perfil, los editores de contexto van en sus bloques, más arriba. */
function FilesOverview({ editorsAbove = false }: { editorsAbove?: boolean }) {
  const { t } = useTranslation('profile')
  const status = useContextStatus()
  const code = <InlineCodeTag />
  if (status.isPending) return <Skeleton className="h-48" />
  if (status.isError) return <ErrorState error={status.error} onRetry={() => status.refetch()} />
  return (
    <div className="grid gap-10">
      <section aria-labelledby="contexto" className="grid gap-3">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 id="contexto" className="text-lg font-semibold tracking-tight">
              {t('context')}
            </h2>
            <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
              <Trans t={t} i18nKey={editorsAbove ? 'contextIntro' : 'contextIntroHere'} components={{ strong: <strong className="font-medium text-foreground" />, code }} />
            </p>
          </div>
          <OpenFolderButton folder="contexto" ariaLabel={t('openContext')} />
        </div>
        <ContextFiles files={status.data.files} editorsAbove={editorsAbove} />
      </section>
      <section aria-labelledby="documentos" className="grid gap-3">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 id="documentos" className="text-lg font-semibold tracking-tight">
              {t('documents')}
            </h2>
            <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
              <Trans t={t} i18nKey="documentsIntro" components={{ code }} />
            </p>
          </div>
          <OpenFolderButton folder="documentos" ariaLabel={t('openDocuments')} />
        </div>
        <DocumentFolders folders={status.data.folders} />
      </section>
    </div>
  )
}

/** Cinco pestañas en una fila: lo del CV junto, la búsqueda, lo que orienta al agente y el historial. */
const TABS = ['about', 'career', 'search', 'documents', 'history'] as const
type Tab = (typeof TABS)[number]

/** Dónde está un bloque: su pestaña, el bloque de la página que lo contiene y su nombre. */
interface BlockPlace {
  id: string
  tab: Tab
  anchor: string
  title: string
}

/** Los bloques que se guardan solos, por el id con el que avisan de que tienen cambios. */
const PLACES: Record<string, { tab: Tab; anchor?: string; title: string }> = {
  personal: { tab: 'about', title: 'blocks.personal.title' },
  skills: { tab: 'career', title: 'blocks.skills.title' },
  languages: { tab: 'career', title: 'blocks.languages.title' },
  experience: { tab: 'career', title: 'blocks.experience.title' },
  projects: { tab: 'career', title: 'blocks.projects.title' },
  education: { tab: 'career', title: 'blocks.education.title' },
  certifications: { tab: 'career', title: 'blocks.certifications.title' },
  extra_sections: { tab: 'career', title: 'blocks.extra.title' },
  stories: { tab: 'career', title: 'blocks.stories.title' },
  'search-role': { tab: 'search', title: 'blocks.searchRole.title' },
  'search-experience': { tab: 'search', title: 'blocks.searchExperience.title' },
  'salary-floor': { tab: 'search', anchor: 'search-experience', title: 'fields.salaryFloor' },
  'search-where': { tab: 'search', title: 'blocks.searchWhere.title' },
  'search-contract': { tab: 'search', title: 'blocks.searchContract.title' },
  cv: { tab: 'documents', title: 'blocks.cv.title' },
  letter: { tab: 'documents', title: 'blocks.letter.title' },
}

/** Los apartados de «Experiencia y formación», en el orden en que salen. */
const CAREER_BLOCKS = ['skills', 'languages', 'experience', 'projects', 'education', 'certifications', 'extra_sections', 'stories'] as const

function usePlace() {
  const { t } = useTranslation('profileEditor')
  const { t: tp } = useTranslation('profile')
  return (id: string): BlockPlace | null => {
    const known = PLACES[id]
    if (known) return { id, tab: known.tab, anchor: known.anchor ?? id, title: t(known.title as never) }
    if (id.startsWith('context-')) {
      const section = id.slice('context-'.length) as ContextSectionName
      return { id, tab: 'documents', anchor: id, title: tp(`sections.${section}.title`) }
    }
    return null
  }
}

/** Lleva hasta un bloque: cambia de pestaña si hace falta y baja hasta él, con el foco en él. */
function useGoTo(setTab: (tab: Tab) => void) {
  return (place: Pick<BlockPlace, 'tab' | 'anchor'>) => {
    setTab(place.tab)
    // Tras pintar la pestaña: antes, el bloque está oculto y no se puede bajar hasta él.
    requestAnimationFrame(() => {
      const target = document.getElementById(blockAnchor(place.anchor))
      if (!target) return
      const smooth = !window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
      target.scrollIntoView?.({ behavior: smooth ? 'smooth' : 'auto', block: 'start' })
      target.focus({ preventScroll: true })
    })
  }
}

/** El fichero no valida: se enseñan sus problemas, pero se puede seguir editando para arreglarlos. */
function FileIssues({ onGo }: { onGo: (place: BlockPlace) => void }) {
  const { t } = useTranslation('profileEditor')
  const { state, dirtyBlocks } = useProfileState()
  const place = usePlace()
  const unsaved = [...dirtyBlocks].flatMap((id) => place(id) ?? [])
  return (
    <>
      {state.issues.length > 0 && (
        <div role="alert" className="mb-4 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm dark:border-amber-800 dark:bg-amber-950/40">
          <p className="font-medium">{t('issues.title')}</p>
          <ul className="mt-1 list-disc pl-5">
            {state.issues.map((issue) => (
              <li key={`${issue.field}-${issue.reason}`}>
                <code className="text-xs">{issue.field}</code>: {issue.reason}
              </li>
            ))}
          </ul>
        </div>
      )}
      {/* Cada bloque se guarda con su botón: se nombran para ir a guardarlos sin buscar qué cambió. */}
      {unsaved.length > 0 && (
        <div
          role="status"
          className="mb-4 flex flex-wrap items-center gap-x-2 gap-y-1.5 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300"
        >
          <span className="font-medium">{t('unsaved.list')}</span>
          {unsaved.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => onGo(item)}
              aria-label={t('unsaved.goTo', { block: item.title, tab: t(`tabs.${item.tab}`) })}
              className="rounded-full border border-amber-400/70 bg-background px-2.5 py-0.5 text-xs font-medium text-foreground outline-none hover:border-amber-600 focus-visible:ring-[3px] focus-visible:ring-ring/50"
            >
              {item.title}
            </button>
          ))}
          <span className="text-xs text-amber-800/80 dark:text-amber-300/80">{t('unsaved.hint')}</span>
        </div>
      )}
    </>
  )
}

/** El índice de «Experiencia y formación»: un enlace por apartado, con cuántos hay y si falta guardar. */
function SectionNav({ onGo }: { onGo: (place: BlockPlace) => void }) {
  const { t } = useTranslation('profileEditor')
  const { profile, dirtyBlocks } = useProfileState()
  const place = usePlace()
  return (
    <nav aria-label={t('sectionNav.label')}>
      <ul className="flex flex-wrap gap-1.5">
        {CAREER_BLOCKS.map((id) => {
          const item = place(id)!
          const count = profile[id]?.length ?? 0
          const dirty = dirtyBlocks.has(id)
          return (
            <li key={id}>
              <a
                href={`#${blockAnchor(id)}`}
                onClick={(event) => {
                  event.preventDefault()
                  onGo(item)
                }}
                className="flex items-baseline gap-1.5 rounded-full border bg-card px-3 py-1 text-sm text-foreground/80 transition-colors outline-none hover:border-foreground/30 focus-visible:ring-2 focus-visible:ring-ring"
              >
                {item.title}
                <span className="tabular text-xs text-muted-foreground">{count}</span>
                {dirty && (
                  <span className="size-1.5 self-center rounded-full bg-amber-500" role="img" aria-label={t('sectionNav.unsaved')} />
                )}
              </a>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}

function Editor() {
  const { t } = useTranslation('profileEditor')
  const [tab, setTab] = useState<Tab>('about')
  const goTo = useGoTo(setTab)
  const hidden = 'data-[state=inactive]:hidden'
  return (
    <Tabs value={tab} onValueChange={(value) => setTab(value as Tab)} className="gap-4">
      <FileIssues onGo={goTo} />
      {/* En móvil, la fila se desplaza en vez de partirse en dos. */}
      <TabsList className="scroll-row w-full justify-start gap-1">
        {TABS.map((name) => (
          <TabsTrigger key={name} value={name} className="h-8 flex-none px-2.5">
            {t(`tabs.${name}`)}
          </TabsTrigger>
        ))}
      </TabsList>
      {/* `forceMount`: cambiar de pestaña no pierde lo que no se ha guardado. */}
      <TabsContent value="about" forceMount className={hidden}>
        <PersonalBlock />
      </TabsContent>
      <TabsContent value="career" forceMount className={cn('grid gap-6', hidden)}>
        <SectionNav onGo={goTo} />
        <SkillsBlock />
        <LanguagesBlock />
        <ExperienceBlock />
        <ProjectsBlock />
        <EducationBlock />
        <CertificationsBlock />
        <ExtraSectionsBlock />
        <StoriesBlock />
      </TabsContent>
      <TabsContent value="search" forceMount className={cn('grid gap-6', hidden)}>
        <SearchRoleBlock />
        <SearchExperienceBlock />
        <SearchWhereBlock />
        <SearchContractBlock />
      </TabsContent>
      <TabsContent value="documents" forceMount className={cn('grid gap-6', hidden)}>
        <CvPreferencesBlock />
        <LetterPreferencesBlock />
        {CONTEXT_SECTIONS.map((section) => (
          <ContextFileEditor key={section} section={section} />
        ))}
        <StyleSamplesBlock />
        <FilesOverview editorsAbove />
      </TabsContent>
      <TabsContent value="history" forceMount className={hidden}>
        <HistoryBlock />
      </TabsContent>
    </Tabs>
  )
}

export function ProfilePage() {
  const { t } = useTranslation('profile')
  const { t: te } = useTranslation('profileEditor')
  const editable = useEditableProfile()
  const code = <InlineCodeTag />

  let body
  if (editable.isPending) {
    body = (
      <div className="grid gap-3">
        <Skeleton className="h-10" />
        <Skeleton className="h-64" />
      </div>
    )
  } else if (editable.isError) {
    body = <ErrorState error={editable.error} onRetry={() => editable.refetch()} />
  } else if (!editable.data.exists) {
    body = (
      <div className="grid gap-10">
        <div className="grid gap-4">
          <StartFromCv />
          <StartByHand />
        </div>
        <FilesOverview />
      </div>
    )
  } else if (editable.data.profile === null) {
    body = (
      <div className="grid gap-10">
        <EmptyState icon={<UserCircleIcon className="size-7" weight="duotone" />} title={te('noProfile.title')}>
          <Trans t={te} i18nKey="noProfile.unreadable" components={{ code }} />
        </EmptyState>
        <FilesOverview />
      </div>
    )
  } else {
    body = (
      <ProfileEditorProvider state={editable.data} reload={() => void editable.refetch()}>
        <Editor />
      </ProfileEditorProvider>
    )
  }

  return (
    <div className="mx-auto max-w-4xl animate-in fade-in duration-300">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold tracking-tight">{t('title')}</h1>
        <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
          <Trans t={t} i18nKey="intro" components={{ code }} />
        </p>
        {/* Fase 25.2: skill `expand`. Pregunta antes de escribir, así que solo en terminal. Sin
            perfil todavía, lo primero es crearlo desde el CV. */}
        {editable.data?.exists && (
          <div className="mt-4">
            <AgentButton action="expand">
              {t('expand')}
            </AgentButton>
          </div>
        )}
      </div>
      {body}
    </div>
  )
}
