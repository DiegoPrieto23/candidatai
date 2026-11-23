import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { AgentTaskView } from '@/api/client'
import { mockApi, renderApp, status } from '@/test/utils'

function task(overrides: Partial<AgentTaskView> = {}): AgentTaskView {
  return {
    id: 3,
    action: 'process-jobs',
    job_id: null,
    milestone_id: null,
    subject: null,
    background: false,
    run_id: null,
    stopping: false,
    stopped_by_user: false,
    status: 'running',
    outcome: null,
    done: 2,
    total: 5,
    started_at: '2026-11-03T10:00:00Z',
    finished_at: null,
    ...overrides,
  }
}

function routes(tasks: AgentTaskView[], extra: Record<string, unknown> = {}) {
  return { 'GET /status': status(), 'GET /agent/tasks': { tasks }, ...extra }
}

describe('Avisos de lo que lanzan los botones', () => {
  it('no sale nada si no hay nada en marcha', async () => {
    const calls = mockApi(routes([]))
    renderApp('/como-funciona')
    await waitFor(() => expect(calls.some((c) => c.path === '/agent/tasks')).toBe(true))
    expect(screen.queryByText(/Leyendo/)).not.toBeInTheDocument()
  })

  it('dice qué hace y cuánto lleva, en cualquier página', async () => {
    mockApi(routes([task()]))
    renderApp('/como-funciona')
    expect(await screen.findByText('Leyendo y valorando las ofertas nuevas…')).toBeInTheDocument()
    expect(screen.getByText('2 de 5')).toBeInTheDocument()
    expect(screen.getByText(/Si te pide permiso, contesta allí/)).toBeInTheDocument()
  })

  it('al terminar la investigación lleva a la pestaña de la empresa', async () => {
    mockApi(
      routes([
        task({
          action: 'research-company',
          job_id: 42,
          subject: 'Data Engineer · Acme',
          total: 0,
          done: 1,
          status: 'finished',
          outcome: 'done',
        }),
      ]),
    )
    renderApp('/como-funciona')
    expect(await screen.findByText('Dosier listo')).toBeInTheDocument()
    expect(screen.getByText('Data Engineer · Acme')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Ver' })).toHaveAttribute('href', '/jobs/42?tab=company')
  })

  it('el CV terminado pasa el testigo al aviso «Tu CV está listo»', async () => {
    const calls = mockApi(
      routes([task({ action: 'generate-cv', job_id: 42, total: 0, done: 1, status: 'finished', outcome: 'done' })], {
        'POST /agent/tasks/3/dismiss': { tasks: [] },
      }),
    )
    renderApp('/como-funciona')
    await waitFor(() => expect(calls.some((c) => c.path === '/agent/tasks/3/dismiss')).toBe(true))
    expect(screen.queryByText('CV generado')).not.toBeInTheDocument()
  })

  it('si tu agente para antes de acabar, lo dice', async () => {
    mockApi(routes([task({ action: 'correct-cv', job_id: 42, total: 0, done: 0, status: 'finished', outcome: 'stopped' })]))
    renderApp('/como-funciona')
    expect(await screen.findByText('Tu agente ha parado')).toBeInTheDocument()
  })

  it('si no hay noticias, no sigue diciendo que trabaja como si nada', async () => {
    mockApi(routes([task({ status: 'stale' })]))
    renderApp('/como-funciona')
    expect(await screen.findByText(/Sin noticias desde hace 30 minutos/)).toBeInTheDocument()
  })

  it('en segundo plano no te manda a ninguna ventana ni, si falla, a «Agente»', async () => {
    mockApi(routes([task({ background: true, status: 'finished', outcome: 'failed' })]))
    renderApp('/como-funciona')
    const notice = (await screen.findByText('No ha salido bien')).closest('[role="status"]') as HTMLElement
    expect(within(notice).queryByRole('link')).not.toBeInTheDocument()
  })

  it('se minimiza y se vuelve a abrir, y cerrarlo avisa a la app', async () => {
    const calls = mockApi(routes([task()], { 'POST /agent/tasks/3/dismiss': { tasks: [] } }))
    renderApp('/como-funciona')
    await screen.findByText('2 de 5')

    await userEvent.click(screen.getByRole('button', { name: 'Minimizar el aviso' }))
    expect(screen.queryByText('2 de 5')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Abrir el aviso/ }))
    expect(screen.getByText('2 de 5')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Cerrar el aviso' }))
    await waitFor(() => expect(calls.some((c) => c.path === '/agent/tasks/3/dismiss')).toBe(true))
  })

  describe('Detener (fase 47.4)', () => {
    const background = (overrides: Partial<AgentTaskView> = {}) =>
      task({ action: 'generate-cv', job_id: 7, subject: 'Data Engineer · Acme', total: 0, done: 0, background: true, run_id: 11, ...overrides })

    it('en segundo plano, «Detener» pide confirmación y cancela su ejecución', async () => {
      const calls = mockApi(routes([background()], { 'POST /agent/runs/11/cancel': { status: 200, body: {} } }))
      renderApp('/como-funciona')
      const notice = (await screen.findByText('Data Engineer · Acme')).closest('[role="status"]') as HTMLElement
      await userEvent.click(within(notice).getByRole('button', { name: 'Detener' }))
      const confirm = within(notice).getByRole('group', { name: /¿Detenerla\?/ })
      expect(within(confirm).getByRole('button', { name: 'Seguir' })).toHaveFocus()
      expect(calls.some((c) => c.path.endsWith('/cancel'))).toBe(false)

      await userEvent.click(within(confirm).getByRole('button', { name: 'Seguir' }))
      expect(within(notice).queryByRole('group')).not.toBeInTheDocument()

      await userEvent.click(within(notice).getByRole('button', { name: 'Detener' }))
      await userEvent.click(within(notice).getByRole('button', { name: 'Sí, detener' }))
      await waitFor(() => expect(calls.some((c) => c.method === 'POST' && c.path === '/agent/runs/11/cancel')).toBe(true))
    })

    it('mientras para dice «Deteniendo…» y al final «Detenida»', async () => {
      mockApi(routes([background({ stopping: true })]))
      renderApp('/como-funciona')
      expect(await screen.findByText('Deteniendo…')).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Detener' })).not.toBeInTheDocument()
    })

    it('detenida por el usuario no dice que el agente haya parado solo', async () => {
      mockApi(routes([background({ status: 'finished', outcome: 'stopped', stopped_by_user: true, finished_at: '2026-11-03T10:05:00Z' })]))
      renderApp('/como-funciona')
      expect(await screen.findByText('Detenida')).toBeInTheDocument()
      expect(screen.getByText(/Lo que tu agente ya había guardado se queda/)).toBeInTheDocument()
      expect(screen.queryByText('Tu agente ha parado')).not.toBeInTheDocument()
    })

    it('en una terminal explica cómo pararla y deja marcarla como terminada', async () => {
      const calls = mockApi(routes([task({ total: 0, done: 0 })], { 'POST /agent/tasks/3/dismiss': { tasks: [] } }))
      renderApp('/como-funciona')
      expect(await screen.findByText('Para pararla, cierra la ventana de tu agente.')).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Detener' })).not.toBeInTheDocument()
      await userEvent.click(screen.getByRole('button', { name: 'Marcar como terminada' }))
      await waitFor(() => expect(calls.some((c) => c.path === '/agent/tasks/3/dismiss')).toBe(true))
    })
  })
})
