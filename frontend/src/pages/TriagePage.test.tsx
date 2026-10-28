import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { TriageItem } from '@/api/client'
import { jobView, matchView, mockApi, renderApp, status, triageItem, triageQueue, type Call } from '@/test/utils'

/** API simulada con estado: aprobar o descartar saca la oferta de la cola; reabrir la devuelve. */
function mockTriage(initial: TriageItem[], extra: Record<string, unknown> = {}) {
  let queue = [...initial]
  const removed = new Map<number, TriageItem>()
  const routes: Record<string, unknown> = {
    'GET /status': () => status(0, queue.length),
    'GET /triage': () => triageQueue(queue),
    ...extra,
  }
  for (const item of initial) {
    routes[`POST /jobs/${item.job.id}/events`] = async (request: Request) => {
      const body = (await request.clone().json()) as { type: string }
      if (body.type === 'reopened') {
        const back = removed.get(item.job.id)
        if (back) queue = [...queue, back].sort((a, b) => (b.match?.score ?? 0) - (a.match?.score ?? 0))
        return { ok: true, event_id: 99, stage: 'pending_triage' }
      }
      removed.set(item.job.id, item)
      queue = queue.filter((i) => i.job.id !== item.job.id)
      return { ok: true, event_id: 99, stage: body.type === 'approved' ? 'approved' : 'closed' }
    }
  }
  return mockApi(routes)
}

function eventCalls(calls: Call[]) {
  return calls.filter((c) => c.method === 'POST').map((c) => ({ path: c.path, body: c.body }))
}

function selected() {
  return screen.getByRole('option', { selected: true })
}

describe('Por revisar', () => {
  it('ordena por score, atenúa las que no llegan al umbral y enseña el desglose', async () => {
    mockTriage([triageItem(1, 82), triageItem(2, 40)])
    renderApp('/por-revisar')

    const detail = await screen.findByRole('article', { name: 'Oferta seleccionada' })
    expect(within(detail).getByRole('heading', { name: 'Oferta 1' })).toBeInTheDocument()
    expect(within(detail).getByLabelText('Score 82 de 100')).toBeInTheDocument()
    expect(within(detail).getByText('Python')).toBeInTheDocument()
    expect(within(detail).getByText('Kafka')).toBeInTheDocument()
    expect(within(detail).getByText(/Sin valorar/)).toBeInTheDocument()
    const options = screen.getAllByRole('option')
    expect(options.map((o) => within(o).getByText(/^Oferta/).textContent)).toEqual(['Oferta 1', 'Oferta 2'])
    expect(within(options[1]).getByLabelText('Score 40 de 100, por debajo del umbral')).toBeInTheDocument()
    expect(screen.getByText('2 ofertas por revisar, de más a menos encaje')).toBeInTheDocument()
  })

  it('dice por qué una oferta bajo el umbral se queda sin valorar en segundo plano (fase 25.4)', async () => {
    mockTriage([triageItem(1, 82), triageItem(2, 40)])
    renderApp('/por-revisar')
    const detail = await screen.findByRole('article', { name: 'Oferta seleccionada' })
    expect(within(detail).queryByText(/Sin valorar en segundo plano/)).not.toBeInTheDocument()
    await userEvent.keyboard('j')
    await waitFor(() => expect(within(screen.getByRole('article', { name: 'Oferta seleccionada' })).getByRole('heading', { name: 'Oferta 2' })).toBeInTheDocument())
    const note = within(screen.getByRole('article', { name: 'Oferta seleccionada' })).getByRole('note')
    expect(note).toHaveTextContent('Sin valorar en segundo plano: su score (40) está por debajo del umbral (45).')
  })

  it('se mueve con J/K y flechas, y abre la ficha con O', async () => {
    mockTriage([triageItem(1, 90), triageItem(2, 80), triageItem(3, 70)], {
      'GET /jobs/2': jobView({ id: 2, title: 'Oferta 2' }),
    })
    renderApp('/por-revisar')
    await screen.findByRole('article')

    await userEvent.keyboard('j')
    expect(within(selected()).getByText('Oferta 2')).toBeInTheDocument()
    await userEvent.keyboard('{ArrowDown}{ArrowDown}') // no pasa del final
    expect(within(selected()).getByText('Oferta 3')).toBeInTheDocument()
    await userEvent.keyboard('kk{ArrowUp}')
    expect(within(selected()).getByText('Oferta 1')).toBeInTheDocument()
    await userEvent.keyboard('j')
    await userEvent.keyboard('o')
    expect(await screen.findByRole('heading', { level: 1, name: 'Oferta 2' })).toBeInTheDocument()
  })

  it('aprueba con A y pasa a la siguiente', async () => {
    const calls = mockTriage([triageItem(1, 90), triageItem(2, 80)])
    renderApp('/por-revisar')
    await screen.findByRole('article')

    await userEvent.keyboard('a')
    expect(within(selected()).getByText('Oferta 2')).toBeInTheDocument()
    expect(await screen.findByRole('status')).toHaveTextContent('Aprobada Oferta 1')
    expect(eventCalls(calls)).toEqual([{ path: '/jobs/1/events', body: { type: 'approved' } }])
  })

  it('descarta con D, motivo con número y confirma con Intro', async () => {
    const calls = mockTriage([triageItem(1, 90), triageItem(2, 80)])
    renderApp('/por-revisar')
    await screen.findByRole('article')

    await userEvent.keyboard('d')
    const dialog = await screen.findByRole('dialog', { name: 'Descartar oferta' })
    const confirm = within(dialog).getByRole('button', { name: 'Descartar' })
    expect(confirm).toBeDisabled() // motivo obligatorio
    await userEvent.keyboard('{Enter}')
    expect(eventCalls(calls)).toEqual([])

    await userEvent.keyboard('2')
    expect(within(dialog).getByRole('radio', { name: /Seniority o años/ })).toHaveAttribute('aria-checked', 'true')
    await userEvent.keyboard('{Enter}')

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(within(selected()).getByText('Oferta 2')).toBeInTheDocument()
    expect(eventCalls(calls)).toEqual([
      { path: '/jobs/1/events', body: { type: 'discarded', reason: 'seniority' } },
    ])
    expect(await screen.findByRole('status')).toHaveTextContent('Descartada Oferta 1 · Seniority o años')
  })

  it('«Otro motivo» exige nota; las teclas dentro de la nota no disparan atajos', async () => {
    const calls = mockTriage([triageItem(1, 90)])
    renderApp('/por-revisar')
    await screen.findByRole('article')

    await userEvent.keyboard('d')
    const dialog = await screen.findByRole('dialog')
    await userEvent.keyboard('7')
    const confirm = within(dialog).getByRole('button', { name: 'Descartar' })
    expect(confirm).toBeDisabled()
    await userEvent.type(within(dialog).getByLabelText(/Nota/), 'Pide 1 y 3')
    expect(within(dialog).getByRole('radio', { name: /Otro motivo/ })).toHaveAttribute('aria-checked', 'true')
    await userEvent.click(confirm)
    await waitFor(() =>
      expect(eventCalls(calls)).toEqual([
        { path: '/jobs/1/events', body: { type: 'discarded', reason: 'other', note: 'Pide 1 y 3' } },
      ]),
    )
    expect(await screen.findByText('Nada por revisar')).toBeInTheDocument()
  })

  it('Esc cierra el diálogo sin descartar', async () => {
    const calls = mockTriage([triageItem(1, 90)])
    renderApp('/por-revisar')
    await screen.findByRole('article')
    await userEvent.keyboard('d')
    await screen.findByRole('dialog')
    await userEvent.keyboard('1{Escape}')
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(eventCalls(calls)).toEqual([])
    expect(within(selected()).getByText('Oferta 1')).toBeInTheDocument()
  })

  it('tría 10 ofertas solo con el teclado', async () => {
    const items = Array.from({ length: 10 }, (_, i) => triageItem(i + 1, 95 - i * 5))
    const calls = mockTriage(items)
    renderApp('/por-revisar')
    await screen.findByRole('article')

    for (let i = 0; i < 10; i++) {
      if (i % 3 === 2) {
        await userEvent.keyboard('d')
        await screen.findByRole('dialog')
        await userEvent.keyboard('1{Enter}')
        await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
      } else {
        await userEvent.keyboard('a')
      }
    }

    expect(await screen.findByText('Nada por revisar')).toBeInTheDocument()
    const posts = eventCalls(calls)
    expect(posts).toHaveLength(10)
    expect(posts.map((p) => p.path)).toEqual(items.map((i) => `/jobs/${i.job.id}/events`))
    expect(posts.filter((p) => (p.body as { type: string }).type === 'discarded')).toHaveLength(3)
  })

  it('deshace un descarte reabriendo la oferta', async () => {
    const calls = mockTriage([triageItem(1, 90), triageItem(2, 80)])
    renderApp('/por-revisar')
    await screen.findByRole('article')
    await userEvent.keyboard('d')
    await screen.findByRole('dialog')
    await userEvent.keyboard('3{Enter}')
    await userEvent.click(await screen.findByRole('button', { name: 'Deshacer' }))

    await waitFor(() => expect(within(selected()).getByText('Oferta 1')).toBeInTheDocument())
    expect(eventCalls(calls).at(-1)).toEqual({ path: '/jobs/1/events', body: { type: 'reopened' } })
    expect(screen.getAllByRole('option')).toHaveLength(2)
  })

  it('si la API falla, la oferta vuelve y se explica', async () => {
    mockApi({
      'GET /status': status(0, 1),
      'GET /triage': triageQueue([triageItem(1, 90)]),
      'POST /jobs/1/events': {
        status: 409,
        body: { ok: false, error: { type: 'invalid_transition', message: 'Ya no está en triaje.', details: [] } },
      },
    })
    renderApp('/por-revisar')
    await screen.findByRole('article')
    await userEvent.keyboard('a')
    expect(await screen.findByRole('alert')).toHaveTextContent('No se pudo guardar: Ya no está en triaje.')
    expect(within(selected()).getByText('Oferta 1')).toBeInTheDocument()
  })

  it('muestra la valoración del agente, sus preguntas y los filtros que no pasa', async () => {
    const item = triageItem(1, 60, {
      match: matchView({
        score: 60,
        hard_filters: { passed: false, failures: [{ filter: 'years', reason: 'Pide 6 años de experiencia.' }] },
        assessment: {
          verdict: 'possible',
          rationale: 'Cubre Python con nivel F.',
          risks: ['dbt solo básico'],
          questions_for_user: ['¿Has usado Kafka?'],
        },
        assessment_stale: true,
        assessment_score: 64,
      }),
    })
    mockTriage([item])
    renderApp('/por-revisar')
    const detail = await screen.findByRole('article')
    expect(within(detail).getByRole('note', { name: 'No pasa los filtros' })).toHaveTextContent('Pide 6 años de experiencia.')
    expect(within(detail).getByText('Encaje posible')).toBeInTheDocument()
    expect(within(detail).getByText('Valorada con un score de 64; ahora es 60 porque el perfil o la oferta cambiaron.')).toBeInTheDocument()
    expect(within(detail).getByText('¿Has usado Kafka?')).toBeInTheDocument()
    expect(within(detail).getByText('dbt solo básico')).toBeInTheDocument()
  })

  it('el descarte por sueldo dice cuánto queda por debajo de tu mínimo (solo la UI lo sabe)', async () => {
    const reason = 'El sueldo publicado está por debajo de tu mínimo salarial.'
    const item = triageItem(1, 60, {
      match: matchView({ score: 60, hard_filters: { passed: false, failures: [{ filter: 'salary', reason }] } }),
    })
    mockTriage([item], { 'GET /jobs/1/salary-gap': { gap_eur: 8000 } })
    renderApp('/por-revisar')
    const note = within(await screen.findByRole('article')).getByRole('note', { name: 'No pasa los filtros' })
    expect(note).toHaveTextContent(reason)
    await waitFor(() => expect(note).toHaveTextContent(/8\.?000\s€ por debajo de tu mínimo/))
  })

  it('avisa si no hay perfil y enseña la cola vacía', async () => {
    mockApi({ 'GET /status': status(), 'GET /triage': triageQueue([], { profile_missing: true }) })
    renderApp('/por-revisar')
    expect(await screen.findByText('Sin perfil no hay score.')).toBeInTheDocument()
    expect(screen.getByText('Nada por revisar')).toBeInTheDocument()
  })

  it('el enlace de la cabecera lleva a «Por revisar» con su recuento', async () => {
    mockTriage([triageItem(1, 90)], { 'GET /jobs': { items: [], total: 0, limit: 50, offset: 0 } })
    renderApp('/')
    const nav = (await screen.findAllByRole('navigation'))[0]
    const link = await within(nav).findByRole('link', { name: /Por revisar/ })
    await waitFor(() => expect(link).toHaveTextContent('1'))
    await userEvent.click(link)
    expect(await screen.findByRole('heading', { level: 1, name: 'Por revisar' })).toBeInTheDocument()
  })
})

describe('Comparación por significado', () => {
  const notInstalled = 'Similitud semántica no disponible: instala el extra con `uv sync --extra matching` (en backend/).'
  const extraStatus = { installed: false, wanted: false, disabled: false, in_docker: false, installing: false, error: null }

  it('explica qué aporta y la instala en segundo plano desde la UI', async () => {
    const item = triageItem(1, 60, {
      match: matchView({ score: 60, breakdown: { ...matchView().breakdown, notes: [notInstalled] } }),
    })
    const calls = mockTriage([item], {
      'GET /matching/semantic': extraStatus,
      'POST /matching/semantic/install': { ...extraStatus, wanted: true, installing: true },
    })
    renderApp('/por-revisar')
    const detail = await screen.findByRole('article')
    await userEvent.click(await within(detail).findByRole('button', { name: 'Qué aporta y cómo activarla' }))
    const dialog = await screen.findByRole('dialog', { name: 'Comparación por significado' })
    expect(within(dialog).getByText(/vale el 30 % del score/)).toBeInTheDocument()
    expect(within(dialog).getByText(/Es permanente/)).toBeInTheDocument()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Instalar' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(calls.some((c: Call) => c.method === 'POST' && c.path === '/matching/semantic/install')).toBe(true)
    expect(await within(detail).findByRole('status')).toHaveTextContent(/Instalando la comparación por significado/)
  })

  it('en Docker no ofrece instalarla', async () => {
    const item = triageItem(1, 60, {
      match: matchView({ score: 60, breakdown: { ...matchView().breakdown, notes: [notInstalled] } }),
    })
    mockTriage([item], { 'GET /matching/semantic': { ...extraStatus, in_docker: true } })
    renderApp('/por-revisar')
    const detail = await screen.findByRole('article')
    await userEvent.click(await within(detail).findByRole('button', { name: 'Qué aporta y cómo activarla' }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText(/En Docker no está disponible/)).toBeInTheDocument()
    expect(within(dialog).queryByRole('button', { name: 'Instalar' })).not.toBeInTheDocument()
  })
})
