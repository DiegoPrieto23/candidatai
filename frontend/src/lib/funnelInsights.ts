import type { FunnelStats } from '@/api/client'

type Channel = FunnelStats['by_channel'][number]
export type ChannelName = Channel['channel']

/**
 * Las frases de arriba de «Resultados»: lo que dicen los datos, no las cifras. Cada una sale solo
 * si sus grupos llegan al mínimo que da el servidor (`min_applied` enviadas para una tasa,
 * `min_replied` respuestas con fecha para una mediana) y si la diferencia que cuenta es clara
 * (`MIN_RATE_GAP`, `MIN_DAYS_GAP`): con menos, una diferencia no dice nada.
 */
export type Insight =
  | { id: 'bestChannel'; channel: ChannelName; rate: number; others: number }
  | { id: 'medianReply'; days: number }
  | { id: 'fastestChannel'; channel: ChannelName; days: number; slowChannel: ChannelName; slowDays: number }
  | { id: 'bestSource'; name: string; rate: number }

/** Diez puntos de tasa de respuesta, o un día de mediana, como poco, para llamarlo «más» o «antes». */
export const MIN_RATE_GAP = 0.1
export const MIN_DAYS_GAP = 1

const rate = (replied: number, applied: number) => (applied ? replied / applied : 0)
/** `a` le saca a `b` al menos `gap` (con margen para el redondeo: 0,3 − 0,2 no da 0,1 exacto). */
const ahead = (a: number, b: number, gap: number) => a - b >= gap - 1e-9

/** El canal con más respuesta frente a todos los demás juntos. */
function bestChannel(stats: FunnelStats): Insight | null {
  const min = stats.min_applied
  const total = stats.by_channel.reduce((acc, c) => ({ applied: acc.applied + c.applied, replied: acc.replied + c.replied }), {
    applied: 0,
    replied: 0,
  })
  const candidates = stats.by_channel
    .filter((c) => c.applied >= min && total.applied - c.applied >= min)
    .map((c) => ({
      channel: c.channel,
      rate: rate(c.replied, c.applied),
      others: rate(total.replied - c.replied, total.applied - c.applied),
    }))
    .sort((a, b) => b.rate - b.others - (a.rate - a.others))
  const best = candidates[0]
  return best && ahead(best.rate, best.others, MIN_RATE_GAP) ? { id: 'bestChannel', ...best } : null
}

function medianReply(stats: FunnelStats): Insight | null {
  const { replied, median_days: days } = stats.response_time
  return days != null && replied >= stats.min_replied ? { id: 'medianReply', days } : null
}

/** El canal que antes responde frente al que más tarda, si los separa al menos un día. */
function fastestChannel(stats: FunnelStats): Insight | null {
  const timed = stats.by_channel
    .filter((c): c is Channel & { median_reply_days: number } => c.median_reply_days != null && c.timed_replies >= stats.min_replied)
    .sort((a, b) => a.median_reply_days - b.median_reply_days)
  const fast = timed[0]
  const slow = timed.at(-1)
  if (!fast || !slow || !ahead(slow.median_reply_days, fast.median_reply_days, MIN_DAYS_GAP)) return null
  return {
    id: 'fastestChannel',
    channel: fast.channel,
    days: fast.median_reply_days,
    slowChannel: slow.channel,
    slowDays: slow.median_reply_days,
  }
}

/** La fuente con más respuesta, si hay al menos dos con datos suficientes y saca ventaja clara a la segunda. */
function bestSource(stats: FunnelStats): Insight | null {
  const ranked = stats.by_source
    .filter((s) => s.applied >= stats.min_applied)
    .map((s) => ({ name: s.name, rate: rate(s.replied, s.applied) }))
    .sort((a, b) => b.rate - a.rate)
  if (ranked.length < 2 || !ahead(ranked[0].rate, ranked[1].rate, MIN_RATE_GAP)) return null
  return { id: 'bestSource', ...ranked[0] }
}

export function funnelInsights(stats: FunnelStats): Insight[] {
  return [bestChannel(stats), medianReply(stats), fastestChannel(stats), bestSource(stats)].filter(
    (i): i is Insight => i !== null,
  )
}
