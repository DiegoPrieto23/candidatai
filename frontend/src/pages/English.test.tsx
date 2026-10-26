import { act, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import { detectLanguage, i18n } from '@/lib/i18n'
import {
  board,
  boardCard,
  jobView,
  mockApi,
  renderApp,
  status,
  triageItem,
  triageQueue,
} from '@/test/utils'

const emptyPage = { items: [], total: 0, limit: 50, offset: 0 }
const noFollowups = { days_without_reply: 7, followups: [] }
const noUpcoming = { days: 7, items: [] }

/** Los tests arrancan en español (`test/setup.ts`): estos pasan a inglés. */
async function english() {
  await act(async () => {
    await i18n.changeLanguage('en')
  })
}

describe('Selector de idioma (fase 23.6)', () => {
  beforeEach(() => localStorage.clear())

  it('cambia la UI al momento, lo recuerda y actualiza <html lang>', async () => {
    mockApi({ 'GET /status': status(0, 3), 'GET /jobs': emptyPage })
    renderApp('/bandeja')
    expect(await screen.findByRole('heading', { level: 1, name: 'Bandeja de ofertas' })).toBeInTheDocument()
    expect(document.documentElement.lang).toBe('es')

    const sidebar = screen.getByRole('complementary', { name: 'Barra lateral' })
    await userEvent.click(within(sidebar).getByRole('button', { name: 'Idioma: Español' }))
    const menu = await screen.findByRole('menu', { name: 'Idioma: Español' })
    expect(within(menu).getByRole('menuitemradio', { name: 'Español' })).toHaveAttribute('aria-checked', 'true')
    await userEvent.click(within(menu).getByRole('menuitemradio', { name: 'English' }))

    expect(await screen.findByRole('heading', { level: 1, name: 'Job inbox' })).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: 'Main navigation' })).toBeInTheDocument()
    expect(await screen.findByRole('link', { name: 'To review (3 to review)' })).toBeInTheDocument()
    expect(document.documentElement.lang).toBe('en')
    expect(localStorage.getItem('cai-language')).toBe('en')
    expect(detectLanguage()).toBe('en')
  })

  it('sin idioma guardado, usa el del navegador: español si es es-*, si no, inglés', () => {
    const original = Object.getOwnPropertyDescriptor(Navigator.prototype, 'languages')
    const setBrowser = (languages: string[]) =>
      Object.defineProperty(navigator, 'languages', { value: languages, configurable: true })
    try {
      setBrowser(['es-MX', 'en'])
      expect(detectLanguage()).toBe('es')
      setBrowser(['de-DE'])
      expect(detectLanguage()).toBe('en')
      setBrowser(['en-US'])
      expect(detectLanguage()).toBe('en')
      localStorage.setItem('cai-language', 'es')
      expect(detectLanguage()).toBe('es')
    } finally {
      delete (navigator as unknown as Record<string, unknown>).languages
      if (original) Object.defineProperty(Navigator.prototype, 'languages', original)
    }
  })
})

describe('Páginas en inglés', () => {
  it('Inicio', async () => {
    const base = status()
    mockApi({
      'GET /status': { ...base, by_stage: { ...base.by_stage, pending_triage: 2, cv_ready: 1 } },
      'GET /followups': noFollowups,
      'GET /upcoming': noUpcoming,
      'GET /jobs': emptyPage,
    })
    await english()
    renderApp('/')
    expect(
      await screen.findByRole('heading', { level: 1, name: 'You have 2 jobs to review and 1 CV ready to send.' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: "Your jobs' journey" })).toBeInTheDocument()
    expect(screen.getByText('Best fit to review')).toBeInTheDocument()
  })

  it('Por revisar', async () => {
    mockApi({ 'GET /status': status(0, 2), 'GET /triage': triageQueue([triageItem(1, 82), triageItem(2, 40)]) })
    await english()
    renderApp('/por-revisar')
    const detail = await screen.findByRole('article', { name: 'Selected job' })
    expect(within(detail).getByLabelText('Score 82 out of 100')).toBeInTheDocument()
    expect(within(detail).getByRole('button', { name: /Approve/ })).toBeInTheDocument()
    expect(within(detail).getByText('Must-have skills')).toBeInTheDocument()
    expect(screen.getByText('2 jobs to review, best fit first')).toBeInTheDocument()
  })

  it('Ficha de oferta', async () => {
    mockApi({ 'GET /status': status(), 'GET /jobs/1': jobView() })
    await english()
    renderApp('/jobs/1')
    expect(await screen.findByRole('heading', { level: 1, name: 'Data Engineer' })).toBeInTheDocument()
    expect(screen.getByText('Mid-level')).toBeInTheDocument()
    expect(screen.getByText(/€38,000 - €46,000 \/ year/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('tab', { name: 'History & notes' }))
    expect(screen.getByText('Extraction saved')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'History' })).toBeInTheDocument()
  })

  it('Procesos', async () => {
    mockApi({
      'GET /status': status(),
      'GET /board': board([boardCard(1, 'approved'), boardCard(2, 'applied', { followup_due: true, days_waiting: 12 })]),
      'GET /upcoming': noUpcoming,
    })
    await english()
    renderApp('/procesos')
    expect(await screen.findByRole('heading', { level: 1, name: 'Processes' })).toBeInTheDocument()
    const applied = await screen.findByRole('region', { name: 'Applied' })
    expect(within(applied).getByText(/Follow-up · 12 days/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Update status of “Oferta 1”' })).toBeInTheDocument()
    expect(screen.getByText('1 follow-up due')).toBeInTheDocument()
  })
})
