import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mockApi, renderApp, status } from '@/test/utils'

const EXTENSION_ID = 'hnaofhehllbkghfehnehamjbkcmdjmle'
const STATUS = { configured: false, extension_id: EXTENSION_ID, version: '0.2.0', folder: 'C:/CandidatAI/app/extension' }

type Reply = { version: string; connected: boolean; kind: string; message: string } | undefined
type Message = { type: string; token?: string }

/** La extensión instalada: `answer` decide qué responde a cada mensaje (`undefined`: no responde). */
function installExtension(answer: (message: Message) => Reply) {
  const sent: Message[] = []
  const runtime: { lastError?: { message: string }; sendMessage: unknown } = {
    sendMessage: (id: string, message: Message, callback: (reply: unknown) => void) => {
      expect(id).toBe(EXTENSION_ID)
      sent.push(message)
      const reply = answer(message)
      runtime.lastError = reply ? undefined : { message: 'Could not establish connection.' }
      setTimeout(() => callback(reply), 0)
    },
  }
  vi.stubGlobal('chrome', { runtime })
  return sent
}

beforeEach(() => {
  vi.spyOn(navigator, 'userAgent', 'get').mockReturnValue(
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
  )
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('«Dónde buscar → Botón del navegador»', () => {
  it('sin la extensión, guía la carga y no deja conectar todavía', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /capture/extension': STATUS,
      'POST /folders/open': { path: STATUS.folder, opened: true },
    })
    renderApp('/fuentes/extension')

    expect(await screen.findByRole('heading', { name: 'Cárgala en tu navegador' })).toBeInTheDocument()
    expect(screen.getByText('chrome://extensions')).toBeInTheDocument()
    expect(screen.getByText(/Esperando a que la cargues/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Conectar' })).toBeDisabled()
    expect(screen.queryByText(/funciona en Chrome, Edge o Brave/)).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Abrir la carpeta de la extensión' }))
    await waitFor(() => expect(calls.some((c) => c.path === '/folders/open')).toBe(true))
    expect(calls.find((c) => c.path === '/folders/open')?.body).toEqual({ folder: 'extension' })
  })

  it('la conecta con un clic: pide la clave a la app y se la pasa a la extensión', async () => {
    let connected = false
    const sent = installExtension((message) => {
      if (message.type === 'pair') connected = message.token === 'clave-de-prueba-0123456789'
      return { version: '0.2.0', connected, kind: connected ? 'connected' : 'no_token', message: '' }
    })
    const calls = mockApi({
      'GET /status': status(),
      'GET /capture/extension': STATUS,
      'POST /capture/pair': { token: 'clave-de-prueba-0123456789', extension_id: EXTENSION_ID },
    })
    renderApp('/fuentes/extension')

    expect(await screen.findByText('Instalada (versión 0.2.0).')).toBeInTheDocument()
    await userEvent.click(await screen.findByRole('button', { name: 'Conectar' }))

    expect(await screen.findByText(/Conectada: la extensión ya puede guardar ofertas/)).toBeInTheDocument()
    expect(calls.filter((c) => c.path === '/capture/pair')).toHaveLength(1)
    expect(sent).toContainEqual({ type: 'pair', token: 'clave-de-prueba-0123456789' })
    expect(screen.getByRole('button', { name: 'Conectar de nuevo' })).toBeEnabled()
  })

  it('avisa si la extensión cargada es de una versión antigua', async () => {
    installExtension(() => ({ version: '0.1.5', connected: true, kind: 'connected', message: '' }))
    mockApi({ 'GET /status': status(), 'GET /capture/extension': { ...STATUS, configured: true } })
    renderApp('/fuentes/extension')

    expect(await screen.findByText(/Tienes una versión antigua de la extensión/)).toBeInTheDocument()
  })

  it('si la extensión rechaza la clave, lo dice', async () => {
    installExtension((message) => ({
      version: '0.2.0',
      connected: false,
      kind: message.type === 'pair' ? 'forbidden' : 'no_token',
      message: message.type === 'pair' ? 'La app no acepta esta extensión.' : '',
    }))
    mockApi({
      'GET /status': status(),
      'GET /capture/extension': STATUS,
      'POST /capture/pair': { token: 'clave-de-prueba-0123456789', extension_id: EXTENSION_ID },
    })
    renderApp('/fuentes/extension')

    await userEvent.click(await screen.findByRole('button', { name: 'Conectar' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('La app no acepta esta extensión.')
  })

  it('fuera de Chrome, Edge o Brave, avisa', async () => {
    vi.spyOn(navigator, 'userAgent', 'get').mockReturnValue('Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0')
    mockApi({ 'GET /status': status(), 'GET /capture/extension': STATUS })
    renderApp('/fuentes/extension')

    expect(await screen.findByText(/funciona en Chrome, Edge o Brave/)).toBeInTheDocument()
  })
})
