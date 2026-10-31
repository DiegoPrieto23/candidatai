import { describe, expect, it } from 'vitest'
import type { BoardCard } from '@/api/client'
import { stepOptions } from '@/lib/moves'
import { BOARD_MOVES } from '@/test/utils'

const card = (stage: BoardCard['stage']) => ({ job_id: 1, stage, reopen_to: null }) as unknown as BoardCard

describe('stepOptions', () => {
  it('en proceso añade lo que no cambia de etapa, sin repetir eventos', () => {
    const options = stepOptions(card('in_process'), BOARD_MOVES)
    const events = options.map((o) => o.event)
    expect(new Set(events).size).toBe(events.length)
    expect(options).toEqual(
      expect.arrayContaining([
        { event: 'offer_received', to: 'in_process' },
        { event: 'test_assigned', to: 'in_process' },
        { event: 'accepted', to: 'closed' },
      ]),
    )
  })

  it('enviada: solo los movimientos del tablero', () => {
    const events = stepOptions(card('applied'), BOARD_MOVES).map((o) => o.event)
    expect(events).toContain('reply_received')
    expect(events).not.toContain('accepted')
  })
})
