import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
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
      name: 'Por hacer: 28 ofertas por revisar, 1 CV listo para enviar y 1 seguimiento pendiente.',
    })
    expect(within(heading).getByRole('link', { name: '28 ofertas por revisar' })).toHaveAttribute('href', '/bandeja/revision')
    expect(within(heading).getByRole('link', { name: '1 CV listo para enviar' })).toHaveAttribute(
      'href',
      '/bandeja?stage=cv_ready',
    )
    expect(screen.getByText(/Para el agente: 3 por leer/)).toBeInTheDocument()
  })

  it('con portales en los que buscar, «Buscar ofertas» lanza la búsqueda con lo guardado', async () => {
    const portal = {
      id: 1, kind: 'agent_browse', kind_label: 'Portal', name: 'InfoJobs', active: true, config: {}, keys_missing: false,
      browse: { allow_agent_browsing: true, search_urls: [], priority: 1, access: 'free', max_offers: 10, notes: '' },
      website: null, last_run_at: null, last_run: null,
    }
    mockApi({
      'GET /status': status(),
      'GET /followups': noFollowups,
      'GET /upcoming': noUpcoming,
      'GET /jobs': page([]),
      'GET /sources': { sources: [portal], agent_browse: { max_result_pages: 5, delay_seconds: 5, default_max_offers: 15, stop_after_known: 5 } },
    })
    renderApp('/')
    expect(await screen.findByRole('button', { name: 'Buscar ofertas' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Ir a buscar ofertas' })).not.toBeInTheDocument()
  })

  it('las contraseñas sin cifrar salen en una banda de Inicio, no flotando en la esquina', async () => {
    mockApi({
      'GET /status': status(),
      'GET /followups': noFollowups,
      'GET /upcoming': noUpcoming,
      'GET /jobs': page([]),
      'GET /secrets/plaintext': {
        keyring: true,
        secrets: [{ name: 'IMAP_PASSWORD_PRINCIPAL', kind: 'mailbox', label: 'Principal' }],
      },
    })
    renderApp('/')
    const band = await screen.findByRole('region', { name: 'Guardar las contraseñas en el llavero del sistema' })
    expect(screen.getByRole('main')).toContainElement(band)
    expect(within(band).getByText('Buzón «Principal»')).toBeInTheDocument()
    await userEvent.click(within(band).getByRole('button', { name: 'Ahora no' }))
    expect(band).not.toBeInTheDocument()
  })

  it('sin nada pendiente lo dice', async () => {
    mockApi({ 'GET /status': status(), 'GET /followups': noFollowups, 'GET /upcoming': noUpcoming, 'GET /jobs': page([]) })
    renderApp('/')
    expect(await screen.findByRole('heading', { level: 1, name: 'Nada pendiente.' })).toBeInTheDocument()
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
    const triage = await screen.findByRole('link', { name: /Por hacer\s*4\s*Por revisar/ })
    expect(triage).toHaveAttribute('href', '/bandeja/revision')
    expect(screen.getByRole('link', { name: /Empresa\s*2\s*Enviada/ })).toHaveAttribute('href', '/bandeja?stage=applied')
    // En Inicio no sale la fila de recuentos de la cabecera.
    expect(screen.queryByRole('navigation', { name: 'Ofertas por etapa' })).not.toBeInTheDocument()
  })

  it('cada etapa del recorrido explica qué es y quién actúa, también con el teclado', async () => {
    mockApi({
      'GET /status': withStages({ pending_triage: 4 }),
      'GET /followups': noFollowups,
      'GET /upcoming': noUpcoming,
      'GET /jobs': page([]),
    })
    renderApp('/')
    const triage = await screen.findByRole('link', { name: /Por hacer\s*4\s*Por revisar/ })
    triage.focus()
    const tooltip = await screen.findByRole('tooltip')
    expect(tooltip).toHaveTextContent(/a la espera de una decisión/)
    expect(tooltip).toHaveTextContent('Quién actúa: quien busca empleo.')
    expect(triage).toHaveAccessibleDescription(/a la espera de una decisión/)
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

})

describe('Primeros pasos (app recién instalada)', () => {
  const base = { 'GET /status': status(), 'GET /followups': noFollowups, 'GET /upcoming': noUpcoming, 'GET /jobs': page([]) }
  const noProfile = { exists: false, file_hash: null, profile: null, issues: [], profile_version_id: null, undo_available: 0 }
  const withProfile = { ...noProfile, exists: true, file_hash: 'h', profile: {}, profile_version_id: 1 }
  const limits = { max_result_pages: 5, delay_seconds: 5, default_max_offers: 15, stop_after_known: 5 }

  it('sin perfil ni portales: subir el CV y configurar dónde buscar con tu agente', async () => {
    mockApi({
      ...base,
      'GET /profile/editable': noProfile,
      'GET /sources': { sources: [], agent_browse: limits },
      'GET /context/documents/cv': [],
    })
    renderApp('/')
    const steps = await screen.findByRole('region', { name: 'Primeros pasos' })
    expect(within(steps).getByRole('button', { name: 'Subir el CV' })).toBeInTheDocument()
    expect(within(steps).getByRole('button', { name: 'Crear el perfil desde un CV' })).toBeInTheDocument()
    expect(within(steps).getByRole('button', { name: 'Configurar con el agente' })).toBeInTheDocument()
    expect(within(steps).getByRole('link', { name: 'o añadir un portal a mano' })).toHaveAttribute('href', '/fuentes/plataformas')
    // Qué hace la app y qué es tu agente, con un enlace a «Agente»; y el perfil sin agente.
    expect(within(steps).getByText(/ordena la búsqueda de empleo/)).toBeInTheDocument()
    expect(within(steps).getByRole('link', { name: 'Qué es y cómo se instala, en «Agente»' })).toHaveAttribute('href', '/agente')
    expect(within(steps).getByRole('link', { name: /Se puede empezar a mano en «Mi perfil»/ })).toHaveAttribute('href', '/perfil')
    expect(within(steps).getByRole('link', { name: /en «Cómo funciona»/ })).toHaveAttribute('href', '/como-funciona')
  })

  it('sin perfil, el titular cuenta los primeros pasos y la única acción rellena es la del paso', async () => {
    mockApi({
      ...base,
      'GET /status': withStages({ pending_extraction: 1 }),
      'GET /profile/editable': noProfile,
      'GET /sources': { sources: [], agent_browse: limits },
      'GET /context/documents/cv': [],
    })
    renderApp('/')
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Quedan 2 primeros pasos para empezar.' }),
    ).toBeInTheDocument()
    await screen.findByRole('region', { name: 'Primeros pasos' })
    // En la página: el botón del agente de la esquina es del marco y está en todas.
    const page = within(screen.getByRole('main'))
    const filled = page.getAllByRole('button').filter((b) => b.getAttribute('data-variant') === 'default')
    expect(filled.map((b) => b.textContent)).toEqual(['Subir el CV'])
    // Sin portales, buscar no podría hacer nada: el botón lleva a elegirlos y lo dice.
    const go = screen.getByRole('link', { name: 'Ir a buscar ofertas' })
    expect(go).toHaveAttribute('href', '/buscar')
    expect(go).toHaveAttribute('data-variant', 'outline')
    expect(screen.queryByRole('button', { name: 'Buscar ofertas' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Valorar las ofertas nuevas' })).toHaveAttribute('data-variant', 'outline')
  })

  it('sin ningún agente instalado, avisa y explica cómo instalar uno', async () => {
    const claude = { name: 'claude', installed: false, info: { display_name: 'Claude Code', install: { windows: 'irm https://claude.ai/install.ps1 | iex' } } }
    mockApi({
      ...base,
      'GET /agent': { available: false, agent: null, reason: 'No hay ningún agente instalado.', actions: [], background: { available: false, agent: null, reason: null }, no_agent_installed: true },
      'GET /agent/agents': { agents: [claude], launchable: [], preferences: { default_agent: null, agents: {}, actions: {} }, effective: [] },
      'GET /profile/editable': noProfile,
      'GET /sources': { sources: [], agent_browse: limits },
      'GET /context/documents/cv': [],
    })
    renderApp('/')
    const notice = await screen.findByRole('region', { name: 'Hace falta un agente de IA' })
    expect(within(notice).getByText(/No es la app de chat de Claude ni claude\.ai/)).toBeInTheDocument()
    expect(await within(notice).findByLabelText('Orden para instalar Claude Code')).toHaveTextContent(
      'irm https://claude.ai/install.ps1 | iex',
    )
    expect(within(notice).getByRole('link', { name: 'La guía paso a paso' })).toHaveAttribute(
      'href',
      expect.stringContaining('EMPEZAR.md#3-instalar-tu-agente'),
    )
    expect(within(notice).getByRole('link', { name: 'Otros agentes, en «Agente»' })).toHaveAttribute('href', '/agente')
  })

  it('con un agente instalado, no hay aviso', async () => {
    mockApi({
      ...base,
      'GET /agent': { available: true, agent: 'claude', reason: null, actions: [], background: { available: true, agent: 'claude', reason: null }, no_agent_installed: false },
      'GET /profile/editable': noProfile,
      'GET /sources': { sources: [], agent_browse: limits },
      'GET /context/documents/cv': [],
    })
    renderApp('/')
    await screen.findByRole('region', { name: 'Primeros pasos' })
    expect(screen.queryByRole('region', { name: 'Hace falta un agente de IA' })).not.toBeInTheDocument()
  })

  it('con el perfil hecho, ese paso queda marcado; con los dos, desaparece', async () => {
    mockApi({ ...base, 'GET /profile/editable': withProfile, 'GET /sources': { sources: [], agent_browse: limits } })
    const view = renderApp('/')
    const steps = await screen.findByRole('region', { name: 'Primeros pasos' })
    expect(within(steps).getByRole('link', { name: /Perfil creado/ })).toHaveAttribute('href', '/perfil')
    expect(within(steps).queryByRole('button', { name: 'Subir el CV' })).not.toBeInTheDocument()
    view.unmount()

    const source = { id: 1, kind: 'agent_browse', name: 'InfoJobs' }
    mockApi({ ...base, 'GET /profile/editable': withProfile, 'GET /sources': { sources: [source], agent_browse: limits } })
    renderApp('/')
    expect(await screen.findByRole('heading', { level: 1 })).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Primeros pasos' })).not.toBeInTheDocument()
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
      name: 'Por hacer: 2 respuestas de empresas por revisar.',
    })
    expect(within(heading).getByRole('link')).toHaveAttribute('href', '/respuestas')
    expect(screen.getByText(/Para el agente: 3 correos sin clasificar/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Revisar respuestas/ })).toBeInTheDocument()
  })
})
