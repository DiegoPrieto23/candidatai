import { type QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Link, Route, Routes } from 'react-router'
import { CompassIcon } from '@phosphor-icons/react'
import { AppShell } from '@/components/AppShell'
import { EmptyState } from '@/components/States'
import { Button } from '@/components/ui/button'
import { TooltipProvider } from '@/components/ui/tooltip'
import { InboxPage } from '@/pages/InboxPage'
import { JobPage } from '@/pages/JobPage'
import { NewJobPage } from '@/pages/NewJobPage'
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
        <Route path="plantillas" element={<TemplatesPage />} />
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
