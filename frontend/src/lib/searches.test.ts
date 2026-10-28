import { describe, expect, it } from 'vitest'
import { buildSearches, canBuildSearches, describeSearch, iconCandidates, platformHome, searchLabel } from '@/lib/searches'

describe('searchLabel', () => {
  it.each([
    ['https://es.indeed.com/jobs?q=data+engineer&l=Madrid%2C+Madrid+provincia', 'data engineer · Madrid'],
    ['https://es.indeed.com/jobs?q=data+analyst&l=Remoto', 'data analyst · Remoto'],
    [
      'https://www.infojobs.net/jobsearch/search-results/list.xhtml?keyword=data%20engineer&provinceIds=33',
      'data engineer · Madrid',
    ],
    [
      'https://www.infojobs.net/jobsearch/search-results/list.xhtml?keyword=analytics%20engineer&teleworkingIds=2',
      'analytics engineer · Remoto',
    ],
    ['https://www.tecnoempleo.com/ofertas-trabajo/?te=data+engineer&pr=,263,', 'data engineer · Madrid'],
    ['https://www.tecnoempleo.com/ofertas-trabajo/?te=data+analyst&en_remoto=1', 'data analyst · Remoto'],
    [
      'https://www.glassdoor.es/Empleo/madrid-data-engineer-empleos-SRCH_IL.0,6_IC2664239_KO7,20.htm',
      'data engineer · Madrid',
    ],
    [
      'https://www.glassdoor.es/Empleo/espa%C3%B1a-analytics-engineer-empleos-SRCH_IL.0,6_IN219_KO7,25.htm?remoteWorkType=1',
      'analytics engineer · Remoto',
    ],
    ['https://www.linkedin.com/jobs/search/?keywords=data&location=Madrid&f_WT=2', 'data · Remoto (Madrid)'],
    ['https://www.getmanfred.com/ofertas-empleo?onlyActive=true', 'Todas las ofertas'],
    ['no es una url', 'Todas las ofertas'],
  ])('%s → %s', (url, label) => {
    expect(searchLabel(url)).toBe(label)
  })
})

describe('platformHome', () => {
  it('saca la página base de la primera búsqueda válida', () => {
    expect(platformHome(['no es url', 'https://www.infojobs.net/jobsearch/x?keyword=a'])).toEqual({
      origin: 'https://www.infojobs.net',
      host: 'infojobs.net',
    })
    expect(platformHome([])).toBeNull()
  })
})

describe('iconCandidates', () => {
  it('prueba primero el icono conocido y después las rutas habituales', () => {
    expect(iconCandidates({ origin: 'https://www.tecnoempleo.com', host: 'tecnoempleo.com' })[0]).toBe(
      'https://www.tecnoempleo.com/graficos/logo_te_192.png',
    )
    expect(iconCandidates({ origin: 'https://www.infojobs.net', host: 'infojobs.net' })).toEqual([
      'https://www.infojobs.net/favicon.ico',
      'https://www.infojobs.net/apple-touch-icon.png',
    ])
    // En un subdominio, también los del dominio principal.
    expect(iconCandidates({ origin: 'https://careers.acme.com', host: 'careers.acme.com' })).toEqual([
      'https://careers.acme.com/favicon.ico',
      'https://careers.acme.com/apple-touch-icon.png',
      'https://acme.com/favicon.ico',
      'https://acme.com/apple-touch-icon.png',
    ])
  })
})

describe('búsquedas desde tu perfil', () => {
  const prefs = {
    roles: ['Data Engineer', 'Analista de datos'],
    locations: { preferred: ['A Coruña', 'Vigo', 'Lugo'], allowed: ['Madrid'] },
    remote_modes: ['remote', 'hybrid'],
  }

  it('cada puesto en tus dos primeras ubicaciones y en remoto', () => {
    expect(buildSearches('linkedin', prefs)).toEqual([
      'https://www.linkedin.com/jobs/search/?keywords=Data%20Engineer&location=A%20Coru%C3%B1a',
      'https://www.linkedin.com/jobs/search/?keywords=Data%20Engineer&location=Vigo',
      'https://www.linkedin.com/jobs/search/?keywords=Data%20Engineer&location=Espa%C3%B1a&f_WT=2',
      'https://www.linkedin.com/jobs/search/?keywords=Analista%20de%20datos&location=A%20Coru%C3%B1a',
      'https://www.linkedin.com/jobs/search/?keywords=Analista%20de%20datos&location=Vigo',
      'https://www.linkedin.com/jobs/search/?keywords=Analista%20de%20datos&location=Espa%C3%B1a&f_WT=2',
    ])
    expect(buildSearches('infojobs', prefs)[0]).toBe('https://www.infojobs.net/ofertas-trabajo/a-coruna?keyword=Data%20Engineer')
    // Tecnoempleo filtra la provincia por id: solo por puesto y en remoto.
    expect(buildSearches('tecnoempleo', prefs)).toEqual([
      'https://www.tecnoempleo.com/ofertas-trabajo/?te=Data%20Engineer&en_remoto=1',
      'https://www.tecnoempleo.com/ofertas-trabajo/?te=Analista%20de%20datos&en_remoto=1',
    ])
  })

  it('lo que se genera se lee como la búsqueda que es', () => {
    for (const platform of ['linkedin', 'infojobs', 'indeed', 'tecnoempleo']) {
      for (const url of buildSearches(platform, prefs)) expect(describeSearch(url).query).toMatch(/^(Data Engineer|Analista de datos)$/)
    }
    expect(searchLabel(buildSearches('indeed', prefs)[2])).toBe('Data Engineer · Remoto')
  })

  it('sin puestos, de un portal desconocido o con ids, nada; y como mucho 10', () => {
    expect(buildSearches('linkedin', { roles: [] })).toEqual([])
    expect(buildSearches('glassdoor', prefs)).toEqual([])
    expect(canBuildSearches('manfred')).toBe(false)
    const many = { roles: Array.from({ length: 8 }, (_, i) => `Rol ${i}`), locations: { preferred: ['Vigo'] } }
    expect(buildSearches('indeed', many)).toHaveLength(8)
    expect(buildSearches('indeed', { ...many, remote_modes: ['remote'] })).toHaveLength(10)
  })
})
