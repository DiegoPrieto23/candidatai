import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { jobCoverLetter, jobView, letterRender, mockApi, renderApp, status } from '@/test/utils'

const NAME = 'Carta de presentación'

function withClipboard() {
  const writeText = vi.fn().mockResolvedValue(undefined)
  Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
  return writeText
}

afterEach(() => {
  Object.defineProperty(navigator, 'clipboard', { value: undefined, configurable: true })
})

describe('Sección Carta de presentación', () => {
  it('no aparece antes de aprobar la oferta', async () => {
    const calls = mockApi({ 'GET /status': status(), 'GET /jobs/1': jobView() })
    renderApp('/jobs/1?tab=application')
    await screen.findByRole('heading', { level: 1, name: 'Data Engineer' })
    expect(screen.queryByRole('region', { name: NAME })).not.toBeInTheDocument()
    expect(calls.some((c) => c.path === '/jobs/1/cover-letter')).toBe(false)
  })

  it('en una cerrada sin carta no aparece', async () => {
    mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView({ stage: 'closed' }),
      'GET /jobs/1/cover-letter': jobCoverLetter({ can_edit: false }, null),
    })
    renderApp('/jobs/1?tab=application')
    await screen.findByRole('heading', { level: 1, name: 'Data Engineer' })
    await waitFor(() => expect(screen.queryByRole('region', { name: NAME })).not.toBeInTheDocument())
  })

  it('sin carta, recuerda qué pedir al agente', async () => {
    mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView({ stage: 'approved' }),
      'GET /jobs/1/cover-letter': jobCoverLetter({}, null),
    })
    renderApp('/jobs/1?tab=application')
    const section = await screen.findByRole('region', { name: NAME })
    expect(await within(section).findByText('Aún sin carta')).toBeInTheDocument()
    expect(within(section).getByText(/escribe la carta de la oferta 1/)).toBeInTheDocument()
    expect(within(section).getByText('Menciona que uso su producto desde 2023.')).toBeInTheDocument()
    expect(within(section).getByText(/Límite: 150 palabras/)).toBeInTheDocument()
  })

  it('enseña la carta, la copia, descarga el TXT y marca otro render para enviar', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView({ stage: 'cv_ready' }),
      'GET /jobs/1/cover-letter': jobCoverLetter(
        {},
        { renders: [letterRender(1), letterRender(2, { selected: false, template_id: 'carta-simple' })] },
      ),
      'POST /renders/2/select': letterRender(2, { selected: true }),
    })
    renderApp('/jobs/1?tab=application')
    const section = await screen.findByRole('region', { name: NAME })
    expect(await within(section).findByText('Hola, equipo de Acme:')).toBeInTheDocument()
    expect(within(section).getByText('15 de 150 palabras')).toBeInTheDocument()
    expect(within(section).getByText('Verificada')).toBeInTheDocument()

    const writeText = withClipboard()
    await userEvent.click(within(section).getByRole('button', { name: 'Copiar texto' }))
    expect(writeText).toHaveBeenCalledWith(
      'Hola, equipo de Acme:\r\n\r\nOs escribo por el puesto de Data Engineer.\r\n',
    )
    expect(within(section).getByRole('link', { name: /Descargar TXT/ })).toHaveAttribute(
      'href',
      'http://127.0.0.1:8000/cover-letters/9/text',
    )
    // A la vista, el que se envía; los demás, plegados.
    await userEvent.click(within(section).getByRole('button', { name: 'Ver 1 versión más' }))
    const second = within(section).getByRole('listitem', { name: 'Versión 2 de la carta' })
    expect(within(second).getByRole('link', { name: /Descargar PDF/ })).toHaveAttribute(
      'href',
      'http://127.0.0.1:8000/renders/2/pdf',
    )
    await userEvent.click(within(second).getByRole('button', { name: /Usar la versión 2 de la carta/ }))
    await waitFor(() => expect(calls.some((c) => c.method === 'POST' && c.path === '/renders/2/select')).toBe(true))
  })

  it('guarda las indicaciones de la oferta', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView({ stage: 'cv_ready' }),
      'GET /jobs/1/cover-letter': jobCoverLetter(),
      'POST /jobs/1/cover-letter/brief': { ok: true, job_id: 1, brief: {}, max_words: 120 },
    })
    renderApp('/jobs/1?tab=application')
    const section = await screen.findByRole('region', { name: NAME })
    // Con carta, las indicaciones van plegadas.
    await userEvent.click(await within(section).findByRole('button', { name: 'Indicaciones' }))
    await userEvent.click(within(section).getByRole('button', { name: 'Editar indicaciones' }))
    const textarea = within(section).getByLabelText('Para esta oferta')
    await userEvent.clear(textarea)
    await userEvent.type(textarea, 'Más formal.')
    const max = within(section).getByLabelText('Máximo de palabras (opcional)')
    await userEvent.clear(max)
    await userEvent.type(max, '120')
    await userEvent.click(within(section).getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(calls.some((c) => c.path === '/jobs/1/cover-letter/brief')).toBe(true))
    expect(calls.find((c) => c.path === '/jobs/1/cover-letter/brief')?.body).toEqual({
      instructions: 'Más formal.',
      max_words: 120,
    })
  })

  it('renderiza con otro diseño, sin agente', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView({ stage: 'cv_ready' }),
      'GET /jobs/1/cover-letter': jobCoverLetter(),
      'POST /cover-letters/9/renders': letterRender(3),
    })
    renderApp('/jobs/1?tab=application')
    const section = await screen.findByRole('region', { name: NAME })
    await userEvent.click(await within(section).findByRole('button', { name: 'Cambiar diseño' }))
    const form = within(section).getByRole('form', { name: 'Generar la carta' })
    expect(within(form).getByRole('option', { name: 'A juego con el CV (Clásica con foto)' })).toBeInTheDocument()
    await userEvent.selectOptions(within(form).getByLabelText('Diseño'), 'carta-simple')
    expect(within(form).getByLabelText('Foto')).toBeDisabled()
    await userEvent.selectOptions(within(form).getByLabelText('Color'), '#2E5E4E')
    await userEvent.click(within(form).getByRole('button', { name: 'Generar' }))
    await waitFor(() => expect(calls.some((c) => c.path === '/cover-letters/9/renders')).toBe(true))
    expect(calls.find((c) => c.path === '/cover-letters/9/renders')?.body).toEqual({
      template_id: 'carta-simple',
      photo: 'exclude',
      accent_color: '#2E5E4E',
    })
  })

  it('se edita a mano y no deja guardar sin cambios', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView({ stage: 'cv_ready' }),
      'GET /jobs/1/cover-letter': jobCoverLetter(),
      'POST /jobs/1/cover-letter': { ok: true, job_id: 1, document_id: 10, word_count: 12, render: letterRender(4) },
    })
    renderApp('/jobs/1?tab=application')
    const section = await screen.findByRole('region', { name: NAME })
    await userEvent.click(await within(section).findByRole('button', { name: 'Editar' }))
    expect(within(section).getByRole('button', { name: 'Guardar' })).toBeDisabled()
    const second = within(section).getByLabelText('Párrafo 2')
    await userEvent.clear(second)
    await userEvent.type(second, 'Migré las cargas de SSIS a Python.')
    await userEvent.click(within(section).getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'POST' && c.path === '/jobs/1/cover-letter')).toBe(true))
    const body = calls.find((c) => c.path === '/jobs/1/cover-letter' && c.method === 'POST')?.body as {
      paragraphs: { text: string; evidence: string[] }[]
    }
    // Las evidencias van tal cual: el servidor añade `user` a los párrafos cambiados.
    expect(body.paragraphs).toEqual([
      { text: 'Os escribo por el puesto de Data Engineer.', evidence: ['extraction'] },
      { text: 'Migré las cargas de SSIS a Python.', evidence: ['exp-norteconsulting/a1'] },
    ])
  })

  it('tras enviar se ve y se copia, pero no se edita ni se renderiza', async () => {
    mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView({ stage: 'applied' }),
      'GET /jobs/1/cover-letter': jobCoverLetter({ can_edit: false }, { edited_by_user: true, verification: null }),
    })
    renderApp('/jobs/1?tab=application')
    // Ya enviada: lo de antes de enviar está plegado.
    const section = await screen.findByRole('region', { name: NAME })
    expect(await within(section).findByText('Editada por ti')).toBeInTheDocument()
    expect(within(section).getByRole('button', { name: 'Copiar texto' })).toBeEnabled()
    expect(within(section).queryByRole('button', { name: /Editar|Añadir/ })).not.toBeInTheDocument()
    expect(within(section).queryByRole('form', { name: 'Generar la carta' })).not.toBeInTheDocument()
  })
})
