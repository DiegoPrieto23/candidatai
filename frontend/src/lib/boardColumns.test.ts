import { describe, expect, it } from 'vitest'
import type { BoardCard } from '@/api/client'
import {
  BOARD_STAGES,
  columnName,
  defaultLayout,
  assignStage,
  canAssign,
  isValidLayout,
  moveColumn,
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

  it('asigna etapas a columnas, ordenadas por el proceso; la columna vacía desaparece', () => {
    let layout = assignStage(defaultLayout(), 'cv_ready', 0)
    expect(layout.map((c) => c.stages)).toEqual([['approved', 'cv_ready'], ['applied'], ['in_process'], ['closed']])
    layout = assignStage(layout, 'approved', 3)
    expect(layout.map((c) => c.stages)).toEqual([['cv_ready'], ['applied'], ['in_process'], ['approved', 'closed']])
    expect(columnName(layout[3])).toBe('Aprobada · Cerrada')
    expect(columnName({ stages: ['approved', 'cv_ready'], name: ' ' })).toBe('Aprobada · CV listo')
    // A una nueva, al final y sin nombre.
    layout = assignStage(layout, 'closed', 'new')
    expect(layout.map((c) => c.stages)).toEqual([['cv_ready'], ['applied'], ['in_process'], ['approved'], ['closed']])
    expect(layout[4].name).toBe('')
  })

  it('entre 3 y 5 columnas: lo que se saldría no se puede asignar', () => {
    // Una etapa que ya va sola no pasa a una nueva: movería su columna y perdería el nombre.
    expect(canAssign(defaultLayout(), 'closed', 'new')).toBe(false)
    expect(assignStage(defaultLayout(), 'closed', 'new')).toEqual(defaultLayout())
    expect(canAssign([{ stages: ['approved', 'cv_ready'], name: '' }, ...defaultLayout().slice(2)], 'cv_ready', 'new')).toBe(true)
    const three = assignStage(assignStage(defaultLayout(), 'cv_ready', 0), 'in_process', 1)
    expect(three).toHaveLength(3)
    expect(canAssign(three, 'closed', 0)).toBe(false) // serían 2
    expect(assignStage(three, 'closed', 0)).toBe(three)
    expect(canAssign(three, 'cv_ready', 1)).toBe(true) // «Aprobada» se queda en la suya
    expect(canAssign(three, 'cv_ready', 'new')).toBe(true) // de 3 a 4
  })

  it('mueve columnas de sitio', () => {
    const moved = moveColumn(defaultLayout(), 4, 0)
    expect(moved.map((c) => c.stages[0])).toEqual(['closed', 'approved', 'cv_ready', 'applied', 'in_process'])
    expect(moveColumn(moved, 0, -1)).toBe(moved)
  })

  it('valida: todas las etapas una vez y entre 3 y 5 columnas, en cualquier orden', () => {
    expect(isValidLayout(defaultLayout())).toBe(true)
    expect(isValidLayout(moveColumn(defaultLayout(), 4, 0))).toBe(true)
    expect(isValidLayout([{ stages: ['cv_ready', 'approved'], name: '' }, ...defaultLayout().slice(2)])).toBe(true)
    expect(isValidLayout([{ stages: ['approved', 'approved'], name: '' }, ...defaultLayout().slice(2)])).toBe(false)
    const two = [{ stages: ['approved', 'cv_ready', 'applied', 'in_process'], name: '' }, ...defaultLayout().slice(4)]
    expect(isValidLayout(two)).toBe(false)
    expect(isValidLayout(defaultLayout().slice(1))).toBe(false)
    expect(isValidLayout('nada')).toBe(false)
  })

  it('guarda, lee y restablece; lo estropeado vuelve a las de siempre', () => {
    const layout = assignStage(defaultLayout(), 'in_process', 2).map((c, i) => (i === 2 ? { ...c, name: 'En marcha' } : c))
    saveLayout(layout)
    expect(readLayout()).toEqual(layout)
    // Uno inválido no se guarda: sigue el anterior.
    saveLayout(defaultLayout().slice(2))
    expect(readLayout()).toEqual(layout)
    // Solo cambiar el orden ya es algo que guardar.
    const reordered = moveColumn(defaultLayout(), 4, 0)
    saveLayout(reordered)
    expect(readLayout()).toEqual(reordered)
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
