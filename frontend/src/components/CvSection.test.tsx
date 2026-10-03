import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import {
  jobCv,
  jobView,
  mockApi,
  processView,
  renderApp,
  renderResult,
  status,
  templateList,
} from '@/test/utils'

const approved = jobView({ stage: 'approved' })
const cvReady = jobView({ stage: 'cv_ready' })

describe('Sección CV de la ficha', () => {
  it('no aparece ni se pide antes de aprobar la oferta', async () => {
    const calls = mockApi({ 'GET /status': status(), 'GET /jobs/1': jobView(), 'GET /templates': templateList() })
    renderApp('/jobs/1')
    await screen.findByRole('heading', { level: 1, name: 'Data Engineer' })
    expect(screen.queryByRole('region', { name: 'CV' })).not.toBeInTheDocument()
    expect(calls.some((c) => c.path === '/jobs/1/cv')).toBe(false)
  })

  it('en una oferta cerrada solo aparece si llegó a tener CV', async () => {
    mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView({ stage: 'closed' }),
      'GET /jobs/1/cv': { job_id: 1, stage: 'closed', can_render: false, cv: null },
      'GET /templates': templateList(),
    })
    renderApp('/jobs/1')
    await screen.findByRole('heading', { level: 1, name: 'Data Engineer' })
    await waitFor(() => expect(screen.queryByRole('region', { name: 'CV' })).not.toBeInTheDocument())
  })

  it('recuerda ejecutar generar-cv si la oferta aprobada aún no tiene CV', async () => {
    mockApi({
      'GET /status': status(),
      'GET /jobs/1': approved,
      'GET /jobs/1/cv': { job_id: 1, stage: 'approved', can_render: true, cv: null },
      'GET /templates': templateList(),
    })
    renderApp('/jobs/1')
    const section = await screen.findByRole('region', { name: 'CV' })
    expect(await within(section).findByText('Aún sin CV')).toBeInTheDocument()
    expect(within(section).getByText('generar-cv 1')).toBeInTheDocument()
    expect(within(section).queryByRole('button', { name: 'Renderizar' })).not.toBeInTheDocument()
  })

  it('muestra la verificación y los renders con avisos, páginas y cobertura', async () => {
    mockApi({
      'GET /status': status(),
      'GET /jobs/1': cvReady,
      'GET /jobs/1/cv': jobCv([
        renderResult(1, { selected: true }),
        renderResult(2, {
          template_id: 'ats-simple',
          options: { photo: false, accent_color: null, hidden_sections: ['projects'] },
          pages: 2,
          template_changed: true,
          warnings: [{ code: 'too_long', message: 'El CV ocupa 2 páginas y el máximo es 1.' }],
        }),
      ]),
      'GET /templates': templateList(),
    })
    renderApp('/jobs/1')
    const section = await screen.findByRole('region', { name: 'CV' })
    expect(await within(section).findByText('Verificado: nada inventado ni exagerado')).toBeInTheDocument()

    const first = within(section).getByRole('listitem', { name: 'Render 1' })
    expect(within(first).getByText('Clásica con foto')).toBeInTheDocument()
    expect(within(first).getByText('Para enviar')).toBeInTheDocument()
    expect(within(first).getByText('2 de 3')).toBeInTheDocument()
    expect(within(first).getByText(/Con foto · Azul/)).toBeInTheDocument()
    expect(within(first).queryByRole('button', { name: /Usar este para enviar/ })).not.toBeInTheDocument()
    expect(within(first).getByRole('link', { name: /Ver PDF/ })).toHaveAttribute(
      'href',
      'http://127.0.0.1:8000/renders/1/pdf',
    )

    const second = within(section).getByRole('listitem', { name: 'Render 2' })
    expect(within(second).getByText('ATS sencilla')).toBeInTheDocument()
    expect(within(second).getByText('2/1')).toBeInTheDocument()
    expect(within(second).getByText('El CV ocupa 2 páginas y el máximo es 1.')).toBeInTheDocument()
    expect(within(second).getByText('Plantilla cambiada')).toBeInTheDocument()
    expect(within(second).getByText(/sin proyectos/)).toBeInTheDocument()
    // Lo más reciente, arriba.
    const items = within(section).getAllByRole('listitem', { name: /^Render/ })
    expect(items.map((i) => i.getAttribute('aria-label'))).toEqual(['Render 2', 'Render 1'])
  })

  it('renderiza con otra plantilla, sin foto, otro color y secciones ocultas', async () => {
    let renders = [renderResult(1, { template_id: 'ats-simple', options: { photo: false, accent_color: null }, selected: true })]
    const calls = mockApi({
      'GET /status': status(),
      'GET /jobs/1': cvReady,
      'GET /jobs/1/cv': () => jobCv(renders),
      'GET /templates': templateList(),
      'POST /documents/1/renders': () => {
        const created = renderResult(2, { options: { photo: false, accent_color: '#7A2E39', hidden_sections: ['projects'] } })
        renders = [...renders, created]
        return created
      },
    })
    renderApp('/jobs/1')
    const form = await screen.findByRole('form', { name: 'Renderizar el CV' })

    // Parte de la plantilla del render seleccionado: ats-simple no lleva foto ni color.
    expect(within(form).getByRole('radio', { name: /ATS sencilla/ })).toBeChecked()
    expect(within(form).getByRole('radio', { name: 'Con foto' })).toBeDisabled()
    expect(within(form).queryByRole('radio', { name: 'Granate' })).not.toBeInTheDocument()

    await userEvent.click(within(form).getByRole('radio', { name: /Clásica con foto/ }))
    expect(within(form).getByRole('radio', { name: 'Azul' })).toBeChecked()
    await userEvent.click(within(form).getByRole('radio', { name: 'Granate' }))
    await userEvent.click(within(form).getByRole('radio', { name: 'Sin foto' }))
    await userEvent.click(within(form).getByRole('checkbox', { name: 'Proyectos' }))
    await userEvent.click(within(form).getByRole('button', { name: 'Renderizar' }))

    await waitFor(() => expect(calls.some((c) => c.method === 'POST')).toBe(true))
    const post = calls.find((c) => c.method === 'POST')
    expect(post?.path).toBe('/documents/1/renders')
    expect(post?.body).toEqual({
      template_id: 'clasica-foto',
      photo: 'exclude',
      accent_color: '#7A2E39',
      hidden_sections: ['projects'],
    })
    expect(await screen.findByRole('listitem', { name: 'Render 2' })).toBeInTheDocument()
  })

  it('enseña el error de la API al renderizar', async () => {
    mockApi({
      'GET /status': status(),
      'GET /jobs/1': cvReady,
      'GET /jobs/1/cv': jobCv([renderResult(1, { selected: true })]),
      'GET /jobs/1/process': processView({ stage: 'cv_ready' }),
      'GET /templates': templateList(),
      'POST /documents/1/renders': {
        status: 503,
        body: { ok: false, error: { type: 'pdf_unavailable', message: 'No hay LibreOffice ni Word.', details: [] } },
      },
    })
    renderApp('/jobs/1')
    await userEvent.click(await screen.findByRole('button', { name: 'Renderizar' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('No hay LibreOffice ni Word.')
  })

  it('marca otro render para enviar', async () => {
    let selected = 1
    const calls = mockApi({
      'GET /status': status(),
      'GET /jobs/1': cvReady,
      'GET /jobs/1/cv': () =>
        jobCv([renderResult(1, { selected: selected === 1 }), renderResult(2, { selected: selected === 2 })]),
      'GET /templates': templateList(),
      'POST /renders/2/select': () => {
        selected = 2
        return { status: 200, body: renderResult(2, { selected: true }) }
      },
    })
    renderApp('/jobs/1')
    const second = await screen.findByRole('listitem', { name: 'Render 2' })
    await userEvent.click(within(second).getByRole('button', { name: /Usar este para enviar/ }))

    await waitFor(() => expect(within(second).getByText('Para enviar')).toBeInTheDocument())
    expect(calls.filter((c) => c.method === 'POST').map((c) => c.path)).toEqual(['/renders/2/select'])
    const first = screen.getByRole('listitem', { name: 'Render 1' })
    expect(within(first).getByRole('button', { name: /Usar este para enviar/ })).toBeInTheDocument()
  })

  it('compara dos renders lado a lado', async () => {
    mockApi({
      'GET /status': status(),
      'GET /jobs/1': cvReady,
      'GET /jobs/1/cv': jobCv([renderResult(1, { selected: true }), renderResult(2), renderResult(3)]),
      'GET /templates': templateList(),
    })
    renderApp('/jobs/1')
    const box = (id: number) =>
      within(screen.getByRole('listitem', { name: `Render ${id}` })).getByRole('checkbox', { name: 'Comparar' })

    await screen.findByRole('listitem', { name: 'Render 1' })
    await userEvent.click(box(1))
    expect(screen.getByText('Marca otro render para verlos lado a lado.')).toBeInTheDocument()
    await userEvent.click(box(3))
    const compare = screen.getByRole('region', { name: 'Comparación de renders' })
    expect(within(compare).getByTitle('PDF del render 1')).toHaveAttribute(
      'src',
      'http://127.0.0.1:8000/renders/1/pdf#view=FitH',
    )
    expect(within(compare).getByTitle('PDF del render 3')).toBeInTheDocument()

    // Un tercero sustituye al más antiguo de la comparación.
    await userEvent.click(box(2))
    expect(within(compare).queryByTitle('PDF del render 1')).not.toBeInTheDocument()
    expect(within(compare).getByTitle('PDF del render 2')).toBeInTheDocument()

    await userEvent.click(within(compare).getByRole('button', { name: 'Cerrar comparación' }))
    expect(screen.queryByRole('region', { name: 'Comparación de renders' })).not.toBeInTheDocument()
  })

  it('muestra los problemas del verificador', async () => {
    mockApi({
      'GET /status': status(),
      'GET /jobs/1': approved,
      'GET /jobs/1/cv': jobCv([renderResult(1, { selected: true })], {
        verification: {
          passed: false,
          issues: [
            { severity: 'blocker', location: 'experience[0].bullets[1]', problem: 'Cifra que no está en el perfil.', suggestion: 'Quítala.' },
          ],
        },
      }),
      'GET /templates': templateList(),
    })
    renderApp('/jobs/1')
    const section = await screen.findByRole('region', { name: 'CV' })
    expect(await within(section).findByText('El verificador encontró problemas')).toBeInTheDocument()
    expect(within(section).getByText('Bloqueante · experience[0].bullets[1]')).toBeInTheDocument()
    expect(within(section).getByText('Cifra que no está en el perfil.')).toBeInTheDocument()
  })
})
