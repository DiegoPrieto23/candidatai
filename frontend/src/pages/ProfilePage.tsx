import { FileTextIcon, FolderIcon, UserCircleIcon, WarningIcon } from '@phosphor-icons/react'
import { Trans, useTranslation } from 'react-i18next'
import type { ContextFileInfo, ContextStatus } from '@/api/client'
import { useContextStatus, useEditableProfile } from '@/api/queries'
import { AgentButton } from '@/components/AgentButton'
import { OpenFolderButton } from '@/components/OpenFolderButton'
import { EmptyState, ErrorState } from '@/components/States'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { CONTEXT_SECTIONS, ContextFileEditor, StyleSamplesBlock } from '@/components/profile/ContextBlocks'
import { ProfileEditorProvider, useProfileState } from '@/components/profile/editor'
import { ExperienceBlock } from '@/components/profile/ExperienceBlock'
import { HistoryBlock } from '@/components/profile/HistoryBlock'
import { CertificationsBlock, EducationBlock, ExtraSectionsBlock, ProjectsBlock } from '@/components/profile/ItemsBlocks'
import { PersonalBlock } from '@/components/profile/PersonalBlock'
import { CvPreferencesBlock, LetterPreferencesBlock, SearchPreferencesBlock } from '@/components/profile/PreferencesBlocks'
import { SkillsBlock } from '@/components/profile/SkillsBlock'
import { StoriesBlock } from '@/components/profile/StoriesBlock'
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

function ContextFiles({ files }: { files: ContextFileInfo[] }) {
  const { t } = useTranslation('profile')
  return (
    <ul className="divide-y rounded-xl border bg-card">
      {files.map((file) => (
        <li key={file.section} className="grid gap-1 px-4 py-3">
          <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
            <span className="flex items-center gap-2 font-medium">
              <FileTextIcon className="size-4 text-muted-foreground" aria-hidden />
              {t(`sections.${file.section}.title`)}
            </span>
            <FileState file={file} />
          </div>
          <p className="text-sm text-muted-foreground">{t(`sections.${file.section}.hint`)}</p>
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
  const { t } = useTranslation('profile')
  return (
    <ul className="divide-y rounded-xl border bg-card">
      {folders.map((folder) => (
        <li key={folder.name} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3">
          <span className="grid gap-0.5">
            <span className="flex items-center gap-2 font-mono text-sm">
              <FolderIcon className="size-4 text-muted-foreground" aria-hidden />
              {folder.name}/
            </span>
            <span className="text-sm text-muted-foreground">{t(`folders.${folder.name}`)}</span>
          </span>
          <span className="text-xs text-muted-foreground">{t('files', { count: folder.files })}</span>
        </li>
      ))}
    </ul>
  )
}

/** El estilo de `InlineCode`, como componente para `Trans`. */
function InlineCodeTag({ children }: { children?: React.ReactNode }) {
  return <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em] text-foreground">{children}</code>
}

/** Estado de los ficheros de contexto y de las carpetas de documentos (fase 13). */
function FilesOverview() {
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
              <Trans t={t} i18nKey="contextIntro" components={{ strong: <strong className="font-medium text-foreground" />, code }} />
            </p>
          </div>
          <OpenFolderButton folder="contexto" ariaLabel={t('openContext')} />
        </div>
        <ContextFiles files={status.data.files} />
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

const TABS = ['personal', 'experience', 'background', 'skills', 'stories', 'search', 'documents', 'context', 'history'] as const

/** El fichero no valida: se enseñan sus problemas, pero se puede seguir editando para arreglarlos. */
function FileIssues() {
  const { t } = useTranslation('profileEditor')
  const { state, dirtyCount } = useProfileState()
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
      {dirtyCount > 0 && (
        <p role="status" className="mb-4 text-sm text-amber-700 dark:text-amber-400">
          {t('unsaved.page', { count: dirtyCount })}
        </p>
      )}
    </>
  )
}

function Editor() {
  const { t } = useTranslation('profileEditor')
  const hidden = 'data-[state=inactive]:hidden'
  return (
    <Tabs defaultValue="personal" className="gap-4">
      <FileIssues />
      <TabsList className="h-auto flex-wrap justify-start">
        {TABS.map((tab) => (
          <TabsTrigger key={tab} value={tab} className="flex-none px-2.5">
            {t(`tabs.${tab}`)}
          </TabsTrigger>
        ))}
      </TabsList>
      {/* `forceMount`: cambiar de pestaña no pierde lo que no se ha guardado. */}
      <TabsContent value="personal" forceMount className={hidden}>
        <PersonalBlock />
      </TabsContent>
      <TabsContent value="experience" forceMount className={hidden}>
        <ExperienceBlock />
      </TabsContent>
      <TabsContent value="background" forceMount className={cn('grid gap-6', hidden)}>
        <ProjectsBlock />
        <EducationBlock />
        <CertificationsBlock />
        <ExtraSectionsBlock />
      </TabsContent>
      <TabsContent value="skills" forceMount className={hidden}>
        <SkillsBlock />
      </TabsContent>
      <TabsContent value="stories" forceMount className={hidden}>
        <StoriesBlock />
      </TabsContent>
      <TabsContent value="search" forceMount className={cn('grid gap-6', hidden)}>
        <SearchPreferencesBlock />
      </TabsContent>
      <TabsContent value="documents" forceMount className={cn('grid gap-6', hidden)}>
        <CvPreferencesBlock />
        <LetterPreferencesBlock />
      </TabsContent>
      <TabsContent value="context" forceMount className={cn('grid gap-6', hidden)}>
        {CONTEXT_SECTIONS.map((section) => (
          <ContextFileEditor key={section} section={section} />
        ))}
        <StyleSamplesBlock />
        <FilesOverview />
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
  } else if (!editable.data.exists || editable.data.profile === null) {
    body = (
      <div className="grid gap-10">
        <EmptyState icon={<UserCircleIcon className="size-7" weight="duotone" />} title={te('noProfile.title')}>
          <Trans t={te} i18nKey={editable.data.exists ? 'noProfile.unreadable' : 'noProfile.body'} components={{ code }} />
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
        {/* Fase 25.2: skill `expand`. Pregunta antes de escribir, así que solo en terminal. */}
        <div className="mt-4 grid gap-2">
          <AgentButton action="expand" variant="outline">
            {t('expand')}
          </AgentButton>
          <p className="text-xs leading-relaxed text-muted-foreground">{t('expandHint')}</p>
        </div>
      </div>
      {body}
    </div>
  )
}
