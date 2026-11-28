import type { Schemas } from '@/api/client'
import { i18n } from '@/lib/i18n'

export type JobSite = NonNullable<Schemas['JobRow']['site']>

/**
 * Fase 48.4: lo que dice el botón que abre la oferta publicada, según la web en la que está:
 * «Ver en LinkedIn», «Ver en el portal de Acme» (un ATS) o, en otra web, «Abrir la oferta
 * publicada».
 */
export function viewLabel(site: JobSite | null | undefined, company: string): string {
  if (site?.kind === 'portal' && site.name) return i18n.t('job:site.view.portal', { name: site.name })
  if (site?.kind === 'ats') return i18n.t('job:site.view.ats', { company })
  return i18n.t('job:site.view.web')
}

/** El `title` del botón: el dominio completo y, en un ATS, cuál es («Greenhouse · boards.greenhouse.io»). */
export function siteTitle(site: JobSite | null | undefined): string | undefined {
  if (!site) return undefined
  return site.kind === 'ats' && site.name ? `${site.name} · ${site.host}` : site.host
}

/** La etiqueta accesible de «Abrir» en la Bandeja: «Abrir Data Engineer en LinkedIn». */
export function openJobLabel(site: JobSite | null | undefined, title: string, company: string): string {
  if (site?.kind === 'portal' && site.name) return i18n.t('job:site.open.portal', { title, name: site.name })
  if (site?.kind === 'ats') return i18n.t('job:site.open.ats', { title, company })
  if (site) return i18n.t('job:site.open.web', { title, host: site.host })
  return i18n.t('inbox:quick.openJob', { title })
}
