import { screen, waitFor, within } from '@testing-library/react'
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
  localStorage.removeItem('cai.browser')
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

    expect(await screen.findByRole('heading', { name: 'Cargarla en el navegador' })).toBeInTheDocument()
    expect(screen.getByText('chrome://extensions')).toBeInTheDocument()
    // La ventana de elegir carpeta no recuerda la del paso 1: la ruta, a la vista y para copiar.
    expect(screen.getByText(STATUS.folder)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Copiar la ruta de la carpeta de la extensión' })).toBeInTheDocument()
    expect(screen.getByText(/pegar esta ruta/)).toBeInTheDocument()
    expect(screen.getByText(/Esperando a que se cargue/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Conectar' })).toBeDisabled()
    expect(screen.queryByText(/funciona en Chrome, Edge o Brave/)).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Abrir la carpeta de la extensión' }))
    await waitFor(() => expect(calls.some((c) => c.path === '/folders/open')).toBe(true))
    expect(calls.find((c) => c.path === '/folders/open')?.body).toEqual({ folder: 'extension' })
  })

  it('«Ver cómo se hace» va junto al título del paso 3 y abre la animación justo debajo', async () => {
    mockApi({ 'GET /status': status(), 'GET /capture/extension': STATUS })
    renderApp('/fuentes/extension')
    const title = await screen.findByRole('heading', { name: 'Fijarla en la barra y usarla' })
    const toggle = within(title.parentElement as HTMLElement).getByRole('button', { name: 'Ver cómo se hace' })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByRole('img', { name: /Enviar a CandidatAI/ })).not.toBeInTheDocument()
    await userEvent.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('img', { name: /Enviar a CandidatAI/ })).toBeInTheDocument()
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

    expect(await screen.findByText(/La extensión instalada es una versión antigua/)).toBeInTheDocument()
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
    expect(await screen.findByText('La app no acepta esta extensión.')).toHaveAttribute('role', 'alert')
  })

  it('fuera de Chrome, Edge o Brave, avisa', async () => {
    vi.spyOn(navigator, 'userAgent', 'get').mockReturnValue('Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0')
    mockApi({ 'GET /status': status(), 'GET /capture/extension': STATUS })
    renderApp('/fuentes/extension')

    // Lo dice antes de los pasos, que no salen: con Firefox no se puede seguir.
    expect(await screen.findByText(/funciona en Chrome, Edge y Brave/)).toBeInTheDocument()
    const picker = screen.getByRole('radiogroup', { name: 'Navegador' })
    expect(within(picker).getByRole('radio', { name: /Firefox/ })).toHaveAttribute('aria-checked', 'true')
    expect(screen.queryByText('firefox://extensions')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Conectar' })).not.toBeInTheDocument()
  })

  it('primero el navegador: con Edge, los pasos de Edge y el aviso de abrir la app en él', async () => {
    mockApi({ 'GET /status': status(), 'GET /capture/extension': STATUS })
    renderApp('/fuentes/extension')

    const picker = await screen.findByRole('radiogroup', { name: 'Navegador' })
    // Detecta Chrome (el de la prueba) y enseña sus pasos.
    expect(within(picker).getByRole('radio', { name: /Chrome \(este\)/ })).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByText('chrome://extensions')).toBeInTheDocument()

    await userEvent.click(within(picker).getByRole('radio', { name: 'Edge' }))
    expect(screen.getByText('edge://extensions')).toBeInTheDocument()
    expect(screen.getByText(/en el panel de la izquierda/)).toBeInTheDocument()
    expect(screen.getByText('Cargar desempaquetada')).toBeInTheDocument()
    expect(screen.getAllByText((_, el) => el?.tagName === 'LI' && /^Pulsar el botón Extensiones/.test(el.textContent ?? ''))).toHaveLength(1)
    expect(screen.getByText(/CandidatAI se abre en Edge/)).toBeInTheDocument()
    // Se recuerda para la próxima vez.
    expect(localStorage.getItem('cai.browser')).toBe('edge')
  })
})
