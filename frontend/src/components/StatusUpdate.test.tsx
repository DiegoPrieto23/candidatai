import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { board, jobView, mockApi, processView, renderApp, status } from '@/test/utils'

function routes(stage: 'cv_ready' | 'applied' | 'in_process') {
  return {
    'GET /status': status(),
    'GET /jobs/1': jobView({ stage }),
    'GET /jobs/1/process': processView({ stage }),
    'GET /board': board([]),
  }
}

describe('«¿Qué ha pasado?» en la ficha', () => {
  it('no aparece antes de enviar la candidatura', async () => {
    mockApi(routes('cv_ready'))
    renderApp('/jobs/1')
    await screen.findByRole('heading', { level: 1, name: 'Data Engineer' })
    expect(screen.queryByRole('region', { name: '¿Qué ha pasado?' })).not.toBeInTheDocument()
  })

  it('enviada: ofrece los pasos posibles y registra un rechazo con su evento', async () => {
    const calls = mockApi({
      ...routes('applied'),
      'POST /jobs/1/events': { status: 201, body: { ok: true, event_id: 9, stage: 'closed' } },
    })
    renderApp('/jobs/1')
    const region = await screen.findByRole('region', { name: '¿Qué ha pasado?' })
    expect(await within(region).findByRole('button', { name: 'Entrevista concertada' })).toBeInTheDocument()
    expect(within(region).getByRole('button', { name: 'Respuesta de la empresa' })).toBeInTheDocument()
    // Aceptar solo es posible ya en proceso.
    expect(within(region).queryByRole('button', { name: 'Aceptar la oferta' })).not.toBeInTheDocument()
    await userEvent.click(within(region).getByRole('button', { name: 'Rechazo de la empresa' }))
    const dialog = await screen.findByRole('dialog')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Registrar' }))
    await waitFor(() => {
      const call = calls.find((c) => c.method === 'POST' && c.path === '/jobs/1/events')
      expect(call?.body).toMatchObject({ type: 'rejected' })
    })
  })

  it('si algo anotado después no encaja con la fecha, propone quitarlo o anotarlo después', async () => {
    const conflicts = {
      conflicts: [
        { id: 31, type: 'followup_sent', occurred_at: '2026-11-05T17:01:00Z', removable: true },
        { id: 32, type: 'followup_sent', occurred_at: '2026-11-05T17:01:01Z', removable: true },
      ],
      can_remove: true,
      suggested_at: '2026-11-05T17:02:00Z',
    }
    const calls = mockApi({
      ...routes('in_process'),
      'POST /jobs/1/events': async (request: Request) => {
        const body = (await request.json()) as { remove_event_ids?: number[] }
        return body.remove_event_ids
          ? { status: 201, body: { ok: true, event_id: 9, stage: 'closed' } }
          : { status: 409, body: { ok: false, error: { type: 'later_events', message: 'No se puede anotar.', details: [] } } }
      },
      'POST /jobs/1/events/check': conflicts,
    })
    renderApp('/jobs/1')
    const region = await screen.findByRole('region', { name: '¿Qué ha pasado?' })
    await userEvent.click(await within(region).findByRole('button', { name: 'Rechazo de la empresa' }))
    const dialog = await screen.findByRole('dialog')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Registrar' }))

    expect(await within(dialog).findByRole('heading', { name: 'Hay algo anotado después de esa fecha' })).toBeInTheDocument()
    expect(within(dialog).getAllByText('Seguimiento enviado')).toHaveLength(2)
    expect(within(dialog).getByRole('button', { name: /^Anotar el / })).toBeInTheDocument()
    expect(within(dialog).queryByRole('alert')).not.toBeInTheDocument()
    await userEvent.click(within(dialog).getByRole('button', { name: /^Quitar estos 2 y anotar el / }))
    await waitFor(() => {
      const posts = calls.filter((c) => c.method === 'POST' && c.path === '/jobs/1/events')
      expect(posts.at(-1)?.body).toMatchObject({ type: 'rejected', remove_event_ids: [31, 32] })
    })
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('en proceso deja anotar otra entrevista, una prueba o una oferta sin cambiar de etapa (H-007)', async () => {
    const calls = mockApi({
      ...routes('in_process'),
      'POST /jobs/1/events': { status: 201, body: { ok: true, event_id: 9, stage: 'in_process' } },
    })
    renderApp('/jobs/1')
    const region = await screen.findByRole('region', { name: '¿Qué ha pasado?' })
    for (const name of ['Respuesta de la empresa', 'Entrevista concertada', 'Entrevista hecha', 'Prueba técnica']) {
      expect(await within(region).findByRole('button', { name })).toBeInTheDocument()
    }
    // Sin oferta registrada no se puede aceptar: primero, la oferta.
    expect(within(region).queryByRole('button', { name: 'Aceptar la oferta' })).not.toBeInTheDocument()
    await userEvent.click(within(region).getByRole('button', { name: 'Oferta recibida' }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByRole('radio', { checked: true })).toHaveTextContent('→ En proceso')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Registrar' }))
    await waitFor(() => {
      const call = calls.find((c) => c.method === 'POST' && c.path === '/jobs/1/events')
      expect(call?.body).toMatchObject({ type: 'offer_received' })
    })
  })

  it('con una oferta registrada, deja aceptarla', async () => {
    const now = new Date().toISOString()
    const offer = { id: 3, type: 'offer_received', actor: 'user', agent_name: null, payload: {}, occurred_at: now, recorded_at: now }
    const base = jobView({ stage: 'in_process' })
    mockApi({ ...routes('in_process'), 'GET /jobs/1': { ...base, events: [...base.events, offer] } })
    renderApp('/jobs/1')
    const region = await screen.findByRole('region', { name: '¿Qué ha pasado?' })
    expect(await within(region).findByRole('button', { name: 'Aceptar la oferta' })).toBeInTheDocument()
  })

  it('lleva a «Anotar oferta» y a «Hitos» para los detalles', async () => {
    mockApi({ ...routes('in_process'), 'GET /jobs/1/received-offer': null })
    renderApp('/jobs/1')
    const region = await screen.findByRole('region', { name: '¿Qué ha pasado?' })
    expect(within(region).getByRole('button', { name: 'Anotar oferta' })).toBeInTheDocument()
    await userEvent.click(within(region).getByRole('button', { name: 'Hitos → Añadir' }))
    await waitFor(() => {
      const focused = document.activeElement
      expect(focused).toHaveAccessibleName('Añadir')
      expect(focused?.closest('#job-milestones')).not.toBeNull()
    })
  })
})
