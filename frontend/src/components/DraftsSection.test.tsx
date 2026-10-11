import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { MessageDraftOut } from '@/api/client'
import { jobView, mockApi, renderApp, status } from '@/test/utils'

const launcher = { available: true, agent: 'claude', reason: null, actions: [] }
const now = new Date().toISOString()

function draft(id: number, changes: Partial<MessageDraftOut> = {}): MessageDraftOut {
  return {
    id,
    job_id: 1,
    kind: 'followup',
    milestone_id: null,
    subject: 'Candidatura a Data Engineer',
    body: 'Hola, Laura:\n\nTe escribo para saber si hay novedades.',
    status: 'draft',
    event_id: null,
    agent_name: 'claude-code',
    created_at: now,
    updated_at: now,
    ...changes,
  }
}

function mockJob(drafts: MessageDraftOut[], sent = 0, extra: Record<string, unknown> = {}) {
  return mockApi({
    'GET /status': status(),
    'GET /agent': launcher,
    'GET /jobs/1': jobView({ stage: 'applied' }),
    'GET /jobs/1/drafts': { job_id: 1, followups_sent: sent, max_followups: 2, drafts },
    ...extra,
  })
}

describe('Borradores de la ficha', () => {
  it('enseña el borrador para copiarlo y ofrece redactar con tu agente', async () => {
    mockJob([draft(5)], 1)
    renderApp('/jobs/1')

    const section = await screen.findByRole('region', { name: 'Borradores' })
    expect(await within(section).findByText('Candidatura a Data Engineer')).toBeInTheDocument()
    expect(within(section).getByText(/Te escribo para saber si hay novedades/)).toBeInTheDocument()
    expect(within(section).getByText(/1 de 2 seguimientos enviados/)).toBeInTheDocument()
    expect(within(section).getByRole('button', { name: 'Copiar texto' })).toBeInTheDocument()
    expect(within(section).getByRole('button', { name: /Redactar seguimiento/ })).toBeInTheDocument()
  })

  it('«Ya lo he enviado» y «Descartar» llaman a la API sin enviar nada', async () => {
    const calls = mockJob([draft(5), draft(6, { kind: 'thank_you', subject: 'Gracias por la entrevista' })], 0, {
      'POST /drafts/5/sent': { ok: true, draft_id: 5, status: 'sent', event_id: 40, stage: 'applied', message: 'Anotado.' },
      'POST /drafts/6/discard': { ok: true, draft_id: 6, status: 'discarded', event_id: null, stage: 'applied', message: 'Descartado.' },
    })
    renderApp('/jobs/1')

    const section = await screen.findByRole('region', { name: 'Borradores' })
    const [first, second] = await within(section).findAllByRole('listitem')
    await userEvent.click(within(first).getByRole('button', { name: 'Ya lo he enviado' }))
    await userEvent.click(within(second).getByRole('button', { name: 'Descartar' }))

    await waitFor(() => expect(calls.some((c) => c.path === '/drafts/6/discard')).toBe(true))
    expect(calls.find((c) => c.path === '/drafts/5/sent')?.body).toEqual({})
    expect(within(second).getByText('Agradecimiento', { exact: false })).toBeInTheDocument()
  })

  it('con el tope de seguimientos lo dice y sin borradores lo explica', async () => {
    mockJob([], 2)
    renderApp('/jobs/1')
    const section = await screen.findByRole('region', { name: 'Borradores' })
    expect(await within(section).findByText(/2 de 2 seguimientos enviados: no conviene insistir más/)).toBeInTheDocument()
    expect(within(section).getByText(/Sin borradores/)).toBeInTheDocument()
  })

  it('no aparece antes de enviar la candidatura', async () => {
    mockApi({ 'GET /status': status(), 'GET /jobs/1': jobView() })
    renderApp('/jobs/1')
    expect(await screen.findByRole('heading', { level: 1, name: 'Data Engineer' })).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Borradores' })).not.toBeInTheDocument()
  })
})
