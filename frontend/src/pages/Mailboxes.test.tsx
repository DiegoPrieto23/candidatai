import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { MailSourceView } from '@/api/client'
import { alertJob, mockApi, renderApp, status } from '@/test/utils'

function mailbox(id: number, overrides: Partial<MailSourceView> = {}): MailSourceView {
  return {
    id,
    label: `Buzón ${id}`,
    kind: 'imap',
    host: 'imap.gmail.com',
    port: 993,
    security: 'ssl',
    user: 'ana@example.com',
    folder: 'Alertas empleo',
    replies_folder: 'INBOX',
    enabled: true,
    read_replies: false,
    allow_private: false,
    from_env: false,
    has_password: true,
    secret_ref: `CAI_IMAP_BUZON_${id}_PASSWORD`,
    path: null,
    last_polled_at: null,
    last_error: null,
    ...overrides,
  }
}

function routes(sources: MailSourceView[], extra: Record<string, unknown> = {}) {
  return {
    'GET /status': status(),
    'GET /alerts': { jobs: [], total: 0, passed: 0, filters_applied: true },
    'GET /mail-sources': { sources, demo: false, can_store_passwords: true },
    ...extra,
  }
}

async function openWizard() {
  await userEvent.click((await screen.findAllByRole('button', { name: 'Añadir buzón' }))[0])
  return screen.findByRole('dialog')
}

describe('Buzones de las alertas (fase 27.4)', () => {
  it('Gmail: prueba la conexión con la ayuda del error y guarda el buzón', async () => {
    const calls = mockApi(
      routes([], {
        'POST /mail-sources/test': {
          status: 200,
          body: { ok: false, code: 'imap_auth', message: 'El servidor IMAP rechazó el usuario o la contraseña.' },
        },
        'POST /mail-sources': { status: 201, body: { source: mailbox(1), message: 'ok', env_line: null } },
      }),
    )
    renderApp('/alertas')
    const dialog = await openWizard()
    expect(within(dialog).getByRole('tab', { name: 'Gmail', selected: true })).toBeInTheDocument()
    expect(within(dialog).getByRole('link', { name: /Contraseñas de aplicación/ })).toHaveAttribute(
      'href',
      'https://myaccount.google.com/apppasswords',
    )
    expect(within(dialog).getByRole('link', { name: /Guía completa/ }).getAttribute('href')).toMatch(/CONFIGURAR_CORREO\.md#gmail$/)
    await userEvent.type(within(dialog).getByLabelText('Usuario (tu dirección)'), 'ana@gmail.com')
    await userEvent.type(within(dialog).getByLabelText('Contraseña de aplicación'), 'abcd efgh')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Probar conexión' }))
    const outcome = await within(dialog).findByRole('status')
    expect(outcome).toHaveTextContent('No se pudo conectar')
    expect(outcome).toHaveTextContent('que la contraseña sea de aplicación')
    expect(calls.find((c) => c.path === '/mail-sources/test')?.body).toMatchObject({
      label: 'Gmail',
      kind: 'imap',
      host: 'imap.gmail.com',
      port: 993,
      user: 'ana@gmail.com',
      password: 'abcd efgh',
    })

    await userEvent.click(within(dialog).getByRole('button', { name: 'Guardar' }))
    expect(calls.find((c) => c.method === 'POST' && c.path === '/mail-sources')?.body).toMatchObject({
      host: 'imap.gmail.com',
      folder: 'INBOX',
    })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('cada proveedor rellena su servidor; Outlook lleva a Gmail o a una carpeta', async () => {
    const calls = mockApi(
      routes([], {
        'POST /mail-sources': {
          status: 201,
          body: { source: mailbox(2, { kind: 'folder', path: 'data/inbox/alertas/' }), message: 'ok', env_line: null },
        },
      }),
    )
    renderApp('/alertas')
    const dialog = await openWizard()
    const host = () => within(dialog).getByLabelText('Servidor IMAP')

    await userEvent.click(within(dialog).getByRole('tab', { name: 'Yahoo' }))
    expect(host()).toHaveValue('imap.mail.yahoo.com')
    expect(within(dialog).getByLabelText('Nombre')).toHaveValue('Yahoo')
    await userEvent.click(within(dialog).getByRole('tab', { name: 'iCloud' }))
    expect(host()).toHaveValue('imap.mail.me.com')
    expect(within(dialog).getByLabelText('Usuario (lo que va antes de @icloud.com)')).toBeInTheDocument()

    await userEvent.click(within(dialog).getByRole('tab', { name: 'Outlook / Hotmail' }))
    expect(within(dialog).getByText(/Microsoft ya no deja entrar por IMAP/)).toBeInTheDocument()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Ir a Gmail' }))
    expect(within(dialog).getByRole('tab', { name: 'Gmail', selected: true })).toBeInTheDocument()
    await userEvent.click(within(dialog).getByRole('tab', { name: 'Outlook / Hotmail' }))
    await userEvent.click(within(dialog).getByRole('button', { name: 'Ir a «Carpeta de .eml»' }))
    expect(within(dialog).getByRole('tab', { name: 'Carpeta de .eml', selected: true })).toBeInTheDocument()
    expect(within(dialog).queryByRole('button', { name: 'Probar conexión' })).not.toBeInTheDocument()
    expect(within(dialog).getByText(/data\/inbox\/alertas\//)).toBeInTheDocument()

    await userEvent.click(within(dialog).getByRole('button', { name: 'Guardar' }))
    expect(calls.find((c) => c.method === 'POST' && c.path === '/mail-sources')?.body).toMatchObject({
      label: 'Carpeta de .eml',
      kind: 'folder',
      folder: 'alertas',
    })
  })

  it('en Docker dice qué línea añadir a .env en vez de cerrar', async () => {
    mockApi(
      routes([], {
        'POST /mail-sources': {
          status: 201,
          body: { source: mailbox(1, { has_password: false }), message: 'ok', env_line: 'CAI_IMAP_GMAIL_PASSWORD=…' },
        },
      }),
    )
    renderApp('/alertas')
    const dialog = await openWizard()
    await userEvent.type(within(dialog).getByLabelText('Usuario (tu dirección)'), 'ana@gmail.com')
    await userEvent.type(within(dialog).getByLabelText('Contraseña de aplicación'), 'x')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Guardar' }))
    expect(await within(dialog).findByText('CAI_IMAP_GMAIL_PASSWORD=…')).toBeInTheDocument()
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('el panel enseña el estado, se abre solo con un error y prueba, desactiva y quita', async () => {
    const principal = mailbox(1, { label: 'Principal', from_env: true, read_replies: true, secret_ref: 'CAI_IMAP_PASSWORD' })
    const broken = mailbox(2, {
      label: 'Trabajo',
      has_password: false,
      last_polled_at: '2026-10-23T08:00:00Z',
      last_error: { code: 'imap_folder', message: 'El servidor IMAP rechazó abrir la carpeta «X».' },
    })
    const calls = mockApi(
      routes([principal, broken], {
        'POST /mail-sources/2/test': { status: 200, body: { ok: true, code: null, message: 'Conectado: carpeta «X» abierta en solo lectura.' } },
        'PATCH /mail-sources/2': { status: 200, body: { source: { ...broken, enabled: false }, message: 'ok', env_line: null } },
        'DELETE /mail-sources/2': { status: 200, body: { message: 'Buzón «Trabajo» quitado.' } },
      }),
    )
    renderApp('/alertas')

    // Abierto de entrada porque uno tiene un error.
    expect(await screen.findByText(/2 buzones/)).toBeInTheDocument()
    expect(screen.getByText(/1 con error/)).toBeInTheDocument()
    expect(screen.getByText('Falta la contraseña (CAI_IMAP_BUZON_2_PASSWORD)')).toBeInTheDocument()
    expect(screen.getByText(/escribe el nombre exacto/)).toBeInTheDocument()
    expect(screen.getByText('de .env')).toBeInTheDocument()
    // La cuenta de .env no se quita desde aquí.
    expect(screen.queryByRole('button', { name: 'Quitar Principal' })).not.toBeInTheDocument()

    const rows = screen.getAllByRole('listitem').filter((li) => li.textContent?.includes('Trabajo'))
    const row = rows[rows.length - 1]
    await userEvent.click(within(row).getByRole('button', { name: 'Probar' }))
    expect(await within(row).findByText(/Conectado/)).toBeInTheDocument()
    await userEvent.click(within(row).getByRole('switch', { name: 'Leer Trabajo' }))
    expect(calls.find((c) => c.method === 'PATCH')?.body).toEqual({ enabled: false })
    await userEvent.click(within(row).getByRole('button', { name: 'Quitar Trabajo' }))
    // Con el foco en el panel, D no abre el descarte de la lista.
    await userEvent.keyboard('d')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    await userEvent.click(within(row).getByRole('button', { name: '¿Quitar? Sí' }))
    expect(calls.some((c) => c.method === 'DELETE' && c.path === '/mail-sources/2')).toBe(true)
  })

  it('editar la cuenta de .env solo deja cambiar el nombre y si lee respuestas', async () => {
    const principal = mailbox(1, { label: 'Principal', from_env: true, secret_ref: 'CAI_IMAP_PASSWORD' })
    const calls = mockApi(
      routes([principal], {
        'PATCH /mail-sources/1': { status: 200, body: { source: principal, message: 'ok', env_line: null } },
      }),
    )
    renderApp('/alertas')
    await userEvent.click(await screen.findByText(/1 buzón/))
    await userEvent.click(screen.getByRole('button', { name: 'Editar Principal' }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).queryByLabelText('Contraseña de aplicación')).not.toBeInTheDocument()
    expect(within(dialog).queryByLabelText('Servidor IMAP')).not.toBeInTheDocument()
    await userEvent.click(within(dialog).getByLabelText('Leer aquí también las respuestas de las empresas'))
    await userEvent.click(within(dialog).getByRole('button', { name: 'Guardar' }))
    expect(calls.find((c) => c.method === 'PATCH')?.body).toEqual({ label: 'Principal', read_replies: true })
  })

  it('la pantalla vacía lleva a «Añadir buzón» y con el diálogo abierto las teclas no descartan', async () => {
    mockApi({
      ...routes([]),
      'GET /alerts': { jobs: [alertJob(1)], total: 1, passed: 1, filters_applied: true },
    })
    renderApp('/alertas')
    await screen.findByText('Alerta 1')
    const dialog = await openWizard()
    await userEvent.click(within(dialog).getByRole('tab', { name: 'Yahoo' }))
    await userEvent.keyboard('d')
    expect(screen.queryByText(/Descartar «/)).not.toBeInTheDocument()
    expect(screen.getAllByRole('dialog')).toHaveLength(1)
  })

  it('sin alertas ni buzones, la pantalla vacía ofrece añadir uno', async () => {
    mockApi(routes([]))
    renderApp('/alertas')
    const empty = await screen.findByText('Sin alertas pendientes')
    const section = empty.closest('section')
    expect(section).not.toBeNull()
    await userEvent.click(within(section as HTMLElement).getByRole('button', { name: 'Añadir buzón' }))
    expect(await screen.findByRole('dialog')).toBeInTheDocument()
  })
})
