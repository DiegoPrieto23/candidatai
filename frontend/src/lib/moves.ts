import type { BoardCard, BoardMove, EventType, Stage } from '@/api/client'
import { i18n } from '@/lib/i18n'
import { STAGE_LABEL } from '@/lib/labels'

/** Un evento posible para mover la tarjeta y la etapa a la que la lleva. */
export interface MoveOption {
  event: EventType
  to: Stage
}

/** Movimientos válidos para una tarjeta; con `target`, solo los que llevan a esa columna. */
export function moveOptions(card: BoardCard, moves: BoardMove[], target?: Stage): MoveOption[] {
  const options: MoveOption[] = []
  for (const move of moves) {
    if (!move.from_stages.includes(card.stage)) continue
    const to = move.event === 'reopened' ? card.reopen_to : move.to
    if (!to || to === card.stage) continue
    if (target && to !== target) continue
    options.push({ event: move.event, to })
  }
  return options
}

/**
 * Los pasos de «¿Qué ha pasado?» en la ficha: los movimientos y, en «En proceso», lo que pasa sin
 * cambiar de etapa (otra respuesta, otra entrevista, una prueba, una oferta). El servidor los
 * admite desde ahí; el tablero no los lista porque no mueven la tarjeta.
 */
export function stepOptions(card: BoardCard, moves: BoardMove[]): MoveOption[] {
  const options = moveOptions(card, moves)
  if (card.stage !== 'in_process') return options
  for (const move of moves) {
    if (move.to === 'in_process') options.push({ event: move.event, to: 'in_process' })
  }
  return options
}

/** Las tarjetas se arrastran solo hacia la derecha: hacia etapas posteriores del tablero. */
export function isForward(order: readonly Stage[], from: Stage, to: Stage): boolean {
  return order.indexOf(to) > order.indexOf(from)
}

/** Por qué no se puede soltar una tarjeta en una columna. */
export function noMoveReason(card: BoardCard, target: Stage): string {
  const t = i18n.getFixedT(null, 'move', 'noMove')
  if (target === 'cv_ready') return t('cvReady')
  if (target === 'approved') return t('approved')
  if (card.stage === 'closed')
    return card.reopen_to ? t('reopenTo', { stage: STAGE_LABEL[card.reopen_to] }) : t('cannotReopen')
  return t('noEvent', { from: STAGE_LABEL[card.stage], to: STAGE_LABEL[target] })
}
