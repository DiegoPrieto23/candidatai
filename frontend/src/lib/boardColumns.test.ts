import { describe, expect, it } from 'vitest'
import type { BoardCard } from '@/api/client'
import {
  BOARD_STAGES,
  columnName,
  defaultLayout,
  isValidLayout,
  joinsOf,
  layoutFromJoins,
  readLayout,
  resetLayout,
  saveLayout,
} from '@/lib/boardColumns'
import { columnMoveOptions } from '@/lib/moves'
import { BOARD_MOVES } from '@/test/utils'

const card = (stage: BoardCard['stage']) => ({ job_id: 1, stage, reopen_to: null }) as unknown as BoardCard

describe('Columnas del tablero', () => {
  it('por defecto, una columna por etapa', () => {
    expect(readLayout()).toEqual(defaultLayout())
    expect(defaultLayout().map((c) => c.stages)).toEqual(BOARD_STAGES.map((s) => [s]))
  })

  it('junta etapas seguidas y conserva los nombres por su primera etapa', () => {
    const layout = layoutFromJoins([true, false, false, false], { approved: 'Por enviar' })
    expect(layout.map((c) => c.stages)).toEqual([['approved', 'cv_ready'], ['applied'], ['in_process'], ['closed']])
    expect(columnName(layout[0])).toBe('Por enviar')
    expect(columnName(layout[1])).toBe('Enviada')
    expect(columnName({ stages: ['approved', 'cv_ready'], name: ' ' })).toBe('Aprobada · CV listo')
    expect(joinsOf(layout)).toEqual([true, false, false, false])
  })

  it('valida: todas las etapas, en orden y entre 3 y 5 columnas', () => {
    expect(isValidLayout(defaultLayout())).toBe(true)
    expect(isValidLayout(layoutFromJoins([true, true, false, false], {}))).toBe(true)
    expect(isValidLayout(layoutFromJoins([true, true, true, false], {}))).toBe(false) // 2 columnas
    expect(isValidLayout([{ stages: ['cv_ready', 'approved'], name: '' }, ...defaultLayout().slice(2)])).toBe(false)
    expect(isValidLayout(defaultLayout().slice(1))).toBe(false)
    expect(isValidLayout('nada')).toBe(false)
  })

  it('guarda, lee y restablece; lo estropeado vuelve a las de siempre', () => {
    const layout = layoutFromJoins([false, false, true, false], { applied: 'En marcha' })
    saveLayout(layout)
    expect(readLayout()).toEqual(layout)
    // Uno inválido no se guarda: sigue el anterior.
    saveLayout(layoutFromJoins([true, true, true, false], {}))
    expect(readLayout()).toEqual(layout)
    resetLayout()
    expect(readLayout()).toEqual(defaultLayout())
    localStorage.setItem('cai-board-columns', '{roto')
    expect(readLayout()).toEqual(defaultLayout())
    localStorage.setItem('cai-board-columns', JSON.stringify([{ stages: ['closed'], name: '' }]))
    expect(readLayout()).toEqual(defaultLayout())
  })

  it('al soltar en una columna con varias etapas, cuentan solo las posteriores a la de la tarjeta', () => {
    const toIt = columnMoveOptions(card('applied'), BOARD_MOVES, BOARD_STAGES, ['applied', 'in_process'])
    expect(toIt.map((o) => o.to)).toEqual(expect.arrayContaining(['in_process']))
    expect(toIt.every((o) => o.to === 'in_process')).toBe(true)
    expect(columnMoveOptions(card('in_process'), BOARD_MOVES, BOARD_STAGES, ['approved', 'cv_ready'])).toEqual([])
  })
})
