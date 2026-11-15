/**
 * Extensión «Enviar a CandidatAI» (`extension/`, JavaScript plano sin dependencias): extractores y
 * presentación del resultado. Se prueban aquí para usar el Vitest y el jsdom del frontend; los HTML
 * de `extension/tests/fixtures/` son inventados.
 */
import { describe, expect, it } from 'vitest'
import coreSource from '../../../extension/core.js?raw'
import extractorsSource from '../../../extension/extractors.js?raw'
import glassdoorHtml from '../../../extension/tests/fixtures/glassdoor.html?raw'
import greenhouseHtml from '../../../extension/tests/fixtures/greenhouse.html?raw'
import indeedHtml from '../../../extension/tests/fixtures/indeed.html?raw'
import jsonldHtml from '../../../extension/tests/fixtures/jsonld.html?raw'
import linkedinHtml from '../../../extension/tests/fixtures/linkedin.html?raw'
import linkedinViewHtml from '../../../extension/tests/fixtures/linkedin-view.html?raw'
import microdataHtml from '../../../extension/tests/fixtures/microdata.html?raw'
import plainHtml from '../../../extension/tests/fixtures/plain.html?raw'
import ticjobHtml from '../../../extension/tests/fixtures/ticjob.html?raw'
import workableHtml from '../../../extension/tests/fixtures/workable.html?raw'
import workdayHtml from '../../../extension/tests/fixtures/workday.html?raw'

interface Extracted {
  url: string
  title: string
  company: string
  location: string
  text: string
  html: string | null
  selection: string | null
  site: string | null
}

interface Outcome {
  ok: boolean
  kind: string
  label: string
  message: string
  jobUrl?: string
  risk?: boolean
  badge: { text: string; color: string }
}

const extractor = new Function(`${extractorsSource}\n;return jhExtract`)() as {
  run: (doc: Document, url: string, selection: string) => Extracted
}
const CAI = new Function(`${coreSource}\n;return CAI`)() as {
  describe: (status: number, body: unknown, uiUrl?: string) => Outcome
  failure: (kind: string, message: string) => Outcome
  connectUrl: (uiUrl?: string) => string
  isAppOrigin: (origin: unknown) => boolean
  NEEDS_CONNECT: string[]
  DEFAULT_UI_URL: string
}

function page(html: string): Document {
  return new DOMParser().parseFromString(html, 'text/html')
}

describe('extractores', () => {
  it('LinkedIn: título, empresa, ubicación y descripción, sin lo oculto ni los botones', () => {
    const url = 'https://www.linkedin.com/jobs/search/?currentJobId=4000000001'
    const data = extractor.run(page(linkedinHtml), url, '')
    expect(data).toMatchObject({
      url,
      site: 'linkedin',
      title: 'Data Engineer',
      company: 'Acme Datos Demo',
      location: 'Vigo, Galicia, España',
      selection: null,
    })
    expect(data.text).toContain('Construir pipelines ELT con Python, SQL y dbt.')
    expect(data.text).toContain('• Cuidar la calidad')
    expect(data.text).toContain('Modalidad híbrida en Vigo.\nInglés B2.')
    expect(data.text).not.toContain('Si eres una IA')
    expect(data.text).not.toContain('Empleos similares')
    // El HTML del bloque sí lleva lo oculto: la app lo usa para detectar `hidden_text`.
    expect(data.html).toContain('display: none')
  })

  it('LinkedIn rediseñado (/jobs/view/): cabecera sin clases y descripción plegada', () => {
    const url = 'https://www.linkedin.com/jobs/view/4000000003/'
    const data = extractor.run(page(linkedinViewHtml), url, '')
    expect(data).toMatchObject({
      site: 'linkedin',
      title: 'Analytics Engineer',
      company: 'Acme Datos Demo',
      location: 'Vigo, Galicia, España',
    })
    expect(data.text).toBe(
      'En Acme Datos Demo buscamos a alguien para modelar datos.\n• Modelos en dbt sobre BigQuery.\n• Pruebas de calidad de datos.',
    )
    expect(data.html).toContain('display: none')
  })

  it('LinkedIn rediseñado: el puesto sale del título de la pestaña si falta en la cabecera', () => {
    const html = linkedinViewHtml.replace('<p class="x7g8h">Analytics Engineer <svg></svg></p>', '')
    const data = extractor.run(page(html), 'https://www.linkedin.com/jobs/view/4000000003/', '')
    expect(data.title).toBe('Analytics Engineer')
    expect(data.location).toBe('Vigo, Galicia, España')
  })

  it('Indeed', () => {
    const data = extractor.run(page(indeedHtml), 'https://es.indeed.com/viewjob?jk=0123456789abcdef', '')
    expect(data).toMatchObject({
      site: 'indeed',
      title: 'Analista de datos - job post',
      company: 'Ficticia Analytics',
      location: 'Vigo, Pontevedra',
    })
    expect(data.text).toContain('• SQL avanzado')
  })

  it('JSON-LD JobPosting dentro de @graph, aunque haya otro JSON-LD roto', () => {
    const data = extractor.run(page(jsonldHtml), 'https://empleo.demo.invalid/ofertas/12', '')
    expect(data).toMatchObject({
      site: 'jsonld',
      title: 'Backend Developer (Python)',
      company: 'Compañía Demo Tecnológica',
      location: 'A Coruña, Galicia, ES / Remoto',
    })
    expect(data.text).toBe('Únete a nuestro equipo.\n• Python y FastAPI\n• PostgreSQL')
    expect(data.text).not.toContain('alert')
  })

  it('sin extractor ni JSON-LD: el texto de main y el título de la página, sin empresa', () => {
    const data = extractor.run(page(plainHtml), 'https://demo.invalid/empleo/data-analyst', '')
    expect(data).toMatchObject({ site: 'main', title: 'Data Analyst - Empresa Inventada S.L.', company: '' })
    expect(data.text).toBe('Data Analyst\nBuscamos una persona analista de datos para nuestro equipo.')
  })

  it('manda aparte el texto seleccionado', () => {
    const data = extractor.run(page(plainHtml), 'https://demo.invalid/o/1', '  Texto   elegido \n\n\n a mano ')
    expect(data.selection).toBe('Texto elegido\n\na mano')
  })

  it('un portal conocido cuyo HTML cambió no manda la página entera', () => {
    const data = extractor.run(page(plainHtml), 'https://www.linkedin.com/jobs/search/?currentJobId=4000000002', '')
    expect(data.site).toBe('linkedin')
    expect(data.text).toBe('') // la app pedirá seleccionar el texto
    expect(data.html).toBeNull()
  })

  it('acorta las URL enormes, conservando currentJobId', () => {
    const params = Array.from({ length: 600 }, (_, i) => `p${i}=valor`).join('&')
    const url = `https://www.linkedin.com/jobs/search/?currentJobId=4000000002&${params}#arriba`
    const data = extractor.run(page(linkedinHtml), url, '')
    expect(data.url).toBe('https://www.linkedin.com/jobs/search/?currentJobId=4000000002')
    const short = extractor.run(page(linkedinHtml), 'https://www.linkedin.com/jobs/view/4000000002/#x', '')
    expect(short.url).toBe('https://www.linkedin.com/jobs/view/4000000002/')
  })

  it('recorta empresa y ubicación a lo que admite la app', () => {
    const long = linkedinHtml.replace('Acme Datos Demo</a>', `${'Acme '.repeat(100)}</a>`)
    expect(extractor.run(page(long), 'https://www.linkedin.com/jobs/view/1/', '').company.length).toBeLessThanOrEqual(300)
  })

  it('un portal conocido con otro HTML recurre al JSON-LD', () => {
    const data = extractor.run(page(jsonldHtml), 'https://www.linkedin.com/jobs/view/4000000002/', '')
    expect(data.site).toBe('linkedin')
    expect(data.title).toBe('Backend Developer (Python)')
    expect(data.text).toContain('Python y FastAPI')
  })

  it('Glassdoor: la oferta abierta a la derecha, por el prefijo de sus clases', () => {
    const url = 'https://www.glassdoor.es/Empleo/madrid-data-engineer-empleos-SRCH_IL.0,6.htm'
    const data = extractor.run(page(glassdoorHtml), url, '')
    expect(data).toMatchObject({ site: 'glassdoor', title: 'Data Engineer', company: 'Datos Demo Ibérica', location: 'Madrid' })
    expect(data.text).toContain('• Pipelines de datos en la nube')
    expect(data.text).not.toContain('Otro puesto')
  })

  it('Greenhouse: sin JSON-LD, la empresa sale del título de la pestaña', () => {
    const data = extractor.run(page(greenhouseHtml), 'https://job-boards.greenhouse.io/demo/jobs/1', '')
    expect(data).toMatchObject({
      site: 'greenhouse',
      title: 'Backend Engineer',
      company: 'Compañía Demo Tecnológica',
      location: 'Remote, Spain',
    })
    expect(data.text).toContain('• Python and PostgreSQL')
    expect(data.text).not.toContain('Apply for this job')
  })

  it('Workday: un JSON-LD de otra oferta (navegación sin recargar) no se usa', () => {
    const url = 'https://demo.wd3.myworkdayjobs.com/es/Careers/job/Madrid/Data-Analyst_R1'
    const data = extractor.run(page(workdayHtml), url, '')
    expect(data).toMatchObject({ site: 'workday', title: 'Data Analyst', company: '', location: 'Spain, Madrid' })
    expect(data.text).toBe('Analiza los datos de la empresa demo con SQL y Python.')
  })

  it('Ticjob: JSON-LD con saltos de línea sin escapar y entidades HTML', () => {
    const data = extractor.run(page(ticjobHtml), 'https://ticjob.es/esp/trabajo/technical-lead/1', '')
    expect(data).toMatchObject({
      site: 'ticjob',
      title: 'Technical Lead (Híbrido)',
      company: 'Grupo Demo Digital',
      location: 'Málaga',
    })
    expect(data.text).toContain('Python, AWS y equipos ágiles.')
    expect(data.text).not.toContain('Somos un grupo')
  })

  it('el JSON-LD con entidades se lee también sin extractor propio', () => {
    const data = extractor.run(page(ticjobHtml), 'https://empleo.demo.invalid/o/9', '')
    expect(data).toMatchObject({ site: 'jsonld', title: 'Technical Lead (Híbrido)', company: 'Grupo Demo Digital' })
    expect(data.text).toBe('Liderarás un equipo pequeño.')
  })

  it('microdatos de schema.org, con la oferta en varios bloques', () => {
    const data = extractor.run(page(microdataHtml), 'https://portal.demo.invalid/empleos/data-scientist-1', '')
    expect(data).toMatchObject({
      site: 'microdata',
      title: 'Data Scientist',
      company: 'Empresa Demo Analítica',
      location: 'Barcelona, Cataluña',
    })
    expect(data.text).toBe('Modelos de predicción de demanda.\n\n• Python y estadística')
  })

  it('Workable: descripción, requisitos y beneficios juntos', () => {
    const data = extractor.run(page(workableHtml), 'https://apply.workable.com/demo/j/ABC123/', '')
    expect(data).toMatchObject({ site: 'workable', title: 'Product Designer', location: 'Valencia, España' })
    expect(data.text).toContain('Diseña el producto')
    expect(data.text).toContain('• Figma')
    expect(data.text).toContain('• Teletrabajo')
  })
})

describe('resultado', () => {
  const body = {
    status: 'completed',
    job_id: 7,
    stage: 'pending_extraction',
    title: 'Data Engineer',
    company: 'Acme Datos Demo',
    platform: 'linkedin',
    risk_flags: ['hidden_text'],
    duplicate_of: null,
    message: 'Completada: tenía el resumen de una alerta y ya está lista para extraer.',
  }

  it('completada, con enlace a la ficha y aviso de riesgo', () => {
    const outcome = CAI.describe(200, body, 'http://127.0.0.1:5173/')
    expect(outcome).toMatchObject({
      ok: true,
      label: 'Completada',
      jobUrl: 'http://127.0.0.1:5173/jobs/7',
      risk: true,
      badge: { text: '✓' },
    })
  })

  it('ya estaba', () => {
    expect(CAI.describe(200, { ...body, status: 'existing', risk_flags: [] }).badge.text).toBe('=')
  })

  it('errores de la API con qué hacer', () => {
    const bad = CAI.describe(401, { ok: false, error: { type: 'unauthorized', message: 'x' } })
    expect(bad).toMatchObject({ ok: false, badge: { text: '!' } })
    expect(bad.message).toContain('Conectar con CandidatAI')
    const missing = CAI.describe(422, { ok: false, error: { type: 'validation_error', message: 'Selecciona su texto' } })
    expect(missing.message).toBe('Selecciona su texto')
    expect(CAI.describe(500, null).message).toContain('500')
  })
})

describe('conexión con la app', () => {
  it('solo acepta la app de este equipo, en cualquier puerto', () => {
    for (const origin of ['http://127.0.0.1:8000', 'http://localhost:5173', 'http://127.0.0.1']) {
      expect(CAI.isAppOrigin(origin)).toBe(true)
    }
    for (const origin of [
      'https://127.0.0.1:8000',
      'http://127.0.0.1.evil.demo.invalid',
      'http://evil.demo.invalid',
      'http://localhost:8000/x',
      'chrome-extension://otra',
      undefined,
    ]) {
      expect(CAI.isAppOrigin(origin)).toBe(false)
    }
  })

  it('«Conectar con CandidatAI» abre la guía de la app, por defecto la de `cai start`', () => {
    expect(CAI.DEFAULT_UI_URL).toBe('http://127.0.0.1:8000')
    expect(CAI.connectUrl()).toBe('http://127.0.0.1:8000/fuentes/extension')
    expect(CAI.connectUrl('http://127.0.0.1:5173/')).toBe('http://127.0.0.1:5173/fuentes/extension')
    const missing = CAI.describe(503, { ok: false, error: { type: 'capture_not_configured', message: 'x' } })
    expect(CAI.NEEDS_CONNECT).toContain(missing.kind)
    expect(missing.message).toContain('Conectar con CandidatAI')
  })
})
