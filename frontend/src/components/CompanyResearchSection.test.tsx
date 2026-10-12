import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { CompanyResearchResult, MessageDraftOut } from '@/api/client'
import { jobView, mockApi, processView, renderApp, status } from '@/test/utils'

const launcher = { available: true, agent: 'claude', reason: null, actions: [] }
const now = new Date().toISOString()

function research(changes: Partial<NonNullable<CompanyResearchResult['research']>> = {}): CompanyResearchResult {
  return {
    job_id: 1,
    company: 'Brétema Analytics',
    research: {
      content: {
        summary: 'Consultora de datos para la distribución gallega [1].',
        product: 'Previsión de demanda [2].',
        news: null,
        engineering_culture: null,
        stack: ['Python', 'dbt'],
        notes: 'Preguntar por las guardias.',
        sources: [
          { title: 'Quiénes somos', url: 'https://bretema.example.com/about', accessed_on: null },
          { title: 'Nota de prensa', url: 'https://prensa.example.com/x', accessed_on: '2026-10-10' },
        ],
      },
      risk_flags: [],
      file: 'documentos/empresas/Bretema-Analytics_1.md',
      agent_name: 'claude-code',
      job_id: 1,
      created_at: now,
      updated_at: now,
      age_days: 2,
      ...changes,
    },
  }
}

function draft(id: number, changes: Partial<MessageDraftOut> = {}): MessageDraftOut {
  return {
    id,
    job_id: 1,
    kind: 'linkedin',
    milestone_id: null,
    subject: null,
    body: 'Hola, Uxía: he visto la oferta de Data Engineer y me encantaría hablar 15 minutos.',
    status: 'draft',
    event_id: null,
    agent_name: 'claude-code',
    created_at: now,
    updated_at: now,
    recipient_role: 'hiring_manager',
    contact_id: null,
    network_contact_id: 3,
    recipient_name: 'Uxía Barreiro',
    attachments: null,
    ...changes,
  }
}

describe('Empresa en la ficha', () => {
  it('enseña el dosier con citas enlazadas, stack y fuentes', async () => {
    mockApi({
      'GET /status': status(),
      'GET /agent': launcher,
      'GET /jobs/1': jobView(),
      'GET /jobs/1/company-research': research(),
    })
    renderApp('/jobs/1')
    const section = await screen.findByRole('region', { name: 'Empresa' })
    expect(await within(section).findByText(/Consultora de datos/)).toBeInTheDocument()
    expect(within(section).getByRole('link', { name: '[1]' })).toHaveAttribute('href', 'https://bretema.example.com/about')
    expect(within(section).getByRole('list', { name: 'Stack' })).toHaveTextContent('Pythondbt')
    const sources = within(section).getByRole('list', { name: 'Fuentes' })
    expect(within(sources).getByRole('link', { name: /Nota de prensa/ })).toHaveAttribute('href', 'https://prensa.example.com/x')
    expect(within(section).getByText('Preguntar por las guardias.')).toBeInTheDocument()
    expect(within(section).getByRole('button', { name: /Actualizar dosier/ })).toBeInTheDocument()
    expect(within(section).getByText(/La carta no lo usa/)).toBeInTheDocument()
  })

  it('sin dosier ofrece investigar', async () => {
    mockApi({
      'GET /status': status(),
      'GET /agent': launcher,
      'GET /jobs/1': jobView({ stage: 'approved' }),
      'GET /jobs/1/process': processView({ stage: 'approved' }),
      'GET /jobs/1/drafts': { job_id: 1, followups_sent: 0, max_followups: 2, drafts: [] },
      'GET /jobs/1/company-research': { job_id: 1, company: 'Brétema Analytics', research: null },
    })
    renderApp('/jobs/1')
    const section = await screen.findByRole('region', { name: 'Empresa' })
    expect(await within(section).findByRole('button', { name: /Investigar empresa/ })).toBeInTheDocument()
  })

  it('avisa si el dosier trae frases para una IA o está viejo', async () => {
    mockApi({
      'GET /status': status(),
      'GET /agent': launcher,
      'GET /jobs/1': jobView(),
      'GET /jobs/1/company-research': research({ risk_flags: ['injection_phrase'], age_days: 45 }),
    })
    renderApp('/jobs/1')
    const section = await screen.findByRole('region', { name: 'Empresa' })
    expect(await within(section).findByText(/frases dirigidas a una IA/)).toBeInTheDocument()
    expect(within(section).getByText(/Tiene 45 días/)).toBeInTheDocument()
  })

  it('una oferta cerrada sin dosier no enseña la sección', async () => {
    mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView({ stage: 'closed' }),
      'GET /jobs/1/company-research': { job_id: 1, company: 'Brétema Analytics', research: null },
    })
    renderApp('/jobs/1')
    await screen.findByRole('heading', { level: 1, name: 'Data Engineer' })
    await waitFor(() => expect(screen.queryByRole('region', { name: 'Empresa' })).not.toBeInTheDocument())
  })
})

describe('Mensajes en Borradores', () => {
  it('antes de enviar: mensaje de LinkedIn con destinatario y recuento, y correo con adjuntos', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /agent': launcher,
      'GET /jobs/1': jobView({ stage: 'approved' }),
      'GET /jobs/1/process': processView({ stage: 'approved' }),
      'GET /jobs/1/company-research': { job_id: 1, company: 'Brétema Analytics', research: null },
      'GET /jobs/1/drafts': {
        job_id: 1,
        followups_sent: 0,
        max_followups: 2,
        drafts: [
          draft(5),
          draft(6, {
            kind: 'email',
            subject: 'Candidatura: Data Engineer',
            body: 'Hola:\n\nOs envío mi candidatura.',
            recipient_role: 'recruiter',
            recipient_name: null,
            network_contact_id: null,
            attachments: ['CV (PDF)', 'Carta de presentación'],
          }),
        ],
      },
      'POST /drafts/5/sent': { ok: true, draft_id: 5, status: 'sent', event_id: null, stage: 'approved', message: 'Anotado.' },
    })
    renderApp('/jobs/1')
    const section = await screen.findByRole('region', { name: 'Borradores' })
    await within(section).findByText('Candidatura: Data Engineer')
    // Las tarjetas (no los adjuntos, que también son `listitem`).
    const [linkedin, email] = within(section)
      .getAllByRole('listitem')
      .filter((li) => li.querySelector('pre'))
    expect(within(linkedin).getByText('Para Uxía Barreiro (responsable del puesto)')).toBeInTheDocument()
    expect(within(linkedin).getByText(`${draft(5).body.length}/300 caracteres`)).toBeInTheDocument()
    expect(within(linkedin).queryByRole('button', { name: /Copiar el asunto/ })).not.toBeInTheDocument()
    expect(within(email).getByText('Para: recruiter')).toBeInTheDocument()
    expect(within(within(email).getByRole('list', { name: 'Adjuntos' })).getAllByRole('listitem')).toHaveLength(2)

    expect(within(section).getByRole('button', { name: /Redactar mensaje/ })).toBeInTheDocument()
    expect(within(section).queryByRole('button', { name: /Redactar seguimiento/ })).not.toBeInTheDocument()
    expect(within(section).queryByText(/seguimientos enviados/)).not.toBeInTheDocument()

    await userEvent.click(within(linkedin).getByRole('button', { name: 'Ya lo he enviado' }))
    await waitFor(() => expect(calls.some((c) => c.path === '/drafts/5/sent')).toBe(true))
  })
})
