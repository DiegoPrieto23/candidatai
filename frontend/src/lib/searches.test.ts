import { describe, expect, it } from 'vitest'
import { iconCandidates, platformHome, searchLabel } from '@/lib/searches'

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
    expect(iconCandidates({ origin: 'https://es.indeed.com', host: 'es.indeed.com' })).toEqual([
      'https://es.indeed.com/favicon.ico',
      'https://es.indeed.com/apple-touch-icon.png',
    ])
  })
})
