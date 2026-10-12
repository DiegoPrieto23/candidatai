import { lazy, Suspense } from 'react'
import { type QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Link, Navigate, Route, Routes } from 'react-router'
import { CompassIcon } from '@phosphor-icons/react'
import { AppShell } from '@/components/AppShell'
import { EmptyState } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { TooltipProvider } from '@/components/ui/tooltip'
import { AgentPage } from '@/pages/AgentPage'
import { AlertsPage } from '@/pages/AlertsPage'
import { HomePage } from '@/pages/HomePage'
import { InboxPage } from '@/pages/InboxPage'
import { JobPage } from '@/pages/JobPage'
import { NewJobPage } from '@/pages/NewJobPage'
import { PlatformsPage } from '@/pages/PlatformsPage'
import { ProfilePage } from '@/pages/ProfilePage'
import { ProcessesPage } from '@/pages/ProcessesPage'
import { RepliesPage } from '@/pages/RepliesPage'
import { SkillsPage } from '@/pages/SkillsPage'
import { SourcesPage } from '@/pages/SourcesPage'
import { TemplatesPage } from '@/pages/TemplatesPage'
import { TriagePage } from '@/pages/TriagePage'

// Recharts pesa: la página del embudo se descarga solo al abrirla.
const FunnelPage = lazy(() => import('@/pages/FunnelPage').then((m) => ({ default: m.FunnelPage })))

function NotFound() {
  return (
    <EmptyState
      icon={<CompassIcon className="size-6" weight="duotone" />}
      title="Esta página no existe"
      action={
        <Button asChild variant="outline">
          <Link to="/">Ir al inicio</Link>
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
        <Route path="respuestas" element={<RepliesPage />} />
        <Route
          path="embudo"
          element={
            <Suspense fallback={<Skeleton className="h-80 rounded-xl" />}>
              <FunnelPage />
            </Suspense>
          }
        />
        <Route path="skills" element={<SkillsPage />} />
        <Route path="alertas" element={<AlertsPage />} />
        <Route path="plantillas" element={<TemplatesPage />} />
        <Route path="perfil" element={<ProfilePage />} />
        <Route path="empresas" element={<SourcesPage />} />
        <Route path="plataformas" element={<PlatformsPage />} />
        <Route path="agente" element={<AgentPage />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}

export function App({ client }: { client: QueryClient }) {
  return (
    <QueryClientProvider client={client}>
      <TooltipProvider delayDuration={300}>
        <AppRoutes />
      </TooltipProvider>
    </QueryClientProvider>
  )
}
