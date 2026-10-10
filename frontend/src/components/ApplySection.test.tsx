import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import {
  assistedApplication,
  attemptView,
  jobPackage,
  jobView,
  mockApi,
  renderApp,
  status,
} from '@/test/utils'

const NAME = 'Candidatura asistida'

function base(stage: 'approved' | 'cv_ready' | 'applied' = 'cv_ready') {
  return {
    'GET /status': status(),
    'GET /jobs/1': jobView({ stage }),
    'GET /jobs/1/package': jobPackage({ stage }),
  }
}

async function section() {
  return screen.findByRole('region', { name: NAME })
}

describe('Candidatura asistida en la ficha', () => {
  it('sin intento, prepara la candidatura y no envía nada', async () => {
    const calls = mockApi({
      ...base(),
      'GET /jobs/1/apply': assistedApplication(),
      'POST /jobs/1/apply/prepare': { status: 202, body: attemptView({ status: 'queued' }) },
    })
    renderApp('/jobs/1')
    const region = await section()
    expect(await within(region).findByText(/Se abrirá boards\.greenhouse\.io/)).toBeInTheDocument()
    await userEvent.click(within(region).getByRole('button', { name: 'Preparar candidatura' }))
    await waitFor(() => expect(calls.some((c) => c.path === '/jobs/1/apply/prepare')).toBe(true))
    expect(calls.some((c) => c.path.endsWith('/submit'))).toBe(false)
  })

  it('en «approved» sin intento ni LinkedIn no aparece', async () => {
    mockApi({ ...base('approved'), 'GET /jobs/1/apply': assistedApplication({ can_prepare: false }) })
    renderApp('/jobs/1')
    await screen.findByRole('heading', { level: 1, name: 'Data Engineer' })
    await waitFor(() => expect(screen.queryByRole('region', { name: NAME })).not.toBeInTheDocument())
  })

  it('en LinkedIn solo abre y prepara', async () => {
    mockApi({
      ...base('approved'),
      'GET /jobs/1/apply': assistedApplication({ mode: 'open', domain: 'www.linkedin.com' }),
    })
    renderApp('/jobs/1')
    const region = await section()
    expect(await within(region).findByRole('button', { name: 'Abrir y preparar' })).toBeInTheDocument()
    expect(within(region).getByText(/LinkedIn no se automatiza/)).toBeInTheDocument()
  })

  it('enseña la revisión: captura, campos y avisos', async () => {
    mockApi({ ...base(), 'GET /jobs/1/apply': assistedApplication({ attempt: attemptView() }) })
    renderApp('/jobs/1')
    const region = await section()
    expect(await within(region).findByText('Listo para revisar')).toBeInTheDocument()
    const shot = within(region).getByRole('img', { name: 'Captura del formulario rellenado' })
    expect(shot.getAttribute('src')).toContain('/apply/5/screenshot/review?v=')
    const table = within(region).getByRole('table', { name: 'Campos del formulario' })
    const email = within(table).getByRole('row', { name: /Email/ })
    expect(within(email).getByText('lucia.varela@example.com')).toBeInTheDocument()
    expect(within(email).getByText('Perfil: correo')).toBeInTheDocument()
    expect(within(table).getByText('Dato sensible: decides tú')).toBeInTheDocument()
    expect(within(table).getByText('Se acepta al enviar')).toBeInTheDocument()
    expect(within(region).getByRole('button', { name: 'Enviar' })).toBeEnabled()
  })

  it('«Enviar» pide el nombre de la empresa y manda la versión revisada', async () => {
    const calls = mockApi({
      ...base(),
      'GET /jobs/1/apply': assistedApplication({ attempt: attemptView() }),
      'POST /apply/5/submit': { status: 202, body: attemptView({ pending_task: { kind: 'apply_submit', status: 'queued', waiting_seconds: 0 } }) },
    })
    renderApp('/jobs/1')
    const region = await section()
    await userEvent.click(await within(region).findByRole('button', { name: 'Enviar' }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText('boards.greenhouse.io')).toBeInTheDocument()
    expect(within(dialog).getByText(/«Submit application»/)).toBeInTheDocument()
    expect(within(dialog).getByText('Acepto la política de privacidad')).toBeInTheDocument()
    const confirm = within(dialog).getByRole('button', { name: 'Enviar candidatura' })
    expect(confirm).toBeDisabled()
    const input = within(dialog).getByLabelText('Escribe el nombre de la empresa para confirmar')
    await userEvent.type(input, 'Otra')
    expect(confirm).toBeDisabled()
    await userEvent.clear(input)
    await userEvent.type(input, 'acme  analytics')
    expect(confirm).toBeEnabled()
    await userEvent.click(confirm)
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    const submit = calls.find((c) => c.path === '/apply/5/submit')
    expect(submit?.body).toEqual({
      company_confirmation: 'acme  analytics',
      reviewed_at: '2026-10-05T10:01:00.123456Z',
    })
  })

  it('muestra el error del servidor al confirmar', async () => {
    mockApi({
      ...base(),
      'GET /jobs/1/apply': assistedApplication({ attempt: attemptView() }),
      'POST /apply/5/submit': {
        status: 409,
        body: {
          ok: false,
          error: { type: 'invalid_transition', message: 'El intento ha cambiado desde que lo revisaste: revísalo otra vez.', details: [] },
        },
      },
    })
    renderApp('/jobs/1')
    const region = await section()
    await userEvent.click(await within(region).findByRole('button', { name: 'Enviar' }))
    const dialog = await screen.findByRole('dialog')
    await userEvent.type(within(dialog).getByLabelText(/nombre de la empresa/), 'Acme Analytics')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Enviar candidatura' }))
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('revísalo otra vez')
  })

  it('con obligatorios vacíos no deja enviar y ofrece volver a revisar', async () => {
    const missing = attemptView({
      can_submit: false,
      missing_required: 1,
      fields: [
        {
          marker: '0',
          label: '¿Cuándo podrías incorporarte?',
          control: 'text',
          kind: 'question',
          required: true,
          status: 'empty',
          source: null,
          value: null,
          note: null,
        },
      ],
    })
    const calls = mockApi({
      ...base(),
      'GET /jobs/1/apply': assistedApplication({ attempt: missing }),
      'POST /apply/5/rescan': { status: 202, body: missing },
    })
    renderApp('/jobs/1')
    const region = await section()
    expect(await within(region).findByRole('button', { name: 'Enviar' })).toBeDisabled()
    expect(within(region).getByText(/Falta 1 campo obligatorio/)).toBeInTheDocument()
    expect(within(region).getByText('Obligatorio sin respuesta')).toBeInTheDocument()
    await userEvent.click(within(region).getByRole('button', { name: 'Volver a revisar' }))
    await waitFor(() => expect(calls.some((c) => c.path === '/apply/5/rescan')).toBe(true))
  })

  it('avisa si el worker no recoge la tarea', async () => {
    const queued = attemptView({
      status: 'queued',
      fields: [],
      pending_task: { kind: 'apply_fill', status: 'queued', waiting_seconds: 40 },
    })
    mockApi({ ...base(), 'GET /jobs/1/apply': assistedApplication({ attempt: queued }) })
    renderApp('/jobs/1')
    const region = await section()
    expect(await within(region).findByText('En cola para el worker…')).toBeInTheDocument()
    expect(within(region).getByText('uv run jh worker')).toBeInTheDocument()
  })

  it('«Lo termino yo» y «Marcar como enviada»', async () => {
    const manual = attemptView({ status: 'manual', can_submit: false })
    const calls = mockApi({
      ...base(),
      'GET /jobs/1/apply': assistedApplication({ attempt: manual }),
      'POST /apply/5/focus': { status: 202, body: manual },
      'POST /jobs/1/apply/manual-done': { status: 200, body: { ok: true, event_id: 9, stage: 'applied' } },
    })
    renderApp('/jobs/1')
    const region = await section()
    expect(within(region).queryByRole('button', { name: 'Enviar' })).not.toBeInTheDocument()
    await userEvent.click(await within(region).findByRole('button', { name: 'Lo termino yo' }))
    await userEvent.click(within(region).getByRole('button', { name: 'Marcar como enviada' }))
    await waitFor(() => expect(calls.some((c) => c.path === '/jobs/1/apply/manual-done')).toBe(true))
    expect(calls.some((c) => c.path === '/apply/5/focus')).toBe(true)
  })

  it('tras enviar enseña la confirmación', async () => {
    const sent = attemptView({ status: 'submitted', has_confirmation: true, can_submit: false })
    mockApi({
      ...base('applied'),
      'GET /jobs/1/apply': assistedApplication({ attempt: sent, can_prepare: false }),
    })
    renderApp('/jobs/1')
    const region = await section()
    expect(await within(region).findByText(/la web confirmó el envío/)).toBeInTheDocument()
    expect(within(region).getByRole('img', { name: 'Captura después de enviar' })).toBeInTheDocument()
  })

  it('en un portal de empleo la oferta se abre en tu navegador, no en el de Job Hunter', async () => {
    const url = 'https://www.glassdoor.es/job-listing/1'
    const calls = mockApi({
      ...base(),
      'GET /jobs/1/apply': assistedApplication({ mode: 'open', domain: 'www.glassdoor.es', url, portal: 'Glassdoor' }),
    })
    renderApp('/jobs/1')
    const region = await section()
    expect(await within(region).findByText(/bloquea los navegadores automatizados/)).toBeInTheDocument()
    const link = within(region).getByRole('link', { name: 'Abrir la oferta en Glassdoor' })
    expect(link).toHaveAttribute('href', url)
    expect(link).toHaveAttribute('target', '_blank')
    expect(within(region).getByRole('button', { name: 'Marcar como enviada' })).toBeInTheDocument()
    expect(calls.some((c) => c.path === '/jobs/1/apply/prepare')).toBe(false)
  })

  it('con el enlace al formulario de la empresa, rellena esa URL', async () => {
    const calls = mockApi({
      ...base(),
      'GET /jobs/1/apply': assistedApplication({ mode: 'open', domain: 'www.glassdoor.es', portal: 'Glassdoor' }),
      'POST /jobs/1/apply/prepare': { status: 202, body: attemptView({ status: 'queued' }) },
    })
    renderApp('/jobs/1')
    const region = await section()
    const button = await within(region).findByRole('button', { name: 'Rellenar ese formulario' })
    expect(button).toBeDisabled()
    await userEvent.type(within(region).getByLabelText('URL del formulario'), 'https://jobs.lever.co/acme/1')
    await userEvent.click(button)
    await waitFor(() => {
      const call = calls.find((c) => c.path === '/jobs/1/apply/prepare')
      expect(call?.body).toEqual({ form_url: 'https://jobs.lever.co/acme/1' })
    })
  })

  it('abierta en el portal: «Rellenar esta página» rellena la pestaña que tienes delante', async () => {
    const opened = attemptView({
      platform: 'board',
      mode: 'open',
      status: 'manual',
      url: 'https://www.glassdoor.es/job-listing/1',
      domain: 'www.glassdoor.es',
      fields: [],
      warnings: [],
      consents: [],
      can_submit: false,
      can_rescan: false,
      can_fill_page: true,
      has_screenshot: false,
      submit_button: null,
    })
    const calls = mockApi({
      ...base(),
      'GET /jobs/1/apply': assistedApplication({ attempt: opened, mode: 'open', portal: 'Glassdoor' }),
      'POST /apply/5/fill-page': { status: 202, body: { ...opened, status: 'queued' } },
    })
    renderApp('/jobs/1')
    const region = await section()
    await userEvent.click(await within(region).findByRole('button', { name: 'Rellenar esta página' }))
    await waitFor(() => expect(calls.some((c) => c.path === '/apply/5/fill-page')).toBe(true))
  })

  it('«Abrir navegador» encola abrirlo', async () => {
    const calls = mockApi({
      ...base(),
      'GET /jobs/1/apply': assistedApplication(),
      'POST /browser/open': { status: 202, body: { ok: true, message: 'El navegador se abrirá en unos segundos.' } },
    })
    renderApp('/jobs/1')
    const region = await section()
    await within(region).findByRole('button', { name: 'Preparar candidatura' })
    await userEvent.click(within(region).getByRole('button', { name: 'Abrir navegador' }))
    expect(await within(region).findByText('El navegador se abrirá en unos segundos.')).toBeInTheDocument()
    expect(calls.some((c) => c.path === '/browser/open')).toBe(true)
  })

  it('«Cancelar» deja el diálogo vacío y Intro no envía', async () => {
    const calls = mockApi({ ...base(), 'GET /jobs/1/apply': assistedApplication({ attempt: attemptView() }) })
    renderApp('/jobs/1')
    const region = await section()
    await userEvent.click(await within(region).findByRole('button', { name: 'Enviar' }))
    let dialog = await screen.findByRole('dialog')
    await userEvent.type(within(dialog).getByLabelText(/nombre de la empresa/), 'Acme Analytics{Enter}')
    expect(calls.some((c) => c.path.endsWith('/submit'))).toBe(false)
    await userEvent.click(within(dialog).getByRole('button', { name: 'Cancelar' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    await userEvent.click(within(region).getByRole('button', { name: 'Enviar' }))
    dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByLabelText(/nombre de la empresa/)).toHaveValue('')
    expect(within(dialog).getByRole('button', { name: 'Enviar candidatura' })).toBeDisabled()
  })

  it('tras un envío sin confirmar no deja reenviar ese intento', async () => {
    const unconfirmed = attemptView({
      status: 'submit_unconfirmed',
      can_submit: false,
      can_rescan: false,
      error: 'No se ha reconocido la página de confirmación.',
    })
    mockApi({ ...base(), 'GET /jobs/1/apply': assistedApplication({ attempt: unconfirmed }) })
    renderApp('/jobs/1')
    const region = await section()
    expect(await within(region).findByText('Envío sin confirmar')).toBeInTheDocument()
    expect(within(region).queryByRole('button', { name: 'Enviar' })).not.toBeInTheDocument()
    expect(within(region).queryByRole('button', { name: 'Volver a revisar' })).not.toBeInTheDocument()
    expect(within(region).getByRole('button', { name: 'Marcar como enviada' })).toBeInTheDocument()
    expect(within(region).getByText(/comprueba en la web o en tu correo/)).toBeInTheDocument()
    expect(within(region).getByRole('button', { name: 'Preparar de nuevo' })).toBeInTheDocument()
  })

  it('enviada pero sin registrar: ofrece marcarla a mano', async () => {
    const sent = attemptView({
      status: 'submitted',
      can_submit: false,
      error: 'Enviada, pero no se pudo registrar «applied»: márcala como enviada a mano.',
    })
    mockApi({ ...base(), 'GET /jobs/1/apply': assistedApplication({ attempt: sent, can_prepare: false }) })
    renderApp('/jobs/1')
    const region = await section()
    expect(await within(region).findByText(/no se pudo registrar/)).toBeInTheDocument()
    expect(within(region).getByRole('button', { name: 'Marcar como enviada' })).toBeInTheDocument()
  })

  it('cuando el worker termina el envío, refresca la ficha', async () => {
    let polls = 0
    const calls = mockApi({
      ...base(),
      'GET /jobs/1/apply': () => {
        polls += 1
        const status = polls === 1 ? 'submitting' : 'submitted'
        return assistedApplication({ attempt: attemptView({ status, can_submit: false }) })
      },
    })
    renderApp('/jobs/1')
    const region = await section()
    expect(await within(region).findByText(/Enviando/)).toBeInTheDocument()
    expect(await within(region).findByText(/la web confirmó el envío/, {}, { timeout: 5000 })).toBeInTheDocument()
    await waitFor(() => expect(calls.filter((c) => c.method === 'GET' && c.path === '/jobs/1').length).toBeGreaterThan(1))
  })
})
