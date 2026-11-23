import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { mockApi, renderApp, status } from '@/test/utils'

/** `Notification` falso: guarda lo que se avisa y deja elegir la respuesta al permiso. */
function fakeNotification(answer: NotificationPermission, initial: NotificationPermission = 'default') {
  const shown: { title: string; body?: string }[] = []
  class FakeNotification {
    static permission: NotificationPermission = initial
    static requestPermission = vi.fn(async () => {
      FakeNotification.permission = answer
      return answer
    })
    onclick: (() => void) | null = null
    constructor(title: string, options?: NotificationOptions) {
      shown.push({ title, body: options?.body })
    }
    close() {}
  }
  vi.stubGlobal('Notification', FakeNotification)
  return { shown, FakeNotification }
}

const routes = (items: unknown[] = []) => ({
  'GET /status': status(),
  'GET /calendar': { start: '2026-10-01', end: '2026-10-31', items: [] },
  'GET /upcoming': { days: 2, items },
  'GET /followups': { days_without_reply: 10, max_followups: 2, followups: [], thank_you_days: 2, thanks_due: [] },
})

describe('Avisos del navegador', () => {
  it('pide el permiso solo al activarlos y avisa de lo que toca', async () => {
    const { shown, FakeNotification } = fakeNotification('granted')
    const soon = new Date(Date.now() + 30 * 60_000).toISOString()
    mockApi(
      routes([
        {
          kind: 'interview',
          job_id: 3,
          job_title: 'Data Engineer',
          company: 'Brétema Analytics',
          stage: 'in_process',
          milestone_id: 7,
          title: 'Entrevista',
          starts_at: soon,
          ends_at: null,
          all_day: false,
          location: null,
        },
      ]),
    )
    renderApp('/calendario')
    const toggle = await screen.findByRole('switch', { name: 'Avisos del navegador' })
    expect(FakeNotification.requestPermission).not.toHaveBeenCalled()
    await userEvent.click(toggle)
    expect(FakeNotification.requestPermission).toHaveBeenCalledOnce()
    await waitFor(() => expect(toggle).toHaveAttribute('aria-checked', 'true'))
    await waitFor(() => expect(shown).toEqual([{ title: 'Entrevista · Brétema Analytics', body: expect.stringContaining('Data Engineer') }]))
  })

  it('si el navegador los bloquea, lo dice y el interruptor queda apagado', async () => {
    fakeNotification('denied', 'denied')
    mockApi(routes())
    renderApp('/calendario')
    expect(await screen.findByRole('switch', { name: 'Avisos del navegador' })).toBeDisabled()
    expect(screen.getByText(/permitir los avisos de esta página/)).toBeInTheDocument()
  })
})
