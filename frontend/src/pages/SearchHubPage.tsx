import { Suspense, useId } from 'react'
import { Outlet, useLocation, useNavigate } from 'react-router'
import { useTranslation } from 'react-i18next'
import {
  BuildingsIcon,
  CompassIcon,
  EnvelopeSimpleIcon,
  MagnifyingGlassIcon,
  GlobeIcon,
  PuzzlePieceIcon,
} from '@phosphor-icons/react'
import { Hint } from '@/components/Hint'
import { PageErrorBoundary } from '@/components/PageErrorBoundary'
import { PageTabs } from '@/components/PageTabs'
import { Skeleton } from '@/components/ui/skeleton'
import { SearchPage } from '@/pages/SearchPage'

/** `/buscar/ajustes` es «Buscar» con «Más ajustes» desplegado. */
const MORE = '/buscar/ajustes'

/**
 * La pestaña «Buscar»: lo que buscas y cómo lanzarlo. Si «Más ajustes» está abierto lo dice la ruta;
 * abrirlo o plegarlo la cambia sin mover la página (`state.stay`) ni volver a montarla (las dos rutas
 * cuelgan de esta).
 */
export function SearchSection() {
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const { t } = useTranslation('search')
  const title = useId()
  const onMore = (open: boolean) => navigate(open ? MORE : '/buscar', { replace: true, state: { stay: true } })
  return (
    <section aria-labelledby={title}>
      {/* Los encabezados de la pestaña cuelgan de este (la búsqueda usa `h3`). */}
      <h2 id={title} className="sr-only">
        {t('nav.search')}
      </h2>
      <SearchPage moreOpen={pathname.startsWith(MORE)} onMore={onMore} />
    </section>
  )
}

/** La pestaña «Dónde buscar»: portales, empresas, correo y extensión, cada uno en su subpestaña con su URL. */
export function WhereSection() {
  const { t } = useTranslation('platforms', { keyPrefix: 'hub' })
  const { t: tNav } = useTranslation('nav')
  const { t: tSearch } = useTranslation('search')
  const title = useId()
  return (
    <section aria-labelledby={title} className="grid grid-cols-[minmax(0,1fr)] gap-5">
      {/* Cada vista se titula con un `h3`: cuelga de este. */}
      <h2 id={title} className="sr-only">
        {tSearch('nav.where')}
      </h2>
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
      <div className="min-w-0">
        <Suspense fallback={<Skeleton className="h-64" />}>
          <Outlet />
        </Suspense>
      </div>
    </section>
  )
}

/**
 * «Buscar ofertas», como «Mi perfil»: el título y dos pestañas, cada una con su URL. «Buscar» (lo que
 * buscas y cómo lanzarlo) y «Dónde buscar» (portales, empresas, correo y extensión). Las rutas de antes
 * (`/buscar/ajustes`, `/fuentes/…`) siguen llevando a su pestaña.
 */
export function SearchHubPage() {
  const { t } = useTranslation('search')
  const { pathname } = useLocation()
  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-6 animate-in fade-in duration-300">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{t('title')}</h1>
        <p className="mt-1.5 text-sm text-muted-foreground">
          {t('intro')} <Hint text={t('introHint')} label={t('introHintLabel')} />
        </p>
      </div>
      <PageTabs
        label={t('nav.label')}
        tabs={[
          { to: '/buscar', label: t('nav.search'), icon: MagnifyingGlassIcon },
          { to: '/fuentes', label: t('nav.where'), icon: GlobeIcon },
        ]}
      />
      {/* Si la pestaña falla, el título y las pestañas siguen: puedes ir a la otra. */}
      <div className="min-w-0">
        <PageErrorBoundary path={pathname}>
          <Suspense fallback={<Skeleton className="h-64" />}>
            <Outlet />
          </Suspense>
        </PageErrorBoundary>
      </div>
    </div>
  )
}
