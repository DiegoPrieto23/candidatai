import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { isUserPost, jobView, milestone, mockApi, processView, renderApp, status } from '@/test/utils'

describe('Sección Proceso de la ficha', () => {
  it('no aparece antes de aprobar la oferta', async () => {
    const calls = mockApi({ 'GET /status': status(), 'GET /jobs/1': jobView() })
    renderApp('/jobs/1')
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
    renderApp('/jobs/1')
    const section = await screen.findByRole('region', { name: 'Proceso' })
    expect(await within(section).findByText(/Enviada el/)).toHaveTextContent('Correo')
    expect(within(section).getByRole('link', { name: 'CV enviado' })).toHaveAttribute(
      'href',
      'http://127.0.0.1:8000/renders/3/pdf',
    )
    expect(within(section).getByText(/7 oct · 10:30/)).toBeInTheDocument()
    expect(within(section).getByRole('link', { name: 'Descargar .ics de «Entrevista»' })).toHaveAttribute(
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
    renderApp('/jobs/1')
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

  it('anota un seguimiento enviado', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView({ stage: 'applied' }),
      'GET /jobs/1/process': processView({
        followup: { due: true, days_waiting: 12, days_without_reply: 10 },
      }),
      'POST /jobs/1/events': { ok: true, event_id: 9, stage: 'applied' },
    })
    renderApp('/jobs/1')
    const section = await screen.findByRole('region', { name: 'Proceso' })
    expect(await within(section).findByText(/12 días sin respuesta/)).toBeInTheDocument()
    await userEvent.click(within(section).getByRole('button', { name: 'Seguimiento enviado' }))
    await waitFor(() => expect(calls.find(isUserPost)?.body).toEqual({ type: 'followup_sent' }))
  })
})
