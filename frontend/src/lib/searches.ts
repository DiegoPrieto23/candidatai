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
