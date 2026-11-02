import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { CvVersion } from '@/api/client'
import { jobCv, jobView, mockApi, renderApp, renderResult, status, templateList } from '@/test/utils'

const pendingCorrection = {
  id: 7,
  job_id: 1,
  instruction: 'El resumen más corto',
  status: 'pending',
  note: null,
  created_at: '2026-11-02T10:00:00Z',
  closed_at: null,
}

function version(changes: Partial<CvVersion> = {}): CvVersion {
  return {
    document_id: 1,
    created_at: '2026-11-01T10:00:00Z',
    current: true,
    origin: 'generated',
    instruction: null,
    note: null,
    verified: true,
    render: renderResult(1),
    changes: [],
    ...changes,
  }
}

function routes(extra: Record<string, unknown> = {}) {
  return {
    'GET /status': status(),
    'GET /jobs/1': jobView({ stage: 'cv_ready' }),
    'GET /jobs/1/cv': jobCv([renderResult(1)]),
    'GET /jobs/1/cv/history': { job_id: 1, versions: [version()], correction: null },
    'GET /jobs/1/cv/brief': { job_id: 1, instructions: '', updated_at: null },
    'GET /templates': templateList(),
    ...extra,
  }
}

async function section() {
  renderApp('/jobs/1?tab=application')
  return screen.findByRole('region', { name: 'CV' })
}

describe('Corregir el CV', () => {
  it('sin texto no se puede pedir; con texto guarda antes de abrir el agente', async () => {
    const calls = mockApi(
      routes({
        'POST /jobs/1/cv/corrections': pendingCorrection,
        'POST /agent/launch': { ok: true, agent: 'claude', model: null, prompt: 'orden', message: 'ok', warning: null, job_id: 1 },
      }),
    )
    const cv = await section()
    const box = await within(cv).findByLabelText('Qué quieres corregir')
    const submit = within(cv).getByRole('button', { name: /Pedir corrección/ })
    expect(submit).toBeDisabled()

    await userEvent.type(box, 'El resumen más corto')
    expect(submit).toBeEnabled()
    await userEvent.click(submit)

    await waitFor(() => expect(calls.some((c) => c.path === '/agent/launch')).toBe(true))
    const saved = calls.findIndex((c) => c.path === '/jobs/1/cv/corrections')
    const launched = calls.findIndex((c) => c.path === '/agent/launch')
    expect(saved).toBeGreaterThanOrEqual(0)
    expect(saved).toBeLessThan(launched)
    expect(calls[saved].body).toEqual({ instruction: 'El resumen más corto' })
    expect(calls[launched].body).toMatchObject({ action: 'correct-cv', job_id: 1 })
    expect(JSON.stringify(calls[launched].body)).not.toContain('resumen')
    await waitFor(() => expect(box).toHaveValue(''))
  })

  it('si no se puede guardar, no abre el agente y dice por qué', async () => {
    const calls = mockApi(
      routes({
        'POST /jobs/1/cv/corrections': {
          status: 409,
          body: { ok: false, error: { type: 'invalid_transition', message: 'Ya no se puede.', details: [] } },
        },
      }),
    )
    const cv = await section()
    await userEvent.type(await within(cv).findByLabelText('Qué quieres corregir'), 'Algo')
    await userEvent.click(within(cv).getByRole('button', { name: /Pedir corrección/ }))
    expect(await within(cv).findByRole('alert')).toHaveTextContent('Ya no se puede.')
    expect(calls.some((c) => c.path === '/agent/launch')).toBe(false)
  })

  it('enseña la pendiente, deja lanzarla sin reescribirla y la cancela', async () => {
    const calls = mockApi(
      routes({
        'GET /jobs/1/cv/history': { job_id: 1, versions: [version()], correction: pendingCorrection },
        'POST /cv-corrections/7/cancel': { ...pendingCorrection, status: 'cancelled' },
      }),
    )
    const cv = await section()
    expect(await within(cv).findByText('Esperando a tu agente:')).toBeInTheDocument()
    expect(within(cv).getByText('El resumen más corto')).toBeInTheDocument()
    expect(within(cv).getByRole('button', { name: /Pedir corrección/ })).toBeEnabled()
    await userEvent.click(within(cv).getByRole('button', { name: 'Cancelar' }))
    await waitFor(() => expect(calls.some((c) => c.path === '/cv-corrections/7/cancel')).toBe(true))
  })

  it('dice por qué tu agente no pudo aplicarla', async () => {
    mockApi(
      routes({
        'GET /jobs/1/cv/history': {
          job_id: 1,
          versions: [version()],
          correction: { ...pendingCorrection, status: 'declined', note: 'Tu perfil no lo respalda.' },
        },
      }),
    )
    const cv = await section()
    expect(await within(cv).findByText('Tu agente no ha podido aplicarla:')).toBeInTheDocument()
    expect(within(cv).getByText('Tu perfil no lo respalda.')).toBeInTheDocument()
  })

  it('tras enviar la candidatura ya no se puede corregir', async () => {
    mockApi(
      routes({
        'GET /jobs/1': jobView({ stage: 'applied' }),
        'GET /jobs/1/cv': { ...jobCv([renderResult(1)]), stage: 'applied', can_render: false },
      }),
    )
    const cv = await section()
    await within(cv).findByRole('listitem', { name: 'Diseño 1' })
    expect(within(cv).queryByLabelText('Qué quieres corregir')).not.toBeInTheDocument()
  })
})

describe('Versiones del CV', () => {
  /** Plegadas por defecto: el botón dice cuántas hay. */
  const openVersions = async (cv: HTMLElement) => {
    const list = await within(cv).findByRole('region', { name: 'Versiones del texto' })
    expect(within(list).queryByRole('listitem')).not.toBeInTheDocument()
    await userEvent.click(within(list).getByRole('button', { name: /^Versiones del texto \(\d+\)$/ }))
    return list
  }

  const history = {
    job_id: 1,
    correction: null,
    versions: [
      version({
        document_id: 2,
        created_at: '2026-11-02T10:00:00Z',
        origin: 'correction',
        instruction: 'El resumen más corto',
        note: 'No quité el proyecto.',
        verified: null,
        changes: [
          { section: 'summary', item: null, removed: ['Resumen largo.'], added: ['Resumen corto.'], reordered: false },
          { section: 'experience', item: 'Dev · Acme', removed: [], added: [], reordered: true },
        ],
      }),
      version({ current: false, render: renderResult(9) }),
    ],
  }

  it('con una sola versión no enseña la lista', async () => {
    mockApi(routes())
    const cv = await section()
    await within(cv).findByLabelText('Qué quieres corregir')
    expect(within(cv).queryByRole('region', { name: 'Versiones del texto' })).not.toBeInTheDocument()
  })

  it('enseña origen, corrección, nota y qué cambió', async () => {
    mockApi(routes({ 'GET /jobs/1/cv/history': history }))
    const cv = await section()
    const list = await openVersions(cv)
    expect(within(list).getByText('Corregida por tu agente')).toBeInTheDocument()
    expect(within(list).getByText('Vigente')).toBeInTheDocument()
    expect(within(list).getByText('El resumen más corto')).toBeInTheDocument()
    expect(within(list).getByText('No quité el proyecto.')).toBeInTheDocument()
    expect(within(list).getByText('Resumen largo.')).toBeInTheDocument()
    expect(within(list).getByText('Resumen corto.')).toBeInTheDocument()
    expect(within(list).getByText('Experiencia · Dev · Acme')).toBeInTheDocument()
    expect(within(list).getByText('Mismo texto, en otro orden.')).toBeInTheDocument()
  })

  it('vuelve a una versión anterior; la vigente no lo ofrece', async () => {
    const calls = mockApi(routes({ 'GET /jobs/1/cv/history': history, 'POST /documents/1/restore': jobCv([renderResult(1)]) }))
    const cv = await section()
    const list = await openVersions(cv)
    const buttons = within(list).getAllByRole('button', { name: 'Volver a esta versión' })
    expect(buttons).toHaveLength(1)
    await userEvent.click(buttons[0])
    await waitFor(() => expect(calls.some((c) => c.path === '/documents/1/restore')).toBe(true))
  })

  it('tras enviar la candidatura se ven, pero no se puede volver', async () => {
    mockApi(
      routes({
        'GET /jobs/1': jobView({ stage: 'applied' }),
        'GET /jobs/1/cv': { ...jobCv([renderResult(1)]), stage: 'applied', can_render: false },
        'GET /jobs/1/cv/history': history,
      }),
    )
    const cv = await section()
    const list = await openVersions(cv)
    expect(within(list).queryByRole('button', { name: 'Volver a esta versión' })).not.toBeInTheDocument()
  })
})

describe('Editar el texto del CV', () => {
  async function openEditor() {
    const cv = await section()
    await userEvent.click(await within(cv).findByRole('button', { name: 'Editar el texto tú' }))
    return within(cv).findByRole('form', { name: 'Editar el texto del CV' })
  }

  it('guarda solo si hay cambios, con la versión de la que parte', async () => {
    const calls = mockApi(
      routes({
        'POST /jobs/1/cv/edit': { ok: true, job_id: 1, document_id: 2, render: renderResult(1), warnings: [] },
      }),
    )
    const form = await openEditor()
    const save = within(form).getByRole('button', { name: 'Guardar versión nueva' })
    expect(save).toBeDisabled()
    const summary = within(form).getByLabelText('Resumen')
    await userEvent.clear(summary)
    await userEvent.type(summary, 'Otro resumen.')
    await userEvent.click(save)
    await waitFor(() => expect(calls.some((c) => c.path === '/jobs/1/cv/edit')).toBe(true))
    const body = calls.find((c) => c.path === '/jobs/1/cv/edit')?.body as {
      base_document_id: number
      content: { summary: string }
    }
    expect(body.base_document_id).toBe(1)
    expect(body.content.summary).toBe('Otro resumen.')
  })

  it('edita viñetas y, si el perfil no lo respalda, avisa pero guarda', async () => {
    const calls = mockApi(
      routes({
        'POST /jobs/1/cv/edit': {
          ok: true,
          job_id: 1,
          document_id: 2,
          render: renderResult(1),
          warnings: [
            { code: 'number', field: 'experience.0.bullets.0', value: '97' },
            { code: 'skill', field: 'skills.0.items.0', value: 'Cobol' },
          ],
        },
      }),
    )
    const form = await openEditor()
    const bullet = within(form).getByRole('textbox', { name: /viñeta 1$/ })
    await userEvent.clear(bullet)
    await userEvent.type(bullet, 'Mejoré un 97 %.')
    await userEvent.click(within(form).getByRole('button', { name: 'Guardar versión nueva' }))
    expect(await screen.findByText('La cifra «97» no aparece en tu perfil.')).toBeInTheDocument()
    expect(screen.getByText(/«Cobol» no está en tu perfil/)).toBeInTheDocument()
    expect(calls.filter((c) => c.path === '/jobs/1/cv/edit')).toHaveLength(1)
  })

  it('enseña el error si el CV cambió mientras editabas', async () => {
    mockApi(
      routes({
        'POST /jobs/1/cv/edit': {
          status: 409,
          body: { ok: false, error: { type: 'conflict', message: 'El CV ha cambiado.', details: [] } },
        },
      }),
    )
    const form = await openEditor()
    await userEvent.type(within(form).getByLabelText('Subtítulo'), ' senior')
    await userEvent.click(within(form).getByRole('button', { name: 'Guardar versión nueva' }))
    expect(await within(form).findByRole('alert')).toHaveTextContent('El CV ha cambiado.')
  })
})

describe('Verificar el CV', () => {
  it('sin verificar ofrece hacerlo; verificado, no', async () => {
    mockApi(routes({ 'GET /jobs/1/cv': jobCv([renderResult(1)], { verification: null }) }))
    const cv = await section()
    expect(await within(cv).findByRole('button', { name: /Verificar esta versión/ })).toBeInTheDocument()
  })

  it('verificado no ofrece volver a hacerlo', async () => {
    mockApi(routes({ 'GET /jobs/1/cv': jobCv([renderResult(1)], { verification: { passed: true, issues: [] } }) }))
    const cv = await section()
    await within(cv).findByLabelText('Qué quieres corregir')
    expect(within(cv).queryByRole('button', { name: /Verificar esta versión/ })).not.toBeInTheDocument()
  })
})
