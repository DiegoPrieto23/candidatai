/**
 * Hablar con la extensión «Enviar a CandidatAI» desde la UI. Su manifiesto deja que las páginas de
 * `127.0.0.1` y `localhost` le escriban (`externally_connectable`): así la UI sabe si está
 * instalada y conectada, y le pasa el token al pulsar «Conectar» sin que nadie lo copie.
 */

/** Lo que responde la extensión (`service_worker.js`, `answerApp`). */
export interface ExtensionReply {
  version: string
  connected: boolean
  kind: string // `connected`, `no_token`, `unauthorized`, `offline`…
  message: string
}

interface ChromeRuntime {
  sendMessage: (extensionId: string, message: unknown, callback: (reply: unknown) => void) => void
  lastError?: { message?: string }
}

function runtime(): ChromeRuntime | null {
  const chrome = (globalThis as { chrome?: { runtime?: Partial<ChromeRuntime> } }).chrome
  return typeof chrome?.runtime?.sendMessage === 'function' ? (chrome.runtime as ChromeRuntime) : null
}

/** Chrome, Edge, Brave… La extensión no funciona en Firefox ni en Safari. */
export function isChromium(): boolean {
  const agent = typeof navigator === 'undefined' ? '' : navigator.userAgent
  return /(Chrome|Chromium|Edg)\//.test(agent) // también «HeadlessChrome/»
}

export function isEdge(): boolean {
  return typeof navigator !== 'undefined' && /\bEdg\//.test(navigator.userAgent)
}

function isReply(value: unknown): value is ExtensionReply {
  return (
    typeof value === 'object' &&
    value !== null &&
    typeof (value as ExtensionReply).version === 'string' &&
    typeof (value as ExtensionReply).connected === 'boolean'
  )
}

/**
 * Un mensaje a la extensión. `null` si no responde: no está instalada, es de antes de que supiera
 * hablar con la app o el navegador no es Chromium.
 */
export function askExtension(
  extensionId: string,
  message: { type: 'ping' } | { type: 'pair'; token: string },
  timeoutMs = 8000,
): Promise<ExtensionReply | null> {
  const chrome = runtime()
  if (!chrome) return Promise.resolve(null)
  return new Promise((resolve) => {
    const timer = setTimeout(() => resolve(null), timeoutMs)
    try {
      chrome.sendMessage(extensionId, message, (reply) => {
        clearTimeout(timer)
        // Leer `lastError` evita que Chrome lo dé por no atendido (y lo saque en la consola).
        resolve(chrome.lastError || !isReply(reply) ? null : reply)
      })
    } catch {
      clearTimeout(timer)
      resolve(null)
    }
  })
}

/** `-1`, `0` o `1`, como `a` sea anterior, igual o posterior a `b` («0.10.0» > «0.9.1»). */
export function compareVersions(a: string, b: string): number {
  const pa = a.split('.').map((n) => Number.parseInt(n, 10) || 0)
  const pb = b.split('.').map((n) => Number.parseInt(n, 10) || 0)
  for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
    const d = (pa[i] ?? 0) - (pb[i] ?? 0)
    if (d !== 0) return Math.sign(d)
  }
  return 0
}
