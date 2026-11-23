import { act, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { i18n } from '@/lib/i18n'
import { mockApi, renderApp, status } from '@/test/utils'

// jsdom no carga imágenes ni tiene canvas: el editor de encuadre avisa del recuadro al montarse y el
// recorte devuelve un JPEG de mentira. Lo que se prueba es qué se sube y cuándo.
vi.mock('react-easy-crop', async () => {
  const { useEffect } = await import('react')
  return {
    default: function FakeCropper(props: {
      cropShape: string
      initialCroppedAreaPercentages?: unknown
      onCropComplete: (percent: unknown, pixels: unknown) => void
    }) {
      useEffect(() => {
        props.onCropComplete({ x: 10, y: 20, width: 50, height: 50 }, { x: 2, y: 4, width: 10, height: 10 })
        // eslint-disable-next-line react-hooks/exhaustive-deps
      }, [])
      return (
        <div
          data-testid="fake-cropper"
          data-shape={props.cropShape}
          data-initial={JSON.stringify(props.initialCroppedAreaPercentages ?? null)}
        />
      )
    },
  }
})
vi.mock('@/lib/cropImage', () => ({
  cropToBlob: vi.fn(async () => new Blob(['recorte'], { type: 'image/jpeg' })),
}))

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

/** Una plantilla de la lista con su forma de foto (para el encuadre). */
function templateWithShape(id: string, photo_shape: string) {
  return {
    id,
    name: id,
    engine: 'docx',
    origin: 'builtin',
    ats_friendly: false,
    photo_supported: true,
    photo_shape,
    columns: 1,
    has_preview: false,
    editable: false,
  }
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
    await openTab('Experiencia y formación')
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
      await openTab('Experiencia y formación')
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
      await openTab('Experiencia y formación')
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
      await openTab('Experiencia y formación')
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
      await openTab('Experiencia y formación')
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
      await openTab('Experiencia y formación')
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
      await openTab('Experiencia y formación')
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
      await openTab('Experiencia y formación')
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
    await openTab('Experiencia y formación')
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

  // Lo que buscas (puestos, lugares, modalidad, años, sueldo, contrato…) se edita en «Buscar ofertas»:
  // sus pruebas están en `SearchPage.test.tsx`.
  it('en una etiqueta, el campo va antes que las etiquetas: los de una fila empiezan a la misma altura', async () => {
    mockApi({ ...BASE, 'GET /sources': { sources: [], agent_browse: { max_result_pages: 3, delay_seconds: 5 } }, 'GET /profile/role-suggestions': [] })
    renderApp('/buscar/ajustes')
    const input = await screen.findByRole('combobox', { name: 'Idiomas de trabajo' })
    const tags = screen.getByRole('list', { name: 'Idiomas de trabajo' })
    expect(input.compareDocumentPosition(tags) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('el nivel de un idioma es un desplegable que conserva el valor libre que ya tenías', async () => {
    mockApi(BASE)
    renderApp('/perfil')
    await openTab('Experiencia y formación')
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

  it('«Documentos» son tres tarjetas con filas plegadas que resumen lo elegido y abren su editor', async () => {
    mockApi({
      ...BASE,
      'GET /profile/editable': {
        ...EDITABLE,
        profile: {
          ...PROFILE,
          preferences: {
            ...PROFILE.preferences,
            cv: { max_pages: 2, photo_policy: { default: true, by_country: { US: false } }, instructions: 'Datos primero.' },
            cover_letter: { tone: 'cercano', max_words: 300, default_format: 'pdf' },
          },
        },
      },
      'GET /context/style-samples': [{ name: 'carta.txt', chars: 1200, risk_flags: [], excerpt: null }],
    })
    renderApp('/perfil')
    await openTab('Documentos')
    for (const name of ['Cómo quieres tus CVs y cartas', 'Notas para tu agente', 'Tus archivos']) {
      expect(await screen.findByRole('region', { name })).toBeInTheDocument()
    }
    const cv = screen.getByRole('region', { name: 'CV' })
    expect(within(cv).getByText(/^Plantilla de la app · hasta 2 páginas · con foto, salvo en .+ · con indicaciones$/)).toBeInTheDocument()
    const letter = screen.getByRole('region', { name: 'Carta' })
    expect(within(letter).getByText('Tono cercano · hasta 300 palabras · en PDF')).toBeInTheDocument()
    expect(screen.queryByLabelText('Plantilla por defecto')).not.toBeInTheDocument()

    await userEvent.click(within(cv).getByRole('button', { name: 'Editar «CV»' }))
    expect(within(cv).getByLabelText('Plantilla por defecto')).toBeVisible()
    await userEvent.click(within(letter).getByRole('button', { name: 'Editar «Carta»' }))
    expect(within(letter).getByLabelText('Tono')).toBeVisible()
    for (const name of ['Estilo de redacción', 'Perfil conductual', 'Criterios', 'Narrativa']) {
      const row = screen.getByRole('region', { name })
      await userEvent.click(within(row).getByRole('button', { name: new RegExp(`^(Editar|Crear) «${name}»$`) }))
      expect(await within(row).findByLabelText(`Texto de ${name}`)).toBeVisible()
    }
    const samples = screen.getByRole('region', { name: 'Muestras de estilo' })
    expect(within(samples).getByText('1 muestra')).toBeInTheDocument()
    await userEvent.click(within(samples).getByRole('button', { name: 'Ver «Muestras de estilo»' }))
    expect(within(samples).getByText('carta.txt')).toBeVisible()
    // Plegar no pierde nada: se oculta y sigue montado.
    await userEvent.click(within(cv).getByRole('button', { name: 'Plegar «CV»' }))
    expect(within(cv).getByLabelText('Plantilla por defecto')).not.toBeVisible()
  })

  it('con cambios sin guardar, la fila no se pliega y el aviso lleva hasta ella', async () => {
    mockApi(BASE)
    renderApp('/perfil')
    await openTab('Documentos')
    const row = await screen.findByRole('region', { name: 'Criterios' })
    await userEvent.click(within(row).getByRole('button', { name: 'Editar «Criterios»' }))
    await userEvent.type(await within(row).findByLabelText('Texto de Criterios'), 'Nada de viajes.')
    expect(within(row).queryByRole('button', { name: 'Plegar «Criterios»' })).not.toBeInTheDocument()
    expect(within(row).getByText(/guárdalos o descártalos para plegarlo/)).toBeInTheDocument()
    await openTab('Sobre ti')
    const notice = screen.getByText('Sin guardar:').parentElement!
    await userEvent.click(within(notice).getByRole('button', { name: /Criterios/ }))
    expect(screen.getByRole('tab', { name: 'Documentos' })).toHaveAttribute('aria-selected', 'true')
    expect(within(row).getByLabelText('Texto de Criterios')).toBeVisible()
  })

  it('edita un fichero de contexto con sus comentarios y lo enseña sin ellos en la vista previa', async () => {
    const calls = mockApi({
      ...BASE,
      'PUT /context/criterios': doc('criterios', '# Criterios\n<!-- Qué no aceptas -->\nSin guardias.\nNada de viajes.\n', { file_hash: 'nuevo' }),
    })
    renderApp('/perfil')
    await openTab('Documentos')
    const block = await screen.findByRole('region', { name: 'Criterios' })
    await userEvent.click(within(block).getByRole('button', { name: 'Editar «Criterios»' }))
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
    await openTab('Experience and education')
    const block = await screen.findByRole('region', { name: 'STAR stories' })
    await userEvent.click(within(block).getByRole('button', { name: 'Add story' }))
    expect(within(block).getByText('Pick at least one piece of evidence.')).toBeInTheDocument()
    expect(within(block).getByRole('button', { name: 'Save' })).toBeDisabled()
    expect(screen.getByRole('tab', { name: 'Documents' })).toBeInTheDocument()
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
    await openTab('Experiencia y formación')
    await openCompany('Norte Consulting')
    const achievement = await screen.findByRole('group', { name: 'Migré 40 procesos ETL a Python.' })
    const improve = within(achievement).getByRole('button', { name: 'Mejorar con mi agente' })
    await waitFor(() => expect(improve).toBeEnabled())
    await userEvent.click(improve)
    await waitFor(() => expect(calls.some((c) => c.path === '/agent/launch')).toBe(true))
    expect(calls.find((c) => c.path === '/agent/launch')?.body).toEqual({ lang: 'es', action: 'improve-profile-item', profile_item: 'exp-norte/a1' })
    await userEvent.click(within(improve.closest<HTMLElement>('[data-slot="agent-button"]')!).getByRole('button', { name: /con Claude Code/ }))
    expect(screen.queryByRole('menuitem', { name: /Dejar para mi próxima sesión/ })).not.toBeInTheDocument()
  })

  it('sin perfil, se sube el CV y tu agente lo crea a partir de él', async () => {
    const agent = { agent: 'claude', display_name: 'Claude Code', model: null, preset: null, reason: 'default', reason_text: 'tu agente por defecto', blocked: null, blocked_code: null, warning: null }
    const action = (id: string) => ({ id, label: id, needs_job: false, needs_milestone: false, needs_profile_item: false, prompt: null, background: false, agent, alternatives: [], background_agent: null })
    const uploaded: unknown[] = []
    const calls = mockApi({
      ...BASE,
      'GET /profile/editable': { ...EDITABLE, exists: false, file_hash: null, profile: null, profile_version_id: null, undo_available: 0 },
      'GET /context': {
        context_dir: 'C:/d/contexto',
        documents_dir: 'C:/d/documentos',
        files: [],
        folders: [
          { name: 'cv', exists: true, files: 0 },
          { name: 'referencias', exists: true, files: 0 },
        ],
      },
      'GET /context/documents/cv': () => uploaded,
      'POST /context/documents/cv': () => {
        const info = { folder: 'cv', name: 'cv-lucia.pdf', size_bytes: 9, uploaded_at: '2026-10-28T10:00:00Z' }
        uploaded.push(info)
        return { status: 201, body: info }
      },
      'GET /agent': {
        available: true,
        agent: 'claude',
        reason: null,
        background: { available: true, agent: 'claude', reason: null },
        actions: [action('create-profile'), action('expand')],
      },
      'POST /agent/launch': { ok: true, agent: 'claude', prompt: 'Usa el skill update-profile…', message: 'ok' },
    })
    renderApp('/perfil')
    expect(await screen.findByRole('heading', { name: 'Empieza por tu CV' })).toBeInTheDocument()
    // Sin perfil, «Mejorar el contenido de mi perfil» todavía no toca.
    expect(screen.queryByRole('button', { name: 'Mejorar el contenido de mi perfil' })).not.toBeInTheDocument()
    // Solo se suben el CV y LinkedIn; el resto de carpetas se rellenan a mano.
    const folders = await screen.findByRole('region', { name: 'Tus archivos' })
    expect(within(folders).getAllByRole('button', { name: /^Subir/ })).toHaveLength(1)

    await userEvent.upload(screen.getByLabelText('Tu CV'), new File(['%PDF-1.7'], 'CV Lucía.pdf', { type: 'application/pdf' }))
    expect(await screen.findByText('CV subido: cv-lucia.pdf')).toBeInTheDocument()
    const post = calls.find((c) => c.method === 'POST' && c.path === '/context/documents/cv')
    expect(post?.body).toEqual({ filename: 'CV Lucía.pdf', content_base64: btoa('%PDF-1.7') })
    expect(screen.getByRole('button', { name: 'Subir otro CV' })).toBeInTheDocument()

    const create = screen.getByRole('button', { name: 'Crear mi perfil desde mi CV' })
    await waitFor(() => expect(create).toBeEnabled())
    await userEvent.click(create)
    await waitFor(() => expect(calls.some((c) => c.path === '/agent/launch')).toBe(true))
    expect(calls.find((c) => c.path === '/agent/launch')?.body).toEqual({ lang: 'es', action: 'create-profile' })
  })

  it('la vista previa del contexto no interpreta HTML', async () => {
    mockApi({
      ...BASE,
      'GET /context/criterios': doc('criterios', '# Criterios\n<script>alert(1)</script>\n<img src=x onerror=alert(1)> **Sin guardias**\n'),
    })
    renderApp('/perfil')
    await openTab('Documentos')
    const block = await screen.findByRole('region', { name: 'Criterios' })
    await userEvent.click(within(block).getByRole('button', { name: 'Editar «Criterios»' }))
    await userEvent.click(await within(block).findByRole('tab', { name: 'Vista previa' }))
    const preview = within(block).getByTestId('markdown-preview')
    expect(preview.querySelector('script, img')).toBeNull()
    expect(preview).toHaveTextContent('<script>alert(1)</script>')
    expect(within(preview).getByText('Sin guardias').tagName).toBe('STRONG')
  })

  const withSkills = (skills: Array<{ name: string; level: string; category?: string | null }>) => ({
    ...BASE,
    'GET /profile/editable': { ...EDITABLE, profile: { ...PROFILE, skills } },
  })

  it('filtra las skills por nivel y una nueva se ve aunque hubiera filtro', async () => {
    mockApi(withSkills([{ name: 'Python', level: 'F' }, { name: 'Go', level: 'B' }]))
    renderApp('/perfil')
    await openTab('Experiencia y formación')
    const block = await screen.findByRole('region', { name: 'Skills' })
    const filters = within(block).getByRole('group', { name: 'Filtrar skills por nivel' })
    const rows = () => within(block).queryAllByRole('textbox', { name: 'Skill' })
    expect(rows()).toHaveLength(2)
    // Un nivel sin skills no se puede elegir: dejaría la lista vacía.
    expect(within(filters).getByRole('button', { name: /^C\+/ })).toBeDisabled()
    await userEvent.click(within(filters).getByRole('button', { name: /^B/ }))
    expect(within(filters).getByRole('button', { name: /^B/ })).toHaveAttribute('aria-pressed', 'true')
    expect(rows().map((r) => (r as HTMLInputElement).value)).toEqual(['Go'])
    // La que editas con un filtro puesto no desaparece aunque deje de casar.
    await userEvent.selectOptions(within(block).getByRole('group', { name: 'Go' }).querySelector('select')!, 'F')
    expect(rows().map((r) => (r as HTMLInputElement).value)).toEqual(['Go'])
    await userEvent.click(within(block).getByRole('button', { name: 'Añadir skill' }))
    expect(within(filters).getByRole('button', { name: /^Todas/ })).toHaveAttribute('aria-pressed', 'true')
    expect(rows()).toHaveLength(3)
    expect(within(filters).getByRole('button', { name: /^Todas/ })).toHaveTextContent('3')
  })

  it('combina el filtro de nivel con el de categoría, con recuentos, atenuados y «Quitar filtros»', async () => {
    mockApi(
      withSkills([
        { name: 'Python', level: 'F', category: 'Lenguajes' },
        { name: 'SQL', level: 'C', category: 'lenguajes ' },
        { name: 'BigQuery', level: 'C', category: 'Cloud y DWH' },
        { name: 'Excel', level: 'B' },
      ]),
    )
    renderApp('/perfil')
    await openTab('Experiencia y formación')
    const block = await screen.findByRole('region', { name: 'Skills' })
    const levels = within(block).getByRole('group', { name: 'Filtrar skills por nivel' })
    const categories = within(block).getByRole('group', { name: 'Filtrar skills por categoría' })
    const names = () => within(block).queryAllByRole('textbox', { name: 'Skill' }).map((r) => (r as HTMLInputElement).value)
    const chip = (group: HTMLElement, name: RegExp) => within(group).getByRole('button', { name })
    // En el orden en que aparecen, sin duplicar «Lenguajes» y con «Sin categoría» al final.
    expect(within(categories).getAllByRole('button').map((b) => b.textContent)).toEqual([
      'Todas4',
      'Lenguajes2',
      'Cloud y DWH1',
      'Sin categoría1',
    ])
    expect(within(block).queryByRole('button', { name: /Quitar filtros/ })).not.toBeInTheDocument()

    await userEvent.click(chip(categories, /^Lenguajes/))
    expect(names()).toEqual(['Python', 'SQL'])
    // Los recuentos de nivel ya son los de «Lenguajes»: B se queda en 0 y atenuado.
    expect(chip(levels, /^Todas/)).toHaveTextContent('2')
    expect(chip(levels, /^B/)).toHaveTextContent('0')
    expect(chip(levels, /^B/)).toBeDisabled()

    await userEvent.click(chip(levels, /^C\d/))
    expect(names()).toEqual(['SQL'])
    expect(chip(categories, /^Cloud/)).toHaveTextContent('1')
    expect(chip(categories, /^Sin categoría/)).toBeDisabled()

    await userEvent.click(within(block).getByRole('button', { name: /Quitar filtros/ }))
    expect(names()).toEqual(['Python', 'SQL', 'BigQuery', 'Excel'])
    expect(chip(levels, /^Todas/)).toHaveAttribute('aria-pressed', 'true')
    expect(chip(categories, /^Todas/)).toHaveAttribute('aria-pressed', 'true')
  })

  it('con muchas categorías, el filtro es un desplegable con búsqueda que atenúa las que vaciarían la lista', async () => {
    const many = ['Lenguajes', 'Cloud', 'BI', 'ML', 'IA', 'Datos', 'DevOps', 'Gestión', 'Idiomas'].map((category, i) => ({
      name: `S${i}`,
      level: i === 0 ? 'F' : 'C',
      category,
    }))
    mockApi(withSkills(many))
    renderApp('/perfil')
    await openTab('Experiencia y formación')
    const block = await screen.findByRole('region', { name: 'Skills' })
    const names = () => within(block).queryAllByRole('textbox', { name: 'Skill' }).map((r) => (r as HTMLInputElement).value)
    expect(within(block).queryByRole('group', { name: 'Filtrar skills por categoría' })).not.toBeInTheDocument()
    const picker = within(block).getByRole('button', { name: 'Filtrar skills por categoría' })
    const levels = within(block).getByRole('group', { name: 'Filtrar skills por nivel' })
    await userEvent.click(within(levels).getByRole('button', { name: /^F/ }))
    await userEvent.click(picker)
    expect(screen.getByRole('option', { name: /Lenguajes/ })).not.toHaveAttribute('aria-disabled')
    expect(screen.getByRole('option', { name: /DevOps/ })).toHaveAttribute('aria-disabled', 'true')
    await userEvent.click(screen.getByRole('option', { name: /DevOps/ }))
    expect(names()).toEqual(['S0'])
    await userEvent.click(within(levels).getByRole('button', { name: /^Todas/ }))
    await userEvent.click(picker)
    await userEvent.type(screen.getByRole('combobox', { name: 'Buscar una categoría' }), 'devo')
    await userEvent.click(screen.getByRole('option', { name: /DevOps/ }))
    expect(names()).toEqual(['S6'])
    expect(within(block).getByRole('button', { name: /Quitar filtros/ })).toBeInTheDocument()
  })

  it('al renombrar la categoría filtrada, el filtro sigue y la fila no desaparece', async () => {
    mockApi(
      withSkills([
        { name: 'Python', level: 'F', category: 'Lenguajes' },
        { name: 'AWS', level: 'C', category: 'Cloud' },
      ]),
    )
    renderApp('/perfil')
    await openTab('Experiencia y formación')
    const block = await screen.findByRole('region', { name: 'Skills' })
    const categories = within(block).getByRole('group', { name: 'Filtrar skills por categoría' })
    await userEvent.click(within(categories).getByRole('button', { name: /^Cloud/ }))
    const field = within(within(block).getByRole('group', { name: 'AWS' })).getByRole('textbox', { name: 'Categoría' })
    await userEvent.clear(field)
    await userEvent.type(field, 'Nube')
    expect(within(block).queryAllByRole('textbox', { name: 'Skill' }).map((r) => (r as HTMLInputElement).value)).toEqual(['AWS'])
    expect(within(categories).getByRole('button', { name: /^Cloud/ })).toHaveAttribute('aria-pressed', 'true')
    expect(within(categories).getByRole('button', { name: /^Nube/ })).toBeInTheDocument()
  })

  it('los idiomas van en una rejilla de Idioma y Nivel, sin «Dónde ponerlo»', async () => {
    mockApi(BASE)
    renderApp('/perfil')
    await openTab('Experiencia y formación')
    const block = await screen.findByRole('region', { name: 'Idiomas' })
    const language = within(block).getByRole('group', { name: 'Inglés' })
    expect(within(language).getByRole('textbox', { name: 'Idioma' })).toHaveValue('Inglés')
    expect(within(language).getByRole('combobox', { name: 'Nivel' })).toBeInTheDocument()
    expect(within(block).queryByText('Dónde ponerlo')).not.toBeInTheDocument()
    expect(within(block).queryByText(/gallego en Galicia/)).not.toBeInTheDocument()
  })

  it('cambiar un idioma conserva «regional» del YAML aunque ya no se vea', async () => {
    const calls = mockApi({
      ...BASE,
      'GET /profile/editable': { ...EDITABLE, profile: { ...PROFILE, languages: [{ language: 'Gallego', level: 'C1', regional: 'Galicia' }] } },
      'PUT /profile/sections/languages': saved('languages', { dry_run: true, diff: 'Nivel: C1 → C2' }),
    })
    renderApp('/perfil')
    await openTab('Experiencia y formación')
    const block = await screen.findByRole('region', { name: 'Idiomas' })
    const language = within(block).getByRole('group', { name: 'Gallego' })
    await userEvent.type(within(language).getByRole('textbox', { name: 'Idioma' }), ' ')
    expect(within(block).getByRole('textbox', { name: 'Idioma' })).toHaveFocus()
    await userEvent.selectOptions(within(block).getByRole('combobox', { name: 'Nivel' }), 'C2')
    await userEvent.click(within(block).getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'PUT')).toBe(true))
    const body = calls.find((c) => c.method === 'PUT')?.body as { content: unknown[] }
    expect(body.content[0]).toMatchObject({ level: 'C2', regional: 'Galicia' })
  })

  it('la foto es opcional: se encuadra, se sube, se cambia y se quita pidiendo confirmación', async () => {
    const crop = { x: 10, y: 20, width: 50, height: 50 }
    const saved = { exists: true, filename: 'photo.jpg', size_bytes: 10, version: 'a', has_original: true, crop }
    const calls = mockApi({
      ...BASE,
      'GET /profile/photo': { exists: false, filename: null, size_bytes: null, version: null },
      'PUT /profile/photo': saved,
      'DELETE /profile/photo': { exists: false, filename: null, size_bytes: null, version: null },
    })
    renderApp('/perfil')
    const block = await screen.findByRole('region', { name: 'Foto para el CV (opcional)' })
    expect(await within(block).findByRole('button', { name: 'Subir foto' })).toBeInTheDocument()
    await userEvent.upload(within(block).getByLabelText('Elegir una foto'), new File(['x'], 'yo.png', { type: 'image/png' }))
    // Primero se encuadra; no se sube nada hasta guardar.
    const dialog = await screen.findByRole('dialog', { name: 'Encuadra tu foto' })
    expect(calls.some((c) => c.method === 'PUT')).toBe(false)
    // Sin plantilla por defecto con otra forma, el recuadro es redondo.
    expect(within(dialog).getByTestId('fake-cropper')).toHaveAttribute('data-shape', 'round')
    expect(within(dialog).getByRole('slider', { name: 'Zoom' })).toBeInTheDocument()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Guardar foto' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(await within(block).findByRole('img', { name: 'Tu foto actual' })).toBeInTheDocument()
    // Se sube el recorte, la original y el recuadro.
    expect(calls.find((c) => c.method === 'PUT')?.body).toEqual({
      content_base64: btoa('recorte'),
      original_base64: btoa('x'),
      crop,
    })
    expect(within(block).getByRole('button', { name: 'Volver a encuadrar' })).toBeInTheDocument()
    await userEvent.click(within(block).getByRole('button', { name: 'Quitar' }))
    expect(calls.some((c) => c.method === 'DELETE')).toBe(false)
    await userEvent.click(within(block).getByRole('button', { name: 'Sí, quitar la foto' }))
    expect(await within(block).findByRole('button', { name: 'Subir foto' })).toBeInTheDocument()
  })

  it('la foto se vuelve a encuadrar desde la original, empezando por el último recuadro', async () => {
    const crop = { x: 5, y: 5, width: 60, height: 60 }
    const calls = mockApi({
      ...BASE,
      'GET /profile/photo': { exists: true, filename: 'photo.jpg', size_bytes: 10, version: 'b', has_original: true, crop },
      'GET /profile/photo/original': { original: true },
      'GET /templates': {
        templates: [{ ...templateWithShape('cuadrada', 'square') }],
        invalid: [],
        fallback_template: 'ats-simple',
      },
      'GET /templates/default': { template_id: 'cuadrada' },
    })
    renderApp('/perfil')
    const block = await screen.findByRole('region', { name: 'Foto para el CV (opcional)' })
    await userEvent.click(await within(block).findByRole('button', { name: 'Volver a encuadrar' }))
    const dialog = await screen.findByRole('dialog', { name: 'Encuadra tu foto' })
    expect(calls.some((c) => c.path === '/profile/photo/original')).toBe(true)
    const cropper = within(dialog).getByTestId('fake-cropper')
    expect(JSON.parse(cropper.getAttribute('data-initial') ?? 'null')).toEqual(crop)
    // La plantilla por defecto lleva la foto cuadrada: el recuadro también.
    expect(cropper).toHaveAttribute('data-shape', 'rect')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Cancelar' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(calls.some((c) => c.method === 'PUT')).toBe(false)
  })

  it('«Generar resumen en inglés» deja el encargo a tu agente', async () => {
    const calls = mockApi({
      ...BASE,
      'GET /profile/suggestions': { suggestions: [] },
      'GET /agent': {
        available: true,
        agent: 'claude',
        reason: null,
        actions: [{ id: 'translate-summary', label: 'translate-summary', needs_job: false, needs_milestone: false }],
      },
      'POST /agent/launch': { ok: true, agent: 'claude', prompt: 'Usa el skill update-profile…', message: 'ok' },
    })
    renderApp('/perfil')
    await userEvent.click(await screen.findByRole('button', { name: /Generar resumen en inglés/ }))
    await waitFor(() =>
      expect(calls.find((c) => c.path === '/agent/launch')?.body).toEqual({ lang: 'es', action: 'translate-summary' }),
    )
  })

  it('con el resumen en español sin guardar, primero hay que guardarlo', async () => {
    mockApi({
      ...BASE,
      'GET /profile/suggestions': { suggestions: [] },
      'GET /agent': { available: true, agent: 'claude', reason: null, actions: [] },
    })
    renderApp('/perfil')
    await userEvent.type(await screen.findByLabelText('Resumen (español)'), ' Y más.')
    expect(screen.getByRole('button', { name: /Generar resumen en inglés/ })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Por qué está desactivado' })).toBeInTheDocument()
  })

  it('la propuesta del resumen en inglés se usa en el campo o se descarta, sin guardar el perfil', async () => {
    const suggestion = {
      id: 7,
      field: 'summary.en',
      text: 'Data Engineer with three years.',
      source: 'Data Engineer con tres años.',
      agent_name: 'claude',
      created_at: '2026-11-14T10:00:00Z',
    }
    const calls = mockApi({
      ...BASE,
      'GET /profile/suggestions': { suggestions: [suggestion] },
      'POST /profile/suggestions/7/used': { suggestions: [] },
    })
    renderApp('/perfil')
    const panel = await screen.findByRole('region', { name: 'Propuesta de tu agente' })
    expect(within(panel).getByText('Data Engineer with three years.')).toBeInTheDocument()
    expect(within(panel).queryByText(/otra versión/)).not.toBeInTheDocument()
    await userEvent.click(within(panel).getByRole('button', { name: /Usar en el campo/ }))
    await waitFor(() => expect(screen.getByLabelText('Resumen (inglés)')).toHaveValue('Data Engineer with three years.'))
    expect(calls.some((c) => c.path === '/profile/suggestions/7/used')).toBe(true)
    // Usarla no guarda el perfil: eso sigue siendo «Guardar».
    expect(calls.some((c) => c.method === 'PUT' && c.path.startsWith('/profile/editable'))).toBe(false)
  })

  it('avisa si la propuesta se hizo con otro resumen en español, y se puede descartar', async () => {
    const calls = mockApi({
      ...BASE,
      'GET /profile/suggestions': {
        suggestions: [
          {
            id: 8,
            field: 'summary.en',
            text: 'Old translation.',
            source: 'Otro resumen.',
            agent_name: null,
            created_at: '2026-11-14T10:00:00Z',
          },
        ],
      },
      'POST /profile/suggestions/8/discard': { suggestions: [] },
    })
    renderApp('/perfil')
    const panel = await screen.findByRole('region', { name: 'Propuesta de tu agente' })
    expect(within(panel).getByText(/Se hizo con otra versión de tu resumen en español/)).toBeInTheDocument()
    await userEvent.click(within(panel).getByRole('button', { name: /Descartar/ }))
    await waitFor(() => expect(screen.queryByRole('region', { name: 'Propuesta de tu agente' })).not.toBeInTheDocument())
    expect(calls.some((c) => c.path === '/profile/suggestions/8/discard')).toBe(true)
    expect(screen.getByLabelText('Resumen (inglés)')).toHaveValue('')
  })

  it('«Experiencia y formación» abre con un índice de apartados: Experiencia primero, cada uno en su bloque', async () => {
    mockApi(BASE)
    renderApp('/perfil')
    await openTab('Experiencia y formación')
    const nav = await screen.findByRole('navigation', { name: 'Ir a un apartado' })
    expect(within(nav).getAllByRole('link').map((link) => link.textContent)).toEqual([
      'Experiencia2',
      'Skills1',
      'Idiomas1',
      'Proyectos1',
      'Formación0',
      'Certificaciones0',
      'Otras secciones0',
      'Historias STAR0',
    ])
    expect(screen.getByRole('region', { name: 'Skills' })).toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: 'Idiomas' })).getByRole('group', { name: 'Inglés' })).toBeInTheDocument()

    await userEvent.click(within(nav).getByRole('link', { name: /^Proyectos/ }))
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole('region', { name: 'Proyectos' })))
  })

  it('cada proyecto arranca plegado, como las empresas, y el que añades se abre', async () => {
    mockApi(BASE)
    renderApp('/perfil')
    await openTab('Experiencia y formación')
    const block = await screen.findByRole('region', { name: 'Proyectos' })
    const project = within(block).getByRole('article', { name: 'TFG de predicción' })
    const header = within(project)
      .getAllByRole('button')
      .find((b) => b.hasAttribute('aria-expanded'))!
    expect(header).toHaveAttribute('aria-expanded', 'false')
    expect(within(project).queryByLabelText('Nombre')).not.toBeInTheDocument()
    await userEvent.click(header)
    expect(within(project).getByLabelText('Nombre')).toHaveValue('TFG de predicción')

    await userEvent.click(within(block).getByRole('button', { name: 'Añadir proyecto' }))
    const added = within(block).getByRole('article', { name: 'Proyecto nuevo' })
    expect(within(added).getByLabelText('Nombre')).toHaveValue('')
    expect(within(block).getByRole('button', { name: 'Plegar todo' })).toBeInTheDocument()
  })

  it('el aviso de cambios sin guardar nombra cada bloque y lleva hasta él', async () => {
    mockApi(BASE)
    renderApp('/perfil')
    const personal = await screen.findByRole('region', { name: 'Datos y resumen' })
    await userEvent.type(within(personal).getByLabelText('Titular'), ' senior')
    await openTab('Experiencia y formación')
    const language = await screen.findByRole('group', { name: 'Inglés' })
    await userEvent.selectOptions(within(language).getByRole('combobox', { name: 'Nivel' }), 'B2')

    const notice = screen.getByText('Sin guardar:').parentElement!
    expect(within(notice).getAllByRole('button').map((b) => b.textContent)).toEqual(['Datos y resumen', 'Idiomas'])
    const nav = screen.getByRole('navigation', { name: 'Ir a un apartado' })
    expect(within(nav).getByRole('link', { name: /^Idiomas.*sin guardar/ })).toBeInTheDocument()

    await userEvent.click(within(notice).getByRole('button', { name: 'Ir a «Datos y resumen» (Sobre ti) para guardarlo' }))
    expect(screen.getByRole('tab', { name: 'Sobre ti' })).toHaveAttribute('aria-selected', 'true')
    await waitFor(() => expect(document.activeElement).toBe(personal))
  })

  it('avisa antes de salir con cambios sin guardar', async () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    mockApi(BASE)
    renderApp('/perfil')
    const block = await screen.findByRole('region', { name: 'Datos y resumen' })
    await userEvent.type(within(block).getByLabelText('Titular'), ' senior')
    await userEvent.click(screen.getAllByRole('link', { name: 'Bandeja de ofertas' })[0])
    expect(confirm).toHaveBeenCalledWith(expect.stringContaining('cambios sin guardar'))
    expect(screen.getByRole('heading', { level: 1, name: 'Mi perfil' })).toBeInTheDocument()
    confirm.mockRestore()
  })
})

describe('Mi perfil › Historial', () => {
  const now = new Date()
  const today = (h: number, m: number) => new Date(now.getFullYear(), now.getMonth(), now.getDate(), h, m).toISOString()
  const hm = (h: number, m: number) => new Intl.DateTimeFormat('es-ES', { hour: '2-digit', minute: '2-digit' }).format(new Date(2026, 0, 1, h, m))
  const version = (id: number, changes: Record<string, unknown>) => ({
    id,
    created_at: today(10, id),
    origin: 'ui',
    first: false,
    current: false,
    restorable: true,
    summary: [],
    ...changes,
  })
  const VERSIONS = {
    versions: [
      version(3, { current: true, restorable: false, summary: [{ block: 'experience', changes: 2 }, { block: 'private', changes: 1 }] }),
      version(2, { origin: 'agent', summary: [{ block: 'skills', changes: 7 }] }),
      version(1, { origin: null, first: true }),
    ],
    has_more: false,
  }
  const detail = (id: number, changes: unknown[], extra: Record<string, unknown> = {}) => ({
    id,
    previous_id: id - 1,
    created_at: today(10, id),
    origin: 'ui',
    current: false,
    restorable: true,
    changes,
    restore_blocks: [],
    technical_diff: '--- versión 1\n+++ versión 2\n-headline: A\n+headline: B\n',
    ...extra,
  })
  const LATEST = detail(
    3,
    [
      { block: 'experience', kind: 'changed', label: 'Data Engineer · Norte Consulting', fields: [{ path: ['end'], before: 'present', after: '2026-03' }] },
      {
        block: 'experience',
        kind: 'added',
        label: 'Reduje la carga.',
        parent: 'Data Engineer · Norte Consulting',
        within: 'achievements',
        fields: [
          { path: ['text'], after: 'Reduje la carga.' },
          { path: ['skills'], added: ['Snowflake'] },
        ],
      },
      { block: 'private', kind: 'changed', hidden: true, fields: [] },
    ],
    { current: true, restorable: false },
  )
  const SKILLS = Array.from({ length: 7 }, (_, i) => ({ block: 'skills', kind: 'added', label: `Skill ${i + 1}`, fields: [{ path: ['level'], after: 'C' }] }))
  const OLDER = detail(2, [{ block: 'skills', kind: 'moved', label: 'SQL', position: [3, 1], fields: [] }, ...SKILLS], {
    restore_blocks: ['personal', 'skills'],
  })
  const routes = {
    ...BASE,
    'GET /profile/versions': VERSIONS,
    'GET /profile/versions/3/changes': LATEST,
    'GET /profile/versions/2/changes': OLDER,
  }

  it('lista las versiones con cuándo, de dónde y qué bloques cambiaron, y abre la actual en texto normal', async () => {
    mockApi(routes)
    renderApp('/perfil')
    await openTab('Historial')
    const list = await screen.findByRole('list', { name: 'Versiones de tu perfil' })
    const rows = within(list).getAllByRole('listitem')
    expect(rows).toHaveLength(3)
    expect(within(rows[0]).getByText(`Hoy, ${hm(10, 3)}`)).toBeInTheDocument()
    expect(within(rows[0]).getByText('Actual')).toBeInTheDocument()
    expect(within(rows[0]).getByText('Experiencia (2 cambios) · Datos privados (ha cambiado)')).toBeInTheDocument()
    expect(within(rows[0]).getByText('Desde la app')).toBeInTheDocument()
    expect(within(rows[1]).getByText('Tu agente')).toBeInTheDocument()
    expect(within(rows[2]).getByText('Tu primer perfil')).toBeInTheDocument()

    // La actual, abierta: por bloques, «Antes → Ahora», con etiqueta además del color.
    const experience = await within(rows[0]).findByRole('region', { name: 'Experiencia' })
    expect(within(experience).getByText('Data Engineer · Norte Consulting')).toBeInTheDocument()
    expect(within(experience).getByText('Fin')).toBeInTheDocument()
    expect(within(experience).getByText('Actualidad').closest('del')).not.toBeNull()
    expect(within(experience).getByText(/marzo de 2026/).closest('ins')).not.toBeNull()
    expect(within(experience).getByText('Logro de Data Engineer · Norte Consulting')).toBeInTheDocument()
    expect(within(experience).getByText('Añadido')).toBeInTheDocument()
    expect(within(experience).getByText('Snowflake')).toBeInTheDocument()
    const hidden = within(rows[0]).getByRole('region', { name: 'Datos privados' })
    expect(within(hidden).getByText(/La cifra no se enseña/)).toBeInTheDocument()
    // Nada de YAML a la vista: el cambio técnico, plegado al final.
    expect(within(rows[0]).queryByText(/headline:/)).not.toBeInTheDocument()
    expect(within(rows[0]).getByText('Es la versión actual')).toBeInTheDocument()
    await userEvent.click(within(rows[0]).getByRole('button', { name: 'Ver el cambio técnico' }))
    expect(within(rows[0]).getByLabelText('Cambio técnico de esta versión')).toHaveTextContent('+headline: B')
  })

  it('una versión con muchos cambios los pliega y se puede volver a ella tras confirmar', async () => {
    const calls = mockApi({
      ...routes,
      'POST /profile/versions/2/restore': { file_hash: 'h2', profile_version_id: 4, blocks: ['personal', 'skills'], undo_available: 2 },
    })
    renderApp('/perfil')
    await openTab('Historial')
    const list = await screen.findByRole('list', { name: 'Versiones de tu perfil' })
    const row = within(list).getAllByRole('listitem')[1]
    await userEvent.click(within(row).getByRole('button', { name: new RegExp(`Hoy, ${hm(10, 2)}`) }))
    const skills = await within(row).findByRole('region', { name: 'Skills' })
    expect(within(skills).getByText('Movido')).toBeInTheDocument()
    expect(within(skills).getByText('3.ª')).toBeInTheDocument()
    expect(within(skills).queryByText('Skill 7')).not.toBeInTheDocument()
    await userEvent.click(within(skills).getByRole('button', { name: 'Ver 3 más' }))
    expect(within(skills).getByText('Skill 7')).toBeInTheDocument()

    await userEvent.click(within(row).getByRole('button', { name: /^Volver a esta versión/ }))
    const dialog = await screen.findByRole('dialog', { name: `¿Volver a la versión de hoy, ${hm(10, 2)}?` })
    expect(within(dialog).getByText('Datos y resumen')).toBeInTheDocument()
    expect(within(dialog).getByText('Skills')).toBeInTheDocument()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Volver a esta versión' }))
    expect(await screen.findByText(`Hecho: tu perfil ha vuelto a la versión de hoy, ${hm(10, 2)}.`)).toBeInTheDocument()
    const post = calls.find((c) => c.method === 'POST' && c.path === '/profile/versions/2/restore')
    expect(post?.body).toEqual({ file_hash: 'h1' })
  })

  it('con cambios sin guardar no deja volver a otra versión ni deshacer', async () => {
    mockApi({ ...routes, 'PUT /profile/sections/headline': saved('headline') })
    renderApp('/perfil')
    await userEvent.type(await screen.findByLabelText('Titular'), ' senior')
    await openTab('Historial')
    expect(await screen.findByText('Guarda o descarta antes los bloques con cambios.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Deshacer el último cambio/ })).toBeDisabled()
    const row = within(screen.getByRole('list', { name: 'Versiones de tu perfil' })).getAllByRole('listitem')[1]
    await userEvent.click(within(row).getByRole('button', { name: new RegExp(`Hoy, ${hm(10, 2)}`) }))
    expect(await within(row).findByRole('button', { name: /^Volver a esta versión/ })).toBeDisabled()
  })
})
