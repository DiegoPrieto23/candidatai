import { describe, expect, it } from 'vitest'
import { MAX_OFFERS, maxOffersOptions } from '@/lib/maxOffers'

describe('maxOffersOptions', () => {
  it('da los de siempre, con los atípicos en su sitio y sin vacíos', () => {
    expect(maxOffersOptions()).toEqual([...MAX_OFFERS])
    expect(maxOffersOptions(12, null, 0, undefined, 10)).toEqual([5, 10, 12, 15, 20, 25, 30, 40, 50, 75, 100])
  })
})
