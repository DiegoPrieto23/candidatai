import '@testing-library/jest-dom/vitest'
import { cleanup, configure } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

// `findBy…` espera 1 s por defecto: poco con toda la suite en paralelo.
configure({ asyncUtilTimeout: 4000 })

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  document.documentElement.classList.remove('dark')
  try {
    localStorage.clear()
  } catch {
    // jsdom sin almacenamiento
  }
})

// jsdom no implementa estas API que usan Radix y el tema.
if (!window.matchMedia) {
  window.matchMedia = (query: string) =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    }) as MediaQueryList
}
globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
}
Element.prototype.scrollIntoView ??= () => {}
Element.prototype.hasPointerCapture ??= () => false
Element.prototype.releasePointerCapture ??= () => {}
