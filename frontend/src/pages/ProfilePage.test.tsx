import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { ContextFileInfo, ContextStatus } from '@/api/client'
import { mockApi, renderApp, status } from '@/test/utils'

function file(section: ContextFileInfo['section'], changes: Partial<ContextFileInfo> = {}): ContextFileInfo {
  return {
    section,
    path: `contexto/${section}.md`,
    exists: true,
    empty: false,
    size_bytes: 2150,
    modified_at: '2026-10-10T08:00:00Z',
    hash: 'abc',
    warnings: [],
    ...changes,
  }
}

function contextStatus(changes: Partial<ContextStatus> = {}): ContextStatus {
  return {
    context_dir: 'C:/cai/data/contexto',
    documents_dir: 'C:/cai/data/documentos',
    files: [
      file('estilo-redaccion'),
      file('perfil-conductual', { empty: true, size_bytes: 500 }),
      file('criterios', { warnings: ['too_large: pasa de 20 KB; solo se usan los primeros. Acórtalo.'] }),
      file('narrativa', { exists: false, empty: true, size_bytes: 0, modified_at: null, hash: null }),
    ],
    folders: [
      { name: 'cv', exists: true, files: 2 },
      { name: 'linkedin', exists: true, files: 1 },
      { name: 'titulos', exists: true, files: 0 },
      { name: 'referencias', exists: false, files: 0 },
      { name: 'candidaturas', exists: true, files: 0 },
    ],
    ...changes,
  }
}

/** Sin `data/profile.yaml`: la página enseña cómo crearlo y el estado del contexto (fase 13). */
const NO_PROFILE = { exists: false, file_hash: null, profile: null, issues: [], profile_version_id: null, undo_available: 0 }
const UNREADABLE = { ...NO_PROFILE, exists: true, file_hash: 'h1', profile_version_id: 1 }

describe('Mi perfil', () => {
  it('enseña el estado de cada fichero de contexto y las carpetas de documentos', async () => {
    mockApi({ 'GET /status': status(), 'GET /context': contextStatus(), 'GET /profile/editable': NO_PROFILE })
    renderApp('/perfil')
    const contexto = await screen.findByRole('region', { name: 'Contexto' })
    const items = within(contexto).getAllByRole('listitem')
    expect(items).toHaveLength(4)
    expect(within(items[0]).getByText('Estilo de redacción')).toBeInTheDocument()
    expect(within(items[0]).getByText('Con contenido')).toBeInTheDocument()
    expect(within(items[0]).getByText(/2,1 KB/)).toBeInTheDocument()
    expect(within(items[1]).getByText('Vacío')).toBeInTheDocument()
    expect(within(items[2]).getByText(/pasa de 20 KB/)).toBeInTheDocument()
    expect(within(items[3]).getByText('No existe')).toBeInTheDocument()
    expect(within(contexto).getByText(/Nunca respalda un hecho/)).toBeInTheDocument()

    const documentos = screen.getByRole('region', { name: 'Documentos' })
    // Con su nombre legible, no el de la carpeta en disco.
    expect(within(documentos).getByText('CV')).toBeInTheDocument()
    expect(within(documentos).getByText('Títulos')).toBeInTheDocument()
    expect(within(documentos).queryByText('titulos')).not.toBeInTheDocument()
    expect(within(documentos).getByText('2 ficheros')).toBeInTheDocument()
    expect(within(documentos).getByText('1 fichero')).toBeInTheDocument()
    // Los editores se despliegan bajo su fila, al pulsar.
    expect(within(contexto).queryByRole('textbox')).not.toBeInTheDocument()
    expect(within(contexto).queryByText(/Edítalos en sus bloques, más arriba/)).not.toBeInTheDocument()
  })

  it('sin perfil, un fichero de contexto que no existe se crea desde su plantilla', async () => {
    const template = '# Narrativa\n<!-- ¿Qué historia cuentas? -->\n'
    const calls = mockApi({
      'GET /status': status(),
      'GET /context': contextStatus(),
      'GET /profile/editable': NO_PROFILE,
      'GET /context/narrativa': {
        section: 'narrativa', path: 'contexto/narrativa.md', exists: false, file_hash: null,
        text: template, size_bytes: template.length, max_bytes: 20480,
      },
      'PUT /context/narrativa': async (request: Request) => {
        const body = (await request.json()) as { text: string }
        return { section: 'narrativa', path: 'contexto/narrativa.md', exists: true, file_hash: 'h-new', text: body.text, size_bytes: body.text.length, max_bytes: 20480 }
      },
    })
    renderApp('/perfil')
    await userEvent.click(await screen.findByRole('button', { name: 'Crear «Narrativa»' }))
    const editor = await screen.findByRole('textbox', { name: /Narrativa/ })
    expect(editor).toHaveValue(template)
    await userEvent.type(editor, 'Del dato al negocio.')
    await userEvent.click(screen.getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'PUT' && c.path === '/context/narrativa')).toBe(true))
    expect(calls.find((c) => c.method === 'PUT')?.body).toEqual({ file_hash: null, text: `${template}Del dato al negocio.` })
  })

  it('«Empezar a mano», si el perfil ya existe, lo dice y vuelve a leerlo', async () => {
    let reads = 0
    mockApi({
      'GET /status': status(),
      'GET /context': contextStatus(),
      'GET /profile/editable': () => {
        reads += 1
        return NO_PROFILE
      },
      'POST /profile': {
        status: 409,
        body: { ok: false, error: { type: 'conflict', message: 'Ha cambiado.', details: [] } },
      },
    })
    renderApp('/perfil')
    await userEvent.click(await screen.findByRole('button', { name: 'Empezar a mano' }))
    await userEvent.type(screen.getByLabelText('Nombre'), 'Demo Persona')
    await userEvent.type(screen.getByLabelText(/^Titular/), 'Analista')
    await userEvent.type(screen.getByLabelText(/^Puesto que buscas/), 'Data Analyst')
    await userEvent.click(screen.getByRole('checkbox', { name: 'Junior' }))
    const before = reads
    await userEvent.click(screen.getByRole('button', { name: 'Crear mi perfil' }))
    expect(await screen.findByText(/Ya tienes un perfil/)).toBeInTheDocument()
    await waitFor(() => expect(reads).toBeGreaterThan(before))
  })

  it('«Empezar a mano» crea el perfil mínimo y abre el editor', async () => {
    let created = false
    const calls = mockApi({
      'GET /status': status(),
      'GET /context': contextStatus(),
      'GET /profile/editable': () =>
        created
          ? {
              exists: true, file_hash: 'h1', issues: [], profile_version_id: 1, undo_available: 0,
              profile: {
                schema_version: 1, personal: { name: 'Demo Persona' }, headline: 'Analista', summary: { es: 'Analista' },
                preferences: { roles: ['Data Analyst'], seniority_target: ['mid'], remote_modes: ['onsite', 'hybrid', 'remote'], languages_for_work: ['es'], cv: { photo_policy: { default: false } } },
              },
            }
          : NO_PROFILE,
      'POST /profile': () => {
        created = true
        return { status: 200, body: { file_hash: 'h1', profile_version_id: 1 } }
      },
    })
    renderApp('/perfil')
    await userEvent.click(await screen.findByRole('button', { name: 'Empezar a mano' }))
    // Sin rellenar, dice qué falta y no envía nada.
    await userEvent.click(screen.getByRole('button', { name: 'Crear mi perfil' }))
    expect(screen.getAllByText('Hace falta para crear tu perfil.')).toHaveLength(3)
    expect(screen.getByText('Elige al menos uno.')).toBeInTheDocument()
    expect(calls.some((c) => c.method === 'POST' && c.path === '/profile')).toBe(false)

    await userEvent.type(screen.getByLabelText('Nombre'), 'Demo Persona')
    await userEvent.type(screen.getByLabelText(/^Titular/), 'Analista')
    await userEvent.type(screen.getByLabelText(/^Puesto que buscas/), 'Data Analyst')
    await userEvent.click(screen.getByRole('checkbox', { name: 'Mid' }))
    await userEvent.click(screen.getByRole('button', { name: 'Crear mi perfil' }))
    await waitFor(() =>
      expect(calls.find((c) => c.method === 'POST' && c.path === '/profile')?.body).toEqual({
        name: 'Demo Persona', headline: 'Analista', role: 'Data Analyst', seniority: ['mid'], summary: null, language: 'es',
      }),
    )
    // El editor, con sus pestañas.
    expect(await screen.findByRole('tab', { name: 'Sobre ti' })).toBeInTheDocument()
  })

  it('abre la carpeta del contexto', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /context': contextStatus(),
      'GET /profile/editable': NO_PROFILE,
      'POST /folders/open': { status: 200, body: { path: 'C:/cai/data/contexto', opened: true } },
    })
    renderApp('/perfil')
    await userEvent.click(await screen.findByRole('button', { name: 'Abrir la carpeta del contexto' }))
    await waitFor(() => expect(calls.some((c) => c.path === '/folders/open')).toBe(true))
    expect(calls.find((c) => c.path === '/folders/open')?.body).toEqual({ folder: 'contexto' })
    expect(screen.queryByText(/No se pudo abrir aquí/)).not.toBeInTheDocument()
  })

  it('si no se puede abrir, enseña la ruta para copiarla', async () => {
    mockApi({
      'GET /status': status(),
      'GET /context': contextStatus(),
      'GET /profile/editable': NO_PROFILE,
      'POST /folders/open': { status: 200, body: { path: 'C:/cai/data/documentos', opened: false } },
    })
    renderApp('/perfil')
    await userEvent.click(await screen.findByRole('button', { name: 'Abrir la carpeta de documentos' }))
    expect(await screen.findByText(/No se pudo abrir aquí/)).toBeInTheDocument()
    expect(screen.getByText('C:/cai/data/documentos')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Copiar ruta' })).toBeInTheDocument()
  })

  it('«Mejorar el contenido de mi perfil» abre el agente y se deshabilita si el agente no puede (fase 25.2)', async () => {
    const claude = {
      agent: 'claude',
      display_name: 'Claude Code',
      model: null,
      preset: null,
      reason: 'default',
      reason_text: 'tu agente por defecto',
      blocked: null,
      blocked_code: null,
      warning: null,
    }
    const expand = { id: 'expand', label: 'Mejorar el contenido de mi perfil', needs_job: false, prompt: 'Usa el skill expand…', background: false }
    const launcher = (agent: Record<string, unknown>) => ({
      available: true,
      agent: 'claude',
      reason: null,
      background: { available: true, agent: 'claude', reason: null },
      actions: [{ ...expand, agent, alternatives: [] }],
    })
    // Con perfil (aquí, uno que no se puede leer, para no montar el editor): sin perfil, lo primero
    // es crearlo desde el CV y el botón no sale.
    const calls = mockApi({
      'GET /status': status(),
      'GET /context': contextStatus(),
      'GET /profile/editable': UNREADABLE,
      'GET /agent': launcher(claude),
      'POST /agent/launch': { ok: true, agent: 'claude', prompt: 'Usa el skill expand…', message: 'ok' },
    })
    const view = renderApp('/perfil')
    const button = await screen.findByRole('button', { name: 'Mejorar el contenido de mi perfil' })
    await waitFor(() => expect(button).toBeEnabled())
    await userEvent.click(button)
    expect(await screen.findByText('Abierto en claude: sigue en la ventana que se acaba de abrir.')).toBeInTheDocument()
    expect(calls.find((c) => c.path === '/agent/launch')?.body).toEqual({ action: 'expand' })
    view.unmount()

    const noAgent = 'Codex no tiene visión, y esta acción lo necesita.'
    mockApi({
      'GET /status': status(),
      'GET /context': contextStatus(),
      'GET /profile/editable': UNREADABLE,
      'GET /agent': launcher({ ...claude, agent: 'codex', display_name: 'Codex', blocked: noAgent, blocked_code: 'capability' }),
    })
    renderApp('/perfil')
    const blocked = await screen.findByRole('button', { name: 'Mejorar el contenido de mi perfil' })
    await waitFor(() => expect(blocked).toBeDisabled())
    expect(blocked).toHaveAccessibleDescription(new RegExp(noAgent))
    // Sin segundo plano: pregunta antes de escribir en el perfil.
    await userEvent.click(within(blocked.closest<HTMLElement>('[data-slot="agent-button"]')!).getByRole('button', { name: /con Codex/ }))
    expect(screen.queryByRole('menuitem', { name: /En segundo plano/ })).not.toBeInTheDocument()
  })

  it('«Importar información desde un CV» sube el CV y lanza a tu agente sobre el perfil que ya tienes', async () => {
    const claude = {
      agent: 'claude',
      display_name: 'Claude Code',
      model: null,
      preset: null,
      reason: 'default',
      reason_text: 'tu agente por defecto',
      blocked: null,
      blocked_code: null,
      warning: null,
    }
    const action = {
      id: 'import-profile-from-cv',
      label: 'Importar información desde un CV',
      needs_job: false,
      prompt: 'Usa el skill update-profile…',
      background: false,
    }
    const calls = mockApi({
      'GET /status': status(),
      'GET /context': contextStatus(),
      'GET /profile/editable': UNREADABLE,
      'GET /context/documents/cv': [],
      'GET /agent': {
        available: true,
        agent: 'claude',
        reason: null,
        background: { available: true, agent: 'claude', reason: null },
        actions: [{ ...action, agent: claude, alternatives: [] }],
      },
      'POST /agent/launch': { ok: true, agent: 'claude', prompt: 'Usa el skill update-profile…', message: 'ok' },
    })
    renderApp('/perfil')
    // El botón de la página abre un diálogo con los dos pasos: subir el CV y lanzar a tu agente.
    await userEvent.click(await screen.findByRole('button', { name: 'Importar información desde un CV' }))
    const dialog = await screen.findByRole('dialog', { name: 'Importar información desde un CV' })
    expect(within(dialog).getByRole('button', { name: 'Subir mi CV' })).toBeInTheDocument()
    const launch = await within(dialog).findByRole('button', { name: 'Importar información desde un CV' })
    await waitFor(() => expect(launch).toBeEnabled())
    await userEvent.click(launch)
    await screen.findByText('Abierto en claude: sigue en la ventana que se acaba de abrir.')
    expect(calls.find((c) => c.path === '/agent/launch')?.body).toEqual({ action: 'import-profile-from-cv' })
  })

  it('está en el menú', async () => {
    mockApi({ 'GET /status': status(), 'GET /context': contextStatus(), 'GET /profile/editable': NO_PROFILE })
    renderApp('/')
    expect(await screen.findByRole('link', { name: 'Mi perfil' })).toHaveAttribute('href', '/perfil')
  })
})
