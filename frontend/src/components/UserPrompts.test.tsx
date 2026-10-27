import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { PromptView } from '@/api/client'
import { mockApi, renderApp, status } from '@/test/utils'

function prompt(changes: Partial<PromptView> = {}): PromptView {
  return {
    id: 4,
    kind: 'captcha',
    title: 'Completa el captcha',
    message: 'InfoJobs pide un captcha en la página de resultados.',
    url: 'https://www.infojobs.net/ofertas-trabajo',
    source_id: 1,
    source_name: 'InfoJobs',
    attempt_id: null,
    status: 'pending',
    created_at: '2026-10-10T10:00:00Z',
    expires_at: '2026-10-10T10:05:00Z',
    answered_at: null,
    seconds_left: 290,
    ...changes,
  }
}

function routes(prompts: PromptView[]) {
  return {
    'GET /status': status(),
    'GET /jobs': { items: [], total: 0, limit: 50, offset: 0 },
    'GET /prompts/pending': { prompts },
    'POST /prompts/4/answer': { status: 200, body: { ...prompt(), status: 'done' } },
  }
}

describe('Avisos al usuario (captcha)', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('sin avisos no aparece nada', async () => {
    const calls = mockApi(routes([]))
    renderApp('/')
    await waitFor(() => expect(calls.some((c) => c.path === '/prompts/pending')).toBe(true))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('pop-up con el aviso, la cuenta atrás y «Ya está»', async () => {
    const calls = mockApi(routes([prompt()]))
    // El reloj, quieto: con la suite cargada, entre la respuesta y la comprobación puede pasar un
    // segundo y la cuenta atrás ya diría 4:49.
    vi.useFakeTimers({ toFake: ['Date'] })
    renderApp('/')
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByRole('heading', { name: /Completa el captcha/ })).toBeInTheDocument()
    expect(within(dialog).getByText(/en InfoJobs, en tu navegador/)).toBeInTheDocument()
    expect(within(dialog).getByRole('timer')).toHaveTextContent('4:50')
    expect(within(dialog).getByRole('timer')).toHaveTextContent('el agente sigue con lo siguiente')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Ya está' }))
    await waitFor(() => {
      const call = calls.find((c) => c.method === 'POST' && c.path === '/prompts/4/answer')
      expect(call?.body).toEqual({ outcome: 'done' })
    })
  })

  it('al cerrarlo queda un botón para volver a abrirlo', async () => {
    mockApi(routes([prompt()]))
    renderApp('/')
    const dialog = await screen.findByRole('dialog')
    await userEvent.click(within(dialog).getByRole('button', { name: /close|cerrar/i }))
    await userEvent.click(await screen.findByRole('button', { name: /Completa el captcha · / }))
    expect(await screen.findByRole('dialog')).toBeInTheDocument()
  })
})
