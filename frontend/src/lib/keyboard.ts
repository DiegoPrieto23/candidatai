/**
 * El foco está en un campo de texto, o dentro del panel de ayuda (que no es modal y deja la página
 * detrás): los atajos de una letra no deben actuar.
 */
export function isTyping(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null
  if (!el) return false
  if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT' || el.isContentEditable) return true
  return typeof el.closest === 'function' && el.closest('[data-help-panel]') !== null
}

/** Intro sobre un botón o un enlace ya hace lo suyo: el atajo no debe sumarse. */
export function isActivatable(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null
  return !!el && (el.tagName === 'BUTTON' || el.tagName === 'A')
}
