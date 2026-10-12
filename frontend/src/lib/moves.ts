import type { BoardCard, BoardMove, EventType, Stage } from '@/api/client'
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

/** Por qué no se puede soltar una tarjeta en una columna. */
export function noMoveReason(card: BoardCard, target: Stage): string {
  if (target === 'cv_ready')
    return 'Una oferta llega a «CV listo» cuando su CV está verificado (skill generate-cv), no a mano.'
  if (target === 'approved') return 'Para volver a «Aprobada» hay que reabrirla desde su ficha.'
  if (card.stage === 'closed')
    return card.reopen_to
      ? `Al reabrirla vuelve a «${STAGE_LABEL[card.reopen_to]}».`
      : 'Esta oferta no se puede reabrir desde el tablero.'
  return `Desde «${STAGE_LABEL[card.stage]}» no hay ningún evento que la lleve a «${STAGE_LABEL[target]}».`
}
