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

describe('Mi perfil', () => {
  it('enseña el estado de cada fichero de contexto y las carpetas de documentos', async () => {
    mockApi({ 'GET /status': status(), 'GET /context': contextStatus() })
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
    expect(within(documentos).getByText('cv/')).toBeInTheDocument()
    expect(within(documentos).getByText('2 ficheros')).toBeInTheDocument()
    expect(within(documentos).getByText('1 fichero')).toBeInTheDocument()
    // Sin editor: el texto se edita fuera de la app.
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
  })

  it('abre la carpeta del contexto', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /context': contextStatus(),
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
      'POST /folders/open': { status: 200, body: { path: 'C:/cai/data/documentos', opened: false } },
    })
    renderApp('/perfil')
    await userEvent.click(await screen.findByRole('button', { name: 'Abrir la carpeta de documentos' }))
    expect(await screen.findByText(/No se pudo abrir aquí/)).toBeInTheDocument()
    expect(screen.getByText('C:/cai/data/documentos')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Copiar ruta' })).toBeInTheDocument()
  })

  it('está en el menú', async () => {
    mockApi({ 'GET /status': status(), 'GET /context': contextStatus() })
    renderApp('/')
    expect(await screen.findByRole('link', { name: 'Mi perfil' })).toHaveAttribute('href', '/perfil')
  })
})
