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
    // Plegado siempre, también en la versión vigente: se abre si quieres verlo.
    expect(within(list).queryByText('Resumen largo.')).not.toBeInTheDocument()
    await userEvent.click(within(list).getByRole('button', { name: /^Qué cambió/ }))
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

describe('Panel de cambios', () => {
  it('las sugerencias solo rellenan la caja y cambiar de pestaña no pierde lo escrito', async () => {
    const coverage = { present: ['Python'], missing: ['dbt'] }
    const calls = mockApi(routes({ 'GET /jobs/1/cv': jobCv([renderResult(1, { keyword_coverage: coverage })]) }))
    const cv = await section()
    await userEvent.click(await within(cv).findByRole('button', { name: 'Menciona dbt' }))
    const box = within(cv).getByLabelText('Qué quieres corregir')
    expect(box).toHaveValue('Menciona dbt')
    await userEvent.click(within(cv).getByRole('button', { name: 'Acorta el resumen' }))
    expect(box).toHaveValue('Menciona dbt\nAcorta el resumen')
    expect(calls.some((c) => c.path === '/jobs/1/cv/corrections')).toBe(false)

    await userEvent.click(within(cv).getByRole('tab', { name: 'Diseño' }))
    expect(box).not.toBeVisible()
    await userEvent.click(within(cv).getByRole('tab', { name: 'Pedir cambios' }))
    expect(within(cv).getByLabelText('Qué quieres corregir')).toHaveValue('Menciona dbt\nAcorta el resumen')
  })
})

describe('Editar el texto del CV', () => {
  async function openEditor() {
    const cv = await section()
    await userEvent.click(await within(cv).findByRole('tab', { name: 'Editar texto' }))
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

describe('Editar logros y skills del CV', () => {
  const richCv = () =>
    jobCv([renderResult(1)], {
      content: {
        language: 'es',
        subtitle: 'Data Engineer',
        summary: 'Resumen ficticio.',
        projects: [],
        education_ids: [],
        certification_ids: [],
        extra_sections: [],
        languages: [],
        include_regional_language: false,
        keywords_targeted: [],
        experience: [
          {
            experience_id: 'exp-1',
            bullets: [
              { text: 'Primer logro.', evidence: ['exp-1/a1'] },
              { text: 'Segundo logro.', evidence: ['exp-1/a2'] },
            ],
          },
        ],
        skills: [
          { group: 'Lenguajes', items: ['Python', 'SQL'] },
          { group: 'Datos', items: ['dbt'] },
        ],
      },
    })

  async function openEditor() {
    const cv = await section()
    await userEvent.click(await within(cv).findByRole('tab', { name: 'Editar texto' }))
    return within(cv).findByRole('form', { name: 'Editar el texto del CV' })
  }

  type Sent = { content: { experience: { bullets: { text: string; evidence: string[] }[] }[]; skills: unknown } }
  const sent = (calls: { path: string; body?: unknown }[]) =>
    calls.find((c) => c.path === '/jobs/1/cv/edit')?.body as Sent

  it('reordena y quita logros con sus evidencias, sin dejar ninguna experiencia vacía', async () => {
    const calls = mockApi(
      routes({
        'GET /jobs/1/cv': richCv(),
        'POST /jobs/1/cv/edit': { ok: true, job_id: 1, document_id: 2, render: renderResult(1), warnings: [] },
      }),
    )
    const form = await openEditor()
    expect(within(form).getByRole('button', { name: 'Subir la viñeta 1 de Data Engineer · Acme' })).toBeDisabled()
    await userEvent.click(within(form).getByRole('button', { name: 'Bajar la viñeta 1 de Data Engineer · Acme' }))
    expect(within(form).getByRole('textbox', { name: /viñeta 1$/ })).toHaveValue('Segundo logro.')
    // Abajo del todo, «Bajar» se desactiva y el foco sigue al logro en su «Subir».
    expect(within(form).getByRole('button', { name: 'Subir la viñeta 2 de Data Engineer · Acme' })).toHaveFocus()
    await userEvent.click(within(form).getByRole('button', { name: 'Quitar la viñeta 2 de Data Engineer · Acme' }))
    expect(within(form).getByRole('button', { name: 'Quitar la viñeta 1 de Data Engineer · Acme' })).toBeDisabled()
    await userEvent.click(within(form).getByRole('button', { name: 'Guardar versión nueva' }))
    await waitFor(() => expect(sent(calls)).toBeDefined())
    expect(sent(calls).content.experience[0].bullets).toEqual([{ text: 'Segundo logro.', evidence: ['exp-1/a2'] }])
  })

  it('añade y quita skills como etiquetas, sin repetirlas', async () => {
    const calls = mockApi(
      routes({
        'GET /jobs/1/cv': richCv(),
        'POST /jobs/1/cv/edit': { ok: true, job_id: 1, document_id: 2, render: renderResult(1), warnings: [] },
      }),
    )
    const form = await openEditor()
    const chips = within(form).getByRole('list', { name: 'Skills de «Lenguajes»' })
    expect(within(chips).getAllByRole('listitem').map((li) => li.textContent)).toEqual(['Python', 'SQL'])
    const add = within(form).getByRole('textbox', { name: 'Añadir una skill a «Lenguajes»' })
    await userEvent.type(add, 'python{Enter}')
    expect(within(form).getByText('«python» ya está en este grupo.')).toBeInTheDocument()
    await userEvent.clear(add)
    // Intro añade la skill y no guarda la versión.
    await userEvent.type(add, 'Scala{Enter}')
    expect(calls.some((c) => c.path === '/jobs/1/cv/edit')).toBe(false)
    expect(add).toHaveValue('')
    await userEvent.type(add, 'Go')
    expect(within(form).getByText('Pulsa Intro para añadir «Go»; si no, no se guarda.')).toBeInTheDocument()
    await userEvent.clear(add)
    await userEvent.click(within(form).getByRole('button', { name: 'Quitar «SQL» de «Lenguajes»' }))
    expect(add).toHaveFocus()
    await userEvent.click(within(form).getByRole('button', { name: 'Guardar versión nueva' }))
    await waitFor(() => expect(sent(calls)).toBeDefined())
    expect(sent(calls).content.skills).toEqual([
      { group: 'Lenguajes', items: ['Python', 'Scala'] },
      { group: 'Datos', items: ['dbt'] },
    ])
  })

  it('añade, renombra, reordena y quita grupos; quitar uno con skills pide confirmación', async () => {
    const calls = mockApi(
      routes({
        'GET /jobs/1/cv': richCv(),
        'POST /jobs/1/cv/edit': { ok: true, job_id: 1, document_id: 2, render: renderResult(1), warnings: [] },
      }),
    )
    const form = await openEditor()
    const save = within(form).getByRole('button', { name: 'Guardar versión nueva' })
    await userEvent.click(within(form).getByRole('button', { name: 'Añadir grupo' }))
    const name = within(form).getByRole('textbox', { name: 'Nombre del grupo 3' })
    expect(name).toHaveFocus()
    // Sin nombre ni skills no se puede guardar.
    expect(save).toBeDisabled()
    expect(within(form).getByText(/cada grupo necesita un nombre/)).toBeInTheDocument()
    // Intro en el nombre no guarda.
    await userEvent.type(name, 'Nube{Enter}')
    expect(calls.some((c) => c.path === '/jobs/1/cv/edit')).toBe(false)
    await userEvent.type(within(form).getByRole('textbox', { name: 'Añadir una skill a «Nube»' }), 'AWS{Enter}')
    expect(save).toBeEnabled()
    await userEvent.click(within(form).getByRole('button', { name: 'Subir el grupo «Nube»' }))

    await userEvent.click(within(form).getByRole('button', { name: 'Quitar el grupo «Lenguajes»' }))
    const confirm = within(form).getByRole('group', { name: 'Quitar el grupo «Lenguajes»' })
    expect(confirm).toHaveTextContent('¿Quitar el grupo «Lenguajes» y sus 2 skills del CV?')
    await userEvent.click(within(confirm).getByRole('button', { name: 'Cancelar' }))
    expect(within(form).getByRole('textbox', { name: 'Nombre del grupo 1' })).toHaveValue('Lenguajes')
    await userEvent.click(within(form).getByRole('button', { name: 'Quitar el grupo «Lenguajes»' }))
    await userEvent.click(within(form).getByRole('button', { name: 'Quitar grupo' }))

    await userEvent.click(save)
    await waitFor(() => expect(sent(calls)).toBeDefined())
    expect(sent(calls).content.skills).toEqual([
      { group: 'Nube', items: ['AWS'] },
      { group: 'Datos', items: ['dbt'] },
    ])
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
