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
    expect(await within(region).findByRole('button', { name: 'Tengo entrevista' })).toBeInTheDocument()
    expect(within(region).getByRole('button', { name: 'Me han respondido' })).toBeInTheDocument()
    // Aceptar solo es posible ya en proceso.
    expect(within(region).queryByRole('button', { name: 'Acepto la oferta' })).not.toBeInTheDocument()
    await userEvent.click(within(region).getByRole('button', { name: 'Me han rechazado' }))
    const dialog = await screen.findByRole('dialog')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Registrar' }))
    await waitFor(() => {
      const call = calls.find((c) => c.method === 'POST' && c.path === '/jobs/1/events')
      expect(call?.body).toMatchObject({ type: 'rejected' })
    })
  })

  it('en proceso también deja aceptar la oferta', async () => {
    mockApi(routes('in_process'))
    renderApp('/jobs/1')
    const region = await screen.findByRole('region', { name: '¿Qué ha pasado?' })
    expect(await within(region).findByRole('button', { name: 'Acepto la oferta' })).toBeInTheDocument()
  })
})
