/** El foco está en un campo de texto: los atajos de una letra no deben actuar. */
export function isTyping(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null
  return !!el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT' || el.isContentEditable)
}

/** Intro sobre un botón o un enlace ya hace lo suyo: el atajo no debe sumarse. */
export function isActivatable(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null
  return !!el && (el.tagName === 'BUTTON' || el.tagName === 'A')
}
