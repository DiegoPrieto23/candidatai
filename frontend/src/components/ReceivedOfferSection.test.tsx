import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { OfferComparison, ReceivedOffer } from '@/api/client'
import { board, jobView, mockApi, processView, renderApp, status } from '@/test/utils'

const launcher = { available: true, agent: 'claude', reason: null, actions: [] }
const launched = { ok: true, agent: 'claude', prompt: 'Usa el skill…', message: 'ok' }
const now = new Date().toISOString()

function offer(changes: Partial<ReceivedOffer> = {}): ReceivedOffer {
  return {
    job_id: 1,
    base_salary: 45000,
    variable: 3000,
    currency: 'EUR',
    period: 'year',
    benefits: 'Seguro médico',
    work_mode: 'hybrid',
    location: 'Vigo',
    start_date: null,
    respond_by: '2026-10-20',
    notes: null,
    amounts_private: true,
    created_at: now,
    updated_at: now,
    ...changes,
  }
}

function ficha(saved: ReceivedOffer | null) {
  return mockApi({
    'GET /status': status(),
    'GET /jobs/1': jobView({ stage: 'in_process' }),
    'GET /jobs/1/process': processView({ stage: 'in_process', offer_received: saved !== null }),
    'GET /jobs/1/received-offer': saved,
    'POST /jobs/1/received-offer': { status: 200, body: offer() },
    'GET /agent': launcher,
    'POST /agent/launch': launched,
  })
}

describe('Oferta recibida en la ficha (fase 21)', () => {
  it('anota la oferta con los importes privados por defecto', { timeout: 15_000 }, async () => {
    const calls = ficha(null)
    renderApp('/jobs/1')
    const section = await screen.findByRole('region', { name: 'Oferta recibida' }, { timeout: 5000 })
    await userEvent.click(within(section).getByRole('button', { name: 'Anotar oferta' }))
    await userEvent.type(within(section).getByLabelText('Fijo bruto'), '45000')
    await userEvent.type(within(section).getByLabelText('Variable bruto anual'), '3000')
    await userEvent.selectOptions(within(section).getByLabelText('Modalidad'), 'hybrid')
    expect(within(section).getByRole('checkbox', { name: /Importes privados/ })).toBeChecked()
    await userEvent.click(within(section).getByRole('button', { name: 'Guardar oferta' }))

    await waitFor(() => expect(calls.some((c) => c.method === 'POST' && c.path === '/jobs/1/received-offer')).toBe(true))
    expect(calls.find((c) => c.path === '/jobs/1/received-offer' && c.method === 'POST')?.body).toMatchObject({
      base_salary: 45000,
      variable: 3000,
      currency: 'EUR',
      period: 'year',
      work_mode: 'hybrid',
      benefits: null,
      amounts_private: true,
    })
  })

  it('enseña la oferta guardada y lanza «Preparar negociación»', async () => {
    const calls = ficha(offer())
    renderApp('/jobs/1')
    const section = await screen.findByRole('region', { name: 'Oferta recibida' }, { timeout: 5000 })
    expect(await within(section).findByText('Seguro médico')).toBeInTheDocument()
    expect(within(section).getByText('Importes privados')).toBeInTheDocument()
    expect(within(section).getByText(/45\.000/)).toBeInTheDocument()
    await userEvent.click(within(section).getByRole('button', { name: /Preparar negociación/ }))
    await waitFor(() =>
      expect(calls.find((c) => c.path === '/agent/launch')?.body).toEqual({ action: 'prepare-negotiation', job_id: 1 }),
    )
  })

  it('no aparece en una oferta sin enviar ni oferta anotada', async () => {
    mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView({ stage: 'approved' }),
      'GET /jobs/1/received-offer': null,
      'GET /agent': launcher,
    })
    renderApp('/jobs/1')
    await screen.findByRole('heading', { level: 1 })
    expect(screen.queryByRole('region', { name: 'Oferta recibida' })).not.toBeInTheDocument()
  })
})

function comparison(changes: Partial<OfferComparison> = {}): OfferComparison {
  return {
    job_id: 1,
    title: 'Data Engineer',
    company: 'Brétema Analytics',
    stage: 'in_process',
    offer: offer(),
    annual_base: 45000,
    annual_total: 48000,
    approximate: false,
    floor_diff_base: 4000,
    floor_diff_total: -1000,
    published: { min: 40000, max: 48000, currency: 'EUR', period: 'year' },
    published_annual_min: 40000,
    published_annual_max: 48000,
    published_diff_min: 5000,
    published_diff_max: -3000,
    remarks: [],
    ...changes,
  }
}

describe('Ofertas recibidas en Procesos (fase 21)', () => {
  it('compara las ofertas lado a lado con tu mínimo', async () => {
    mockApi({
      'GET /status': status(),
      'GET /board': board([]),
      'GET /upcoming': { days: 7, items: [] },
      'GET /followups': { days_without_reply: 10, followups: [], thanks_due: [] },
      'GET /received-offers': {
        floor_eur: 41000,
        offers: [comparison(), comparison({ job_id: 2, company: 'Néboa Data', floor_diff_base: null, remarks: ['Sin fijo anotado.'] })],
      },
    })
    renderApp('/procesos')
    const section = await screen.findByRole('region', { name: 'Ofertas recibidas' }, { timeout: 5000 })
    expect(within(section).getByText(/Tu mínimo: 41\.000/)).toBeInTheDocument()
    expect(within(section).getByRole('link', { name: 'Brétema Analytics' })).toHaveAttribute('href', '/jobs/1')
    const row = within(section).getByRole('row', { name: /Fijo frente a tu mínimo/ })
    expect(row).toHaveTextContent('+4000 €')
    expect(within(section).getByRole('row', { name: /Total frente a tu mínimo/ })).toHaveTextContent('−1000 €')
    expect(within(section).getByText('Sin fijo anotado.')).toBeInTheDocument()
  })

  it('no aparece sin ofertas recibidas', async () => {
    mockApi({
      'GET /status': status(),
      'GET /board': board([]),
      'GET /upcoming': { days: 7, items: [] },
      'GET /received-offers': { floor_eur: null, offers: [] },
    })
    renderApp('/procesos')
    await screen.findByRole('heading', { name: 'Procesos' })
    expect(screen.queryByRole('region', { name: 'Ofertas recibidas' })).not.toBeInTheDocument()
  })
})
