import { act, fireEvent, render } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ICON_RETRY_MS, SiteIcon } from './SiteIcon'

afterEach(() => vi.useRealTimers())

describe('SiteIcon', () => {
  it('vuelve a pedir el icono una vez, al rato, mientras la app lo descarga', () => {
    vi.useFakeTimers()
    const { container } = render(<SiteIcon name="Acme" sourceId={7} host="acme.com" />)
    const first = container.querySelector('img')!
    expect(first.getAttribute('src')).toMatch(/\/sources\/7\/icon\?v=acme\.com$/)

    fireEvent.error(first)
    expect(container.querySelector('img')).toBeNull()
    expect(container.textContent).toBe('A')

    act(() => vi.advanceTimersByTime(ICON_RETRY_MS))
    const retry = container.querySelector('img')!
    expect(retry.getAttribute('src')).toMatch(/[?&]retry=1$/)

    fireEvent.error(retry)
    act(() => vi.advanceTimersByTime(ICON_RETRY_MS * 3))
    expect(container.querySelector('img')).toBeNull()
    expect(container.textContent).toBe('A')
  })

  it('sin web, la inicial', () => {
    const { container } = render(<SiteIcon name="infojobs" sourceId={1} host={null} />)
    expect(container.querySelector('img')).toBeNull()
    expect(container.textContent).toBe('I')
  })
})
