import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { mockApi, renderApp, status, templateInfo, templateList } from '@/test/utils'

describe('Galería de plantillas', () => {
  it('muestra cada plantilla con su preview y sus etiquetas', async () => {
    mockApi({
      'GET /status': status(),
      'GET /templates': templateList({
        templates: [
          templateInfo(),
          templateInfo({
            id: 'clasica-foto',
            name: 'Clásica con foto',
            ats_friendly: false,
            photo_supported: true,
            accent_colors: { default: '#1F4E79', choices: ['#1F4E79', '#2E5E4E', '#7A2E39', '#3F3F46'], free: false },
          }),
          templateInfo({ id: 'mi-cv', name: 'Mi CV', origin: 'user', columns: 2, has_preview: false }),
        ],
      }),
    })
    renderApp('/plantillas')

    expect(screen.getByRole('heading', { level: 1, name: 'Plantillas de CV' })).toBeInTheDocument()
    const ats = await screen.findByRole('article', { name: 'ATS sencilla' })
    expect(within(ats).getByRole('img', { name: 'Vista previa de ATS sencilla' })).toHaveAttribute(
      'src',
      'http://127.0.0.1:8000/templates/ats-simple/preview.png',
    )
    const atsTags = within(within(ats).getByRole('list', { name: 'Características' })).getAllByRole('listitem')
    expect(atsTags.map((t) => t.textContent)).toEqual(['Apta para ATS', 'Sin foto', '1 columna', 'PDF y Word', 'De la app'])

    const classic = screen.getByRole('article', { name: 'Clásica con foto' })
    expect(within(classic).getByText('No apta para ATS')).toBeInTheDocument()
    expect(within(classic).getByText('Con foto')).toBeInTheDocument()
    expect(within(classic).getByText('4 colores')).toBeInTheDocument()

    const own = screen.getByRole('article', { name: 'Mi CV' })
    expect(within(own).getByText('Sin vista previa')).toBeInTheDocument()
    expect(within(own).getByText('2 columnas')).toBeInTheDocument()
    expect(within(own).getByText('Tuya')).toBeInTheDocument()
  })

  it('lista las plantillas que no son válidas y por qué', async () => {
    mockApi({
      'GET /status': status(),
      'GET /templates': templateList({
        invalid: [{ id: 'rota', path: 'data/templates/rota', reason: 'Falta el fichero del motor docx.' }],
      }),
    })
    renderApp('/plantillas')
    const problems = await screen.findByRole('region', { name: 'Plantillas con problemas' })
    expect(within(problems).getByText('rota')).toBeInTheDocument()
    expect(within(problems).getByText(/Falta el fichero del motor docx/)).toBeInTheDocument()
  })

  it('se llega desde la navegación', async () => {
    mockApi({ 'GET /status': status(), 'GET /jobs': { items: [], total: 0 }, 'GET /templates': templateList() })
    renderApp('/')
    await userEvent.click(screen.getByRole('link', { name: 'Plantillas' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Plantillas de CV' })).toBeInTheDocument()
  })

  describe('Mi CV', () => {
    const pending = {
      name: 'mi-cv.docx',
      path: 'data/uploads/mi-cv.docx',
      size: 48_000,
      format: 'docx',
      supported: true,
      template_id: null,
      agent_command: 'import-cv-template data/uploads/mi-cv.docx',
      uploaded_at: '2026-10-02T09:00:00Z',
    }
    const mine = templateInfo({
      id: 'mi-cv',
      name: 'Mi CV',
      origin: 'user',
      from_user_cv: true,
      has_source_preview: true,
    })

    it('sin subidas invita a subir el CV', async () => {
      mockApi({
        'GET /status': status(),
        'GET /templates': templateList(),
        'GET /uploads': [],
        'GET /templates/default': { template_id: null },
      })
      renderApp('/plantillas')
      expect(await screen.findByText('Aún no has subido tu CV')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Subir mi CV/ })).toBeInTheDocument()
    })

    it('sube el fichero a la API', async () => {
      // El `FormData` de jsdom no es compatible con el `Request` de Node (en un navegador sí): uno
      // mínimo que se serializa como texto basta para ver que se envía el fichero.
      vi.stubGlobal(
        'FormData',
        class {
          private parts: string[] = []
          append(key: string, value: File) {
            this.parts.push(`${key}=${value.name}`)
          }
          toString() {
            return this.parts.join('&')
          }
        },
      )
      const calls = mockApi({
        'GET /status': status(),
        'GET /templates': templateList(),
        'GET /uploads': [],
        'GET /templates/default': { template_id: null },
        'POST /uploads': pending,
      })
      renderApp('/plantillas')
      await screen.findByText('Aún no has subido tu CV')
      const file = new File(['docx'], 'Mi CV.docx', {
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      })
      await userEvent.upload(screen.getByLabelText('Fichero del CV'), file)
      await waitFor(() => expect(calls.some((c) => c.method === 'POST' && c.path === '/uploads')).toBe(true))
      const upload = calls.find((c) => c.method === 'POST' && c.path === '/uploads')
      expect(String(upload?.body)).toContain('Mi CV.docx')
    })

    it('un CV pendiente muestra la petición para el agente; un PDF avisa de que se recrea', async () => {
      mockApi({
        'GET /status': status(),
        'GET /templates': templateList(),
        'GET /uploads': [
          pending,
          { ...pending, name: 'canva.pdf', format: 'pdf', agent_command: 'import-cv-template data/uploads/canva.pdf' },
        ],
        'GET /templates/default': { template_id: null },
      })
      renderApp('/plantillas')
      const card = await screen.findByRole('listitem', { name: 'mi-cv.docx' })
      expect(within(card).getByText('Pendiente de importar')).toBeInTheDocument()
      // La orden para copiar, plegada: lo normal es el botón que abre el agente.
      expect(within(card).queryByText('import-cv-template data/uploads/mi-cv.docx')).not.toBeInTheDocument()
      await userEvent.click(within(card).getByRole('button', { name: '¿Prefieres pedírselo tú a tu agente?' }))
      expect(within(card).getByText('import-cv-template data/uploads/mi-cv.docx')).toBeInTheDocument()
      expect(within(card).queryByText(/recrea el diseño/)).not.toBeInTheDocument()
      const pdf = screen.getByRole('listitem', { name: 'canva.pdf' })
      expect(within(pdf).getByText(/el agente recrea el diseño:/)).toBeInTheDocument()
      expect(screen.queryByText(/08b/)).not.toBeInTheDocument()
    })

    it('«Convertir en plantilla» abre el agente con el CV subido', async () => {
      const calls = mockApi({
        'GET /status': status(),
        'GET /templates': templateList(),
        'GET /uploads': [pending],
        'GET /templates/default': { template_id: null },
        'GET /agent': { available: true, agent: 'claude', reason: null, actions: [] },
        'POST /agent/launch': { ok: true, agent: 'claude', prompt: 'Usa el skill import-cv-template…', message: 'ok' },
      })
      renderApp('/plantillas')
      const card = await screen.findByRole('listitem', { name: 'mi-cv.docx' })
      await userEvent.click(within(card).getByRole('button', { name: 'Convertir en plantilla' }))
      await waitFor(() =>
        expect(calls.find((c) => c.path === '/agent/launch')?.body).toEqual({
          action: 'import-cv-template',
          upload: 'mi-cv.docx',
        }),
      )
    })

    it('un CV importado desde PDF muestra original y recreación y avisa de que solo da PDF', async () => {
      const canva = templateInfo({
        id: 'canva',
        name: 'Canva',
        engine: 'html',
        origin: 'user',
        columns: 2,
        from_user_cv: true,
        has_source_preview: true,
      })
      mockApi({
        'GET /status': status(),
        'GET /templates': templateList({ templates: [templateInfo(), canva] }),
        'GET /uploads': [{ ...pending, name: 'canva.pdf', format: 'pdf', template_id: 'canva' }],
        'GET /templates/default': { template_id: null },
      })
      renderApp('/plantillas')
      const card = await screen.findByRole('listitem', { name: 'canva.pdf' })
      expect(within(card).getByRole('img', { name: 'Recreación con tu perfil' })).toHaveAttribute(
        'src',
        'http://127.0.0.1:8000/templates/canva/preview-real.png',
      )
      expect(within(card).getByText(/solo da PDF/)).toBeInTheDocument()

      const gallery = screen.getByRole('article', { name: 'Canva' })
      const pair = within(gallery).getByLabelText('Original y recreación')
      expect(within(pair).getByRole('img', { name: 'Original de Canva' })).toHaveAttribute(
        'src',
        'http://127.0.0.1:8000/templates/canva/source.png',
      )
      expect(within(pair).getByRole('img', { name: 'Recreación de Canva' })).toHaveAttribute(
        'src',
        'http://127.0.0.1:8000/templates/canva/preview.png',
      )
      const tags = within(within(gallery).getByRole('list', { name: 'Características' })).getAllByRole('listitem')
      expect(tags.map((t) => t.textContent)).toContain('Solo PDF')
      const builtin = screen.getByRole('article', { name: 'ATS sencilla' })
      expect(within(builtin).queryByText('Solo PDF')).not.toBeInTheDocument()
    })

    it('un CV importado se compara con el original y se marca por defecto', async () => {
      const calls = mockApi({
        'GET /status': status(),
        'GET /templates': templateList({ templates: [templateInfo(), mine] }),
        'GET /uploads': [{ ...pending, template_id: 'mi-cv' }],
        'GET /templates/default': { template_id: 'clasica-foto' },
        'POST /templates/mi-cv/default': {
          template_id: 'mi-cv',
          profile_version_id: 3,
          created: true,
          conflicts: ['Las ofertas con ATS workday seguirán usando «ats-simple» (regla de `template_rules`).'],
        },
      })
      renderApp('/plantillas')
      const card = await screen.findByRole('listitem', { name: 'mi-cv.docx' })
      expect(within(card).getByRole('img', { name: 'Original' })).toHaveAttribute(
        'src',
        'http://127.0.0.1:8000/templates/mi-cv/source.png',
      )
      expect(within(card).getByRole('img', { name: 'Con tu perfil' })).toHaveAttribute(
        'src',
        'http://127.0.0.1:8000/templates/mi-cv/preview-real.png',
      )
      await userEvent.click(within(card).getByRole('button', { name: /Usar por defecto/ }))
      expect(calls.some((c) => c.method === 'POST' && c.path === '/templates/mi-cv/default')).toBe(true)
      const rules = await within(card).findByRole('list', { name: 'Reglas que eligen otra plantilla' })
      expect(within(rules).getByText(/ATS workday/)).toBeInTheDocument()

      const gallery = screen.getByRole('article', { name: 'Mi CV' })
      expect(within(gallery).getByText('Tu CV')).toBeInTheDocument()
    })

    it('si no se puede hacer la vista con tu perfil, lo dice en vez de enseñar una imagen rota', async () => {
      mockApi({
        'GET /status': status(),
        'GET /templates': templateList({ templates: [templateInfo(), mine] }),
        'GET /uploads': [{ ...pending, template_id: 'mi-cv' }],
        'GET /templates/default': { template_id: null },
      })
      renderApp('/plantillas')
      const card = await screen.findByRole('listitem', { name: 'mi-cv.docx' })
      fireEvent.error(within(card).getByRole('img', { name: 'Con tu perfil' }))
      expect(within(card).queryByRole('img', { name: 'Con tu perfil' })).not.toBeInTheDocument()
      expect(within(card).getByText(/No se ha podido hacer la vista con tu perfil/)).toBeInTheDocument()
    })
  })
})
