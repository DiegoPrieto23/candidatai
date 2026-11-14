import { useState } from 'react'

/** Los navegadores que se pueden elegir. Los tres primeros admiten la extensión; los otros dos, no. */
export const BROWSERS = ['chrome', 'edge', 'brave', 'firefox', 'safari'] as const
export type BrowserId = (typeof BROWSERS)[number]

const STORAGE_KEY = 'cai.browser'

export function supportsExtension(browser: BrowserId): boolean {
  return browser === 'chrome' || browser === 'edge' || browser === 'brave'
}

/** El navegador en el que está abierta la app. Opera, Vivaldi y demás Chromium cuentan como Chrome. */
export function detectBrowser(): BrowserId {
  if (typeof navigator === 'undefined') return 'chrome'
  const agent = navigator.userAgent
  if ('brave' in navigator) return 'brave'
  if (/\bEdg\//.test(agent)) return 'edge'
  if (/(Chrome|Chromium)\//.test(agent)) return 'chrome'
  if (/Firefox\//.test(agent)) return 'firefox'
  if (/Safari\//.test(agent)) return 'safari'
  return 'chrome'
}

function stored(): BrowserId | null {
  try {
    const value = localStorage.getItem(STORAGE_KEY)
    return BROWSERS.includes(value as BrowserId) ? (value as BrowserId) : null
  } catch {
    return null
  }
}

/**
 * Tu navegador habitual: el que elegiste o, si nunca has elegido, el que se detecta. Se recuerda en
 * este navegador; es solo una comodidad, así que sin almacenamiento vuelve a detectarse.
 */
export function useBrowserChoice(): { browser: BrowserId; detected: BrowserId; choose: (browser: BrowserId) => void } {
  const detected = detectBrowser()
  const [browser, setBrowser] = useState<BrowserId>(() => stored() ?? detected)
  const choose = (next: BrowserId) => {
    setBrowser(next)
    try {
      localStorage.setItem(STORAGE_KEY, next)
    } catch {
      // Sin almacenamiento: vale para esta visita.
    }
  }
  return { browser, detected, choose }
}
