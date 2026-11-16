/** Los números que se ofrecen para «ofertas por portal» (el servidor admite de 1 a 100). */
export const MAX_OFFERS = [5, 10, 15, 20, 25, 30, 40, 50, 75, 100] as const

/** Las opciones, con `current` entre ellas si no es una de las de siempre (lo guardó el agente). */
export function maxOffersOptions(...current: (number | null | undefined)[]): number[] {
  const values = new Set<number>(MAX_OFFERS)
  for (const value of current) if (value && value > 0) values.add(value)
  return [...values].sort((a, b) => a - b)
}
