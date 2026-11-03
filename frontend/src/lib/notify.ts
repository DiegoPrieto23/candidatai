/** Notificación del sistema si la pestaña no está a la vista (y el permiso ya está dado). */
export function notifyIfHidden(title: string, body: string) {
  if (typeof window === 'undefined' || !('Notification' in window)) return
  if (Notification.permission !== 'granted' || document.visibilityState === 'visible') return
  try {
    const n = new Notification(title, { body })
    n.onclick = () => {
      window.focus()
      n.close()
    }
  } catch {
    // Algunos navegadores no dejan crearlas fuera de un service worker: queda el aviso de la página.
  }
}
