import { Suspense, useEffect, useRef, useState, type MouseEvent, type RefObject } from 'react'
import { Link, Outlet, useLocation, useNavigationType, type Location } from 'react-router'
import { useTranslation } from 'react-i18next'
import { BuildingsIcon, CompassIcon, EnvelopeSimpleIcon, PuzzlePieceIcon } from '@phosphor-icons/react'
import { Hint } from '@/components/Hint'
import { blockAnchor } from '@/components/profile/editor'
import type { SectionFocus } from '@/lib/searchFocus'
import { PageErrorBoundary } from '@/components/PageErrorBoundary'
import { PageTabs } from '@/components/PageTabs'
import { Skeleton } from '@/components/ui/skeleton'
import { pages } from '@/lib/pages'
import { cn } from '@/lib/utils'
import { SearchPage } from '@/pages/SearchPage'
import { SearchSettingsPage } from '@/pages/SearchSettingsPage'

type Section = 'search' | 'settings' | 'where'

/** Cada sección, su ancla y la ruta que lleva a ella (las de siempre siguen funcionando). */
const SECTIONS: readonly { id: Section; anchor: string; to: string }[] = [
  { id: 'search', anchor: 'buscar', to: '/buscar' },
  { id: 'settings', anchor: 'ajustes', to: '/buscar/ajustes' },
  { id: 'where', anchor: 'donde', to: '/fuentes/plataformas' },
]

/** Las vistas de «Dónde buscar», cada una con su URL de siempre. */
const WHERE = [
  { to: '/fuentes/plataformas', page: pages.platforms.Page },
  { to: '/fuentes/empresas', page: pages.sources.Page },
  { to: '/fuentes/correo', page: pages.emailAlerts.Page },
  { to: '/fuentes/extension', page: pages.extension.Page },
] as const

function sectionOf(pathname: string): Section {
  if (pathname.startsWith('/buscar/ajustes')) return 'settings'
  if (pathname.startsWith('/buscar/donde') || pathname.startsWith('/fuentes')) return 'where'
  return 'search'
}

function anchorOf(section: Section): string {
  return SECTIONS.find((s) => s.id === section)!.anchor
}

const FOCUS: Record<SectionFocus, string> = {
  // La caja de «Puestos que buscas», en el primer bloque de la configuración.
  roles: `#${blockAnchor('search-role')} input`,
}

function focusOf(state: unknown): string | null {
  const focus = (state as { focus?: unknown } | null)?.focus
  return typeof focus === 'string' && focus in FOCUS ? FOCUS[focus as SectionFocus] : null
}

/**
 * Lleva la sección de la URL arriba del todo. Lo de encima carga después (portales, perfil) y la
 * empujaría hacia abajo: mientras crece, se vuelve a alinear, hasta que tú mueves la página o pasan
 * unos segundos. Va por la clave de la navegación, no por la ruta: un enlace a la misma URL (estás en
 * `/buscar/ajustes` pero has subido) también baja. Con `state.focus`, deja además el cursor en ese
 * campo en cuanto aparece.
 */
function useScrollToSection(location: Location, container: RefObject<HTMLElement | null>) {
  const { pathname, key, state } = location
  // Atrás y Adelante traen el `state` de entonces: llevan a la sección, pero no vuelven a enfocar.
  const navigation = useNavigationType()
  // La navegación de la vez anterior: en modo estricto el efecto corre dos veces con la misma.
  const previous = useRef<string | null>(null)
  useEffect(() => {
    const section = sectionOf(pathname)
    const unchanged = previous.current === null || previous.current === key
    previous.current = key
    const focus = unchanged || navigation === 'POP' ? null : focusOf(state)
    // Al abrir «Buscar» desde otra página, AppShell ya ha subido arriba del todo.
    if (section === 'search' && unchanged) return
    const target = () => document.getElementById(anchorOf(section))
    let active = true
    let pending = focus
    const align = () => {
      if (!active) return
      target()?.scrollIntoView({ block: 'start' })
      const field = pending ? document.querySelector<HTMLElement>(pending) : null
      if (field) {
        field.focus({ preventScroll: true })
        pending = null
      }
    }
    align()
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(align)
    if (container.current) observer?.observe(container.current)
    const stop = () => {
      active = false
      observer?.disconnect()
    }
    const timer = window.setTimeout(stop, 3000)
    const events = ['wheel', 'touchstart', 'keydown', 'pointerdown'] as const
    for (const name of events) window.addEventListener(name, stop, { once: true, passive: true })
    return () => {
      stop()
      window.clearTimeout(timer)
      for (const name of events) window.removeEventListener(name, stop)
    }
    // `state` y el tipo de navegación van con `key`: cada navegación trae los suyos.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, pathname, container])
}

/** La sección que tienes delante: la última cuyo principio ya ha pasado por debajo del índice. */
function useVisibleSection(initial: Section): Section {
  const [visible, setVisible] = useState(initial)
  // Al cambiar la URL, manda la sección de la URL (ajuste durante el render, sin efecto).
  const [from, setFrom] = useState(initial)
  if (from !== initial) {
    setFrom(initial)
    setVisible(initial)
  }
  useEffect(() => {
    const onScroll = () => {
      let current: Section = 'search'
      for (const { id, anchor } of SECTIONS) {
        const top = document.getElementById(anchor)?.getBoundingClientRect().top
        if (top !== undefined && top <= 120) current = id
      }
      // Al final de la página, la última, aunque su principio no llegue arriba.
      if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4) current = 'where'
      setVisible(current)
    }
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])
  return visible
}

/** «Dónde buscar»: portales, empresas, correo y extensión, cada uno en su vista con su URL. */
function WhereSection({ pathname }: { pathname: string }) {
  const { t } = useTranslation('platforms', { keyPrefix: 'hub' })
  const { t: tNav } = useTranslation('nav')
  const current = WHERE.find((w) => pathname.startsWith(w.to)) ?? WHERE[0]
  const Page = current.page
  return (
    <div className="grid gap-5">
      <PageTabs
        label={t('label')}
        level="sub"
        tabs={[
          { to: '/fuentes/plataformas', label: t('platforms'), icon: CompassIcon },
          { to: '/fuentes/empresas', label: t('companies'), icon: BuildingsIcon },
          { to: '/fuentes/correo', label: tNav('tabs.email'), icon: EnvelopeSimpleIcon },
          { to: '/fuentes/extension', label: t('extension'), icon: PuzzlePieceIcon },
        ]}
      />
      <Suspense fallback={<Skeleton className="h-64" />}>
        <Page />
      </Suspense>
    </div>
  )
}

/**
 * «Buscar ofertas», en una página: lanzar la búsqueda, su configuración y dónde se busca, con un
 * índice fijo arriba. Las rutas de antes (`/buscar/ajustes`, `/fuentes/…`) abren esta misma página en
 * su sección: van todas bajo una misma ruta de diseño, así que cambiar de sección no la vuelve a montar.
 */
export function SearchHubPage() {
  const { t } = useTranslation('search')
  const location = useLocation()
  const { pathname } = location
  const container = useRef<HTMLDivElement>(null)
  const section = sectionOf(pathname)
  const visible = useVisibleSection(section)
  useScrollToSection(location, container)
  // «Dónde buscar» en el índice vuelve a la vista que tenías abierta.
  const [lastWhere, setLastWhere] = useState('/fuentes/plataformas')
  if (pathname.startsWith('/fuentes/') && pathname !== lastWhere) setLastWhere(pathname)

  const jump = (event: MouseEvent, id: Section) => {
    // Ya en esa URL, el enlace no cambia nada: se baja a mano.
    if (sectionOf(pathname) === id) {
      event.preventDefault()
      document.getElementById(anchorOf(id))?.scrollIntoView({ block: 'start' })
    }
    // Con el teclado, el siguiente Tab sigue en la sección elegida, no en el índice.
    requestAnimationFrame(() => document.getElementById(anchorOf(id))?.focus({ preventScroll: true }))
  }

  const label = (id: Section) =>
    id === 'search' ? t('nav.search') : id === 'settings' ? t('nav.settings') : t('nav.where')

  return (
    <div ref={container} className="animate-in fade-in duration-300">
      <div className="mb-4">
        <h1 className="text-2xl font-semibold tracking-tight">{t('title')}</h1>
        <p className="mt-1.5 text-sm text-muted-foreground">
          {t('intro')} <Hint text={t('introHint')} label={t('introHintLabel')} />
        </p>
      </div>

      <nav
        aria-label={t('nav.label')}
        className="z-10 -mx-4 mb-6 border-b bg-background/85 px-4 backdrop-blur-md supports-[backdrop-filter]:bg-background/70 sm:-mx-8 sm:px-8 lg:sticky lg:top-0"
      >
        <ul className="scroll-row -mb-px flex max-w-full gap-5">
          {SECTIONS.map(({ id, to }) => (
            <li key={id} className="flex-none">
              <Link
                to={id === 'where' ? lastWhere : to}
                replace
                onClick={(event) => jump(event, id)}
                aria-current={visible === id ? 'location' : undefined}
                className={cn(
                  'block border-b-2 pt-3 pb-2.5 text-sm whitespace-nowrap transition-colors outline-none',
                  'focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset',
                  visible === id
                    ? 'border-primary font-medium text-foreground'
                    : 'border-transparent text-muted-foreground hover:border-foreground/20 hover:text-foreground',
                )}
              >
                {label(id)}
              </Link>
            </li>
          ))}
        </ul>
      </nav>

      {/* Cada sección con su red: si una falla, las otras dos siguen. */}
      <div className="grid gap-14">
        {/* Sin barra lateral, la cabecera de la app va fija arriba: las secciones paran por debajo. */}
        <section id="buscar" tabIndex={-1} aria-labelledby="buscar-title" className="outline-none scroll-mt-32 lg:scroll-mt-16">
          <h2 id="buscar-title" className="sr-only">
            {t('nav.search')}
          </h2>
          <PageErrorBoundary path={pathname}>
            <SearchPage />
          </PageErrorBoundary>
        </section>
        <section id="ajustes" tabIndex={-1} aria-labelledby="ajustes-title" className="outline-none scroll-mt-32 lg:scroll-mt-16">
          <h2 id="ajustes-title" className="text-xl font-semibold tracking-tight">
            {t('nav.settings')}
          </h2>
          <PageErrorBoundary path={pathname}>
            <SearchSettingsPage />
          </PageErrorBoundary>
        </section>
        <section id="donde" tabIndex={-1} aria-labelledby="donde-title" className="outline-none scroll-mt-32 lg:scroll-mt-16">
          <h2 id="donde-title" className="mb-4 text-xl font-semibold tracking-tight">
            {t('nav.where')}
          </h2>
          <PageErrorBoundary path={pathname}>
            <WhereSection pathname={pathname} />
          </PageErrorBoundary>
        </section>
      </div>
      {/* Las rutas hijas no pintan nada: solo dicen la sección (y `/fuentes` lleva a la primera vista). */}
      <Outlet />
    </div>
  )
}
