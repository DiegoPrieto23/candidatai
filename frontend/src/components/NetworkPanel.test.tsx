import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { ContactOut, JobNetwork, NetworkPerson } from '@/api/client'
import { jobView, mockApi, processView, renderApp, status, triageItem, triageQueue } from '@/test/utils'

function person(id: number, changes: Partial<NetworkPerson> = {}): NetworkPerson {
  return {
    id,
    name: 'Uxía Barreiro',
    position: 'Data Engineering Manager',
    company: 'Brétema Analytics',
    linkedin_url: 'https://www.linkedin.com/in/uxia-demo',
    connected_on: '2024-03-14',
    match: 'exact',
    contact_id: null,
    ...changes,
  }
}

function network(people: NetworkPerson[], changes: Partial<JobNetwork> = {}): JobNetwork {
  return {
    job_id: 1,
    company: 'Brétema Analytics',
    network_size: 10,
    imported_at: '2026-10-12T10:00:00Z',
    people,
    ...changes,
  }
}

function contact(changes: Partial<ContactOut> = {}): ContactOut {
  return {
    id: 7,
    job_id: 1,
    name: 'Uxía Barreiro',
    role: 'Data Engineering Manager',
    email: null,
    phone: null,
    linkedin: 'https://www.linkedin.com/in/uxia-demo',
    notes: null,
    created_at: '2026-10-12T10:00:00Z',
    relation: 'referral',
    referral: null,
    referral_at: null,
    network_contact_id: 3,
    ...changes,
  }
}

describe('Tu red en la ficha', () => {
  it('dice a quién conoces en la empresa y lo añade al proceso con su papel', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView({ stage: 'approved' }),
      'GET /jobs/1/process': processView({ stage: 'approved' }),
      'GET /jobs/1/network': network([
        person(3),
        person(4, { name: 'Sabela Outeiro', position: 'Analytics Engineer', company: 'Brétema', match: 'probable' }),
      ]),
      'POST /jobs/1/contacts/from-network': contact(),
    })
    renderApp('/jobs/1?tab=company')

    const panel = await screen.findByRole('region', { name: 'Tu red' })
    expect(await within(panel).findByText('Conoces a 2 personas en Brétema Analytics.')).toBeInTheDocument()
    expect(within(panel).getByRole('link', { name: /Uxía Barreiro/ })).toHaveAttribute(
      'href',
      'https://www.linkedin.com/in/uxia-demo',
    )
    expect(within(panel).getByText(/En LinkedIn pone «Brétema»/)).toBeInTheDocument()

    const [first] = within(panel).getAllByRole('listitem')
    await userEvent.click(within(first).getByRole('button', { name: 'Añadir al proceso' }))
    await userEvent.selectOptions(within(first).getByLabelText('Papel de Uxía Barreiro en el proceso'), 'recruiter')
    await userEvent.click(within(first).getByRole('button', { name: 'Añadir' }))
    await waitFor(() => expect(calls.some((c) => c.path === '/jobs/1/contacts/from-network')).toBe(true))
    expect(calls.find((c) => c.path === '/jobs/1/contacts/from-network')?.body).toEqual({
      network_contact_id: 3,
      relation: 'recruiter',
    })
  })

  it('antes de aprobar enseña a quién conoces pero no deja añadirlo', async () => {
    mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView(),
      'GET /jobs/1/network': network([person(3, { contact_id: null })]),
    })
    renderApp('/jobs/1?tab=company')
    const panel = await screen.findByRole('region', { name: 'Tu red' })
    expect(await within(panel).findByText('Conoces a 1 persona en Brétema Analytics.')).toBeInTheDocument()
    expect(within(panel).queryByRole('button', { name: 'Añadir al proceso' })).not.toBeInTheDocument()
    expect(within(panel).getByText(/Apruébala para añadirlos/)).toBeInTheDocument()
  })

  it('sin red importada explica cómo y la importa desde la carpeta de siempre', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView(),
      'GET /jobs/1/network': network([], { network_size: 0, imported_at: null }),
      'GET /network': {
        size: 0,
        without_company: 0,
        imported_at: null,
        default_file: 'documentos/linkedin/Connections.csv',
        default_file_exists: true,
      },
      'POST /network/import': { ok: true, path: 'x', total: 10, added: 10, updated: 0, removed: 0, skipped: 0, without_company: 1, message: 'ok' },
    })
    renderApp('/jobs/1?tab=company')
    const panel = await screen.findByRole('region', { name: 'Tu red' })
    expect(await within(panel).findByText('data/documentos/linkedin/Connections.csv')).toBeInTheDocument()
    const button = within(panel).getByRole('button', { name: 'Importar mis contactos' })
    await waitFor(() => expect(button).toBeEnabled())
    await userEvent.click(button)
    await waitFor(() => expect(calls.some((c) => c.path === '/network/import')).toBe(true))
    expect(calls.find((c) => c.path === '/network/import')?.body).toEqual({})
  })

  it('el contacto del proceso enseña su papel y marca la referencia', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView({ stage: 'applied' }),
      'GET /jobs/1/process': processView({ stage: 'applied', contacts: [contact()] }),
      'GET /jobs/1/network': network([person(3, { contact_id: 7 })]),
      'GET /jobs/1/drafts': { job_id: 1, followups_sent: 0, max_followups: 2, drafts: [] },
      'POST /contacts/7/referral': { status: 200, body: contact({ referral: 'given' }) },
    })
    renderApp('/jobs/1?tab=company')
    const panel = await screen.findByRole('region', { name: 'Tu red' })
    expect(await within(panel).findByText('Ya es contacto del proceso')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('tab', { name: 'Proceso' }))
    const section = await screen.findByRole('region', { name: 'Proceso' })
    expect(await within(section).findByText('Referencia')).toBeInTheDocument()
    await userEvent.selectOptions(within(section).getByLabelText('Referencia de Uxía Barreiro'), 'given')
    await waitFor(() => expect(calls.some((c) => c.path === '/contacts/7/referral')).toBe(true))
    expect(calls.find((c) => c.path === '/contacts/7/referral')?.body).toEqual({ referral: 'given' })
  })
})

describe('Tu red en el triaje', () => {
  it('insignia «Conoces a N» y los nombres con sus cargos en el detalle', async () => {
    const item = triageItem(1, 80)
    mockApi({
      'GET /status': status(0, 1),
      'GET /triage': triageQueue([{ ...item, job: { ...item.job, known_contacts: 2 } }]),
      'GET /jobs/1/network': network([
        person(3),
        person(4, { name: 'Antón Lema', position: 'Recruiter' }),
      ]),
    })
    renderApp('/triaje')
    expect(await screen.findByText('Conoces a 2')).toBeInTheDocument()
    const detail = await screen.findByRole('article', { name: 'Oferta seleccionada' })
    expect(
      await within(detail).findByText(
        /Conoces a 2 personas en Brétema Analytics: Uxía Barreiro \(Data Engineering Manager\) y Antón Lema \(Recruiter\)/,
      ),
    ).toBeInTheDocument()
  })
})
