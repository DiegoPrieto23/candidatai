import '@testing-library/jest-dom/vitest'
import { cleanup, configure } from '@testing-library/react'
import { afterEach, beforeEach, vi } from 'vitest'
import { i18n } from '@/lib/i18n'

// `findBy…` espera 1 s por defecto: poco con toda la suite en paralelo.
configure({ asyncUtilTimeout: 4000 })

// Los tests arrancan en español (fase 23.6): los que prueban el inglés lo cambian ellos.
beforeEach(async () => {
  if (i18n.language !== 'es') await i18n.changeLanguage('es')
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  document.documentElement.classList.remove('dark')
  try {
    localStorage.clear()
    sessionStorage.clear()
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
