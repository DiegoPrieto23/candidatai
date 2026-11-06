import { screen, waitFor, within } from '@testing-library/react'
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
    await userEvent.click(screen.getByRole('link', { name: 'Mi perfil' }))
    await userEvent.click(await screen.findByRole('link', { name: 'Plantillas de CV' }))
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
      expect(await screen.findByText('Aún no has subido ningún CV de ejemplo')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Subir nueva plantilla/ })).toBeInTheDocument()
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
      await screen.findByText('Aún no has subido ningún CV de ejemplo')
      const file = new File(['docx'], 'Mi CV.docx', {
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      })
      await userEvent.upload(screen.getByLabelText('Fichero con el diseño de la plantilla'), file)
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

    it('un CV ya convertido no sale en «Mi CV»: es una plantilla más de la lista', async () => {
      const canva = templateInfo({
        id: 'canva',
        name: 'Canva',
        engine: 'html',
        origin: 'user',
        columns: 2,
        from_user_cv: true,
        has_source_preview: true,
        editable: true,
      })
      mockApi({
        'GET /status': status(),
        'GET /templates': templateList({ templates: [templateInfo(), canva] }),
        'GET /uploads': [{ ...pending, name: 'canva.pdf', format: 'pdf', template_id: 'canva' }],
        'GET /templates/default': { template_id: null },
      })
      renderApp('/plantillas')
      const gallery = await screen.findByRole('article', { name: 'Canva' })
      expect(screen.queryByRole('listitem', { name: 'canva.pdf' })).not.toBeInTheDocument()
      expect(screen.queryByRole('img', { name: 'Con tu perfil' })).not.toBeInTheDocument()

      const pair = within(gallery).getByLabelText('Original y recreación')
      expect(within(pair).getByRole('img', { name: 'Original de Canva' })).toHaveAttribute(
        'src',
        'http://127.0.0.1:8000/templates/canva/source.png',
      )
      const tags = within(within(gallery).getByRole('list', { name: 'Características' })).getAllByRole('listitem')
      expect(tags.map((t) => t.textContent)).toContain('Solo PDF')
      const builtin = screen.getByRole('article', { name: 'ATS sencilla' })
      expect(within(builtin).queryByText('Solo PDF')).not.toBeInTheDocument()
    })

    it('una plantilla tuya se marca por defecto desde la lista y explica las reglas', async () => {
      const calls = mockApi({
        'GET /status': status(),
        'GET /templates': templateList({ templates: [templateInfo(), { ...mine, editable: true }] }),
        'GET /uploads': [],
        'GET /templates/default': { template_id: 'clasica-foto' },
        'POST /templates/mi-cv/default': {
          template_id: 'mi-cv',
          profile_version_id: 3,
          created: true,
          conflicts: ['Las ofertas con ATS workday seguirán usando «ats-simple» (regla de `template_rules`).'],
        },
      })
      renderApp('/plantillas')
      const card = await screen.findByRole('article', { name: 'Mi CV' })
      expect(within(card).getByText('Tu CV')).toBeInTheDocument()
      await userEvent.click(within(card).getByRole('button', { name: /Usar por defecto/ }))
      expect(calls.some((c) => c.method === 'POST' && c.path === '/templates/mi-cv/default')).toBe(true)
      const rules = await within(card).findByRole('list', { name: 'Reglas que eligen otra plantilla' })
      expect(within(rules).getByText(/ATS workday/)).toBeInTheDocument()
    })

    it('una de la app no se renombra, pero se puede usar por defecto', async () => {
      mockApi({
        'GET /status': status(),
        'GET /templates': templateList({ templates: [templateInfo()] }),
        'GET /uploads': [],
        'GET /templates/default': { template_id: 'ats-simple' },
      })
      renderApp('/plantillas')
      const card = await screen.findByRole('article', { name: 'ATS sencilla' })
      expect(within(card).queryByRole('button', { name: /Cambiar el nombre/ })).not.toBeInTheDocument()
      expect(await within(card).findByText('Plantilla por defecto')).toBeInTheDocument()
      // Y las demás, también las de la app, ofrecen «Usar por defecto» y «Eliminar».
      expect(within(card).getByRole('button', { name: 'Eliminar ATS sencilla' })).toBeInTheDocument()
    })

    it('todas las plantillas, también las de la app, ofrecen «Usar por defecto»', async () => {
      const calls = mockApi({
        'GET /status': status(),
        'GET /templates': templateList(),
        'GET /uploads': [],
        'GET /templates/default': { template_id: 'ats-simple' },
        'POST /templates/clasica-foto/default': { template_id: 'clasica-foto', profile_version_id: 3, created: true, conflicts: [] },
      })
      renderApp('/plantillas')
      const card = await screen.findByRole('article', { name: 'Clásica con foto' })
      await userEvent.click(within(card).getByRole('button', { name: /Usar por defecto/ }))
      expect(calls.some((c) => c.method === 'POST' && c.path === '/templates/clasica-foto/default')).toBe(true)
    })

    it('eliminar una de la app la quita de tu lista, lo dice y se puede restaurar', async () => {
      const calls = mockApi({
        'GET /status': status(),
        'GET /templates': templateList(),
        'GET /uploads': [],
        'GET /templates/default': { template_id: null },
        'GET /templates/hidden': [],
        'DELETE /templates/clasica-foto': { template_id: 'clasica-foto', default_cleared: false, hidden: true },
      })
      renderApp('/plantillas')
      const card = await screen.findByRole('article', { name: 'Clásica con foto' })
      await userEvent.click(within(card).getByRole('button', { name: 'Eliminar Clásica con foto' }))
      const dialog = await screen.findByRole('dialog')
      expect(within(dialog).getByText('¿Eliminar «Clásica con foto» de tu lista?')).toBeInTheDocument()
      expect(within(dialog).getByText(/no se borra del programa y la puedes restaurar/)).toBeInTheDocument()
      await userEvent.click(within(dialog).getByRole('button', { name: 'Eliminar' }))
      await waitFor(() =>
        expect(calls.some((c) => c.method === 'DELETE' && c.path === '/templates/clasica-foto')).toBe(true),
      )
    })

    it('las eliminadas salen aparte con «Restaurar»', async () => {
      const calls = mockApi({
        'GET /status': status(),
        'GET /templates': templateList({ templates: [templateInfo()] }),
        'GET /uploads': [],
        'GET /templates/default': { template_id: null },
        'GET /templates/hidden': [templateInfo({ id: 'clasica-foto', name: 'Clásica con foto' })],
        'POST /templates/clasica-foto/restore': { template_id: 'clasica-foto', restored: true },
      })
      renderApp('/plantillas')
      const section = await screen.findByRole('region', { name: 'Plantillas eliminadas' })
      expect(within(section).getByText('Plantillas eliminadas (1)')).toBeInTheDocument()
      await userEvent.click(within(section).getByRole('button', { name: 'Restaurar Clásica con foto' }))
      await waitFor(() =>
        expect(calls.some((c) => c.method === 'POST' && c.path === '/templates/clasica-foto/restore')).toBe(true),
      )
    })

    it('renombra una plantilla tuya', async () => {
      const calls = mockApi({
        'GET /status': status(),
        'GET /templates': templateList({ templates: [{ ...mine, editable: true }] }),
        'GET /uploads': [],
        'GET /templates/default': { template_id: null },
        'PATCH /templates/mi-cv': { ...mine, name: 'CV en inglés' },
      })
      renderApp('/plantillas')
      const card = await screen.findByRole('article', { name: 'Mi CV' })
      await userEvent.click(within(card).getByRole('button', { name: 'Cambiar el nombre de Mi CV' }))
      const input = within(card).getByRole('textbox', { name: 'Nombre de la plantilla' })
      await userEvent.clear(input)
      await userEvent.type(input, 'CV en inglés{Enter}')
      await waitFor(() =>
        expect(calls.find((c) => c.method === 'PATCH' && c.path === '/templates/mi-cv')?.body).toEqual({
          name: 'CV en inglés',
        }),
      )
    })

    it('eliminar pide confirmación y dice qué pasa si es la de por defecto', async () => {
      const calls = mockApi({
        'GET /status': status(),
        'GET /templates': templateList({ templates: [{ ...mine, editable: true }] }),
        'GET /uploads': [],
        'GET /templates/default': { template_id: 'mi-cv' },
        'DELETE /templates/mi-cv': { template_id: 'mi-cv', default_cleared: true },
      })
      renderApp('/plantillas')
      const card = await screen.findByRole('article', { name: 'Mi CV' })
      await within(card).findByText('Plantilla por defecto')
      await userEvent.click(within(card).getByRole('button', { name: 'Eliminar Mi CV' }))
      const dialog = await screen.findByRole('dialog')
      expect(within(dialog).getByText(/Es tu plantilla por defecto/)).toBeInTheDocument()
      expect(calls.some((c) => c.method === 'DELETE')).toBe(false)

      await userEvent.click(within(dialog).getByRole('button', { name: 'Eliminar' }))
      await waitFor(() =>
        expect(calls.some((c) => c.method === 'DELETE' && c.path === '/templates/mi-cv')).toBe(true),
      )
    })

    it('cancelar no elimina nada', async () => {
      const calls = mockApi({
        'GET /status': status(),
        'GET /templates': templateList({ templates: [{ ...mine, editable: true }] }),
        'GET /uploads': [],
        'GET /templates/default': { template_id: null },
      })
      renderApp('/plantillas')
      const card = await screen.findByRole('article', { name: 'Mi CV' })
      await userEvent.click(within(card).getByRole('button', { name: 'Eliminar Mi CV' }))
      const dialog = await screen.findByRole('dialog')
      await userEvent.click(within(dialog).getByRole('button', { name: 'Cancelar' }))
      expect(calls.some((c) => c.method === 'DELETE')).toBe(false)
    })
  })
})
