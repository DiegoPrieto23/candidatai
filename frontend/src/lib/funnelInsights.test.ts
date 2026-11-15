import { describe, expect, it } from 'vitest'
import type { FunnelStats } from '@/api/client'
import { funnelInsights } from '@/lib/funnelInsights'

type Channel = FunnelStats['by_channel'][number]
type Source = FunnelStats['by_source'][number]

const channel = (name: Channel['channel'], applied: number, replied: number, median: number | null): Channel => ({
  channel: name,
  found: applied,
  approved: applied,
  applied,
  replied,
  interview: 0,
  reply_rate: applied ? replied / applied : null,
  median_reply_days: median,
  timed_replies: median == null ? 0 : replied,
})

const source = (id: number, name: string, applied: number, replied: number): Source => ({
  source_id: id,
  kind: 'infojobs',
  name,
  found: applied,
  approved: applied,
  applied,
  replied,
  interview: 0,
  reply_rate: applied ? replied / applied : null,
  tokens: 0,
  cost_usd: null,
})

function stats(overrides: Partial<FunnelStats> = {}): FunnelStats {
  return {
    min_applied: 10,
    min_replied: 5,
    by_channel: [
      channel('referral', 10, 4, 3),
      channel('company', 0, 0, null),
      channel('portal', 30, 3, 1),
      channel('manual', 20, 3, null),
    ],
    by_source: [source(1, 'InfoJobs', 20, 4), source(2, 'Adzuna', 10, 1)],
    response_time: { applied: 60, replied: 10, median_days: 9, mean_days: 10, awaiting_reply: 3, closed_without_reply: 2 },
    ...overrides,
  } as FunnelStats
}

describe('funnelInsights', () => {
  it('saca la frase de cada cosa con datos suficientes', () => {
    expect(funnelInsights(stats())).toEqual([
      // Referencia, 4/10, frente a los demás juntos, 6/50.
      { id: 'bestChannel', channel: 'referral', rate: 0.4, others: 0.12 },
      { id: 'medianReply', days: 9 },
      { id: 'bestSource', name: 'InfoJobs', rate: 0.2 },
    ])
  })

  it('compara el canal más rápido con el más lento cuando los dos tienen bastantes respuestas', () => {
    const insights = funnelInsights(
      stats({ by_channel: [channel('referral', 10, 5, 3), channel('company', 20, 6, 12), channel('portal', 30, 2, 1)] }),
    )
    expect(insights).toContainEqual({ id: 'fastestChannel', channel: 'referral', days: 3, slowChannel: 'company', slowDays: 12 })
  })

  it('sin el mínimo de enviadas o de respuestas no dice nada', () => {
    const few = stats({
      by_channel: [channel('referral', 9, 9, 1), channel('portal', 30, 3, 2)],
      by_source: [source(1, 'InfoJobs', 9, 9), source(2, 'Adzuna', 30, 3)],
      response_time: { applied: 39, replied: 4, median_days: 2, mean_days: 2, awaiting_reply: 0, closed_without_reply: 0 },
    })
    expect(funnelInsights(few)).toEqual([])
  })

  it('una diferencia de menos de diez puntos o de un día no se cuenta como hallazgo', () => {
    const close = stats({
      by_channel: [channel('referral', 20, 7, 3), channel('company', 20, 6, 3.5), channel('portal', 20, 6, 3.2)],
      by_source: [source(1, 'InfoJobs', 20, 7), source(2, 'Adzuna', 20, 6)],
    })
    expect(funnelInsights(close).map((i) => i.id)).toEqual(['medianReply'])
  })

  it('la mediana de un canal cuenta solo las respuestas con fecha', () => {
    const undated = stats({
      by_channel: [{ ...channel('referral', 10, 6, 1), timed_replies: 2 }, channel('portal', 30, 6, 9)],
    })
    expect(funnelInsights(undated).map((i) => i.id)).not.toContain('fastestChannel')
  })

  it('no elige un canal que responde menos que el resto ni una fuente empatada', () => {
    const tie = stats({
      by_channel: [channel('portal', 20, 2, null), channel('manual', 20, 2, null)],
      by_source: [source(1, 'InfoJobs', 10, 1), source(2, 'Adzuna', 10, 1)],
    })
    expect(funnelInsights(tie).map((i) => i.id)).toEqual(['medianReply'])
  })
})
