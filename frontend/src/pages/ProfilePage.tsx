import { useState } from 'react'
import { UserCircleIcon } from '@phosphor-icons/react'
import { Trans, useTranslation } from 'react-i18next'
import { useEditableProfile, type ContextSectionName } from '@/api/queries'
import { AgentButton } from '@/components/AgentButton'
import { EmptyState, ErrorState } from '@/components/States'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { DocumentsTab, FilesCard, NotesCard } from '@/components/profile/DocumentsTab'
import { ProfileEditorProvider, blockAnchor, useProfileState } from '@/components/profile/editor'
import { ExperienceBlock } from '@/components/profile/ExperienceBlock'
import { HistoryBlock } from '@/components/profile/HistoryBlock'
import { CertificationsBlock, EducationBlock, ExtraSectionsBlock, ProjectsBlock } from '@/components/profile/ItemsBlocks'
import { PersonalBlock } from '@/components/profile/PersonalBlock'
import { PhotoBlock } from '@/components/profile/PhotoBlock'
import { LanguagesBlock, SkillsBlock } from '@/components/profile/SkillsBlock'
import { StartByHand } from '@/components/profile/StartByHand'
import { ImportFromCv } from '@/components/profile/ImportFromCv'
import { StartFromCv } from '@/components/profile/StartFromCv'
import { StoriesBlock } from '@/components/profile/StoriesBlock'
import { focusArrival } from '@/lib/focus'
import { cn } from '@/lib/utils'

/** El estilo de `InlineCode`, como componente para `Trans`. */
function InlineCodeTag({ children }: { children?: React.ReactNode }) {
  return <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em] text-foreground">{children}</code>
}

/** Cuatro pestañas en una fila: lo del CV junto, lo que orienta al agente y el historial. */
const TABS = ['about', 'career', 'documents', 'history'] as const
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
  cv: { tab: 'documents', title: 'blocks.cv.title' },
  letter: { tab: 'documents', title: 'blocks.letter.title' },
}

/** Los apartados de «Experiencia y formación», en el orden en que salen. */
const CAREER_BLOCKS = ['experience', 'skills', 'languages', 'projects', 'education', 'certifications', 'extra_sections', 'stories'] as const

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
      focusArrival(target)
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
                className="flex items-baseline gap-1.5 rounded-md border bg-card px-2.5 py-1 text-sm text-foreground/80 transition-colors outline-none hover:border-foreground/30 focus-visible:ring-2 focus-visible:ring-ring"
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
      <TabsContent value="about" forceMount className={cn('grid gap-6', hidden)}>
        <PersonalBlock />
        <PhotoBlock />
      </TabsContent>
      <TabsContent value="career" forceMount className={cn('grid gap-6', hidden)}>
        <SectionNav onGo={goTo} />
        <ExperienceBlock />
        <SkillsBlock />
        <LanguagesBlock />
        <ProjectsBlock />
        <EducationBlock />
        <CertificationsBlock />
        <ExtraSectionsBlock />
        <StoriesBlock />
      </TabsContent>
      <TabsContent value="documents" forceMount className={cn('grid gap-6', hidden)}>
        <DocumentsTab />
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
        <NotesCard />
        <FilesCard />
      </div>
    )
  } else if (editable.data.profile === null) {
    body = (
      <div className="grid gap-10">
        <EmptyState icon={<UserCircleIcon className="size-7" weight="duotone" />} title={te('noProfile.title')}>
          <Trans t={te} i18nKey="noProfile.unreadable" components={{ code }} />
        </EmptyState>
        <NotesCard />
        <FilesCard />
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
    <div className="max-w-4xl animate-in fade-in duration-300">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold tracking-tight">{t('title')}</h1>
        <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
          <Trans t={t} i18nKey="intro" components={{ code }} />
        </p>
        {/* Fase 25.2: skill `expand`. Pregunta antes de escribir, así que solo en terminal. Sin
            perfil todavía, lo primero es crearlo desde el CV. */}
        {editable.data?.exists && (
          <div className="mt-4 flex flex-wrap items-start gap-2">
            <ImportFromCv />
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
