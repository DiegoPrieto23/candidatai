import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { BusyLabel, StableLabel } from './StableLabel'

describe('StableLabel', () => {
  it('reserva el texto más largo sin ponerlo en el DOM', () => {
    render(<button type="button"><StableLabel text="Copiar" reserve={['Copiado', 'No se pudo copiar']} /></button>)
    const button = screen.getByRole('button', { name: 'Copiar' })
    expect(button.querySelector('.stable-label')).toHaveAttribute('data-reserve', 'No se pudo copiar')
    expect(button).toHaveTextContent(/^Copiar$/)
  })

  it('BusyLabel reserva siempre el otro texto', () => {
    const { rerender } = render(<BusyLabel busy={false} busyText="Guardando…" text="Guardar" />)
    expect(screen.getByText('Guardar')).toHaveAttribute('data-reserve', 'Guardando…')
    rerender(<BusyLabel busy busyText="Guardando…" text="Guardar" />)
    expect(screen.getByText('Guardando…')).toHaveAttribute('data-reserve', 'Guardar')
  })
})
