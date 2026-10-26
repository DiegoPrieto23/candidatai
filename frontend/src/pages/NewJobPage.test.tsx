import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { jobView, mockApi, renderApp, status } from '@/test/utils'

describe('Alta de ofertas', () => {
  it('da de alta por URL y lleva a la ficha', async () => {
    const calls = mockApi({
      'GET /status': status(1),
      'POST /jobs/url': { job_id: 7, created: true, duplicate_of: null, risk_flags: [] },
      'GET /jobs/7': jobView({ id: 7, extraction: null }),
    })
    renderApp('/nueva')

    await userEvent.type(screen.getByLabelText('Enlace de la oferta'), 'https://example.com/jobs/7')
    await userEvent.click(screen.getByRole('button', { name: 'Dar de alta' }))

    expect(await screen.findByText(/Oferta dada de alta/)).toBeInTheDocument()
    expect(calls.find((c) => c.method === 'POST')?.body).toEqual({ url: 'https://example.com/jobs/7' })
  })

  it('muestra el error de la API bajo el formulario', async () => {
    mockApi({
      'GET /status': status(),
      'POST /jobs/url': {
        status: 422,
        body: { ok: false, error: { type: 'invalid_request', message: 'LinkedIn no se descarga: pega el texto.', details: [] } },
      },
    })
    renderApp('/nueva')
    await userEvent.type(screen.getByLabelText('Enlace de la oferta'), 'https://www.linkedin.com/jobs/view/1')
    await userEvent.click(screen.getByRole('button', { name: 'Dar de alta' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('LinkedIn no se descarga: pega el texto.')
  })

  it('da de alta pegando el texto y avisa si era un duplicado', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'POST /jobs/text': { job_id: 8, created: true, duplicate_of: 3, risk_flags: [] },
      'GET /jobs/8': jobView({ id: 8, stage: 'closed' }),
    })
    renderApp('/nueva')

    await userEvent.click(screen.getByRole('tab', { name: /Pegar texto/ }))
    const submit = screen.getByRole('button', { name: 'Dar de alta' })
    expect(submit).toBeDisabled()
    await userEvent.type(screen.getByLabelText('Puesto'), 'Data Engineer')
    await userEvent.type(screen.getByLabelText('Empresa'), 'Brétema Analytics')
    await userEvent.type(screen.getByLabelText('Texto de la oferta'), 'Buscamos Data Engineer.')
    await userEvent.click(submit)

    expect(await screen.findByRole('link', { name: 'oferta 3' })).toHaveAttribute('href', '/jobs/3')
    expect(calls.find((c) => c.method === 'POST')?.body).toEqual({
      title: 'Data Engineer',
      company: 'Brétema Analytics',
      text: 'Buscamos Data Engineer.',
      location: null,
      url: null,
    })
  })

  it('marca el campo con error de validación', async () => {
    mockApi({
      'GET /status': status(),
      'POST /jobs/text': {
        status: 422,
        body: {
          ok: false,
          error: { type: 'validation_error', message: 'Entrada no válida (1 error): title.', details: [{ field: 'title', received: '', reason: 'No puede estar vacío.' }] },
        },
      },
    })
    renderApp('/nueva')
    await userEvent.click(screen.getByRole('tab', { name: /Pegar texto/ }))
    await userEvent.type(screen.getByLabelText('Puesto'), 'x')
    await userEvent.type(screen.getByLabelText('Empresa'), 'y')
    await userEvent.type(screen.getByLabelText('Texto de la oferta'), 'z')
    await userEvent.click(screen.getByRole('button', { name: 'Dar de alta' }))
    expect(await screen.findByText('No puede estar vacío.')).toBeInTheDocument()
  })
})
