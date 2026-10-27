import { render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { PageErrorBoundary } from '@/components/PageErrorBoundary'

function Broken({ message }: { message: string }): never {
  throw new Error(message)
}

const CHUNK = 'Failed to fetch dynamically imported module: http://127.0.0.1:8000/assets/InboxPage-abc.js'

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
  })

  it('si no llega su código (la app se actualizó), recarga una vez y luego avisa', () => {
    render(
      <PageErrorBoundary path="/bandeja">
        <Broken message={CHUNK} />
      </PageErrorBoundary>,
    )
    expect(reload).toHaveBeenCalledTimes(1)
    expect(screen.getByRole('alert')).toHaveTextContent('No se ha podido abrir esta página')

    // Si vuelve a fallar enseguida, no recarga en bucle.
    render(
      <PageErrorBoundary path="/bandeja">
        <Broken message={CHUNK} />
      </PageErrorBoundary>,
    )
    expect(reload).toHaveBeenCalledTimes(1)
    screen.getAllByRole('button', { name: 'Recargar' })[1]!.click()
    expect(reload).toHaveBeenCalledTimes(2)
  })

  it('otro error avisa sin recargar y se vuelve a intentar al cambiar de página', () => {
    const { rerender } = render(
      <PageErrorBoundary path="/bandeja">
        <Broken message="algo falló al pintar" />
      </PageErrorBoundary>,
    )
    expect(reload).not.toHaveBeenCalled()
    expect(screen.getByRole('alert')).toBeInTheDocument()
    rerender(
      <PageErrorBoundary path="/procesos">
        <p>Procesos</p>
      </PageErrorBoundary>,
    )
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.getByText('Procesos')).toBeInTheDocument()
  })
})
