import { render, screen, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { PageErrorBoundary } from '@/components/PageErrorBoundary'

function Broken({ message }: { message: string }): never {
  throw new Error(message)
}

const CHUNK = 'Failed to fetch dynamically imported module: http://127.0.0.1:8000/assets/InboxPage-abc.js'

function inRouter(children: ReactNode) {
  return <MemoryRouter>{children}</MemoryRouter>
}

/** La app contesta (`true`) o no (`false`) a la comprobación del aviso. */
function apiAnswers(answers: boolean) {
  const fetch = vi.fn(async () => (answers ? Response.json({}) : Promise.reject(new TypeError('Failed to fetch'))))
  vi.stubGlobal('fetch', fetch)
  return fetch
}

describe('Una página que no se puede abrir', () => {
  const reload = vi.fn()

  beforeEach(() => {
    vi.stubGlobal('location', { ...window.location, reload })
    // React avisa en la consola de cada error capturado: aquí es lo esperado.
    vi.spyOn(console, 'error').mockImplementation(() => undefined)
  })

  afterEach(() => {
    reload.mockReset()
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('si no llega su código y la app no contesta, recarga una vez y luego dice que la app no responde', async () => {
    const fetch = apiAnswers(false)
    render(
      inRouter(
        <PageErrorBoundary path="/bandeja">
          <Broken message={CHUNK} />
        </PageErrorBoundary>,
      ),
    )
    expect(reload).toHaveBeenCalledTimes(1)
    expect(await screen.findByRole('alert')).toHaveTextContent('La app no responde')
    expect(fetch).toHaveBeenCalledWith(expect.stringMatching(/\/status$/), expect.anything())

    // Si vuelve a fallar enseguida, no recarga en bucle.
    render(
      inRouter(
        <PageErrorBoundary path="/bandeja">
          <Broken message={CHUNK} />
        </PageErrorBoundary>,
      ),
    )
    expect(reload).toHaveBeenCalledTimes(1)
    await waitFor(() => expect(screen.getAllByRole('button', { name: 'Recargar' })).toHaveLength(2))
    screen.getAllByRole('button', { name: 'Recargar' })[1]!.click()
    expect(reload).toHaveBeenCalledTimes(2)
  })

  it('si falla al pintar, no culpa a una actualización: lleva a Inicio y dice dónde avisar (H-001)', () => {
    const fetch = apiAnswers(true)
    const { rerender } = render(
      inRouter(
        <PageErrorBoundary path="/bandeja">
          <Broken message="algo falló al pintar" />
        </PageErrorBoundary>,
      ),
    )
    expect(reload).not.toHaveBeenCalled()
    const alert = screen.getByRole('alert')
    expect(alert).toHaveTextContent('Esta página ha fallado')
    expect(alert).not.toHaveTextContent(/actualizado|parado/)
    expect(screen.getByRole('link', { name: 'Volver a Inicio' })).toHaveAttribute('href', '/')
    expect(screen.getByRole('link', { name: 'GitHub' })).toHaveAttribute('href', expect.stringContaining('/issues'))
    expect(alert).toHaveTextContent('F12')
    expect(fetch).not.toHaveBeenCalled()

    // Al cambiar de página se vuelve a intentar.
    rerender(
      inRouter(
        <PageErrorBoundary path="/procesos">
          <p>Procesos</p>
        </PageErrorBoundary>,
      ),
    )
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.getByText('Procesos')).toBeInTheDocument()
  })

  it('si no llega su código pero la app contesta, es la página la que falla', async () => {
    sessionStorage.setItem('cai-chunk-reload', String(Date.now())) // ya se recargó hace nada
    apiAnswers(true)
    render(
      inRouter(
        <PageErrorBoundary path="/calendario">
          <Broken message={CHUNK} />
        </PageErrorBoundary>,
      ),
    )
    expect(reload).not.toHaveBeenCalled()
    expect(await screen.findByRole('alert')).toHaveTextContent('Esta página ha fallado')
  })
})
