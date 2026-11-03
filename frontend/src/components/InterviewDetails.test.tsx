import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { type MilestoneOut } from '@/api/client'
import { canCorrectGuide, interviewPhase, planIsStale } from '@/lib/interviews'
import { jobView, milestone, mockApi, processView, renderApp, status } from '@/test/utils'

const launcher = { available: true, agent: 'claude', reason: null, actions: [] }
const launched = { ok: true, agent: 'claude', prompt: 'Usa el skill…', message: 'ok' }
const future = new Date(Date.now() + 2 * 86_400_000).toISOString()

function ficha(milestones: MilestoneOut[], changes: Parameters<typeof processView>[0] = {}) {
  return mockApi({
    'GET /status': status(),
    'GET /jobs/1': jobView({ stage: 'in_process' }),
    'GET /jobs/1/process': processView({ stage: 'in_process', milestones, ...changes }),
    'GET /agent': launcher,
    'POST /agent/launch': launched,
  })
}

describe('Entrevistas en la ficha (fase 17)', () => {
  it('una entrevista por venir tiene «Preparar» y «Simulacro», que lanzan con el hito', async () => {
    const calls = ficha([milestone(5, { starts_at: future })])
    renderApp('/jobs/1')
    const section = await screen.findByRole('region', { name: 'Proceso' })
    await userEvent.click(await within(section).findByRole('button', { name: 'Simulacro' }))
    await waitFor(() => expect(calls.some((c) => c.path === '/agent/launch')).toBe(true))
    expect(calls.find((c) => c.path === '/agent/launch')?.body).toEqual({
      action: 'mock-interview',
      milestone_id: 5,
    })
    expect(within(section).getByRole('button', { name: 'Preparar' })).toBeInTheDocument()
    expect(within(section).queryByRole('button', { name: 'Repasar' })).not.toBeInTheDocument()
  })

  const guide = {
    file: '1-5-bretema-guia.pdf',
    language: 'es',
    title: 'Data Engineer',
    saved_at: '2026-10-20T10:00:00Z',
    agent_name: 'codex',
    restored: false,
  } as const
  const past = new Date(Date.now() - 4 * 86_400_000).toISOString()

  it('tras la entrevista se pueden pedir cambios a la guía: el texto va aparte, no en la orden', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView({ stage: 'in_process' }),
      'GET /jobs/1/process': processView({
        stage: 'in_process',
        milestones: [milestone(5, { starts_at: past, guide })],
      }),
      'GET /agent': launcher,
      'POST /agent/launch': launched,
      'POST /milestones/5/guide/correction': milestone(5, { starts_at: past, guide: { ...guide, correction: 'Sin código.' } }),
    })
    renderApp('/jobs/1')
    const section = await screen.findByRole('region', { name: 'Proceso' })
    await userEvent.click(await within(section).findByRole('button', { name: 'Pedir cambios a la guía' }))
    const apply = within(section).getByRole('button', { name: 'Aplicar cambios' })
    expect(apply).toBeDisabled()
    await userEvent.type(within(section).getByLabelText('Qué quieres cambiar'), 'Sin código.')
    await userEvent.click(apply)
    await waitFor(() => expect(calls.some((c) => c.path === '/agent/launch')).toBe(true))
    expect(calls.find((c) => c.path === '/milestones/5/guide/correction')?.body).toEqual({ instruction: 'Sin código.' })
    expect(calls.find((c) => c.path === '/agent/launch')?.body).toEqual({
      action: 'correct-interview-guide',
      milestone_id: 5,
    })
  })

  it('los cambios pendientes se ven al abrir la ficha y se pueden cancelar', async () => {
    const pending = milestone(5, { starts_at: future, guide: { ...guide, correction: 'Sin código.' } })
    const calls = mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView({ stage: 'in_process' }),
      'GET /jobs/1/process': processView({ stage: 'in_process', milestones: [pending] }),
      'GET /agent': launcher,
      'POST /milestones/5/guide/correction/cancel': milestone(5, { starts_at: future, guide }),
    })
    renderApp('/jobs/1')
    const section = await screen.findByRole('region', { name: 'Proceso' })
    expect(await within(section).findByText('Sin código.')).toBeInTheDocument()
    expect(within(section).getByRole('button', { name: 'Aplicar cambios' })).toBeEnabled()
    await userEvent.click(within(section).getByRole('button', { name: 'Cancelar' }))
    await waitFor(() => expect(calls.some((c) => c.path === '/milestones/5/guide/correction/cancel')).toBe(true))
  })

  const versioned = { ...guide, other_saved_at: '2026-10-19T10:00:00Z', restored: false }
  const changes = {
    milestone_id: 5,
    older_saved_at: '2026-10-19T10:00:00Z',
    newer_saved_at: '2026-10-20T10:00:00Z',
    instruction: 'Sin código.',
    changes: [
      { part: 'section', section: 'Posibles preguntas', removed: ['SQL: SELECT 1;'], added: [], reordered: false },
      { part: 'sources', section: null, removed: [], added: ['Web — https://example.com'], reordered: false },
    ],
  }

  it('la versión anterior enseña qué cambió y se puede volver a ella', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView({ stage: 'in_process' }),
      'GET /jobs/1/process': processView({
        stage: 'in_process',
        milestones: [milestone(5, { starts_at: past, guide: versioned })],
      }),
      'GET /agent': launcher,
      'GET /milestones/5/guide/changes': changes,
      'POST /milestones/5/guide/restore': milestone(5, { starts_at: past, guide: { ...versioned, restored: true } }),
    })
    renderApp('/jobs/1')
    const section = await screen.findByRole('region', { name: 'Proceso' })
    await userEvent.click(await within(section).findByRole('button', { name: /^Versión anterior/ }))
    expect(await within(section).findByText('Sin código.')).toBeInTheDocument()
    expect(within(section).getByText('Posibles preguntas')).toBeInTheDocument()
    expect(within(section).getByText('SQL: SELECT 1;')).toBeInTheDocument()
    expect(within(section).getByText('Fuentes')).toBeInTheDocument()
    await userEvent.click(within(section).getByRole('button', { name: 'Volver a la versión anterior' }))
    await waitFor(() => expect(calls.some((c) => c.path === '/milestones/5/guide/restore')).toBe(true))
  })

  it('tras volver, se ofrece la versión más reciente', async () => {
    mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView({ stage: 'in_process' }),
      'GET /jobs/1/process': processView({
        stage: 'in_process',
        milestones: [milestone(5, { starts_at: past, guide: { ...versioned, restored: true } })],
      }),
      'GET /agent': launcher,
      'GET /milestones/5/guide/changes': changes,
    })
    renderApp('/jobs/1')
    const section = await screen.findByRole('region', { name: 'Proceso' })
    await userEvent.click(await within(section).findByRole('button', { name: /^Versión más reciente/ }))
    expect(await within(section).findByRole('button', { name: 'Volver a la versión más reciente' })).toBeEnabled()
  })

  it('con cambios pedidos no se puede volver, y dice por qué', async () => {
    mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView({ stage: 'in_process' }),
      'GET /jobs/1/process': processView({
        stage: 'in_process',
        milestones: [milestone(5, { starts_at: past, guide: { ...versioned, correction: 'Otra cosa.' } })],
      }),
      'GET /agent': launcher,
      'GET /milestones/5/guide/changes': changes,
    })
    renderApp('/jobs/1')
    const section = await screen.findByRole('region', { name: 'Proceso' })
    await userEvent.click(await within(section).findByRole('button', { name: /^Versión anterior/ }))
    expect(await within(section).findByRole('button', { name: 'Volver a la versión anterior' })).toBeDisabled()
    expect(within(section).getByText(/Primero cancela los cambios pedidos/)).toBeInTheDocument()
  })

  it('con la entrevista cancelada explica por qué no se piden cambios, y se ve sin poder volver', async () => {
    mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView({ stage: 'in_process' }),
      'GET /jobs/1/process': processView({
        stage: 'in_process',
        milestones: [milestone(5, { starts_at: past, status: 'cancelled', guide: versioned })],
      }),
      'GET /agent': launcher,
      'GET /milestones/5/guide/changes': changes,
    })
    renderApp('/jobs/1')
    const section = await screen.findByRole('region', { name: 'Proceso' })
    expect(await within(section).findByText(/porque la entrevista está cancelada/)).toBeInTheDocument()
    expect(within(section).queryByRole('button', { name: 'Pedir cambios a la guía' })).not.toBeInTheDocument()
    await userEvent.click(within(section).getByRole('button', { name: /^Versión anterior/ }))
    expect(await within(section).findByText('Sin código.')).toBeInTheDocument()
    expect(within(section).queryByRole('button', { name: 'Volver a la versión anterior' })).not.toBeInTheDocument()
  })

  it('sin guía, cancelada o con el proceso cerrado no se piden cambios', () => {
    expect(canCorrectGuide(milestone(5), 'in_process')).toBe(false)
    expect(canCorrectGuide(milestone(5, { guide }), 'in_process')).toBe(true)
    expect(canCorrectGuide(milestone(5, { guide, status: 'cancelled' }), 'in_process')).toBe(false)
    expect(canCorrectGuide(milestone(5, { guide }), 'closed')).toBe(false)
  })

  it('guarda las indicaciones de cada entrevista para «Preparar» y «Simulacro»', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView({ stage: 'in_process' }),
      'GET /jobs/1/process': processView({
        stage: 'in_process',
        milestones: [
          milestone(5, { starts_at: future, interview_type: 'technical', prep_instructions: 'Repasar dbt.' }),
          milestone(7, { starts_at: future, title: 'Entrevista final' }),
        ],
      }),
      'GET /agent': launcher,
      'POST /agent/launch': launched,
      'POST /milestones/7/prep-instructions': milestone(7, { prep_instructions: 'Más peso a SQL.' }),
    })
    renderApp('/jobs/1')
    const section = await screen.findByRole('region', { name: 'Proceso' })
    const boxes = await within(section).findAllByLabelText('Indicaciones para preparar y ensayar (opcional)')
    expect(boxes).toHaveLength(2)
    expect(boxes[0]).toHaveValue('Repasar dbt.')
    expect(within(section).getByText('Técnica')).toBeInTheDocument()

    // Sin guardar a mano: salir de la caja (p. ej. al pulsar «Preparar») ya la guarda.
    await userEvent.type(boxes[1], 'Más peso a SQL.')
    await userEvent.click(within(section).getAllByRole('button', { name: 'Preparar' })[1])
    await waitFor(() =>
      expect(calls.find((c) => c.path === '/milestones/7/prep-instructions')?.body).toEqual({
        instructions: 'Más peso a SQL.',
      }),
    )
    expect(calls.filter((c) => c.path.endsWith('/prep-instructions'))).toHaveLength(1)
    await waitFor(() =>
      expect(calls.find((c) => c.path === '/agent/launch')?.body).toEqual({
        action: 'prepare-interview',
        milestone_id: 7,
      }),
    )
  })

  it('una entrevista pasada tiene «Repasar» y enseña el repaso guardado', async () => {
    const calls = ficha([
      milestone(6, {
        status: 'done',
        debrief_notes: 'Preguntaron por dbt.',
        next_steps: 'Prueba técnica la semana que viene.',
      }),
    ])
    renderApp('/jobs/1')
    const section = await screen.findByRole('region', { name: 'Proceso' })
    const debrief = await within(section).findByLabelText('Repaso de la entrevista')
    expect(debrief).toHaveTextContent('Preguntaron por dbt.')
    expect(debrief).toHaveTextContent('Prueba técnica la semana que viene.')
    expect(within(section).queryByRole('button', { name: 'Preparar' })).not.toBeInTheDocument()
    await userEvent.click(within(section).getByRole('button', { name: 'Repasar otra vez' }))
    await waitFor(() =>
      expect(calls.find((c) => c.path === '/agent/launch')?.body).toEqual({
        action: 'debrief-interview',
        milestone_id: 6,
      }),
    )
  })

  it('enlaza la guía de preparación en PDF', async () => {
    ficha([
      milestone(5, {
        starts_at: future,
        guide: {
          file: '1-5-bretema-guia.pdf',
          language: 'es',
          title: 'Data Engineer',
          saved_at: '2026-10-20T10:00:00Z',
          restored: false,
          agent_name: 'codex',
        },
      }),
    ])
    renderApp('/jobs/1')
    const section = await screen.findByRole('region', { name: 'Proceso' })
    const link = await within(section).findByRole('link', { name: 'Guía de preparación (PDF)' })
    expect(link.getAttribute('href')).toMatch(/\/milestones\/5\/guide\.pdf$/)
    expect(link).toHaveAttribute('target', '_blank')
    // Con la miniatura de su portada; si no llega, queda el icono.
    const cover = section.querySelector('img')!
    expect(cover.getAttribute('src')).toMatch(/\/milestones\/5\/guide\.png$/)
    expect(cover.closest('a')?.getAttribute('href')).toMatch(/\/milestones\/5\/guide\.pdf$/)
    fireEvent.error(cover)
    await waitFor(() => expect(section.querySelector('img')).toBeNull())
    expect(within(section).getByRole('link', { name: 'Guía de preparación (PDF)' })).toBeInTheDocument()
  })

  it('enseña el plan por días con su dosier', async () => {
    ficha([
      milestone(7, {
        starts_at: future,
        prep_plan: {
          dossier: '1-7-acme.md',
          saved_at: '2026-10-12T08:00:00Z',
          blocks: [
            { date: '2026-10-13', minutes: 45, topic: 'Historias STAR', detail: 's1 y s2' },
            { date: '2026-10-13', minutes: 30, topic: 'dbt' },
            { date: '2026-10-14', minutes: 60, topic: 'Simulacro' },
          ],
        },
      }),
    ])
    renderApp('/jobs/1')
    const section = await screen.findByRole('region', { name: 'Proceso' })
    const summary = await within(section).findByText(/Plan de preparación · 3 bloques, 135 min/)
    await userEvent.click(summary)
    expect(within(section).getByText(/mar, 13 oct/i)).toBeInTheDocument()
    expect(within(section).getByText(/Historias STAR/)).toHaveTextContent('s1 y s2')
    expect(within(section).getByText('1-7-acme.md')).toBeInTheDocument()
    expect(within(section).getByRole('button', { name: 'Abrir carpeta de dosieres' })).toBeInTheDocument()
  })

  it('con una propuesta recibida, «Dudas antes de aceptar» lanza con la oferta', async () => {
    const calls = ficha([], { offer_received: true })
    renderApp('/jobs/1')
    const section = await screen.findByRole('region', { name: 'Proceso' })
    await userEvent.click(await within(section).findByRole('button', { name: 'Dudas antes de aceptar' }))
    await waitFor(() =>
      expect(calls.find((c) => c.path === '/agent/launch')?.body).toEqual({ action: 'offer-questions', job_id: 1 }),
    )
  })
})

describe('interviewPhase', () => {
  const now = new Date('2026-10-12T10:00:00Z')
  it('decide qué botones van en cada entrevista', () => {
    const later = '2026-10-13T10:00:00Z'
    expect(interviewPhase(milestone(1, { starts_at: later }), 'in_process', now)).toBe('upcoming')
    expect(interviewPhase(milestone(1, { starts_at: later }), 'closed', now)).toBeNull()
    expect(interviewPhase(milestone(1), 'in_process', now)).toBe('past')
    expect(interviewPhase(milestone(1, { status: 'cancelled' }), 'in_process', now)).toBeNull()
    expect(interviewPhase(milestone(1, { kind: 'test', starts_at: later }), 'in_process', now)).toBeNull()
  })
})

describe('entrevistas de todo el día y plan desactualizado', () => {
  it('una de todo el día se prepara ese día y se repasa al acabar', () => {
    const day = milestone(1, { all_day: true, starts_at: '2026-10-12T00:00:00+02:00' })
    expect(interviewPhase(day, 'in_process', new Date('2026-10-12T21:00:00+02:00'))).toBe('upcoming')
    expect(interviewPhase(day, 'in_process', new Date('2026-10-13T00:30:00+02:00'))).toBe('past')
  })

  it('avisa si hay bloques después del día de la entrevista', () => {
    const plan = {
      saved_at: '2026-10-10T08:00:00Z',
      blocks: [{ date: '2026-10-14', minutes: 45, topic: 'dbt' }],
    }
    const moved = milestone(1, { starts_at: '2026-10-13T10:00:00+02:00', prep_plan: plan })
    const same = milestone(1, { starts_at: '2026-10-14T10:00:00+02:00', prep_plan: plan })
    expect(planIsStale(moved)).toBe(true)
    expect(planIsStale(same)).toBe(false)
  })
})
