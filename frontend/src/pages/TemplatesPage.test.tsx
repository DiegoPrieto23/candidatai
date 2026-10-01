import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
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
            accent_colors: { default: '#1F4E79', choices: ['#1F4E79', '#2E5E4E', '#7A2E39', '#3F3F46'] },
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
    expect(atsTags.map((t) => t.textContent)).toEqual(['Apta para ATS', 'Sin foto', '1 columna', 'Motor docx', 'Integrada'])

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
})
