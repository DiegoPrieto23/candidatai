import { Outlet } from 'react-router'
import { useTranslation } from 'react-i18next'
import { BuildingsIcon, CompassIcon, EnvelopeSimpleIcon, PuzzlePieceIcon } from '@phosphor-icons/react'
import { PageTabs } from '@/components/PageTabs'

/**
 * «Dónde buscar» (fase 23.3; antes «Fuentes»): de dónde salen tus ofertas. Une las plataformas que recorre tu agente,
 * las empresas objetivo (APIs de ATS y portales), las alertas por correo y el botón del navegador, cada uno en su
 * pestaña con su propia URL.
 */
export function SourcesHubPage() {
  const { t } = useTranslation('platforms', { keyPrefix: 'hub' })
  const { t: tNav } = useTranslation('nav')
  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-6">
      <PageTabs
        label={t('label')}
        className="mx-auto max-w-3xl"
        tabs={[
          { to: '/fuentes/plataformas', label: t('platforms'), icon: CompassIcon },
          { to: '/fuentes/empresas', label: t('companies'), icon: BuildingsIcon },
          { to: '/fuentes/correo', label: tNav('tabs.email'), icon: EnvelopeSimpleIcon },
          { to: '/fuentes/extension', label: t('extension'), icon: PuzzlePieceIcon },
        ]}
      />
      <Outlet />
    </div>
  )
}
