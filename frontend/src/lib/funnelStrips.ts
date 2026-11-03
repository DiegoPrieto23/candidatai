import type { FunnelStats } from '@/api/client'

/** Ancho mínimo dibujado, sobre la franja mayor: una etapa a 0 o casi también tiene que verse. */
export const FUNNEL_MIN_WIDTH = 0.05

/** Las franjas del gráfico de embudo. Solo el dibujo usa el ancho mínimo: las cifras que se leen son las reales. */
export function funnelStrips(steps: Pick<FunnelStats['steps'][number], 'step' | 'count'>[]) {
  const top = Math.max(1, ...steps.map((s) => s.count))
  return steps.map((s) => ({
    name: s.step,
    width: Math.max(s.count, top * FUNNEL_MIN_WIDTH),
    fill: s.count > 0 ? 'var(--chart-1)' : 'var(--muted-foreground)',
  }))
}
