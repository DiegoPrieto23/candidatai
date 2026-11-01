import { type QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Link, Navigate, Route, Routes, useLocation } from 'react-router'
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
  emailAlerts: { Page: EmailAlertsPage },
  calendar: { Page: CalendarPage },
  extension: { Page: ExtensionPage },
  funnel: { Page: FunnelPage },
  howItWorks: { Page: HowItWorksPage },
  inbox: { Page: InboxPage },
  inboxHub: { Page: InboxHubPage },
  job: { Page: JobPage },
  newJob: { Page: NewJobPage },
  platforms: { Page: PlatformsPage },
  processes: { Page: ProcessesPage },
  processesHub: { Page: ProcessesHubPage },
  profile: { Page: ProfilePage },
  profileHub: { Page: ProfileHubPage },
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

/** Una ruta antigua: lleva a la nueva sin perder lo que traía el enlace (`?view=agenda`…). */
function MovedTo({ to }: { to: string }) {
  const { search } = useLocation()
  return <Navigate to={`${to}${search}`} replace />
}

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<HomePage />} />
        <Route path="como-funciona" element={<HowItWorksPage />} />
        <Route path="bandeja" element={<InboxHubPage />}>
          <Route index element={<InboxPage />} />
          <Route path="revision" element={<TriagePage />} />
          <Route path="por-completar" element={<AlertsPage />} />
        </Route>
        <Route path="jobs/:id" element={<JobPage />} />
        <Route path="nueva" element={<NewJobPage />} />
        <Route path="procesos" element={<ProcessesHubPage />}>
          <Route index element={<ProcessesPage />} />
          <Route path="calendario" element={<CalendarPage />} />
        </Route>
        <Route path="embudo" element={<FunnelPage />} />
        <Route path="perfil" element={<ProfileHubPage />}>
          <Route index element={<ProfilePage />} />
          <Route path="skills" element={<SkillsPage />} />
          <Route path="plantillas" element={<TemplatesPage />} />
        </Route>
        {/* Antes tenían entrada propia en la barra: los enlaces guardados siguen funcionando. */}
        <Route path="por-revisar" element={<MovedTo to="/bandeja/revision" />} />
        <Route path="triaje" element={<MovedTo to="/bandeja/revision" />} />
        <Route path="alertas" element={<MovedTo to="/bandeja/por-completar" />} />
        <Route path="calendario" element={<MovedTo to="/procesos/calendario" />} />
        <Route path="respuestas" element={<MovedTo to="/procesos" />} />
        <Route path="skills" element={<MovedTo to="/perfil/skills" />} />
        <Route path="plantillas" element={<MovedTo to="/perfil/plantillas" />} />
        <Route path="fuentes" element={<SourcesHubPage />}>
          <Route index element={<Navigate to="/fuentes/plataformas" replace />} />
          <Route path="empresas" element={<SourcesPage />} />
          <Route path="plataformas" element={<PlatformsPage />} />
          <Route path="correo" element={<EmailAlertsPage />} />
          <Route path="extension" element={<ExtensionPage />} />
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
