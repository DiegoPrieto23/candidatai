import { act, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { i18n } from '@/lib/i18n'
import { mockApi, renderApp, status } from '@/test/utils'

/** «Mi perfil» editable (fase 25.7b), con una candidata ficticia como la de `demo/`. */
const PROFILE = {
  schema_version: 1,
  personal: { name: 'Lucía Varela', email: 'lucia@example.com', phone: '+34 600 000 000', city: 'Vigo' },
  headline: 'Data Engineer',
  summary: { es: 'Data Engineer con tres años.' },
  experience: [
    {
      id: 'exp-norte',
      company: 'Norte Consulting',
      role: 'Data Engineer',
      start: '2024-03',
      end: 'present',
      achievements: [
        {
          id: 'a1',
          text: 'Migré 40 procesos ETL a Python.',
          metrics: '-35 % de carga',
          skills: ['Python'],
          source: 'https://github.com/demo/etl',
        },
      ],
    },
    {
      id: 'exp-sur',
      company: 'Sur Analytics',
      role: 'Data Analyst',
      city: 'Vigo',
      start: '2022-01',
      end: '2024-02',
      achievements: [
        { id: 'b1', text: 'Monté el cuadro de mando de ventas.', skills: ['Python'] },
        { id: 'b2', text: 'Automaticé el informe semanal.', skills: ['Python'] },
      ],
    },
  ],
  projects: [{ id: 'prj-tfg', name: 'TFG de predicción', text: 'Modelo de demanda.' }],
  skills: [{ name: 'Python', level: 'F' }],
  basic_skills: ['Docker'],
  languages: [{ language: 'Inglés', level: 'C1 (Cambridge)' }],
  stories: [],
  preferences: {
    roles: ['Data Engineer'],
    seniority_target: ['junior', 'mid'],
    remote_modes: ['remote', 'hybrid'],
    locations: { preferred: ['Vigo'] },
    languages_for_work: ['es', 'en'],
    cv: { photo_policy: { default: true } },
    exclude_signals: ['fixed_term'],
  },
}

const EDITABLE = {
  exists: true,
  file_hash: 'h1',
  profile: PROFILE,
  issues: [],
  profile_version_id: 3,
  undo_available: 1,
  policy_discard_title_keywords: ['sales'],
  policy_years_tolerance: 1,
}

const saved = (section: string, changes: Record<string, unknown> = {}) => ({
  section,
  dry_run: false,
  changed: true,
  diff: '',
  file_hash: 'h2',
  profile_version_id: 4,
  version_created: true,
  rescore_queued: true,
  generated_ids: [],
  warnings: [],
  ...changes,
})

const doc = (section: string, text = '# Título\n<!-- guía -->\n', changes: Record<string, unknown> = {}) => ({
  section,
  path: `contexto/${section}.md`,
  exists: true,
  file_hash: `hash-${section}`,
  text,
  size_bytes: text.length,
  max_bytes: 20480,
  ...changes,
})

const BASE = {
  'GET /status': status(),
  'GET /profile/editable': EDITABLE,
  'GET /context': { context_dir: 'C:/d/contexto', documents_dir: 'C:/d/documentos', files: [], folders: [] },
  'GET /context/estilo-redaccion': doc('estilo-redaccion'),
  'GET /context/perfil-conductual': doc('perfil-conductual'),
  'GET /context/criterios': doc('criterios', '# Criterios\n<!-- Qué no aceptas -->\nSin guardias.\n'),
  'GET /context/narrativa': doc('narrativa', '', { exists: false, file_hash: null }),
  'GET /context/style-samples': [],
  'GET /templates': { templates: [], invalid: [], fallback_template: 'ats-simple' },
  'GET /profile/salary-floor': { salary_floor_eur: 30000, file_hash: 'h1' },
}

async function openTab(name: string) {
  await userEvent.click(await screen.findByRole('tab', { name }))
}

/** La tarjeta de una empresa de «Experiencia» y el botón de su cabecera, que la pliega y despliega. */
async function company(name: string) {
  const block = await screen.findByRole('region', { name: 'Experiencia' })
  const article = await within(block).findByRole('article', { name })
  const header = within(article)
    .getAllByRole('button')
    .find((b) => b.hasAttribute('aria-expanded'))!
  return { article, header }
}

/** Despliega una empresa (arrancan plegadas, fase 27.2). */
async function openCompany(name: string) {
  const { article, header } = await company(name)
  if (header.getAttribute('aria-expanded') !== 'true') await userEvent.click(header)
  return article
}

describe('Mi perfil editable', () => {
  it('guarda un logro con el hash que leyó y enseña el error de un campo en su sitio', async () => {
    const calls = mockApi({
      ...BASE,
      'PUT /profile/sections/experience': (request: Request) =>
        request
          .clone()
          .json()
          .then((body: { content: { start: string }[] }) =>
            body.content[0].start === '2024-03'
              ? saved('experience')
              : {
                  status: 422,
                  body: {
                    ok: false,
                    error: {
                      type: 'validation_error',
                      message: 'Perfil no válido (1 error)',
                      details: [{ field: 'experience.0.start', received: null, reason: 'Debe ser una fecha con formato AAAA-MM.' }],
                    },
                  },
                },
          ),
    })
    renderApp('/perfil')
    await openTab('Experiencia')
    await openCompany('Norte Consulting')
    const achievement = await screen.findByRole('group', { name: 'Migré 40 procesos ETL a Python.' })
    const text = within(achievement).getByLabelText('Logro')
    await userEvent.clear(text)
    await userEvent.type(text, 'Migré 40 procesos ETL a Python sobre Snowflake.')
    const block = screen.getByRole('region', { name: 'Experiencia' })
    expect(within(block).getByText('Sin guardar')).toBeInTheDocument()
    await userEvent.click(within(block).getByRole('button', { name: 'Guardar' }))

    await waitFor(() => expect(calls.some((c) => c.method === 'PUT')).toBe(true))
    const put = calls.find((c) => c.method === 'PUT')
    expect(put?.path).toBe('/profile/sections/experience')
    expect(put?.body).toMatchObject({ file_hash: 'h1', dry_run: false })
    const content = (put?.body as { content: { achievements: { id: string; text: string; metrics: string }[] }[] }).content
    expect(content[0].achievements[0]).toEqual({
      id: 'a1',
      text: 'Migré 40 procesos ETL a Python sobre Snowflake.',
      metrics: '-35 % de carga',
      skills: ['Python'],
      source: 'https://github.com/demo/etl', // lo que el formulario no enseña vuelve tal cual
    })

    // Un error de validación aparece junto a su campo.
    const article = within(block).getByRole('article', { name: 'Norte Consulting' })
    const start = within(article).getByLabelText('Inicio')
    await userEvent.clear(start)
    await userEvent.type(start, '2024-04')
    await userEvent.click(within(block).getByRole('button', { name: 'Guardar' }))
    expect(await within(article).findByText('Debe ser una fecha con formato AAAA-MM.')).toBeInTheDocument()
    expect(within(block).getByRole('alert')).toHaveTextContent('Hay campos que revisar')
    // Escribe mucho texto con `userEvent.type`: con la batería entera en paralelo pasa de 15 s.
  }, 30_000)

  describe('«Experiencia» plegable (fase 27.2)', () => {
    it('arranca plegada y desplegar una empresa no abre las otras', async () => {
      mockApi(BASE)
      renderApp('/perfil')
      await openTab('Experiencia')
      const norte = await company('Norte Consulting')
      const sur = await company('Sur Analytics')
      expect(norte.header).toHaveAttribute('aria-expanded', 'false')
      expect(sur.header).toHaveAttribute('aria-expanded', 'false')
      expect(sur.header).toHaveTextContent('2022-01 – 2024-02 · Vigo · 2 logros')
      expect(screen.queryByLabelText('Empresa')).not.toBeInTheDocument()

      await userEvent.click(norte.header)
      expect(norte.header).toHaveAttribute('aria-expanded', 'true')
      expect(norte.header).toHaveAttribute('aria-controls')
      expect(sur.header).toHaveAttribute('aria-expanded', 'false')
      expect(within(norte.article).getByLabelText('Empresa')).toHaveValue('Norte Consulting')
      // Subir, bajar y borrar quedan fuera del botón de la cabecera.
      expect(within(norte.header).queryByRole('button')).not.toBeInTheDocument()
    })

    it('«Desplegar todo» y «Plegar todo»', async () => {
      mockApi(BASE)
      renderApp('/perfil')
      await openTab('Experiencia')
      const block = await screen.findByRole('region', { name: 'Experiencia' })
      await userEvent.click(within(block).getByRole('button', { name: 'Desplegar todo' }))
      expect((await company('Norte Consulting')).header).toHaveAttribute('aria-expanded', 'true')
      expect((await company('Sur Analytics')).header).toHaveAttribute('aria-expanded', 'true')
      await userEvent.click(within(block).getByRole('button', { name: 'Plegar todo' }))
      expect(within(block).queryByLabelText('Empresa')).not.toBeInTheDocument()
    })

    it('«Añadir empresa» abre la nueva con el foco en «Empresa», y sigue abierta al bajarla', async () => {
      mockApi(BASE)
      renderApp('/perfil')
      await openTab('Experiencia')
      const block = await screen.findByRole('region', { name: 'Experiencia' })
      await userEvent.click(within(block).getByRole('button', { name: 'Añadir empresa' }))
      const fresh = await company('Empresa nueva')
      expect(fresh.header).toHaveAttribute('aria-expanded', 'true')
      expect(within(fresh.article).getByLabelText('Empresa')).toHaveFocus()

      // Con una clave por índice, al bajarla se desplegaría la empresa que ocupa su sitio.
      await userEvent.click(within(fresh.article).getByRole('button', { name: 'Bajar Empresa nueva' }))
      expect((await company('Empresa nueva')).header).toHaveAttribute('aria-expanded', 'true')
      expect((await company('Norte Consulting')).header).toHaveAttribute('aria-expanded', 'false')
    })

    it('reordenar mantiene desplegada la misma empresa', async () => {
      mockApi(BASE)
      renderApp('/perfil')
      await openTab('Experiencia')
      await openCompany('Sur Analytics')
      const norte = await company('Norte Consulting')
      await userEvent.click(within(norte.article).getByRole('button', { name: 'Bajar Norte Consulting' }))
      const articles = within(screen.getByRole('region', { name: 'Experiencia' })).getAllByRole('article')
      expect(articles.map((a) => a.getAttribute('aria-label'))).toEqual(['Sur Analytics', 'Norte Consulting'])
      expect((await company('Sur Analytics')).header).toHaveAttribute('aria-expanded', 'true')
      expect((await company('Norte Consulting')).header).toHaveAttribute('aria-expanded', 'false')
    })

    it('plegar y desplegar conserva un cambio sin guardar', async () => {
      mockApi(BASE)
      renderApp('/perfil')
      await openTab('Experiencia')
      const article = await openCompany('Norte Consulting')
      const role = within(article).getByLabelText('Puesto')
      await userEvent.clear(role)
      await userEvent.type(role, 'Data Lead')
      const { header } = await company('Norte Consulting')
      await userEvent.click(header)
      expect(within(article).queryByLabelText('Puesto')).not.toBeInTheDocument()
      expect(header).toHaveTextContent('Data Lead · Norte Consulting')
      await userEvent.click(header)
      expect(within(article).getByLabelText('Puesto')).toHaveValue('Data Lead')
      expect(within(screen.getByRole('region', { name: 'Experiencia' })).getByText('Sin guardar')).toBeInTheDocument()
    })

    it('un error de validación despliega su empresa y el aviso dice cuántas tienen errores', async () => {
      mockApi({
        ...BASE,
        'PUT /profile/sections/experience': {
          status: 422,
          body: {
            ok: false,
            error: {
              type: 'validation_error',
              message: 'Perfil no válido (1 error)',
              details: [{ field: 'experience.1.achievements.0.text', received: '', reason: 'No puede estar vacío.' }],
            },
          },
        },
      })
      renderApp('/perfil')
      await openTab('Experiencia')
      const article = await openCompany('Norte Consulting')
      await userEvent.type(within(article).getByLabelText('Ciudad'), 'Vigo')
      const block = screen.getByRole('region', { name: 'Experiencia' })
      await userEvent.click(within(block).getByRole('button', { name: 'Guardar' }))

      const sur = await company('Sur Analytics')
      await waitFor(() => expect(sur.header).toHaveAttribute('aria-expanded', 'true'))
      expect(within(sur.article).getByText('No puede estar vacío.')).toBeInTheDocument()
      expect(within(block).getByText('Revisa 1 empresa: tiene errores.')).toBeInTheDocument()
    })

    it('una empresa nueva sigue desplegada después de guardarla', async () => {
      // Tras guardar, la app vuelve a leer el perfil: ya trae la empresa nueva, con su id.
      let profile: Record<string, unknown> = PROFILE
      const calls = mockApi({
        ...BASE,
        'GET /profile/editable': () => ({ ...EDITABLE, profile }),
        'PUT /profile/sections/experience': (request: Request) =>
          request
            .clone()
            .json()
            .then((body: { content: Record<string, unknown>[] }) => {
              profile = { ...PROFILE, experience: [{ ...body.content[0], id: 'exp-nueva' }, ...PROFILE.experience] }
              return saved('experience')
            }),
      })
      renderApp('/perfil')
      await openTab('Experiencia')
      const block = await screen.findByRole('region', { name: 'Experiencia' })
      await userEvent.click(within(block).getByRole('button', { name: 'Añadir empresa' }))
      const fresh = (await company('Empresa nueva')).article
      await userEvent.type(within(fresh).getByLabelText('Empresa'), 'Atlántica')
      await userEvent.type(within(fresh).getByLabelText('Puesto'), 'Data Engineer')
      await userEvent.click(within(block).getByRole('button', { name: 'Guardar' }))

      expect(await within(block).findByText('Guardado')).toBeInTheDocument()
      const body = calls.find((c) => c.method === 'PUT')?.body as { content: Record<string, unknown>[] }
      expect(body.content[0]).not.toHaveProperty('_key') // la clave local no llega al servidor
      await waitFor(() => expect(within(block).queryByText('Sin guardar')).not.toBeInTheDocument())
      expect((await company('Atlántica')).header).toHaveAttribute('aria-expanded', 'true')
    })
  })

  it('una historia STAR no se guarda sin evidencia y el selector las lista por su nombre', async () => {
    const calls = mockApi({ ...BASE, 'PUT /profile/sections/stories': saved('stories') })
    renderApp('/perfil')
    await openTab('Historias STAR')
    const block = await screen.findByRole('region', { name: 'Historias STAR' })
    await userEvent.click(within(block).getByRole('button', { name: 'Añadir historia' }))
    const story = within(block).getByRole('article', { name: 'Historia nueva' })
    await userEvent.type(within(story).getByLabelText('Título de la historia'), 'Migración sin parar')
    await userEvent.type(within(story).getByLabelText('Situación'), 'Cargas lentas.')
    await userEvent.type(within(story).getByLabelText('Tarea'), 'Migrar.')
    await userEvent.type(within(story).getByLabelText('Acción'), 'Por dominios.')
    await userEvent.type(within(story).getByLabelText('Resultado'), '-35 %.')
    const save = within(block).getByRole('button', { name: 'Guardar' })
    expect(save).toBeDisabled()
    expect(within(block).getByText('Elige al menos una evidencia.')).toBeInTheDocument()

    await userEvent.click(within(block).getByRole('checkbox', { name: /Migré 40 procesos ETL/ }))
    expect(within(block).getByRole('checkbox', { name: /TFG de predicción/ })).not.toBeChecked()
    expect(save).toBeEnabled()
    await userEvent.click(save)
    await waitFor(() => expect(calls.some((c) => c.method === 'PUT')).toBe(true))
    const body = calls.find((c) => c.method === 'PUT')?.body as { content: { evidence: string[]; title: string }[] }
    expect(body.content[0]).toMatchObject({ title: 'Migración sin parar', evidence: ['exp-norte/a1'] })
  })

  it('las preferencias de búsqueda enseñan el diff antes de guardar', async () => {
    const diff = '-  roles: [Data Engineer]\n+  roles: [Data Engineer, Analytics Engineer]'
    let current: unknown = EDITABLE
    const calls = mockApi({
      ...BASE,
      // Como el servidor: después de guardar, el perfil ya trae el cambio.
      'GET /profile/editable': () => current,
      'PUT /profile/sections/preferences': (request: Request) =>
        request
          .clone()
          .json()
          .then((body: { dry_run: boolean; content: unknown }) => {
            if (body.dry_run) return saved('preferences', { dry_run: true, diff, file_hash: 'h1', version_created: false })
            current = { ...EDITABLE, file_hash: 'h2', profile: { ...PROFILE, preferences: body.content } }
            return saved('preferences', { diff })
          }),
    })
    renderApp('/perfil')
    await openTab('Búsqueda')
    const block = await screen.findByRole('region', { name: 'Puesto' })
    await userEvent.type(within(block).getByRole('textbox', { name: 'Puestos que buscas' }), 'Analytics Engineer{Enter}')
    await userEvent.click(within(block).getByRole('button', { name: 'Guardar' }))

    expect(await within(block).findByLabelText('Cambios en tu perfil')).toHaveTextContent('Analytics Engineer')
    expect(within(block).getByText(/se recalculan los scores/)).toBeInTheDocument()
    const puts = () => calls.filter((c) => c.method === 'PUT')
    expect(puts()).toHaveLength(1)
    expect(puts()[0].body).toMatchObject({ dry_run: true })
    expect((puts()[0].body as { content: { roles: string[]; cv: unknown } }).content).toMatchObject({
      roles: ['Data Engineer', 'Analytics Engineer'],
      cv: { photo_policy: { default: true } }, // el resto de `preferences`, tal cual
      exclude_signals: ['fixed_term'],
    })

    await userEvent.click(within(block).getByRole('button', { name: 'Guardar estos cambios' }))
    await waitFor(() => expect(puts()).toHaveLength(2))
    expect(puts()[1].body).toMatchObject({ dry_run: false, file_hash: 'h1' })
    expect(await within(block).findByText('Guardado')).toBeInTheDocument()
  })

  it('«Búsqueda» va en cuatro bloques, cada uno con su botón de guardar', async () => {
    mockApi(BASE)
    renderApp('/perfil')
    await openTab('Búsqueda')
    for (const name of ['Puesto', 'Experiencia y sueldo', 'Dónde y cómo', 'Contrato y empresa']) {
      const block = await screen.findByRole('region', { name })
      expect(within(block).getByRole('button', { name: 'Guardar' })).toBeDisabled()
    }
    const role = screen.getByRole('region', { name: 'Puesto' })
    expect(within(role).getByText(/También descartan las de la configuración de la app: sales/)).toBeInTheDocument()
    const where = screen.getByRole('region', { name: 'Dónde y cómo' })
    expect(within(where).getByRole('textbox', { name: 'Solo si no es presencial' })).toBeInTheDocument()
    const years = screen.getByRole('group', { name: 'Años de experiencia que pida la oferta' })
    expect(within(years).getByText(/Se admite 1 año de margen/)).toBeInTheDocument()
  })

  it('en una etiqueta, el campo va antes que las etiquetas: los de una fila empiezan a la misma altura', async () => {
    mockApi(BASE)
    renderApp('/perfil')
    await openTab('Búsqueda')
    const block = await screen.findByRole('region', { name: 'Dónde y cómo' })
    const input = within(block).getByRole('textbox', { name: 'Ubicaciones preferidas' })
    const tags = within(block).getByRole('list', { name: 'Ubicaciones preferidas' })
    expect(input.compareDocumentPosition(tags) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('los años mínimo y máximo se guardan como un rango', async () => {
    const calls = mockApi({ ...BASE, 'PUT /profile/sections/preferences': saved('preferences', { dry_run: true, diff: '+  min_years_required: 2' }) })
    renderApp('/perfil')
    await openTab('Búsqueda')
    const block = await screen.findByRole('region', { name: 'Experiencia y sueldo' })
    await userEvent.type(within(block).getByRole('spinbutton', { name: 'Desde' }), '2')
    await userEvent.type(within(block).getByRole('spinbutton', { name: 'Hasta' }), '5')
    await userEvent.click(within(block).getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(calls.filter((c) => c.method === 'PUT')).toHaveLength(1))
    expect((calls.find((c) => c.method === 'PUT')!.body as { content: unknown }).content).toMatchObject({
      min_years_required: 2,
      max_years_required: 5,
      roles: ['Data Engineer'],
    })
  })

  it('el sueldo mínimo va con candado, se guarda aparte y sin diff', async () => {
    const calls = mockApi({
      ...BASE,
      'PUT /profile/salary-floor': { changed: true, file_hash: 'h2', profile_version_id: 4, rescore_queued: true },
    })
    renderApp('/perfil')
    await openTab('Búsqueda')
    const block = await screen.findByRole('region', { name: 'Experiencia y sueldo' })
    const field = await within(block).findByRole('spinbutton', { name: 'Sueldo mínimo' })
    await waitFor(() => expect(field).toHaveValue(30000))
    expect(within(block).getByText(/tu agente nunca ve esta cifra/)).toBeInTheDocument()
    const button = within(block).getByRole('button', { name: 'Guardar sueldo' })
    expect(button).toBeDisabled()

    await userEvent.clear(field)
    await userEvent.type(field, '-3')
    expect(within(block).getByText(/número entero de euros mayor que 0/)).toBeInTheDocument()
    expect(button).toBeDisabled()

    await userEvent.clear(field)
    await userEvent.type(field, '35000')
    await userEvent.click(button)
    expect(await within(block).findByText('Sueldo guardado')).toBeInTheDocument()
    const put = calls.find((c) => c.method === 'PUT')!
    expect(put.path).toBe('/profile/salary-floor')
    expect(put.body).toEqual({ file_hash: 'h1', salary_floor_eur: 35000 })
    expect(calls.some((c) => c.path === '/profile/sections/preferences')).toBe(false)
  })

  it('si el fichero cambió, el sueldo da conflicto y ofrece «Recargar»', async () => {
    const calls = mockApi({
      ...BASE,
      'PUT /profile/salary-floor': {
        status: 409,
        body: { ok: false, error: { type: 'conflict', message: 'El fichero ha cambiado.', details: [] } },
      },
    })
    renderApp('/perfil')
    await openTab('Búsqueda')
    const block = await screen.findByRole('region', { name: 'Experiencia y sueldo' })
    const field = await within(block).findByRole('spinbutton', { name: 'Sueldo mínimo' })
    await waitFor(() => expect(field).toHaveValue(30000))
    await userEvent.clear(field)
    await userEvent.type(field, '35000')
    await userEvent.click(within(block).getByRole('button', { name: 'Guardar sueldo' }))
    expect(await within(block).findByRole('alert')).toBeInTheDocument()
    const editableReads = () => calls.filter((c) => c.path === '/profile/editable').length
    const before = editableReads()
    await userEvent.click(within(block).getByRole('button', { name: 'Recargar' }))
    await waitFor(() => expect(editableReads()).toBeGreaterThan(before))
    expect(within(block).queryByRole('alert')).not.toBeInTheDocument()
  })

  it('contrato y empresa: casillas, y «Temporal» de exclude_signals se guarda como contract_types', async () => {
    const calls = mockApi({ ...BASE, 'PUT /profile/sections/preferences': saved('preferences', { dry_run: true, diff: 'x' }) })
    renderApp('/perfil')
    await openTab('Búsqueda')
    const block = await screen.findByRole('region', { name: 'Contrato y empresa' })
    // `exclude_signals: [fixed_term]` es no aceptar temporal: «Temporal» sale sin marcar.
    expect(within(block).getByRole('checkbox', { name: 'Indefinido' })).toBeChecked()
    expect(within(block).getByRole('checkbox', { name: 'Temporal' })).not.toBeChecked()
    expect(within(block).getByRole('checkbox', { name: 'Autónomo / freelance' })).toBeChecked()
    expect(within(block).getByRole('checkbox', { name: 'Parcial' })).not.toBeChecked()
    expect(within(block).getAllByText(/Sin marcar nada: cualquiera/)).toHaveLength(2)

    await userEvent.click(within(block).getByRole('checkbox', { name: 'Jornada completa' }))
    await userEvent.click(within(block).getByRole('checkbox', { name: /Excluir consultoras/ }))
    await userEvent.click(within(block).getByRole('checkbox', { name: /Descartar las que no dicen qué empresa contrata/ }))
    await userEvent.click(within(block).getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(calls.filter((c) => c.method === 'PUT')).toHaveLength(1))
    const content = (calls.find((c) => c.method === 'PUT')!.body as { content: Record<string, unknown> }).content
    expect(content).toMatchObject({
      contract_types: ['permanent', 'freelance'],
      employment_types: ['full_time'],
      excluded_employer_kinds: ['consultancy'],
      exclude_signals: ['employer_hidden'],
      roles: ['Data Engineer'],
    })
  })

  it('el nivel de un idioma es un desplegable que conserva el valor libre que ya tenías', async () => {
    mockApi(BASE)
    renderApp('/perfil')
    await openTab('Skills e idiomas')
    const language = await screen.findByRole('group', { name: 'Inglés' })
    expect(within(language).getByRole('combobox', { name: 'Nivel' })).toHaveValue('__other__')
    expect(within(language).getByLabelText('Nivel (texto libre)')).toHaveValue('C1 (Cambridge)')
    await userEvent.selectOptions(within(language).getByRole('combobox', { name: 'Nivel' }), 'B2')
    expect(within(language).queryByLabelText('Nivel (texto libre)')).not.toBeInTheDocument()
    await userEvent.selectOptions(within(language).getByRole('combobox', { name: 'Nivel' }), '__other__')
    const free = within(language).getByLabelText('Nivel (texto libre)')
    expect(free).toHaveValue('')
    await userEvent.type(free, 'Alto medio')
    expect(free).toHaveValue('Alto medio')
  })

  it('edita un fichero de contexto con sus comentarios y lo enseña sin ellos en la vista previa', async () => {
    const calls = mockApi({
      ...BASE,
      'PUT /context/criterios': doc('criterios', '# Criterios\n<!-- Qué no aceptas -->\nSin guardias.\nNada de viajes.\n', { file_hash: 'nuevo' }),
    })
    renderApp('/perfil')
    await openTab('Contexto y estilo')
    const block = await screen.findByRole('region', { name: 'Criterios' })
    const editor = await within(block).findByLabelText('Texto de Criterios')
    expect(editor).toHaveValue('# Criterios\n<!-- Qué no aceptas -->\nSin guardias.\n')
    await userEvent.type(editor, 'Nada de viajes.')
    await userEvent.click(within(block).getByRole('tab', { name: 'Vista previa' }))
    const preview = within(block).getByTestId('markdown-preview')
    expect(preview).toHaveTextContent('Sin guardias. Nada de viajes.')
    expect(preview).not.toHaveTextContent('Qué no aceptas')

    await userEvent.click(within(block).getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'PUT')).toBe(true))
    expect(calls.find((c) => c.method === 'PUT')?.body).toEqual({
      file_hash: 'hash-criterios',
      text: '# Criterios\n<!-- Qué no aceptas -->\nSin guardias.\nNada de viajes.',
    })
    expect(await within(block).findByText('Guardado')).toBeInTheDocument()
  })

  it('si el fichero cambió por fuera, avisa y ofrece recargar', async () => {
    mockApi({
      ...BASE,
      'PUT /profile/sections/headline': {
        status: 409,
        body: { ok: false, error: { type: 'conflict', message: 'data/profile.yaml ha cambiado', details: [] } },
      },
    })
    renderApp('/perfil')
    const block = await screen.findByRole('region', { name: 'Datos y resumen' })
    const headline = within(block).getByLabelText('Titular')
    await userEvent.clear(headline)
    await userEvent.type(headline, 'Analytics Engineer')
    await userEvent.click(within(block).getByRole('button', { name: 'Guardar' }))
    expect(await within(block).findByRole('alert')).toHaveTextContent('Tu perfil ha cambiado desde que abriste la página')
    expect(within(block).getByRole('button', { name: 'Recargar' })).toBeInTheDocument()
  })

  it('el contacto se edita, marcado como privado', async () => {
    mockApi(BASE)
    renderApp('/perfil')
    const block = await screen.findByRole('region', { name: 'Datos y resumen' })
    expect(within(block).getByLabelText('Teléfono')).toHaveValue('+34 600 000 000')
    expect(within(block).getByText(/Tu agente no lo ve/)).toBeInTheDocument()
  })

  it('en inglés', async () => {
    await act(async () => {
      await i18n.changeLanguage('en')
    })
    mockApi(BASE)
    renderApp('/perfil')
    await openTab('STAR stories')
    const block = await screen.findByRole('region', { name: 'STAR stories' })
    await userEvent.click(within(block).getByRole('button', { name: 'Add story' }))
    expect(within(block).getByText('Pick at least one piece of evidence.')).toBeInTheDocument()
    expect(within(block).getByRole('button', { name: 'Save' })).toBeDisabled()
    expect(screen.getByRole('tab', { name: 'Context and style' })).toBeInTheDocument()
  })

  it('«Mejorar con mi agente» lleva el id del logro y no se puede dejar para luego', async () => {
    const agent = { agent: 'claude', display_name: 'Claude Code', model: null, preset: null, reason: 'default', reason_text: 'tu agente por defecto', blocked: null, blocked_code: null, warning: null }
    const action = (id: string) => ({ id, label: id, needs_job: false, needs_milestone: false, needs_profile_item: id === 'improve-profile-item', prompt: null, background: false, agent, alternatives: [], background_agent: null })
    const calls = mockApi({
      ...BASE,
      'GET /agent': {
        available: true,
        agent: 'claude',
        reason: null,
        background: { available: true, agent: 'claude', reason: null },
        actions: [action('improve-profile-item'), action('propose-stories'), action('expand')],
      },
      'POST /agent/launch': { ok: true, agent: 'claude', prompt: 'Usa el skill update-profile…', message: 'ok' },
    })
    renderApp('/perfil')
    await openTab('Experiencia')
    await openCompany('Norte Consulting')
    const achievement = await screen.findByRole('group', { name: 'Migré 40 procesos ETL a Python.' })
    const improve = within(achievement).getByRole('button', { name: 'Mejorar con mi agente' })
    await waitFor(() => expect(improve).toBeEnabled())
    await userEvent.click(improve)
    await waitFor(() => expect(calls.some((c) => c.path === '/agent/launch')).toBe(true))
    expect(calls.find((c) => c.path === '/agent/launch')?.body).toEqual({ action: 'improve-profile-item', profile_item: 'exp-norte/a1' })
    await userEvent.click(within(improve.closest<HTMLElement>('[data-slot="agent-button"]')!).getByRole('button', { name: /con Claude Code/ }))
    expect(screen.queryByRole('menuitem', { name: /Dejar para mi próxima sesión/ })).not.toBeInTheDocument()
  })

  it('la vista previa del contexto no interpreta HTML', async () => {
    mockApi({
      ...BASE,
      'GET /context/criterios': doc('criterios', '# Criterios\n<script>alert(1)</script>\n<img src=x onerror=alert(1)> **Sin guardias**\n'),
    })
    renderApp('/perfil')
    await openTab('Contexto y estilo')
    const block = await screen.findByRole('region', { name: 'Criterios' })
    await userEvent.click(await within(block).findByRole('tab', { name: 'Vista previa' }))
    const preview = within(block).getByTestId('markdown-preview')
    expect(preview.querySelector('script, img')).toBeNull()
    expect(preview).toHaveTextContent('<script>alert(1)</script>')
    expect(within(preview).getByText('Sin guardias').tagName).toBe('STRONG')
  })

  it('avisa antes de salir con cambios sin guardar', async () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    mockApi(BASE)
    renderApp('/perfil')
    const block = await screen.findByRole('region', { name: 'Datos y resumen' })
    await userEvent.type(within(block).getByLabelText('Titular'), ' senior')
    await userEvent.click(screen.getAllByRole('link', { name: 'Bandeja' })[0])
    expect(confirm).toHaveBeenCalledWith(expect.stringContaining('cambios sin guardar'))
    expect(screen.getByRole('heading', { level: 1, name: 'Mi perfil' })).toBeInTheDocument()
    confirm.mockRestore()
  })
})
