import { fireEvent, screen, waitFor, within } from '@testing-library/react'
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
  it('enseña el estado de cada nota para tu agente y las carpetas de tus archivos', async () => {
    mockApi({ 'GET /status': status(), 'GET /context': contextStatus(), 'GET /profile/editable': NO_PROFILE, 'GET /context/style-samples': [] })
    renderApp('/perfil')
    const notes = await screen.findByRole('region', { name: 'Notas para el agente' })
    await within(notes).findByRole('region', { name: 'Estilo de redacción' })
    const row = (name: string) => within(notes).getByRole('region', { name })
    expect(await within(row('Estilo de redacción')).findByText('Con contenido')).toBeInTheDocument()
    expect(within(row('Perfil conductual')).getByText('Vacío')).toBeInTheDocument()
    expect(within(row('Criterios')).getByText(/pasa de 20 KB/)).toBeInTheDocument()
    expect(within(row('Narrativa')).getByText('No existe')).toBeInTheDocument()
    expect(within(row('Narrativa')).getByRole('button', { name: 'Crear «Narrativa»' })).toBeInTheDocument()
    // La explicación larga va en la ayuda de la tarjeta, no a la vista.
    expect(within(notes).queryByText(/Nunca respaldan un hecho/)).not.toBeInTheDocument()
    expect(within(notes).getByRole('button', { name: 'Qué es «Notas para el agente»' })).toBeInTheDocument()

    const files = screen.getByRole('region', { name: 'Archivos' })
    // Con su nombre legible, no el de la carpeta en disco.
    expect(within(files).getByText('CV')).toBeInTheDocument()
    expect(within(files).getByText('Títulos')).toBeInTheDocument()
    expect(within(files).queryByText('titulos')).not.toBeInTheDocument()
    expect(within(files).getByText('2 ficheros')).toBeInTheDocument()
    expect(within(files).getByText('1 fichero')).toBeInTheDocument()
    expect(within(files).getAllByText('Vacía')).toHaveLength(3)
    // Los editores se despliegan bajo su fila, al pulsar.
    expect(within(notes).queryByRole('textbox')).not.toBeInTheDocument()
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
    await userEvent.type(screen.getByLabelText(/^Puesto buscado/), 'Data Analyst')
    await userEvent.click(screen.getByRole('checkbox', { name: 'Junior' }))
    const before = reads
    await userEvent.click(screen.getByRole('button', { name: 'Crear el perfil' }))
    expect(await screen.findByText(/Ya hay un perfil/)).toBeInTheDocument()
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
    await userEvent.click(screen.getByRole('button', { name: 'Crear el perfil' }))
    expect(screen.getAllByText('Hace falta para crear el perfil.')).toHaveLength(3)
    expect(screen.getByText('Hace falta al menos uno.')).toBeInTheDocument()
    expect(calls.some((c) => c.method === 'POST' && c.path === '/profile')).toBe(false)

    await userEvent.type(screen.getByLabelText('Nombre'), 'Demo Persona')
    await userEvent.type(screen.getByLabelText(/^Titular/), 'Analista')
    await userEvent.type(screen.getByLabelText(/^Puesto buscado/), 'Data Analyst')
    await userEvent.click(screen.getByRole('checkbox', { name: 'Mid' }))
    await userEvent.click(screen.getByRole('button', { name: 'Crear el perfil' }))
    await waitFor(() =>
      expect(calls.find((c) => c.method === 'POST' && c.path === '/profile')?.body).toEqual({
        name: 'Demo Persona', headline: 'Analista', role: 'Data Analyst', seniority: ['mid'], summary: null, language: 'es',
      }),
    )
    // El editor, con sus pestañas.
    expect(await screen.findByRole('tab', { name: 'Datos personales' })).toBeInTheDocument()
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
      reason_text: 'el agente por defecto',
      blocked: null,
      blocked_code: null,
      warning: null,
    }
    const expand = { id: 'expand', label: 'Mejorar el contenido del perfil', needs_job: false, prompt: 'Usa el skill expand…', background: false }
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
    const button = await screen.findByRole('button', { name: 'Mejorar el contenido del perfil' })
    await waitFor(() => expect(button).toBeEnabled())
    await userEvent.click(button)
    expect(await screen.findByText('Abierto en claude, en una ventana aparte detrás del navegador: si pide un permiso o una respuesta, está en la barra de tareas.')).toBeInTheDocument()
    expect(calls.find((c) => c.path === '/agent/launch')?.body).toEqual({ lang: 'es', action: 'expand' })
    view.unmount()

    const noAgent = 'Codex no tiene visión, y esta acción lo necesita.'
    mockApi({
      'GET /status': status(),
      'GET /context': contextStatus(),
      'GET /profile/editable': UNREADABLE,
      'GET /agent': launcher({ ...claude, agent: 'codex', display_name: 'Codex', blocked: noAgent, blocked_code: 'capability' }),
    })
    renderApp('/perfil')
    const blocked = await screen.findByRole('button', { name: 'Mejorar el contenido del perfil' })
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
      reason_text: 'el agente por defecto',
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
    expect(within(dialog).getByRole('button', { name: 'Subir el CV' })).toBeInTheDocument()
    const launch = await within(dialog).findByRole('button', { name: 'Importar información desde un CV' })
    await waitFor(() => expect(launch).toBeEnabled())
    await userEvent.click(launch)
    await screen.findByText('Abierto en claude, en una ventana aparte detrás del navegador: si pide un permiso o una respuesta, está en la barra de tareas.')
    expect(calls.find((c) => c.path === '/agent/launch')?.body).toEqual({ lang: 'es', action: 'import-profile-from-cv' })
  })

  it('sin perfil, el CV se sube arrastrándolo a la caja; un formato que no vale no se sube', async () => {
    let uploaded = false
    const calls = mockApi({
      'GET /status': status(),
      'GET /context': contextStatus(),
      'GET /profile/editable': NO_PROFILE,
      'GET /context/documents/cv': () =>
        uploaded ? [{ name: 'cv-demo.pdf', size_bytes: 1000, modified_at: '2026-11-15T08:00:00Z' }] : [],
      'POST /context/documents/cv': () => {
        uploaded = true
        return { name: 'cv-demo.pdf' }
      },
    })
    renderApp('/perfil')
    const button = await screen.findByRole('button', { name: 'Subir el CV' })
    const zone = button.closest('div.border-dashed') as HTMLElement
    expect(within(zone).getByText('Arrastrar aquí el CV o subirlo desde el equipo')).toBeInTheDocument()

    const drag = (files: File[]) => ({ dataTransfer: { files, types: ['Files'] } })
    fireEvent.dragOver(zone, drag([]))
    expect(within(zone).getByText('Soltar para subirlo')).toBeInTheDocument()
    fireEvent.drop(zone, drag([new File(['x'], 'foto.png', { type: 'image/png' })]))
    expect(await screen.findByRole('alert')).toHaveTextContent('Ese formato no se admite')
    expect(calls.some((c) => c.method === 'POST' && c.path === '/context/documents/cv')).toBe(false)

    fireEvent.drop(zone, drag([new File(['%PDF'], 'cv-demo.pdf', { type: 'application/pdf' })]))
    await screen.findByText('CV subido: cv-demo.pdf')
    expect(calls.find((c) => c.path === '/context/documents/cv' && c.method === 'POST')?.body).toMatchObject({
      filename: 'cv-demo.pdf',
    })
    expect(screen.getByRole('button', { name: 'Subir otro CV' })).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('está en el menú', async () => {
    mockApi({ 'GET /status': status(), 'GET /context': contextStatus(), 'GET /profile/editable': NO_PROFILE })
    renderApp('/')
    expect(await screen.findByRole('link', { name: 'Mi perfil' })).toHaveAttribute('href', '/perfil')
  })
})
