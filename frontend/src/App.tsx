import { type QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Link, Navigate, Route, Routes } from 'react-router'
import { useTranslation } from 'react-i18next'
import { CompassIcon } from '@phosphor-icons/react'
import { AppShell } from '@/components/AppShell'
import { EmptyState } from '@/components/States'
import { Button } from '@/components/ui/button'
import { TooltipProvider } from '@/components/ui/tooltip'
import { useLanguage } from '@/lib/i18n'
import { pages } from '@/lib/pages'
// «Hoy» es la entrada más común: va en el chunk inicial, sin esperar a otro.
import { HomePage } from '@/pages/HomePage'

const {
  agent: { Page: AgentPage },
  alerts: { Page: AlertsPage },
  calendar: { Page: CalendarPage },
  funnel: { Page: FunnelPage },
  inbox: { Page: InboxPage },
  job: { Page: JobPage },
  newJob: { Page: NewJobPage },
  platforms: { Page: PlatformsPage },
  processes: { Page: ProcessesPage },
  profile: { Page: ProfilePage },
  replies: { Page: RepliesPage },
  skills: { Page: SkillsPage },
  sources: { Page: SourcesPage },
  sourcesHub: { Page: SourcesHubPage },
  templates: { Page: TemplatesPage },
  triage: { Page: TriagePage },
} = pages

function NotFound() {
  const { t } = useTranslation()
  return (
    <EmptyState
      icon={<CompassIcon className="size-6" weight="duotone" />}
      title={t('notFound.title')}
      action={
        <Button asChild variant="outline">
          <Link to="/">{t('notFound.goHome')}</Link>
        </Button>
      }
    />
  )
}

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<HomePage />} />
        <Route path="bandeja" element={<InboxPage />} />
        <Route path="jobs/:id" element={<JobPage />} />
        <Route path="nueva" element={<NewJobPage />} />
        <Route path="por-revisar" element={<TriagePage />} />
        {/* Antes «Triaje»: los enlaces guardados siguen funcionando. */}
        <Route path="triaje" element={<Navigate to="/por-revisar" replace />} />
        <Route path="procesos" element={<ProcessesPage />} />
        <Route path="calendario" element={<CalendarPage />} />
        <Route path="respuestas" element={<RepliesPage />} />
        <Route path="embudo" element={<FunnelPage />} />
        <Route path="skills" element={<SkillsPage />} />
        <Route path="alertas" element={<AlertsPage />} />
        <Route path="plantillas" element={<TemplatesPage />} />
        <Route path="perfil" element={<ProfilePage />} />
        <Route path="fuentes" element={<SourcesHubPage />}>
          <Route index element={<Navigate to="/fuentes/plataformas" replace />} />
          <Route path="empresas" element={<SourcesPage />} />
          <Route path="plataformas" element={<PlatformsPage />} />
        </Route>
        {/* Antes de la fase 23.3 eran páginas sueltas: los enlaces guardados siguen funcionando. */}
        <Route path="empresas" element={<Navigate to="/fuentes/empresas" replace />} />
        <Route path="plataformas" element={<Navigate to="/fuentes/plataformas" replace />} />
        <Route path="agente" element={<AgentPage />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}

export function App({ client }: { client: QueryClient }) {
  // Al cambiar de idioma se vuelven a montar las páginas: así no queda ningún texto (etiquetas,
  // fechas) del idioma anterior. Los datos siguen en la caché de TanStack Query.
  const { language } = useLanguage()
  return (
    <QueryClientProvider client={client}>
      <TooltipProvider delayDuration={300}>
        <AppRoutes key={language} />
      </TooltipProvider>
    </QueryClientProvider>
  )
}
