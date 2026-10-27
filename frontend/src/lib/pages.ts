/**
 * Cada página en su propio chunk: el arranque descarga solo la barra lateral y «Hoy», y el resto se
 * pide al entrar en ella o antes, al pasar el ratón o enfocar su enlace (`preloadRoute`).
 */
import { createElement, lazy, type ComponentType } from 'react'

type Loader = () => Promise<ComponentType>

function lazyPage(load: Loader) {
  let pending: Promise<ComponentType> | undefined
  let loaded: ComponentType | undefined
  const preload = () => {
    pending ??= load().then(
      (Component) => (loaded = Component),
      (error: unknown) => {
        pending = undefined // sin red: el siguiente intento vuelve a pedirla
        throw error
      },
    )
    return pending
  }
  const Lazy = lazy(() => preload().then((Component) => ({ default: Component })))
  // Ya descargada (al pasar por su enlace o en una visita anterior), se pinta sin pasar por el
  // `Suspense`: ni un fotograma con el esqueleto.
  const Page = () => createElement(loaded ?? Lazy)
  return { Page, preload }
}

export const pages = {
  inbox: lazyPage(() => import('@/pages/InboxPage').then((m) => m.InboxPage)),
  job: lazyPage(() => import('@/pages/JobPage').then((m) => m.JobPage)),
  newJob: lazyPage(() => import('@/pages/NewJobPage').then((m) => m.NewJobPage)),
  triage: lazyPage(() => import('@/pages/TriagePage').then((m) => m.TriagePage)),
  processes: lazyPage(() => import('@/pages/ProcessesPage').then((m) => m.ProcessesPage)),
  calendar: lazyPage(() => import('@/pages/CalendarPage').then((m) => m.CalendarPage)),
  replies: lazyPage(() => import('@/pages/RepliesPage').then((m) => m.RepliesPage)),
  // Recharts pesa: va en el chunk del embudo.
  funnel: lazyPage(() => import('@/pages/FunnelPage').then((m) => m.FunnelPage)),
  skills: lazyPage(() => import('@/pages/SkillsPage').then((m) => m.SkillsPage)),
  alerts: lazyPage(() => import('@/pages/AlertsPage').then((m) => m.AlertsPage)),
  templates: lazyPage(() => import('@/pages/TemplatesPage').then((m) => m.TemplatesPage)),
  profile: lazyPage(() => import('@/pages/ProfilePage').then((m) => m.ProfilePage)),
  sourcesHub: lazyPage(() => import('@/pages/SourcesHubPage').then((m) => m.SourcesHubPage)),
  sources: lazyPage(() => import('@/pages/SourcesPage').then((m) => m.SourcesPage)),
  platforms: lazyPage(() => import('@/pages/PlatformsPage').then((m) => m.PlatformsPage)),
  agent: lazyPage(() => import('@/pages/AgentPage').then((m) => m.AgentPage)),
}

type PageKey = keyof typeof pages

/** Las páginas que pinta cada ruta (`/fuentes` abre la de plataformas dentro de la suya). */
const ROUTES: [prefix: string, keys: PageKey[]][] = [
  ['/bandeja', ['inbox']],
  ['/jobs/', ['job']],
  ['/nueva', ['newJob']],
  ['/por-revisar', ['triage']],
  ['/procesos', ['processes']],
  ['/calendario', ['calendar']],
  ['/respuestas', ['replies']],
  ['/embudo', ['funnel']],
  ['/skills', ['skills']],
  ['/alertas', ['alerts']],
  ['/plantillas', ['templates']],
  ['/perfil', ['profile']],
  ['/fuentes/empresas', ['sourcesHub', 'sources']],
  ['/fuentes', ['sourcesHub', 'platforms']],
  ['/agente', ['agent']],
]

/** Descarga todas las páginas (los tests, para pintarlas sin esperar). */
export function preloadAllPages(): Promise<unknown> {
  return Promise.all(Object.values(pages).map((page) => page.preload()))
}

/** Empieza a descargar la página de `to` (un enlace de la app) sin esperar al clic. */
export function preloadRoute(to: string): void {
  const keys = ROUTES.find(([prefix]) => to.startsWith(prefix))?.[1] ?? []
  for (const key of keys) void pages[key].preload().catch(() => undefined)
}
