import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { jobView, mockApi, renderApp, status } from '@/test/utils'

const LINKEDIN = 'https://www.linkedin.com/jobs/view/4012345678'
const EXTENSION_ID = 'hnaofhehllbkghfehnehamjbkcmdjmle'
const LINKEDIN_ERROR = {
  status: 422,
  body: {
    ok: false,
    error: {
      type: 'linkedin_url',
      message: 'Las ofertas de LinkedIn no se descargan. … (`add_job_from_text` o `cai jobs add-text`).',
      details: [],
    },
  },
}

/** La extensión del navegador, instalada y conectada (o no, con `connected: false`). */
function installExtension(connected: boolean) {
  vi.stubGlobal('chrome', {
    runtime: {
      sendMessage: (_id: string, _message: unknown, callback: (reply: unknown) => void) =>
        setTimeout(() => callback({ version: '0.3.0', connected, kind: connected ? 'connected' : 'no_token', message: '' }), 0),
    },
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

async function submitLinkedIn(connected: boolean | null) {
  if (connected !== null) installExtension(connected)
  mockApi({
    'GET /status': status(),
    'POST /jobs/url': LINKEDIN_ERROR,
    'GET /capture/extension': { configured: true, extension_id: EXTENSION_ID, version: '0.3.0', folder: 'C:/CandidatAI/app/extension' },
  })
  renderApp('/nueva')
  await userEvent.type(screen.getByLabelText('Enlace de la oferta'), LINKEDIN)
  await userEvent.click(screen.getByRole('button', { name: 'Dar de alta' }))
}

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
        body: { ok: false, error: { type: 'invalid_request', message: 'No se descargan direcciones locales.', details: [] } },
      },
    })
    renderApp('/nueva')
    await userEvent.type(screen.getByLabelText('Enlace de la oferta'), 'http://localhost/jobs/1')
    await userEvent.click(screen.getByRole('button', { name: 'Dar de alta' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('No se descargan direcciones locales.')
  })

  it('una URL de LinkedIn guía hacia el botón del navegador o «Pegar texto», sin nombres internos', async () => {
    await submitLinkedIn(null)
    const guide = (await screen.findByText(/se añaden de una de estas dos formas/)).parentElement as HTMLElement
    expect(guide).not.toHaveTextContent(/add_job_from_text|cai jobs|add-text/)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    // Primero el botón del navegador: abre la oferta en otra pestaña y, sin extensión, lleva a instalarla.
    expect(screen.getByRole('status')).toHaveTextContent('Las ofertas de LinkedIn se añaden')
    const open = within(guide).getByRole('link', { name: /^Abrir la oferta/ })
    expect(open).toHaveAttribute('href', LINKEDIN)
    expect(open).toHaveAttribute('target', '_blank')
    expect(within(guide).getByRole('link', { name: 'Instalar el botón del navegador' })).toHaveAttribute(
      'href',
      '/fuentes/extension',
    )
    const headings = within(guide).getAllByRole('heading').map((h) => h.textContent)
    expect(headings).toEqual(['Con el botón del navegador', 'Pegando el texto'])
  })

  it('con el botón del navegador ya conectado, lo dice en una línea en vez de mandar a instalarlo', async () => {
    await submitLinkedIn(true)
    expect(await screen.findByText('Tu botón del navegador está conectado.')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Instalar el botón del navegador' })).not.toBeInTheDocument()
  })

  it('instalado pero sin conectar, sigue llevando a «Botón del navegador»', async () => {
    await submitLinkedIn(false)
    expect(await screen.findByRole('link', { name: 'Instalar el botón del navegador' })).toBeInTheDocument()
    expect(screen.queryByText('Tu botón del navegador está conectado.')).not.toBeInTheDocument()
  })

  it('«Pegar texto» del aviso de LinkedIn cambia de pestaña con la URL rellena', async () => {
    await submitLinkedIn(null)
    await screen.findByText(/se añaden de una de estas dos formas/)
    await userEvent.click(screen.getByRole('button', { name: 'Pegar texto' }))
    expect(await screen.findByLabelText(/^Enlace(?! de)/)).toHaveValue(LINKEDIN)
    expect(screen.getByRole('tab', { name: /Pegar texto/ })).toHaveAttribute('aria-selected', 'true')
  })

  it('si no puede abrir la página, lo explica sin el error técnico y lleva a pegar el texto', async () => {
    mockApi({
      'GET /status': status(),
      'POST /jobs/url': {
        status: 422,
        body: {
          ok: false,
          error: { type: 'page_unavailable', message: 'No se pudo descargar https://example.com/jobs/9: [WinError 10061] …', details: [] },
        },
      },
    })
    renderApp('/nueva')
    await userEvent.type(screen.getByLabelText('Enlace de la oferta'), 'https://example.com/jobs/9')
    await userEvent.click(screen.getByRole('button', { name: 'Dar de alta' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('No he podido abrir esa página')
    expect(alert).not.toHaveTextContent('WinError')
    await userEvent.click(screen.getByRole('button', { name: 'Pegar el texto' }))
    expect(await screen.findByLabelText(/^Enlace(?! de)/)).toHaveValue('https://example.com/jobs/9')
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
    await userEvent.type(screen.getByLabelText(/^Puesto/), 'Data Engineer')
    await userEvent.type(screen.getByLabelText(/^Empresa/), 'Brétema Analytics')
    await userEvent.type(screen.getByLabelText(/^Texto de la oferta/), 'Buscamos Data Engineer.')
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

  it('marca lo obligatorio y dice qué falta mientras «Dar de alta» está desactivado (H-012)', async () => {
    mockApi({ 'GET /status': status() })
    renderApp('/nueva')

    await userEvent.click(screen.getByRole('tab', { name: /Pegar texto/ }))
    expect(screen.getByLabelText(/^Puesto\s*\(obligatorio\)$/)).toBeInTheDocument()
    expect(screen.getByLabelText(/^Empresa\s*\(obligatorio\)$/)).toBeInTheDocument()
    const submit = screen.getByRole('button', { name: 'Dar de alta' })
    await userEvent.type(screen.getByLabelText(/^Texto de la oferta/), 'Data Engineer en Brétema.')
    expect(submit).toBeDisabled()
    expect(submit).toHaveAccessibleDescription('Para darla de alta, falta el puesto y la empresa.')
    await userEvent.type(screen.getByLabelText(/^Puesto/), 'Data Engineer')
    expect(submit).toHaveAccessibleDescription('Para darla de alta, falta la empresa.')
    await userEvent.type(screen.getByLabelText(/^Empresa/), 'Brétema')
    expect(submit).toBeEnabled()
    expect(screen.queryByText(/Para darla de alta/)).not.toBeInTheDocument()
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
    await userEvent.type(screen.getByLabelText(/^Puesto/), 'x')
    await userEvent.type(screen.getByLabelText(/^Empresa/), 'y')
    await userEvent.type(screen.getByLabelText(/^Texto de la oferta/), 'z')
    await userEvent.click(screen.getByRole('button', { name: 'Dar de alta' }))
    expect(await screen.findByText('No puede estar vacío.')).toBeInTheDocument()
  })
})
