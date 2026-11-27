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
    steps: [],
    last_tool: null,
    agent: null,
    asks_permissions: false,
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
    expect(screen.getByText(/Si pide permiso, se contesta allí/)).toBeInTheDocument()
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
    expect(await screen.findByText('El agente ha parado')).toBeInTheDocument()
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
      expect(screen.getByText(/Lo que el agente ya había guardado se queda/)).toBeInTheDocument()
      expect(screen.queryByText('El agente ha parado')).not.toBeInTheDocument()
    })

    it('en una terminal explica cómo pararla y deja marcarla como terminada', async () => {
      const calls = mockApi(routes([task({ total: 0, done: 0 })], { 'POST /agent/tasks/3/dismiss': { tasks: [] } }))
      renderApp('/como-funciona')
      expect(await screen.findByText('Para pararla, se cierra la ventana del agente.')).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Detener' })).not.toBeInTheDocument()
      await userEvent.click(screen.getByRole('button', { name: 'Marcar como terminada' }))
      await waitFor(() => expect(calls.some((c) => c.path === '/agent/tasks/3/dismiss')).toBe(true))
    })
  })

  describe('Sin ventana: el avance y la conversación en el portal (fase 48.1a)', () => {
    const steps = (current: number): AgentTaskView['steps'] =>
      ['job', 'profile', 'write', 'pdf', 'verify', 'done'].map((id, index) => ({
        id,
        state: index < current ? 'done' : index === current ? 'current' : 'pending',
      }))
    const cv = (overrides: Partial<AgentTaskView> = {}) =>
      task({
        action: 'generate-cv',
        job_id: 7,
        subject: 'Data Engineer · Acme',
        total: 0,
        done: 0,
        background: true,
        run_id: 11,
        agent: 'claude',
        steps: steps(2),
        last_tool: 'get_profile',
        ...overrides,
      })
    let seq = 0
    const event = (kind: string, more: Record<string, unknown> = {}) => ({
      seq: ++seq,
      at: '2026-11-03T10:00:00Z',
      kind,
      tool: null,
      text: null,
      ok: null,
      sub: false,
      ...more,
    })
    const conversation = (status = 'running') => {
      seq = 0
      return {
        run_id: 11,
        status,
        last_seq: 6,
        events: [
          event('system', { text: 'started' }),
          event('tool_start', { tool: 'get_profile' }),
          event('tool_result', { tool: 'get_profile', ok: true }),
          event('text', { text: 'El perfil cubre dbt.\n<b>no es HTML</b>' }),
          event('tool_start', { tool: 'Agent', text: 'writer' }),
          event('tool_start', { tool: 'save_cv_content', sub: true }),
        ],
      }
    }

    it('dice el paso en curso con la barra de pasos y el tiempo', async () => {
      mockApi(routes([cv()]))
      renderApp('/como-funciona')
      const notice = (await screen.findByText('Data Engineer · Acme')).closest('[role="status"]') as HTMLElement
      expect(within(notice).getByText('3/6 · Redactar')).toBeInTheDocument()
      expect(within(notice).getByText(/^(\d+:)?\d\d:\d\d$/)).toBeInTheDocument()
      expect(within(notice).queryByText(/ventana del agente/)).not.toBeInTheDocument()
    })

    it('sin pasos, dice la última herramienta que ha usado', async () => {
      mockApi(routes([cv({ action: 'assess-fit-job', steps: [], last_tool: 'save_fit_assessment' })]))
      renderApp('/como-funciona')
      expect(await screen.findByText('Guardando la valoración')).toBeInTheDocument()
    })

    it('«Ver conversación» abre el panel con lo que hace y escribe el agente, como texto plano', async () => {
      const calls = mockApi(routes([cv()], { 'GET /agent/runs/11/events': conversation(), 'GET /agent/agents': { agents: [] } }))
      renderApp('/como-funciona')
      await userEvent.click(await screen.findByRole('button', { name: 'Ver conversación' }))
      const panel = await screen.findByRole('complementary', { name: 'Generando el CV…' })
      expect(within(panel).getByText('Leyendo el perfil')).toBeInTheDocument()
      expect(within(panel).getByText('Subagente writer')).toBeInTheDocument()
      expect(within(panel).getByText('(subagente)')).toBeInTheDocument()
      // El texto del agente sale tal cual: ni HTML ni saltos de línea perdidos.
      const said = within(panel).getByText(/El perfil cubre dbt\./)
      expect(said.textContent).toBe('El perfil cubre dbt.\n<b>no es HTML</b>')
      expect(said.querySelector('b')).toBeNull()
      expect(within(panel).getByRole('list', { name: 'Pasos' })).toBeInTheDocument()
      expect(calls.find((c) => c.path === '/agent/runs/11/events')?.search.get('after')).toBe('0')

      await userEvent.keyboard('{Escape}')
      expect(screen.queryByRole('complementary', { name: 'Generando el CV…' })).not.toBeInTheDocument()
    })

    it('al terminar, el resultado con el enlace y la conversación se siguen viendo', async () => {
      const done = conversation('done')
      done.events.push(event('tool_result', { tool: 'save_cv_content', ok: true, sub: true }), event('result', { ok: true }))
      mockApi(
        // «Verificar CV»: «Generar» y «Corregir» pasan el relevo al aviso «Tu CV está listo».
        routes([cv({ action: 'verify-cv', status: 'finished', outcome: 'done', steps: steps(3), finished_at: '2026-11-03T10:03:00Z' })], {
          'GET /agent/runs/11/events': done,
          'GET /agent/agents': { agents: [] },
        }),
      )
      renderApp('/como-funciona')
      await userEvent.click(await screen.findByRole('button', { name: 'Ver conversación' }))
      const panel = await screen.findByRole('complementary', { name: 'CV verificado' })
      expect(within(panel).getByText('Terminado')).toBeInTheDocument()
      expect(within(panel).getByRole('link', { name: 'Ver' })).toHaveAttribute('href', '/jobs/7')
    })

    describe('Preguntas y permisos en el panel (fase 48.1b)', () => {
      const prompt = (overrides: Record<string, unknown>) => ({
        id: 5,
        kind: 'permission',
        title: 'Tu agente pide permiso',
        message: 'mkdir -p tmp/x',
        url: null,
        source_id: null,
        source_name: null,
        attempt_id: null,
        status: 'pending',
        created_at: '2026-11-03T10:00:30Z',
        expires_at: '2026-11-03T10:05:30Z',
        answered_at: null,
        seconds_left: 240,
        options: ['once', 'always', 'deny'],
        answer: null,
        job_id: 7,
        run_id: 11,
        tool: 'Bash',
        ...overrides,
      })

      it('el aviso se pone ámbar con «Responder» y el permiso se concede desde el panel', async () => {
        const permission = prompt({})
        const conv = { ...conversation(), prompts: [permission] }
        const calls = mockApi(
          routes([cv({ asks_permissions: true })], {
            'GET /prompts/pending': { prompts: [permission] },
            'GET /agent/runs/11/events': conv,
            'GET /agent/agents': { agents: [] },
            'POST /prompts/5/answer': { ...permission, status: 'done', answer: 'once' },
          }),
        )
        renderApp('/como-funciona')
        expect(await screen.findByText('El agente pide permiso para seguir.')).toBeInTheDocument()
        // El pop-up de avisos no lo repite: se contesta en el panel.
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
        await userEvent.click(screen.getByRole('button', { name: 'Responder' }))
        const card = await screen.findByRole('listitem', { name: 'Permiso' })
        expect(within(card).getByText('Quiere usar Bash:')).toBeInTheDocument()
        expect(within(card).getByText('mkdir -p tmp/x')).toBeInTheDocument()
        expect(within(card).getByText(/Se deniega solo en 4:00/)).toBeInTheDocument()
        expect(within(card).getByRole('button', { name: 'Permitir siempre en este proyecto' })).toBeInTheDocument()
        expect(screen.queryByText(/no pide permisos al portal/)).not.toBeInTheDocument()
        await userEvent.click(within(card).getByRole('button', { name: 'Permitir una vez' }))
        await waitFor(() =>
          expect(calls.find((c) => c.path === '/prompts/5/answer')?.body).toEqual({ outcome: 'done', answer: 'once' }),
        )
      })

      it('una pregunta se contesta en su tarjeta, con opciones o escrita', async () => {
        const question = prompt({ kind: 'question', title: 'Tu agente te pregunta', message: '¿Con foto?', options: ['Sí', 'No'], tool: null })
        const calls = mockApi(
          routes([cv()], {
            'GET /prompts/pending': { prompts: [question] },
            'GET /agent/runs/11/events': { ...conversation(), prompts: [question] },
            'GET /agent/agents': { agents: [] },
            'POST /prompts/5/answer': { ...question, status: 'done', answer: 'Sí' },
          }),
        )
        renderApp('/como-funciona')
        expect(await screen.findByText('El agente espera una respuesta.')).toBeInTheDocument()
        await userEvent.click(screen.getByRole('button', { name: 'Responder' }))
        const card = await screen.findByRole('listitem', { name: 'Pregunta del agente' })
        expect(within(card).getByText('¿Con foto?')).toBeInTheDocument()
        await userEvent.click(within(card).getByRole('button', { name: 'Sí' }))
        await waitFor(() =>
          expect(calls.find((c) => c.path === '/prompts/5/answer')?.body).toEqual({ outcome: 'done', answer: 'Sí' }),
        )
        // Sin permisos al portal (Codex, OpenCode), el panel lo explica.
        expect(screen.getByText(/no pide permisos al portal/)).toBeInTheDocument()
      })

      it('sin «siempre» donde la app no lo ofrece', async () => {
        const once = prompt({ options: ['once', 'deny'] })
        mockApi(
          routes([cv({ asks_permissions: true })], {
            'GET /prompts/pending': { prompts: [once] },
            'GET /agent/runs/11/events': { ...conversation(), prompts: [once] },
            'GET /agent/agents': { agents: [] },
          }),
        )
        renderApp('/como-funciona')
        await userEvent.click(await screen.findByRole('button', { name: 'Responder' }))
        const card = await screen.findByRole('listitem', { name: 'Permiso' })
        expect(within(card).getByRole('button', { name: 'Permitir una vez' })).toBeInTheDocument()
        expect(within(card).queryByRole('button', { name: /siempre/ })).not.toBeInTheDocument()
      })

      it('lo ya contestado se queda en la conversación', async () => {
        const answered = prompt({ status: 'done', answer: 'always', seconds_left: 0, answered_at: '2026-11-03T10:01:00Z' })
        mockApi(
          routes([cv({ asks_permissions: true })], {
            'GET /agent/runs/11/events': { ...conversation(), prompts: [answered] },
            'GET /agent/agents': { agents: [] },
          }),
        )
        renderApp('/como-funciona')
        await userEvent.click(await screen.findByRole('button', { name: 'Ver conversación' }))
        const card = await screen.findByRole('listitem', { name: 'Permiso' })
        expect(within(card).getByText(/Permitido siempre en este proyecto/)).toBeInTheDocument()
        expect(within(card).queryByRole('button')).not.toBeInTheDocument()
      })
    })

    it('si falla, deja abrirla en una ventana', async () => {
      const calls = mockApi(
        routes([cv({ status: 'finished', outcome: 'failed', finished_at: '2026-11-03T10:03:00Z' })], {
          'POST /agent/runs/11/open': { status: 202, body: { ok: true, agent: 'claude', message: '' } },
        }),
      )
      renderApp('/como-funciona')
      await userEvent.click(await screen.findByRole('button', { name: 'Abrir en una ventana' }))
      await waitFor(() => expect(calls.some((c) => c.method === 'POST' && c.path === '/agent/runs/11/open')).toBe(true))
    })
  })
})
