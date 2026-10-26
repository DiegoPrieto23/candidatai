import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { Schemas } from '@/api/client'
import { mockApi, renderApp, status } from '@/test/utils'

type View = Schemas['SkillGapsView']
type Gap = Schemas['SkillGap']

function gap(changes: Partial<Gap> & Pick<Gap, 'skill' | 'key'>): Gap {
  return {
    must_have_count: 1,
    nice_to_have_count: 0,
    jobs_count: 1,
    weight: 0.5,
    mark: null,
    examples: [{ job_id: 7, title: 'Data Engineer', company: 'Brétema Analytics', score: 62, kind: 'must_have' }],
    ...changes,
  }
}

function view(changes: Partial<View> = {}): View {
  return {
    days: 60,
    jobs_considered: 4,
    gaps: [
      gap({ skill: 'Data Warehousing', key: 'data warehousing', must_have_count: 2, nice_to_have_count: 1, jobs_count: 3, weight: 1.2 }),
      gap({ skill: 'Kafka', key: 'kafka', must_have_count: 0, nice_to_have_count: 2, jobs_count: 2, weight: 1.6, mark: 'gap' }),
      gap({ skill: 'Terraform', key: 'terraform', mark: 'have' }),
    ],
    profile_skills: [
      { name: 'Python', level: 'F' },
      { name: 'Snowflake', level: 'F' },
      { name: 'dbt', level: 'basic' },
    ],
    ...changes,
  }
}

const AGENT = { available: true, agent: 'claude', reason: null, actions: [] }

const skillNames = () =>
  within(screen.getByRole('table', { name: 'Skills ausentes por frecuencia' }))
    .getAllByRole('rowheader')
    .map((cell) => cell.textContent)

describe('Skills', () => {
  it('lista las ausentes por frecuencia, con su desglose y ejemplos', async () => {
    const calls = mockApi({ 'GET /status': status(), 'GET /skills/gaps': view(), 'GET /agent': AGENT })
    renderApp('/skills')

    await screen.findByRole('table', { name: 'Skills ausentes por frecuencia' })
    expect(skillNames()).toEqual(['Data Warehousing', 'Kafka', 'Terraform'])
    expect(screen.getByText('obligatoria en 2, deseable en 1')).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: /Data Engineer · Brétema Analytics/ })[0]).toHaveAttribute('href', '/jobs/7')
    expect(calls.find((c) => c.path === '/skills/gaps')?.search.get('days')).toBe('60')
    // Hay una marcada «La tengo»: aparece el botón para añadirlas al perfil.
    expect(screen.getByRole('button', { name: /Añadir al perfil las que tengo \(1\)/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Plan de formación/ })).toBeInTheDocument()
  })

  it('van de 25 en 25 y un filtro vuelve a la primera página', async () => {
    const many = Array.from({ length: 30 }, (_, i) =>
      gap({ skill: `Skill ${i + 1}`, key: `skill ${i + 1}`, jobs_count: 40 - i, must_have_count: 40 - i }),
    )
    mockApi({ 'GET /status': status(), 'GET /skills/gaps': view({ gaps: many }), 'GET /agent': AGENT })
    renderApp('/skills')
    await screen.findByRole('table', { name: 'Skills ausentes por frecuencia' })
    expect(skillNames()).toHaveLength(25)
    expect(screen.getByText('1-25 de 30')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /Siguientes/ }))
    expect(skillNames()).toEqual(['Skill 26', 'Skill 27', 'Skill 28', 'Skill 29', 'Skill 30'])
    await userEvent.click(screen.getByRole('button', { name: 'Obligatorias' }))
    expect(skillNames()[0]).toBe('Skill 1')
  })

  it('ordena por peso y filtra por tipo, marca y periodo', async () => {
    const calls = mockApi({ 'GET /status': status(), 'GET /skills/gaps': view(), 'GET /agent': AGENT })
    renderApp('/skills')
    await screen.findByRole('table', { name: 'Skills ausentes por frecuencia' })

    await userEvent.click(screen.getByRole('button', { name: 'Peso' }))
    expect(skillNames()).toEqual(['Kafka', 'Data Warehousing', 'Terraform'])

    await userEvent.click(screen.getByRole('button', { name: 'Obligatorias' }))
    expect(skillNames()).toEqual(['Data Warehousing', 'Terraform'])

    await userEvent.click(screen.getByRole('button', { name: 'Todas', pressed: false }))
    await userEvent.click(screen.getByRole('button', { name: 'Sin decidir' }))
    expect(skillNames()).toEqual(['Data Warehousing'])

    await userEvent.click(screen.getByRole('button', { name: '90 días' }))
    await waitFor(() => expect(calls.filter((c) => c.path === '/skills/gaps').at(-1)?.search.get('days')).toBe('90'))
  })

  it('«Es lo mismo que…» añade el alias con una skill del perfil', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /skills/gaps': view(),
      'GET /agent': AGENT,
      'POST /skills/aliases': {
        ok: true,
        skill: 'Data Warehousing',
        canonical: 'Snowflake',
        profile_skill: 'Snowflake',
        added: true,
        rescore_queued: true,
      },
    })
    renderApp('/skills')
    await screen.findByRole('table', { name: 'Skills ausentes por frecuencia' })

    const row = screen.getByRole('group', { name: 'Acciones para Data Warehousing' })
    await userEvent.click(within(row).getByRole('button', { name: /Es lo mismo que/ }))
    const dialog = await screen.findByRole('dialog', { name: '«Data Warehousing» es lo mismo que…' })
    expect(within(dialog).getByRole('button', { name: 'Son lo mismo' })).toBeDisabled()

    await userEvent.type(within(dialog).getByRole('textbox', { name: 'Buscar en tu perfil' }), 'snow')
    expect(within(dialog).getAllByRole('radio')).toHaveLength(1)
    await userEvent.click(within(dialog).getByRole('radio', { name: /Snowflake/ }))
    await userEvent.click(within(dialog).getByRole('button', { name: 'Son lo mismo' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(calls.find((c) => c.path === '/skills/aliases')?.body).toEqual({
      skill: 'Data Warehousing',
      profile_skill: 'Snowflake',
    })
    expect(screen.getByText(/cuenta ya como «Snowflake»/)).toHaveAttribute('role', 'status')
    // Se vuelve a pedir la lista: el hueco desaparece.
    await waitFor(() => expect(calls.filter((c) => c.path === '/skills/gaps').length).toBeGreaterThan(1))
  })

  it('enseña el error si el alias choca con otro', async () => {
    mockApi({
      'GET /status': status(),
      'GET /skills/gaps': view(),
      'GET /agent': AGENT,
      'POST /skills/aliases': {
        status: 422,
        body: { ok: false, error: { type: 'invalid_request', message: '«Kafka» ya es sinónimo de «Apache Kafka».', details: [] } },
      },
    })
    renderApp('/skills')
    await screen.findByRole('table', { name: 'Skills ausentes por frecuencia' })
    await userEvent.click(
      within(screen.getByRole('group', { name: 'Acciones para Kafka' })).getByRole('button', { name: /Es lo mismo que/ }),
    )
    const dialog = await screen.findByRole('dialog')
    await userEvent.click(within(dialog).getByRole('radio', { name: /Python/ }))
    await userEvent.click(within(dialog).getByRole('button', { name: 'Son lo mismo' }))
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('ya es sinónimo de «Apache Kafka»')
  })

  it('marca «No la tengo» y «La tengo», y quita la marca al pulsar otra vez', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /skills/gaps': view(),
      'GET /agent': AGENT,
      'POST /skills/marks': (request: Request) =>
        request.json().then((body: { skill: string; status: string | null }) => ({
          ok: true,
          key: body.skill.toLowerCase(),
          skill: body.skill,
          mark: body.status,
        })),
    })
    renderApp('/skills')
    await screen.findByRole('table', { name: 'Skills ausentes por frecuencia' })

    const dwh = screen.getByRole('group', { name: 'Acciones para Data Warehousing' })
    await userEvent.click(within(dwh).getByRole('button', { name: /No la tengo/ }))
    const kafka = screen.getByRole('group', { name: 'Acciones para Kafka' })
    expect(within(kafka).getByRole('button', { name: /No la tengo/ })).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(within(kafka).getByRole('button', { name: /No la tengo/ }))

    await waitFor(() => expect(calls.filter((c) => c.path === '/skills/marks')).toHaveLength(2))
    expect(calls.filter((c) => c.path === '/skills/marks').map((c) => c.body)).toEqual([
      { skill: 'Data Warehousing', status: 'gap' },
      { skill: 'Kafka', status: null },
    ])
  })

  it('sin perfil explica cómo crearlo y sin huecos lo celebra', async () => {
    mockApi({
      'GET /status': status(),
      'GET /agent': AGENT,
      'GET /skills/gaps': { status: 404, body: { ok: false, error: { type: 'not_found', message: 'Sin perfil', details: [] } } },
    })
    const first = renderApp('/skills')
    expect(await screen.findByText('Aún no tienes perfil')).toBeInTheDocument()
    first.unmount()

    mockApi({ 'GET /status': status(), 'GET /agent': AGENT, 'GET /skills/gaps': view({ gaps: [] }) })
    renderApp('/skills')
    expect(await screen.findByText('Tu perfil cubre lo que piden tus ofertas')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Añadir al perfil/ })).not.toBeInTheDocument()
  })
})
