import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { jobRow, mockApi, renderApp, status } from '@/test/utils'

const page = (items: unknown[]) => ({ items, total: items.length, limit: 50, offset: 0 })
const noFollowups = { days_without_reply: 7, followups: [] }
const noUpcoming = { days: 7, items: [] }

function withStages(stages: Partial<ReturnType<typeof status>['by_stage']>) {
  const base = status()
  return { ...base, by_stage: { ...base.by_stage, ...stages } }
}

describe('Inicio', () => {
  it('resume lo que te toca hoy con enlaces a cada lista', async () => {
    mockApi({
      'GET /status': withStages({ pending_triage: 28, cv_ready: 1, pending_extraction: 3 }),
      'GET /followups': { days_without_reply: 7, followups: [{ job_id: 9, title: 'BI', company: 'Acme', url: null, channel: null, applied_at: '2026-10-01T10:00:00Z', last_followup_at: null, days_waiting: 10 }] },
      'GET /upcoming': noUpcoming,
      'GET /jobs': page([]),
    })
    renderApp('/')
    const heading = await screen.findByRole('heading', {
      level: 1,
      name: 'Tienes 28 ofertas por revisar, 1 CV listo para enviar y 1 seguimiento pendiente.',
    })
    expect(within(heading).getByRole('link', { name: '28 ofertas por revisar' })).toHaveAttribute('href', '/por-revisar')
    expect(within(heading).getByRole('link', { name: '1 CV listo para enviar' })).toHaveAttribute(
      'href',
      '/bandeja?stage=cv_ready',
    )
    expect(screen.getByText(/Para tu agente: 3 por extraer/)).toBeInTheDocument()
  })

  it('sin nada pendiente lo dice', async () => {
    mockApi({ 'GET /status': status(), 'GET /followups': noFollowups, 'GET /upcoming': noUpcoming, 'GET /jobs': page([]) })
    renderApp('/')
    expect(await screen.findByRole('heading', { level: 1, name: 'Nada pendiente por tu parte.' })).toBeInTheDocument()
    expect(await screen.findByText(/No hay ofertas por revisar/)).toBeInTheDocument()
  })

  it('el recorrido enlaza cada etapa y marca las que te tocan', async () => {
    mockApi({
      'GET /status': withStages({ pending_triage: 4, applied: 2 }),
      'GET /followups': noFollowups,
      'GET /upcoming': noUpcoming,
      'GET /jobs': page([]),
    })
    renderApp('/')
    const triage = await screen.findByRole('link', { name: /Te toca\s*4\s*Por revisar/ })
    expect(triage).toHaveAttribute('href', '/por-revisar')
    expect(screen.getByRole('link', { name: /Empresa\s*2\s*Enviada/ })).toHaveAttribute('href', '/procesos')
    // En Inicio no sale la fila de recuentos de la cabecera.
    expect(screen.queryByRole('navigation', { name: 'Ofertas por etapa' })).not.toBeInTheDocument()
  })

  it('lista las ofertas por revisar con más encaje primero', async () => {
    const calls = mockApi({
      'GET /status': withStages({ pending_triage: 1 }),
      'GET /followups': noFollowups,
      'GET /upcoming': noUpcoming,
      'GET /jobs': page([jobRow({ id: 7, title: 'Data Engineer', company: 'Acme', score: 81 })]),
    })
    renderApp('/')
    expect(await screen.findAllByRole('link', { name: /Data Engineer/ })).not.toHaveLength(0)
    const search = calls.find((c) => c.path === '/jobs' && c.search.get('stage') === 'pending_triage')?.search
    expect(search?.get('sort')).toBe('score')
    expect(search?.get('dir')).toBe('desc')
  })

  it('lleva a las respuestas por revisar y ofrece clasificar las nuevas con tu agente', async () => {
    mockApi({
      'GET /status': status(),
      'GET /followups': noFollowups,
      'GET /upcoming': noUpcoming,
      'GET /jobs': page([]),
      'GET /agent': { available: true, agent: 'claude', reason: null, actions: [] },
      'GET /replies': { replies: [], counts: { new: 3, proposed: 2, accepted: 0, ignored: 0 } },
    })
    renderApp('/')
    const heading = await screen.findByRole('heading', {
      level: 1,
      name: 'Tienes 2 respuestas de empresas por revisar.',
    })
    expect(within(heading).getByRole('link')).toHaveAttribute('href', '/respuestas')
    expect(screen.getByText(/Para tu agente: 3 correos sin clasificar/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Revisar respuestas/ })).toBeInTheDocument()
  })
})

describe('Primeros pasos (app recién instalada)', () => {
  const base = { 'GET /status': status(), 'GET /followups': noFollowups, 'GET /upcoming': noUpcoming, 'GET /jobs': page([]) }
  const noProfile = { exists: false, file_hash: null, profile: null, issues: [], profile_version_id: null, undo_available: 0 }
  const withProfile = { ...noProfile, exists: true, file_hash: 'h', profile: {}, profile_version_id: 1 }
  const limits = { max_result_pages: 2, delay_seconds: 5, default_max_offers: 15 }

  it('sin perfil ni portales: subir el CV y configurar dónde buscar con tu agente', async () => {
    mockApi({
      ...base,
      'GET /profile/editable': noProfile,
      'GET /sources': { sources: [], agent_browse: limits },
      'GET /context/documents/cv': [],
    })
    renderApp('/')
    const steps = await screen.findByRole('region', { name: 'Primeros pasos' })
    expect(within(steps).getByRole('button', { name: 'Subir mi CV' })).toBeInTheDocument()
    expect(within(steps).getByRole('button', { name: 'Crear mi perfil desde mi CV' })).toBeInTheDocument()
    expect(within(steps).getByRole('button', { name: 'Configurar con mi agente' })).toBeInTheDocument()
    expect(within(steps).getByRole('link', { name: 'o añade un portal tú' })).toHaveAttribute('href', '/fuentes/plataformas')
  })

  it('con el perfil hecho, ese paso queda marcado; con los dos, desaparece', async () => {
    mockApi({ ...base, 'GET /profile/editable': withProfile, 'GET /sources': { sources: [], agent_browse: limits } })
    const view = renderApp('/')
    const steps = await screen.findByRole('region', { name: 'Primeros pasos' })
    expect(within(steps).getByRole('link', { name: /Perfil creado/ })).toHaveAttribute('href', '/perfil')
    expect(within(steps).queryByRole('button', { name: 'Subir mi CV' })).not.toBeInTheDocument()
    view.unmount()

    const source = { id: 1, kind: 'agent_browse', name: 'InfoJobs' }
    mockApi({ ...base, 'GET /profile/editable': withProfile, 'GET /sources': { sources: [source], agent_browse: limits } })
    renderApp('/')
    expect(await screen.findByRole('heading', { level: 1 })).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Primeros pasos' })).not.toBeInTheDocument()
  })
})
