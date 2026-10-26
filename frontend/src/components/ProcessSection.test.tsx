import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { isUserPost, jobView, milestone, mockApi, processView, renderApp, status } from '@/test/utils'

describe('Sección Proceso de la ficha', () => {
  it('no aparece antes de aprobar la oferta', async () => {
    const calls = mockApi({ 'GET /status': status(), 'GET /jobs/1': jobView() })
    renderApp('/jobs/1?tab=process')
    await screen.findByRole('heading', { level: 1, name: 'Data Engineer' })
    expect(screen.queryByRole('region', { name: 'Proceso' })).not.toBeInTheDocument()
    expect(calls.some((c) => c.path === '/jobs/1/process')).toBe(false)
  })

  it('muestra envío, CV enviado, hitos con su .ics y contactos', async () => {
    mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView({ stage: 'in_process' }),
      'GET /jobs/1/process': processView({
        stage: 'in_process',
        applied_at: '2026-09-20T10:00:00Z',
        channel: 'email',
        milestones: [milestone(5, { location: 'https://meet.example/x' })],
        contacts: [
          {
            id: 1,
            job_id: 1,
            name: 'Ana Pérez',
            role: 'Recruiter',
            email: 'ana@example.com',
            phone: null,
            linkedin: null,
            notes: null,
            created_at: '2026-09-21T10:00:00Z',
          },
        ],
        documents: { cv_render_id: 3, cv_sent: true, answers_document_id: null, cover_letter_document_id: null },
      }),
    })
    renderApp('/jobs/1?tab=process')
    const section = await screen.findByRole('region', { name: 'Proceso' })
    expect(await within(section).findByText(/Enviada el/)).toHaveTextContent('Correo')
    expect(within(section).getByRole('link', { name: 'CV enviado' })).toHaveAttribute(
      'href',
      'http://127.0.0.1:8000/renders/3/pdf',
    )
    expect(within(section).getByText(/7 oct · 10:30/)).toBeInTheDocument()
    expect(within(section).getByRole('link', { name: 'Añadir «Entrevista» a mi calendario' })).toHaveAttribute(
      'href',
      'http://127.0.0.1:8000/milestones/5/ics',
    )
    expect(within(section).getByRole('link', { name: 'ana@example.com' })).toHaveAttribute(
      'href',
      'mailto:ana@example.com',
    )
  })

  it('no deja crear una entrevista antes de enviar; un plazo sí', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView({ stage: 'approved' }),
      'GET /jobs/1/process': processView({ stage: 'approved' }),
      'POST /jobs/1/milestones': milestone(6, { kind: 'deadline', all_day: true }),
    })
    renderApp('/jobs/1?tab=process')
    const section = await screen.findByRole('region', { name: 'Proceso' })
    const [addMilestone] = await within(section).findAllByRole('button', { name: 'Añadir' }) // hitos, primero
    await userEvent.click(addMilestone)
    await userEvent.type(within(section).getByLabelText('Fecha y hora (Madrid)'), '2026-10-07T10:30')
    expect(within(section).getByRole('button', { name: 'Guardar hito' })).toBeDisabled()
    expect(within(section).getByText(/cuando la candidatura ya está enviada/)).toBeInTheDocument()

    await userEvent.selectOptions(within(section).getByLabelText('Tipo'), 'deadline')
    await userEvent.click(within(section).getByLabelText('Todo el día'))
    expect(within(section).getByLabelText('Día')).toHaveValue('2026-10-07') // conserva el día
    await userEvent.clear(within(section).getByLabelText('Día'))
    await userEvent.type(within(section).getByLabelText('Día'), '2026-10-09')
    await userEvent.click(within(section).getByRole('button', { name: 'Guardar hito' }))
    await waitFor(() => expect(calls.some(isUserPost)).toBe(true))
    expect(calls.find(isUserPost)?.body).toMatchObject({
      kind: 'deadline',
      all_day: true,
      starts_at: '2026-10-09T00:00:00+02:00',
    })
  })

  it('una entrevista lleva su tipo; editarla lo puede quitar', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView({ stage: 'in_process' }),
      'GET /jobs/1/process': processView({
        stage: 'in_process',
        milestones: [milestone(5, { kind: 'interview', interview_type: 'hr' })],
      }),
      'POST /jobs/1/milestones': milestone(6, { kind: 'interview', interview_type: 'technical' }),
      'POST /milestones/5': milestone(5, { kind: 'interview' }),
    })
    renderApp('/jobs/1?tab=process')
    const section = await screen.findByRole('region', { name: 'Proceso' })
    expect(await within(section).findByText('RR. HH. o encaje cultural')).toBeInTheDocument()

    const [addMilestone] = within(section).getAllByRole('button', { name: 'Añadir' })
    await userEvent.click(addMilestone)
    await userEvent.selectOptions(within(section).getByLabelText('Tipo de entrevista'), 'technical')
    await userEvent.type(within(section).getByLabelText('Fecha y hora (Madrid)'), '2026-10-07T10:30')
    await userEvent.click(within(section).getByRole('button', { name: 'Guardar hito' }))
    await waitFor(() => expect(calls.some((c) => c.path === '/jobs/1/milestones')).toBe(true))
    expect(calls.find((c) => c.path === '/jobs/1/milestones')?.body).toMatchObject({
      kind: 'interview',
      interview_type: 'technical',
    })

    await userEvent.click(within(section).getByRole('button', { name: /^Editar «/ }))
    expect(within(section).getByLabelText('Tipo de entrevista')).toHaveValue('hr')
    await userEvent.selectOptions(within(section).getByLabelText('Tipo de entrevista'), '')
    await userEvent.click(within(section).getByRole('button', { name: 'Guardar hito' }))
    await waitFor(() =>
      expect(calls.find((c) => c.path === '/milestones/5')?.body).toMatchObject({ interview_type: null }),
    )
  })

  it('borra un hito tras confirmar y avisa de lo que se pierde', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView({ stage: 'in_process' }),
      'GET /jobs/1/process': processView({
        stage: 'in_process',
        milestones: [
          milestone(5, {
            kind: 'interview',
            status: 'cancelled',
            prep_plan: { blocks: [], saved_at: '2026-10-20T10:00:00Z', agent_name: null, dossier: null },
            prep_instructions: 'En inglés',
          }),
        ],
      }),
      'POST /milestones/5/delete': { ok: true, milestone_id: 5, job_id: 1, deleted_events: 2, stage: 'applied' },
    })
    renderApp('/jobs/1?tab=process')
    const section = await screen.findByRole('region', { name: 'Proceso' })
    // También una cancelada (ya no se edita) se puede borrar.
    await userEvent.click(await within(section).findByRole('button', { name: 'Borrar «Entrevista»' }))
    const dialog = await screen.findByRole('dialog')
    expect(dialog).toHaveTextContent('desaparece también del historial y del embudo')
    expect(dialog).toHaveTextContent('el plan de preparación')
    expect(dialog).toHaveTextContent('tus indicaciones para preparar y ensayar')
    expect(dialog).not.toHaveTextContent('el repaso')

    await userEvent.click(within(dialog).getByRole('button', { name: 'No borrar' }))
    expect(calls.some((c) => c.path === '/milestones/5/delete')).toBe(false)

    await userEvent.click(within(section).getByRole('button', { name: 'Borrar «Entrevista»' }))
    await userEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Borrar' }))
    await waitFor(() => expect(calls.some((c) => c.path === '/milestones/5/delete')).toBe(true))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('anota un seguimiento enviado', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView({ stage: 'applied' }),
      'GET /jobs/1/process': processView({
        followup: { due: true, days_waiting: 12, days_without_reply: 10 },
      }),
      'POST /jobs/1/events': { ok: true, event_id: 9, stage: 'applied' },
    })
    renderApp('/jobs/1?tab=process')
    const section = await screen.findByRole('region', { name: 'Proceso' })
    expect(await within(section).findByText(/12 días sin respuesta/)).toBeInTheDocument()
    await userEvent.click(within(section).getByRole('button', { name: 'Seguimiento enviado' }))
    await waitFor(() => expect(calls.find(isUserPost)?.body).toEqual({ type: 'followup_sent' }))
  })
})
