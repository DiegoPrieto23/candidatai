import { useSyncExternalStore } from 'react'
import type { Stage } from '@/api/client'
import { STAGE_LABEL } from '@/lib/labels'

/**
 * Columnas del Tablero: una vista sobre las etapas. Cada columna junta las etapas que se quiera, en
 * el orden que se quiera, y puede llevar un nombre propio. Agrupar, ordenar o renombrar no cambia
 * ninguna etapa ni ningún evento: se guarda solo en este navegador.
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

/** Las columnas cubren todas las etapas, cada una una vez, y son entre 3 y 5. */
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
  return stages.length === BOARD_STAGES.length && BOARD_STAGES.every((stage) => stages.includes(stage))
}

/** Las de siempre: una columna por etapa, en su orden y sin nombre. */
export function isDefault(layout: BoardColumnSetting[]): boolean {
  return (
    layout.length === BOARD_STAGES.length &&
    layout.every((c, i) => c.stages.length === 1 && c.stages[0] === BOARD_STAGES[i] && !c.name.trim())
  )
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

const stageOrder = (stage: Stage) => (BOARD_STAGES as readonly Stage[]).indexOf(stage)

/** Dentro de una columna, las etapas van en el orden del proceso, como sus tarjetas. */
function sorted(stages: Stage[]): Stage[] {
  return [...stages].sort((a, b) => stageOrder(a) - stageOrder(b))
}

/** La columna en la que está una etapa. */
export function columnOf(layout: BoardColumnSetting[], stage: Stage): number {
  return layout.findIndex((column) => column.stages.includes(stage))
}

/**
 * Si la etapa puede ir a la columna `target` (o a una nueva, al final): sin pasar de 5 columnas y
 * sin bajar de 3, porque la columna que se queda sin etapas desaparece. Una etapa que ya va sola no
 * pasa a una nueva: solo movería su columna al final y le quitaría el nombre (para eso, las flechas).
 */
export function canAssign(layout: BoardColumnSetting[], stage: Stage, target: number | 'new'): boolean {
  const from = columnOf(layout, stage)
  if (target === from) return true
  const emptiesFrom = layout[from]?.stages.length === 1
  if (emptiesFrom && target === 'new') return false
  const count = layout.length + (target === 'new' ? 1 : 0) - (emptiesFrom ? 1 : 0)
  return count >= MIN_COLUMNS && count <= MAX_COLUMNS
}

/** Lleva la etapa a otra columna (o a una nueva, al final, sin nombre). */
export function assignStage(layout: BoardColumnSetting[], stage: Stage, target: number | 'new'): BoardColumnSetting[] {
  if (!canAssign(layout, stage, target) || target === columnOf(layout, stage)) return layout
  const next = layout.map((column, i) => ({
    ...column,
    stages: sorted(
      i === target ? [...column.stages.filter((s) => s !== stage), stage] : column.stages.filter((s) => s !== stage),
    ),
  }))
  if (target === 'new') next.push({ stages: [stage], name: '' })
  return next.filter((column) => column.stages.length > 0)
}

/** Cambia una columna de sitio. */
export function moveColumn(layout: BoardColumnSetting[], from: number, to: number): BoardColumnSetting[] {
  if (from === to || to < 0 || to >= layout.length) return layout
  const next = [...layout]
  const [moved] = next.splice(from, 1)
  next.splice(to, 0, moved)
  return next
}
