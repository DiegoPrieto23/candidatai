import { describe, expect, it } from 'vitest'
import { moveOptions, noMoveReason } from '@/lib/moves'
import { formatWhen, fromLocalInput, toLocalDateInput, toLocalInput } from '@/lib/time'
import { BOARD_MOVES, boardCard } from '@/test/utils'

describe('Horas de Madrid', () => {
  it('convierte la hora de pared a ISO con el desfase de verano y de invierno', () => {
    expect(fromLocalInput('2026-10-07T10:30')).toBe('2026-10-07T10:30:00+02:00')
    expect(fromLocalInput('2026-12-01T10:00')).toBe('2026-12-01T10:00:00+01:00')
    expect(fromLocalInput('2026-12-01')).toBe('2026-12-01T00:00:00+01:00')
    expect(fromLocalInput('mañana')).toBeNull()
    expect(fromLocalInput('2026-02-31T10:00')).toBeNull()
    expect(fromLocalInput('2026-10-07T25:00')).toBeNull()
  })

  it('pinta los instantes en hora de Madrid', () => {
    expect(toLocalInput('2026-10-07T08:30:00Z')).toBe('2026-10-07T10:30')
    expect(toLocalDateInput('2026-12-31T23:30:00Z')).toBe('2027-01-01')
    expect(formatWhen('2026-10-07T08:30:00Z')).toMatch(/7 oct.*10:30/)
    expect(formatWhen('2026-10-06T22:00:00Z', true)).toMatch(/7 oct/)
  })
})

describe('Movimientos del kanban', () => {
  it('ofrece solo los eventos que llevan a la columna de destino', () => {
    const approved = boardCard(1, 'approved')
    expect(moveOptions(approved, BOARD_MOVES, 'applied').map((o) => o.event)).toEqual(['applied_manually'])
    expect(moveOptions(approved, BOARD_MOVES, 'closed').map((o) => o.event)).toEqual([
      'discarded',
      'rejected',
      'withdrawn',
      'expired',
    ])
    expect(moveOptions(approved, BOARD_MOVES, 'cv_ready')).toEqual([])
    expect(noMoveReason(approved, 'cv_ready')).toMatch(/CV está verificado/)
  })

  it('reabre a la etapa previa al cierre y a ninguna otra', () => {
    const closed = boardCard(2, 'closed', { reopen_to: 'applied', closed_by: 'rejected' })
    expect(moveOptions(closed, BOARD_MOVES, 'applied')).toEqual([{ event: 'reopened', to: 'applied' }])
    expect(moveOptions(closed, BOARD_MOVES, 'in_process')).toEqual([])
    expect(noMoveReason(closed, 'in_process')).toBe('Al reabrirla vuelve a «Enviada».')
  })
})
