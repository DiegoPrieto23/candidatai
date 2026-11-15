import { useSyncExternalStore } from 'react'
import type { Stage } from '@/api/client'
import { STAGE_LABEL } from '@/lib/labels'

/**
 * Columnas del Tablero: una vista sobre las etapas. Cada columna junta etapas seguidas y puede
 * llevar un nombre propio. Agrupar o renombrar no cambia ninguna etapa ni ningún evento: se guarda
 * solo en este navegador.
 */
export interface BoardColumnSetting {
  stages: Stage[]
  /** Vacío: el nombre de sus etapas. */
  name: string
}

export const BOARD_STAGES = ['approved', 'cv_ready', 'applied', 'in_process', 'closed'] as const satisfies readonly Stage[]
export type BoardStage = (typeof BOARD_STAGES)[number]
export const MIN_COLUMNS = 3
export const MAX_COLUMNS = BOARD_STAGES.length
export const MAX_NAME = 40

const STORAGE_KEY = 'cai-board-columns'
const listeners = new Set<() => void>()

export function defaultLayout(): BoardColumnSetting[] {
  return BOARD_STAGES.map((stage) => ({ stages: [stage], name: '' }))
}

/** Las columnas cubren todas las etapas, en orden, sin repetir, y son entre 3 y 5. */
export function isValidLayout(value: unknown): value is BoardColumnSetting[] {
  if (!Array.isArray(value) || value.length < MIN_COLUMNS || value.length > MAX_COLUMNS) return false
  const stages: unknown[] = []
  for (const column of value) {
    if (typeof column !== 'object' || column === null) return false
    const { stages: own, name } = column as Partial<BoardColumnSetting>
    if (!Array.isArray(own) || own.length === 0) return false
    if (typeof name !== 'string' || name.length > MAX_NAME) return false
    stages.push(...own)
  }
  return stages.length === BOARD_STAGES.length && stages.every((stage, i) => stage === BOARD_STAGES[i])
}

function isDefault(layout: BoardColumnSetting[]): boolean {
  return layout.length === BOARD_STAGES.length && layout.every((c) => !c.name.trim())
}

let cache: { raw: string | null; layout: BoardColumnSetting[] } | null = null

/** Lo guardado o, si no hay nada válido (o no hay almacenamiento), las columnas de siempre. */
export function readLayout(): BoardColumnSetting[] {
  let raw: string | null = null
  try {
    raw = localStorage.getItem(STORAGE_KEY)
  } catch {
    raw = null
  }
  if (cache && cache.raw === raw) return cache.layout
  let layout = defaultLayout()
  if (raw) {
    try {
      const parsed: unknown = JSON.parse(raw)
      if (isValidLayout(parsed)) layout = parsed.map((c) => ({ stages: [...c.stages], name: c.name.trim() }))
    } catch {
      // Valor estropeado: las de siempre.
    }
  }
  cache = { raw, layout }
  return layout
}

export function saveLayout(layout: BoardColumnSetting[]): void {
  if (!isValidLayout(layout)) return
  try {
    if (isDefault(layout)) localStorage.removeItem(STORAGE_KEY)
    else localStorage.setItem(STORAGE_KEY, JSON.stringify(layout))
  } catch {
    // Sin almacenamiento: dura lo que la pestaña no se recargue.
    cache = { raw: null, layout }
  }
  listeners.forEach((notify) => notify())
}

export function resetLayout(): void {
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch {
    cache = null
  }
  listeners.forEach((notify) => notify())
}

function subscribe(notify: () => void): () => void {
  listeners.add(notify)
  return () => listeners.delete(notify)
}

export function useBoardLayout(): BoardColumnSetting[] {
  return useSyncExternalStore(subscribe, readLayout, readLayout)
}

/** El nombre que se ve: el propio o los de sus etapas. */
export function columnName(column: BoardColumnSetting): string {
  return column.name.trim() || column.stages.map((stage) => STAGE_LABEL[stage]).join(' · ')
}

/** Identificador estable de la columna (para soltar tarjetas): su primera etapa. */
export function columnId(column: BoardColumnSetting): Stage {
  return column.stages[0]
}

// --- Editor ---------------------------------------------------------------------------------

/** `joins[i]`: la etapa `i` y la siguiente van en la misma columna. */
export function joinsOf(layout: BoardColumnSetting[]): boolean[] {
  const joins: boolean[] = []
  for (const column of layout) {
    column.stages.forEach((_, i) => joins.push(i < column.stages.length - 1))
  }
  return joins.slice(0, BOARD_STAGES.length - 1)
}

/** Las columnas que salen de unir etapas; cada una conserva el nombre de la que empezaba igual. */
export function layoutFromJoins(joins: boolean[], names: Partial<Record<Stage, string>>): BoardColumnSetting[] {
  const layout: BoardColumnSetting[] = []
  BOARD_STAGES.forEach((stage, i) => {
    if (i > 0 && joins[i - 1]) layout[layout.length - 1].stages.push(stage)
    else layout.push({ stages: [stage], name: names[stage] ?? '' })
  })
  return layout
}
