import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { DemoPlayer } from './ExtensionDemo'

function reducedMotion(reduce: boolean) {
  vi.spyOn(window, 'matchMedia').mockImplementation(
    (query: string) =>
      ({
        matches: reduce && query.includes('prefers-reduced-motion'),
        media: query,
        addEventListener: () => {},
        removeEventListener: () => {},
      }) as unknown as MediaQueryList,
  )
}

afterEach(() => vi.restoreAllMocks())

describe('Demostración del botón del navegador', () => {
  it('va plegada bajo «Ver cómo se hace» y, al abrirla, enseña la animación con su texto alternativo', async () => {
    reducedMotion(false)
    render(<DemoPlayer animated="/anim.webp" still="/still.webp" />)
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Ver cómo se hace' }))
    const img = screen.getByRole('img', { name: /Enviar a CandidatAI/ })
    expect(img).toHaveAttribute('src', '/anim.webp')
    expect(screen.queryByRole('button', { name: 'Reproducir la animación' })).not.toBeInTheDocument()
  })

  it('con menos movimiento, el fotograma fijo y un botón para reproducirla', async () => {
    reducedMotion(true)
    render(<DemoPlayer animated="/anim.webp" still="/still.webp" />)
    await userEvent.click(screen.getByRole('button', { name: 'Ver cómo se hace' }))
    expect(screen.getByRole('img')).toHaveAttribute('src', '/still.webp')
    await userEvent.click(screen.getByRole('button', { name: 'Reproducir la animación' }))
    expect(screen.getByRole('img')).toHaveAttribute('src', '/anim.webp')
  })
})
