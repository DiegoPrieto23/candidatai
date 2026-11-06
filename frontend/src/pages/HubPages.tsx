import { Outlet } from 'react-router'
import { useTranslation } from 'react-i18next'
import {
  CompassIcon,
  FileTextIcon,
  GraduationCapIcon,
  LightningIcon,
  MagnifyingGlassIcon,
  SlidersHorizontalIcon,
  ListChecksIcon,
  TrayIcon,
  UserCircleIcon,
} from '@phosphor-icons/react'
import { useStatus } from '@/api/queries'
import { PageTabs } from '@/components/PageTabs'

/**
 * Las secciones de la barra lateral con varias páginas: cada una, en su pestaña y con su URL. Solo
 * está montada la página de la pestaña abierta, así que sus atajos de teclado no chocan entre sí.
 */

/** «Bandeja de ofertas»: todas las ofertas, y las dos etapas que se repasan una a una con el teclado. */
export function InboxHubPage() {
  const { t } = useTranslation('nav', { keyPrefix: 'tabs' })
  const byStage = useStatus().data?.by_stage
  const toReview = byStage?.pending_triage ?? 0
  const toComplete = byStage?.pending_detail ?? 0
  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-6">
      <PageTabs
        label={t('inboxLabel')}
        tabs={[
          { to: '/bandeja', label: t('inbox'), icon: TrayIcon, end: true },
          {
            to: '/bandeja/por-completar',
            label: t('complete'),
            icon: LightningIcon,
            count: toComplete,
            countLabel: t('withCount', { label: t('complete'), count: toComplete }),
          },
          {
            to: '/bandeja/revision',
            label: t('review'),
            icon: ListChecksIcon,
            count: toReview,
            countLabel: t('withCount', { label: t('review'), count: toReview }),
          },
        ]}
      />
      <div className="min-w-0">
        <Outlet />
      </div>
    </div>
  )
}

/** «Buscar ofertas»: lanzar una búsqueda, decidir qué buscas y dónde. */
export function SearchHubPage() {
  const { t } = useTranslation('nav', { keyPrefix: 'tabs' })
  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-6">
      <PageTabs
        label={t('searchLabel')}
        tabs={[
          { to: '/buscar', label: t('search'), icon: MagnifyingGlassIcon, end: true },
          { to: '/buscar/ajustes', label: t('searchSettings'), icon: SlidersHorizontalIcon },
          { to: '/fuentes', label: t('sources'), icon: CompassIcon },
        ]}
      />
      <div className="min-w-0">
        <Outlet />
      </div>
    </div>
  )
}

/** «Mi perfil»: lo que alimenta todo lo demás, lo que tus ofertas piden y no tienes y cómo se ve tu CV. */
export function ProfileHubPage() {
  const { t } = useTranslation('nav', { keyPrefix: 'tabs' })
  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-6">
      <PageTabs
        label={t('profileLabel')}
        tabs={[
          { to: '/perfil', label: t('profile'), icon: UserCircleIcon, end: true },
          { to: '/perfil/skills', label: t('skills'), icon: GraduationCapIcon },
          { to: '/perfil/plantillas', label: t('templates'), icon: FileTextIcon },
        ]}
      />
      <div className="min-w-0">
        <Outlet />
      </div>
    </div>
  )
}
