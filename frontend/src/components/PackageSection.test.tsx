import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { isUserPost, jobPackage, jobView, mockApi, renderApp, SCREENING, status } from '@/test/utils'

const NAME = 'Paquete de candidatura'

function withClipboard() {
  const writeText = vi.fn().mockResolvedValue(undefined)
  Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
  return writeText
}

afterEach(() => {
  Object.defineProperty(navigator, 'clipboard', { value: undefined, configurable: true })
})

describe('Paquete de candidatura en la ficha', () => {
  it('en «approved» sin respuestas no aparece', async () => {
    mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView({ stage: 'approved' }),
      'GET /jobs/1/package': jobPackage({ stage: 'approved', cv: null, answers: null }),
    })
    renderApp('/jobs/1?tab=application')
    await screen.findByRole('heading', { level: 1, name: 'Data Engineer' })
    await waitFor(() => expect(screen.queryByRole('region', { name: NAME })).not.toBeInTheDocument())
  })

  it('muestra el CV elegido y el aviso de datos pendientes; sin carta no hay hueco', async () => {
    mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView({ stage: 'cv_ready' }),
      'GET /jobs/1/package': jobPackage(),
    })
    renderApp('/jobs/1?tab=application')
    const section = await screen.findByRole('region', { name: NAME })
    expect(await within(section).findByRole('link', { name: 'Abrir PDF' })).toHaveAttribute(
      'href',
      'http://127.0.0.1:8000/renders/3/pdf',
    )
    expect(within(section).getByText('1 respuesta espera un dato tuyo (salario, disponibilidad…).')).toBeInTheDocument()
    expect(within(section).getByText(/Falta un dato tuyo/)).toBeInTheDocument()
    expect(within(section).getByRole('button', { name: 'Copiar la respuesta 2' })).toBeDisabled()
    expect(within(section).queryByText('Carta de presentación')).not.toBeInTheDocument()
    // Ningún botón envía nada.
    expect(within(section).queryByRole('button', { name: /enviar/i })).not.toBeInTheDocument()
  })

  it('copia cada respuesta con su botón', async () => {
    mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView({ stage: 'cv_ready' }),
      'GET /jobs/1/package': jobPackage(),
    })
    renderApp('/jobs/1?tab=application')
    const section = await screen.findByRole('region', { name: NAME })
    const writeText = withClipboard()
    await userEvent.click(await within(section).findByRole('button', { name: 'Copiar la respuesta 1' }))
    expect(writeText).toHaveBeenCalledWith('Sí: migré las cargas de SSIS a Python.')
    expect(await within(section).findByText('Copiado')).toBeInTheDocument()
  })

  it('edita una respuesta sin agente: guarda todas, con la editada ya sin dato pendiente', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView({ stage: 'cv_ready' }),
      'GET /jobs/1/package': jobPackage(),
      'POST /jobs/1/answers': { ok: true, job_id: 1, document_id: 8, needs_user_input: 0 },
    })
    renderApp('/jobs/1?tab=application')
    const section = await screen.findByRole('region', { name: NAME })
    await userEvent.click(await within(section).findByRole('button', { name: 'Editar la respuesta 2' }))
    await userEvent.type(within(section).getByLabelText('Respuesta'), '45.000 € brutos al año')
    await userEvent.click(within(section).getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(calls.some(isUserPost)).toBe(true))
    expect(calls.find(isUserPost)?.body).toEqual({
      answers: [
        SCREENING!.answers[0],
        // Al cambiar el texto, el respaldo incluye al usuario.
        { question: 'Expectativa salarial', answer: '45.000 € brutos al año', evidence: ['user'], needs_user_input: false },
      ],
    })
  })

  it('incluye la carta vigente para copiarla y abrir su PDF', async () => {
    mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView({ stage: 'cv_ready' }),
      'GET /jobs/1/package': jobPackage({
        cover_letter: {
          document_id: 9,
          text: 'Hola, equipo de Acme:\r\n\r\nOs escribo por el puesto.\r\n',
          word_count: 6,
          edited_by_user: false,
          verified: true,
          render_id: 4,
          pdf_url: '/renders/4/pdf',
        },
      }),
    })
    renderApp('/jobs/1?tab=application')
    const section = await screen.findByRole('region', { name: NAME })
    expect(await within(section).findByText('6 palabras · Verificada')).toBeInTheDocument()
    const writeText = withClipboard()
    await userEvent.click(within(section).getByRole('button', { name: 'Copiar carta' }))
    expect(writeText).toHaveBeenCalledWith('Hola, equipo de Acme:\r\n\r\nOs escribo por el puesto.\r\n')
    const pdfLinks = within(section).getAllByRole('link', { name: /Abrir PDF/ })
    expect(pdfLinks.at(-1)).toHaveAttribute('href', 'http://127.0.0.1:8000/renders/4/pdf')
  })

  it('tras enviar se ve y se copia, pero no se edita', async () => {
    mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView({ stage: 'applied' }),
      'GET /jobs/1/package': jobPackage({
        stage: 'applied',
        can_edit: false,
        cv: { ...jobPackage().cv!, sent: true },
        answers: { ...SCREENING!, edited_by_user: true },
      }),
    })
    renderApp('/jobs/1?tab=application')
    // Ya enviada: lo de antes de enviar está plegado.
    const section = await screen.findByRole('region', { name: NAME })
    expect(await within(section).findByText('Editadas por ti')).toBeInTheDocument()
    expect(within(section).getByText(/El que enviaste/)).toBeInTheDocument()
    expect(within(section).getByRole('button', { name: 'Copiar la respuesta 1' })).toBeEnabled()
    expect(within(section).queryByRole('button', { name: /Editar/ })).not.toBeInTheDocument()
    expect(within(section).queryByRole('button', { name: 'Añadir pregunta' })).not.toBeInTheDocument()
  })
})
