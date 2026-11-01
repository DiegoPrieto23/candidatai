/**
 * Da el foco a lo que se busca al llegar desde un enlace o un aviso (un bloque del perfil, el
 * primer botón de un bloque) y lo marca con `data-arrived` hasta que lo pierde. Tras un clic el
 * navegador no activa `:focus-visible`, así que sin la marca el foco no se vería; el anillo lo pinta
 * `index.css`, en claro y en oscuro.
 */
export function focusArrival(el: HTMLElement | null | undefined) {
  if (!el) return
  el.focus({ preventScroll: true })
  // Si no acepta el foco (un botón desactivado), sin marca: no habría `blur` que la quitara.
  if (document.activeElement !== el || el.hasAttribute('data-arrived')) return
  el.setAttribute('data-arrived', '')
  el.addEventListener('blur', () => el.removeAttribute('data-arrived'), { once: true })
}
