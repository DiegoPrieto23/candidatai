/**
 * Búsquedas de una plataforma (fuentes `agent_browse`) en lenguaje de persona: «data engineer ·
 * Madrid» en vez de la URL. Es una lectura aproximada de los parámetros habituales de los portales;
 * lo que no entiende lo deja fuera y la URL completa sigue a mano.
 */

import { i18n, intlLocale } from '@/lib/i18n'

export type SearchSummary = { query: string | null; place: string | null }

const QUERY_PARAMS = ['q', 'keyword', 'keywords', 'te', 'k', 'query', 'search', 'what']
const PLACE_PARAMS = ['l', 'location', 'where', 'loc', 'city']
const REMOTE_FLAGS: Record<string, (value: string) => boolean> = {
  remoteWorkType: (v) => v === '1',
  en_remoto: (v) => v === '1',
  teleworkingIds: (v) => v !== '',
  remote: (v) => v === 'true' || v === '1',
  f_WT: (v) => v.split(',').includes('2'), // LinkedIn: 2 = en remoto
}
// Ids de provincia de los portales que no la ponen en claro.
const PROVINCES: Record<string, Record<string, string>> = {
  'infojobs.net': { provinceIds: '33', name: 'Madrid' },
  'tecnoempleo.com': { pr: '263', name: 'Madrid' },
}

function host(url: URL): string {
  return url.hostname.replace(/^www\./, '')
}

function clean(text: string): string {
  return text.replace(/[+_-]+/g, ' ').replace(/\s+/g, ' ').trim()
}

function capitalize(text: string): string {
  return text.charAt(0).toLocaleUpperCase(intlLocale()) + text.slice(1)
}

/** Glassdoor: `/Empleo/<lugar>-<puesto>-empleos-SRCH_IL.0,6_..._KO7,20.htm`: los rangos dicen qué es qué. */
function glassdoor(url: URL): SearchSummary | null {
  const match = /\/([^/]+)-empleos-SRCH_(.+)\.htm$/i.exec(decodeURIComponent(url.pathname))
  if (!match) return null
  const [, slug, ranges] = match
  const range = (key: string) => {
    const found = new RegExp(`${key}\\.?(\\d+),(\\d+)`).exec(ranges)
    return found ? clean(slug.slice(Number(found[1]), Number(found[2]))) : null
  }
  const place = range('IL')
  return { query: range('KO'), place: place ? capitalize(place) : null }
}

export function describeSearch(raw: string): SearchSummary {
  let url: URL
  try {
    url = new URL(raw)
  } catch {
    return { query: null, place: null }
  }
  const params = url.searchParams
  const fromPath = host(url).startsWith('glassdoor.') ? glassdoor(url) : null

  const queryParam = QUERY_PARAMS.map((p) => params.get(p)).find((v) => v?.trim())
  const query = queryParam ? clean(queryParam) : (fromPath?.query ?? null)

  const remote = Object.entries(REMOTE_FLAGS).some(([p, test]) => params.has(p) && test(params.get(p) ?? ''))
  const placeParam = PLACE_PARAMS.map((p) => params.get(p)).find((v) => v?.trim())
  const province = PROVINCES[host(url)]
  let place = placeParam ? clean(placeParam.split(',')[0]) : (fromPath?.place ?? null)
  if (!place && province) {
    const [param, id] = Object.entries(province)[0]
    if ((params.get(param) ?? '').split(',').includes(id)) place = province.name
  }
  if (remote)
    place =
      place && !/^(remoto|remote|españa|spain)$/i.test(place)
        ? i18n.t('platforms:searches.remoteIn', { place })
        : i18n.t('platforms:searches.remote')
  return { query, place }
}

/** Texto de la etiqueta: «data engineer · Madrid», o «Todas las ofertas» si no filtra nada. */
export function searchLabel(raw: string): string {
  const { query, place } = describeSearch(raw)
  const parts = [query, place].filter(Boolean)
  return parts.length ? parts.join(' · ') : i18n.t('platforms:searches.all')
}

/** Página base de una plataforma, sacada de sus búsquedas: `https://www.infojobs.net` e `infojobs.net`. */
export function platformHome(urls: string[]): { origin: string; host: string } | null {
  for (const raw of urls) {
    try {
      const url = new URL(raw)
      if (url.protocol === 'https:' || url.protocol === 'http:') return { origin: url.origin, host: host(url) }
    } catch {
      // URL mal formada: probamos con la siguiente.
    }
  }
  return null
}

// Portales que no sirven su icono en `/favicon.ico` (o no dejan cargarlo desde otra web).
const KNOWN_ICONS: Record<string, string> = {
  'tecnoempleo.com': 'https://www.tecnoempleo.com/graficos/logo_te_192.png',
  'glassdoor.es': 'https://www.glassdoor.com/favicon.ico',
  'glassdoor.com': 'https://www.glassdoor.com/favicon.ico',
}

/**
 * Dónde probar el icono de una web, en orden: el conocido, `/favicon.ico` y el de iOS. En un
 * subdominio (`careers.acme.com`), también los del dominio principal.
 */
export function iconCandidates(home: { origin: string; host: string }): string[] {
  const known = KNOWN_ICONS[home.host]
  const origins = [home.origin]
  const base = home.host.split('.').slice(-2).join('.')
  if (base !== home.host) origins.push(`${new URL(home.origin).protocol}//${base}`)
  return [
    ...(known ? [known] : []),
    ...origins.flatMap((origin) => [`${origin}/favicon.ico`, `${origin}/apple-touch-icon.png`]),
  ]
}

// --- Búsquedas desde tu perfil ------------------------------------------------------------------

/** Lo que usa del perfil: `preferences.roles`, `locations` y `remote_modes`. */
export type SearchPreferences = {
  roles?: string[]
  locations?: { preferred?: string[]; allowed?: string[] }
  remote_modes?: string[]
}

const MAX_SEARCHES = 10 // el máximo que admite una plataforma
const MAX_PLACES = 2

function slug(text: string): string {
  return text
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
}

/**
 * Cómo se busca en cada portal conocido: un puesto, en un sitio (o en cualquiera) y, si se puede
 * pedir, solo en remoto. Glassdoor y Manfred no están: sus búsquedas llevan ids que no se pueden
 * sacar de un nombre de ciudad.
 */
// Lo que entienden los portales por «en toda España» y «en remoto». Ya codificados: son
// parámetros de su búsqueda, no textos de la UI.
const ANYWHERE = 'Espa%C3%B1a'
const REMOTE = 'Remoto'

const BUILDERS: Record<string, (role: string, place: string | null, remote: boolean) => string | null> = {
  infojobs: (role, place, remote) =>
    remote
      ? null
      : `https://www.infojobs.net/ofertas-trabajo${place ? `/${slug(place)}` : ''}?keyword=${encodeURIComponent(role)}`,
  tecnoempleo: (role, place, remote) =>
    place ? null : `https://www.tecnoempleo.com/ofertas-trabajo/?te=${encodeURIComponent(role)}${remote ? '&en_remoto=1' : ''}`,
  indeed: (role, place, remote) =>
    `https://es.indeed.com/jobs?q=${encodeURIComponent(role)}&l=${remote ? REMOTE : place ? encodeURIComponent(place) : ANYWHERE}`,
  linkedin: (role, place, remote) =>
    `https://www.linkedin.com/jobs/search/?keywords=${encodeURIComponent(role)}&location=${place ? encodeURIComponent(place) : ANYWHERE}${remote ? '&f_WT=2' : ''}`,
}

export function canBuildSearches(platform: string): boolean {
  return platform in BUILDERS
}

/**
 * Las búsquedas de un portal conocido a partir de tu perfil: cada puesto que buscas, en tus
 * ubicaciones preferidas (las dos primeras) y, si aceptas remoto, en remoto. Como mucho 10, por
 * orden de prioridad de los puestos. Vacío si el portal no se conoce o no hay puestos.
 */
export function buildSearches(platform: string, prefs: SearchPreferences | null | undefined): string[] {
  const build = BUILDERS[platform]
  const roles = (prefs?.roles ?? []).map((r) => r.trim()).filter(Boolean)
  if (!build || roles.length === 0) return []
  const preferred = prefs?.locations?.preferred ?? []
  const places = (preferred.length ? preferred : (prefs?.locations?.allowed ?? [])).slice(0, MAX_PLACES)
  const remote = (prefs?.remote_modes ?? []).includes('remote')
  const urls: string[] = []
  for (const role of roles) {
    const variants: [string | null, boolean][] = [...(places.length ? places : [null]).map((p): [string | null, boolean] => [p, false])]
    if (remote) variants.push([null, true])
    for (const [place, isRemote] of variants) {
      const url = build(role, place, isRemote)
      if (url && !urls.includes(url)) urls.push(url)
    }
  }
  return urls.slice(0, MAX_SEARCHES)
}
