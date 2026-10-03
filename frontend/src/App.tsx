import { type QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Link, Route, Routes } from 'react-router'
import { CompassIcon } from '@phosphor-icons/react'
import { AppShell } from '@/components/AppShell'
import { EmptyState } from '@/components/States'
import { Button } from '@/components/ui/button'
import { TooltipProvider } from '@/components/ui/tooltip'
import { AlertsPage } from '@/pages/AlertsPage'
import { InboxPage } from '@/pages/InboxPage'
import { JobPage } from '@/pages/JobPage'
import { NewJobPage } from '@/pages/NewJobPage'
import { PlatformsPage } from '@/pages/PlatformsPage'
import { ProcessesPage } from '@/pages/ProcessesPage'
import { SourcesPage } from '@/pages/SourcesPage'
import { TemplatesPage } from '@/pages/TemplatesPage'
import { TriagePage } from '@/pages/TriagePage'

function NotFound() {
  return (
    <EmptyState
      icon={<CompassIcon className="size-6" weight="duotone" />}
      title="Esta página no existe"
      action={
        <Button asChild variant="outline">
          <Link to="/">Ir a la bandeja</Link>
        </Button>
      }
    />
  )
}

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<InboxPage />} />
        <Route path="jobs/:id" element={<JobPage />} />
        <Route path="nueva" element={<NewJobPage />} />
        <Route path="triaje" element={<TriagePage />} />
        <Route path="procesos" element={<ProcessesPage />} />
        <Route path="alertas" element={<AlertsPage />} />
        <Route path="plantillas" element={<TemplatesPage />} />
        <Route path="empresas" element={<SourcesPage />} />
        <Route path="plataformas" element={<PlatformsPage />} />
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
