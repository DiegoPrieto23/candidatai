import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeAll, describe, expect, it } from 'vitest'
import type { Calibration, CalibrationGroup, FunnelStats } from '@/api/client'
import { mockApi, renderApp, status } from '@/test/utils'

const summary = (found: number, approved: number, applied: number, replied: number, interview: number) => ({
  found,
  approved,
  applied,
  replied,
  interview,
  reply_rate: applied ? Math.round((replied / applied) * 10_000) / 10_000 : null,
})

const STEPS: [FunnelStats['steps'][number]['step'], string, number][] = [
  ['found', 'Encontradas', 10],
  ['triaged', 'Triadas', 8],
  ['approved', 'Aprobadas', 6],
  ['applied', 'Enviadas', 5],
  ['replied', 'Con respuesta', 3],
  ['interview', 'Entrevista', 1],
  ['offer', 'Oferta', 1],
  ['accepted', 'Aceptadas', 1],
]

function stats(overrides: Partial<FunnelStats> = {}): FunnelStats {
  return {
    since: null,
    duplicates_excluded: 1,
    steps: STEPS.map(([step, label, count], i) => ({
      step,
      label,
      count,
      rate_from_previous: i ? Math.round((count / STEPS[i - 1][2]) * 10_000) / 10_000 : null,
      rate_from_start: count / 10,
    })),
    by_source: [
      { source_id: 1, kind: 'greenhouse', name: 'Greenhouse Acme', ...summary(5, 3, 3, 2, 1) },
      { source_id: 2, kind: 'email_alerts', name: 'Alertas', ...summary(5, 3, 2, 1, 0) },
    ],
    by_title: [
      { title: 'data engineer', group: 'title', ...summary(3, 3, 3, 3, 1) },
      { title: 'Otros', group: 'others', ...summary(3, 1, 0, 0, 0) },
      { title: 'Sin extraer', group: 'not_extracted', ...summary(1, 0, 0, 0, 0) },
    ],
    by_week: [
      { week: '2026-W38', week_start: '2026-09-14', ...summary(2, 2, 2, 2, 1) },
      { week: '2026-W39', week_start: '2026-09-21', ...summary(5, 3, 2, 0, 0) },
    ],
    by_referral: [
      { group: 'given', ...summary(2, 2, 2, 2, 1) },
      { group: 'requested', ...summary(1, 1, 1, 0, 0) },
      { group: 'none', ...summary(7, 3, 2, 1, 0) },
    ],
    response_time: {
      applied: 5,
      replied: 3,
      median_days: 2,
      mean_days: 2.2,
      awaiting_reply: 1,
      closed_without_reply: 1,
    },
    discard_reasons: [
      { reason: 'skills', count: 2 },
      { reason: 'unspecified', count: 1 },
    ],
    hard_filter_failures: [{ filter: 'location', count: 2 }],
    ...overrides,
  }
}

const EMPTY = stats({
  duplicates_excluded: 0,
  steps: stats().steps.map((s) => ({ ...s, count: 0, rate_from_previous: null, rate_from_start: null })),
  by_source: [],
  by_title: [],
  by_week: [],
  response_time: { applied: 0, replied: 0, median_days: null, mean_days: null, awaiting_reply: 0, closed_without_reply: 0 },
  discard_reasons: [],
  hard_filter_failures: [],
})

describe('Embudo', () => {
  // La ruta carga la página en diferido (Recharts): se precarga para no depender de lo que tarde
  // la importación con toda la batería en paralelo.
  beforeAll(async () => {
    await import('@/pages/FunnelPage')
  }, 30_000)

  it('muestra el embudo, las cifras clave, los desgloses y los motivos', async () => {
    mockApi({ 'GET /status': status(), 'GET /stats/funnel': stats() })
    renderApp('/embudo')

    const funnel = await screen.findByRole('table', { name: 'Ofertas por paso del embudo' })
    const rows = within(funnel).getAllByRole('row').slice(1)
    // Intl separa la cifra del «%» con un espacio duro.
    const text = (el: HTMLElement) => el.textContent?.replace(/ /g, ' ')
    expect(rows.map(text)).toEqual([
      'Encontradas10',
      'Triadas8 · 80 %',
      'Aprobadas6 · 75 %',
      'Enviadas5 · 83 %',
      'Con respuesta3 · 60 %',
      'Entrevista1 · 33 %',
      'Oferta1 · 100 %',
      'Aceptadas1 · 100 %',
    ])
    expect(screen.getByText(/Sin contar 1 duplicadas/)).toBeInTheDocument()

    const response = screen.getByRole('region', { name: 'Primera respuesta' })
    expect(within(response).getByText('2 días')).toBeInTheDocument()
    expect(within(response).getByText('2,2 días')).toBeInTheDocument()
    expect(within(response).getByText('1 esperando · 1 cerradas')).toBeInTheDocument()

    const sources = screen.getByRole('table', { name: 'Embudo por fuente' })
    const greenhouse = within(sources).getByRole('row', { name: /Greenhouse Acme/ })
    expect(within(greenhouse).getAllByRole('cell').map(text)).toEqual(['5', '3', '3', '2', '1', '67 %'])
    expect(within(sources).getByText('Alertas por correo')).toBeInTheDocument()

    const titles = screen.getByRole('table', { name: 'Embudo por tipo de puesto' })
    expect(within(titles).getByRole('rowheader', { name: 'Otros' })).toBeInTheDocument()
    expect(within(titles).getByRole('rowheader', { name: 'Sin extraer' })).toBeInTheDocument()

    expect(screen.getByRole('table', { name: 'Ofertas por semana' })).toHaveTextContent('14 sept (2026-W38)')

    const referrals = screen.getByRole('table', { name: 'Embudo por referencia' })
    const given = within(referrals).getByRole('row', { name: /Con referencia/ })
    expect(within(given).getAllByRole('cell').map(text)).toEqual(['2', '2', '2', '2', '1', '100 %'])
    expect(within(referrals).getByRole('rowheader', { name: 'Sin referencia' })).toBeInTheDocument()

    const discards = screen.getByRole('table', { name: 'Descartes por motivo' })
    expect(within(discards).getByRole('rowheader', { name: 'No encaja el stack' })).toBeInTheDocument()
    expect(within(discards).getByRole('rowheader', { name: 'Sin motivo' })).toBeInTheDocument()
    const filters = screen.getByRole('table', { name: 'Cierres por filtro duro' })
    expect(within(filters).getByRole('rowheader', { name: 'Ubicación' })).toBeInTheDocument()
  })

  it('pide el periodo elegido con `since`', async () => {
    const calls = mockApi({ 'GET /status': status(), 'GET /stats/funnel': stats() })
    renderApp('/embudo')
    await screen.findByRole('table', { name: 'Ofertas por paso del embudo' })
    const funnelCalls = () => calls.filter((c) => c.path === '/stats/funnel')
    expect(funnelCalls()[0].search.get('since')).toBeNull()

    await userEvent.click(screen.getByRole('button', { name: '30 días' }))
    await waitFor(() => expect(funnelCalls()).toHaveLength(2))
    expect(funnelCalls()[1].search.get('since')).toMatch(/^\d{4}-\d{2}-\d{2}$/)
    expect(screen.getByRole('button', { name: '30 días' })).toHaveAttribute('aria-pressed', 'true')

    fireEvent.change(screen.getByLabelText('Desde'), { target: { value: '2026-09-01' } })
    await waitFor(() => expect(funnelCalls().at(-1)?.search.get('since')).toBe('2026-09-01'))
    expect(screen.getByRole('button', { name: '30 días' })).toHaveAttribute('aria-pressed', 'false')
  })

  it('explica el estado vacío', async () => {
    mockApi({ 'GET /status': status(), 'GET /stats/funnel': EMPTY })
    renderApp('/embudo')
    expect(await screen.findByText('Aún no hay datos')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '90 días' }))
    expect(await screen.findByText('No hay ofertas en este periodo')).toBeInTheDocument()
  })

  it('muestra un error si la API falla', async () => {
    mockApi({
      'GET /status': status(),
      'GET /stats/funnel': { status: 500, body: { ok: false, error: { type: 'internal', message: 'Fallo', details: [] } } },
    })
    renderApp('/embudo')
    expect(await screen.findByRole('alert')).toHaveTextContent('No se ha podido cargar')
  })
})

// --- ¿Acierta el score? (fase 20) -------------------------------------------------------------

const AGENT = { available: true, agent: 'claude', reason: null, actions: [] }

const interval = (rate: number | null, low: number | null, high: number | null) => ({ rate, low, high })

function group(key: string, label: string, applied: number, replied: number, interview: number, awaiting = 0): CalibrationGroup {
  return {
    key,
    label,
    applied,
    replied,
    interview,
    awaiting,
    reply_rate: applied ? interval(replied / applied, 0.1, 0.9) : interval(null, null, null),
    interview_rate: applied ? interval(interview / applied, 0.05, 0.6) : interval(null, null, null),
    low_data: applied < 10,
  }
}

function calibration(overrides: Partial<Calibration> = {}): Calibration {
  return {
    since: null,
    min_cases: 10,
    confidence: 0.95,
    total: { ...group('total', 'Total', 24, 9, 4, 3), reply_rate: interval(0.375, 0.2116, 0.5729) },
    by_score: [
      group('lt60', '< 60', 4, 0, 0),
      group('60_74', '60-74', 0, 0, 0),
      group('75_84', '75-84', 8, 3, 1, 2),
      { ...group('gte85', '≥ 85', 12, 6, 3, 1), reply_rate: interval(0.5, 0.2538, 0.7462) },
      group('none', 'Sin score', 0, 0, 0),
    ],
    by_verdict: [group('strong', 'Fuerte', 12, 6, 3)],
    by_source: [group('1', 'Greenhouse Acme', 14, 7, 3), group('2', 'Alertas por correo', 10, 2, 1)],
    by_platform: [group('none', 'Sin portal', 24, 9, 4)],
    by_template: [group('clasica', 'clasica', 24, 9, 4)],
    by_cover_letter: [group('with', 'Con carta', 6, 3, 2), group('without', 'Sin carta', 18, 6, 2)],
    by_referral: [group('given', 'Con referencia', 2, 2, 1), group('none', 'Sin referencia', 22, 7, 3)],
    by_days_to_apply: [group('0_1', '0-1 días', 24, 9, 4)],
    ...overrides,
  }
}

describe('¿Acierta el score?', () => {
  beforeAll(async () => {
    await import('@/pages/FunnelPage')
  }, 30_000)

  // Intl separa la cifra del «%» con un espacio duro.
  const text = (el: HTMLElement) => el.textContent?.replace(/ /g, ' ')

  it('muestra la respuesta por tramo de score con su intervalo y el aviso', async () => {
    mockApi({
      'GET /status': status(),
      'GET /stats/funnel': stats(),
      'GET /stats/calibration': calibration(),
      'GET /agent': AGENT,
    })
    renderApp('/embudo')

    const panel = await screen.findByRole('region', { name: '¿Acierta el score?' })
    expect(within(panel).getByText(/Orientativo/)).toBeInTheDocument()
    expect(within(panel).getByText('cai eval matching')).toBeInTheDocument()
    expect(within(panel).getByRole('button', { name: 'Revisar mi búsqueda' })).toBeInTheDocument()
    const table = await within(panel).findByRole('table', { name: 'Calibración por score' })
    const summary = within(panel).getByText((_, el) => el?.tagName === 'P' && /enviadas · respuesta/.test(el.textContent ?? ''))
    expect(text(summary)).toBe('24 enviadas · respuesta 38 % · entrevista 17 %')
    const top = within(table).getByRole('row', { name: /≥ 85/ })
    expect(within(top).getAllByRole('cell').map(text)).toEqual(['12', '50 % (25 %–75 %)', '25 % (5 %–60 %)', '1'])
    expect(within(top).queryByText('pocos datos')).not.toBeInTheDocument()
    expect(within(within(table).getByRole('row', { name: /75-84/ })).getByText('pocos datos')).toBeInTheDocument()
    const empty = within(table).getByRole('row', { name: /60-74/ })
    expect(within(empty).getAllByRole('cell').map(text)).toEqual(['0', '—', '—', '—'])
    expect(within(empty).queryByText('pocos datos')).not.toBeInTheDocument()

    await userEvent.click(within(panel).getByRole('tab', { name: 'Fuente' }))
    const sources = await within(panel).findByRole('table', { name: 'Calibración por fuente' })
    const greenhouse = within(sources).getByRole('row', { name: /Greenhouse Acme/ })
    expect(within(greenhouse).queryByText('pocos datos')).not.toBeInTheDocument()
    expect(within(sources).getByRole('row', { name: /Alertas por correo/ })).toBeInTheDocument()
  })

  it('pide la calibración con el mismo periodo', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /stats/funnel': stats(),
      'GET /stats/calibration': calibration(),
      'GET /agent': AGENT,
    })
    renderApp('/embudo')
    await screen.findByRole('table', { name: 'Calibración por score' })
    const calibrationCalls = () => calls.filter((c) => c.path === '/stats/calibration')
    expect(calibrationCalls()[0].search.get('since')).toBeNull()

    fireEvent.change(screen.getByLabelText('Desde'), { target: { value: '2026-09-01' } })
    await waitFor(() => expect(calibrationCalls().at(-1)?.search.get('since')).toBe('2026-09-01'))
  })

  it('con un periodo sin ofertas nuevas, sigue enseñando lo enviado en él', async () => {
    mockApi({
      'GET /status': status(),
      'GET /stats/funnel': EMPTY,
      'GET /stats/calibration': calibration(),
      'GET /agent': AGENT,
    })
    renderApp('/embudo')
    expect(await screen.findByText('Aún no hay datos')).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: '¿Acierta el score?' })).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: '30 días' }))
    expect(await screen.findByText('No hay ofertas en este periodo')).toBeInTheDocument()
    const panel = await screen.findByRole('region', { name: '¿Acierta el score?' })
    expect(await within(panel).findByRole('table', { name: 'Calibración por score' })).toBeInTheDocument()
  })

  it('sin candidaturas enviadas lo dice', async () => {
    const none = group('total', 'Total', 0, 0, 0)
    mockApi({
      'GET /status': status(),
      'GET /stats/funnel': stats(),
      'GET /stats/calibration': calibration({ total: none }),
      'GET /agent': AGENT,
    })
    renderApp('/embudo')
    const panel = await screen.findByRole('region', { name: '¿Acierta el score?' })
    expect(await within(panel).findByText(/Aún no has enviado ninguna candidatura/)).toBeInTheDocument()
    expect(within(panel).queryByRole('table')).not.toBeInTheDocument()
  })
})
