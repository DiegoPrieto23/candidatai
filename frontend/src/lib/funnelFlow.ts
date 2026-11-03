/**
 * El dibujo del embudo: de lo enviado a lo aceptado, con una rama por cada grupo de candidaturas que
 * se quedó en un paso. Solo geometría, sin React, para poder probarla.
 *
 * El alto de cada franja es proporcional a las candidaturas que lleva. Lo muy pequeño conserva un
 * mínimo para que se vea: solo afecta al dibujo, las cifras que se leen son las reales.
 */

export const FLOW_STEPS = ['applied', 'replied', 'interview', 'offer', 'accepted'] as const
export type FlowStep = (typeof FLOW_STEPS)[number]
export type StopOutcome = 'open' | 'rejected' | 'withdrawn' | 'expired'

export interface FlowStop {
  step: string
  outcome: StopOutcome
  count: number
}

export interface FlowNode {
  step: FlowStep
  count: number
  x: number
  y: number
  height: number
}

export interface FlowRibbon {
  key: string
  step: FlowStep
  /** La rama de un grupo que se quedó en este paso; `null`: los que pasaron al siguiente. */
  outcome: StopOutcome | null
  count: number
  path: string
}

export interface FlowEnd {
  key: string
  step: FlowStep
  outcome: StopOutcome
  count: number
  x: number
  y: number
  height: number
}

export interface FlowLayout {
  nodes: FlowNode[]
  ribbons: FlowRibbon[]
  ends: FlowEnd[]
  height: number
}

export const NODE_WIDTH = 12
export const END_WIDTH = 10
/** El alto de la franja de todas las enviadas. */
const FULL_HEIGHT = 100
const MIN_HEIGHT = 3
const END_GAP = 10
/** Lo que ocupa una línea de texto junto a una rama: dos seguidas no se pisan. */
const END_MIN_ROW = 16
/** Lo que baja una rama, como mínimo, para separarse de la franja que sigue. */
const BRANCH_DROP = 20
/** Dónde acaba una rama entre dos pasos: deja a su derecha el hueco para su texto. */
const END_AT = 0.42

/** Una franja entre dos tramos verticales, con las curvas en la mitad. */
function ribbon(x0: number, y0: number, h0: number, x1: number, y1: number, h1: number): string {
  const middle = (x0 + x1) / 2
  return [
    `M${x0} ${y0}`,
    `C${middle} ${y0} ${middle} ${y1} ${x1} ${y1}`,
    `L${x1} ${y1 + h1}`,
    `C${middle} ${y1 + h1} ${middle} ${y0 + h0} ${x0} ${y0 + h0}`,
    'Z',
  ].join(' ')
}

export function layoutFlow(counts: Record<FlowStep, number>, stops: readonly FlowStop[], width: number): FlowLayout {
  const scale = FULL_HEIGHT / Math.max(1, counts.applied)
  const size = (count: number) => (count > 0 ? Math.max(count * scale, MIN_HEIGHT) : 0)
  const gap = (width - NODE_WIDTH) / (FLOW_STEPS.length - 1)

  const nodes: FlowNode[] = FLOW_STEPS.map((step, index) => ({
    step,
    count: counts[step],
    x: index * gap,
    y: 0,
    height: size(counts[step]),
  }))
  const ribbons: FlowRibbon[] = []
  const ends: FlowEnd[] = []

  nodes.forEach((node, index) => {
    const next = nodes[index + 1]
    if (!next) return
    const from = node.x + NODE_WIDTH
    if (next.count > 0) {
      ribbons.push({
        key: `${node.step}:next`,
        step: node.step,
        outcome: null,
        count: next.count,
        path: ribbon(from, 0, next.height, next.x, 0, next.height),
      })
    }
    let source = next.height
    let target = Math.max(next.height, node.height * 0.35) + BRANCH_DROP
    const endX = node.x + gap * END_AT
    for (const stop of stops) {
      if (stop.step !== node.step || stop.count <= 0) continue
      const height = size(stop.count)
      const key = `${stop.step}:${stop.outcome}`
      ribbons.push({
        key,
        step: node.step,
        outcome: stop.outcome,
        count: stop.count,
        path: ribbon(from, source, height, endX, target, height),
      })
      ends.push({ key, step: node.step, outcome: stop.outcome, count: stop.count, x: endX, y: target, height })
      source += height
      target += Math.max(height, END_MIN_ROW) + END_GAP
    }
  })

  const bottoms = [...nodes.map((n) => n.y + n.height), ...ends.map((e) => e.y + Math.max(e.height, END_MIN_ROW))]
  return { nodes, ribbons, ends, height: Math.ceil(Math.max(0, ...bottoms)) + 4 }
}

/** A dónde lleva cada rama: a esa etapa en la Bandeja. */
export function stopLink(step: string, outcome: StopOutcome): string {
  if (outcome !== 'open') return '/bandeja?stage=closed'
  return step === 'applied' ? '/bandeja?stage=applied' : '/bandeja?stage=in_process'
}

/** El grupo más grande de los que se quedaron en un paso sin seguir abiertos o esperando. */
export function biggestStop(stops: readonly FlowStop[]): FlowStop | null {
  return stops.reduce<FlowStop | null>((best, stop) => (stop.count > (best?.count ?? 0) ? stop : best), null)
}
