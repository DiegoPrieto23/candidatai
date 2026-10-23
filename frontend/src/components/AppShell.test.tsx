import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import { mockApi, renderApp, status } from '@/test/utils'

const emptyPage = { items: [], total: 0, limit: 50, offset: 0 }

describe('Banner del modo demo', () => {
  it('sale en todas las páginas si la carpeta de datos es una demo', async () => {
    mockApi({ 'GET /status': { ...status(), demo_mode: true }, 'GET /jobs': emptyPage })
    renderApp('/')
    const banner = await screen.findByRole('note', { name: 'Modo demo' })
    expect(banner).toHaveTextContent('Modo demo: datos ficticios.')
  })

  it('no sale con tus datos', async () => {
    mockApi({ 'GET /status': status(), 'GET /jobs': emptyPage })
    renderApp('/bandeja')
    expect(await screen.findByText('Tu bandeja está vacía')).toBeInTheDocument()
    expect(screen.queryByRole('note', { name: 'Modo demo' })).not.toBeInTheDocument()
  })
})

describe('Barra lateral (fase 23.3)', () => {
  const routes = () => ({
    'GET /status': status(0, 3, 2),
    'GET /jobs': emptyPage,
    'GET /replies': { replies: [], counts: { proposed: 1, new: 0, accepted: 0, ignored: 0 } },
  })

  beforeEach(() => {
    localStorage.clear()
  })

  it('agrupa las páginas y enseña lo que te espera', async () => {
    mockApi(routes())
    renderApp('/bandeja')
    const nav = screen.getByRole('navigation', { name: 'Navegación principal' })
    for (const group of ['Búsqueda', 'Procesos', 'Análisis', 'Configurar']) {
      expect(within(nav).getByRole('list', { name: group })).toBeInTheDocument()
    }
    const names = within(nav)
      .getAllByRole('link')
      .map((link) => link.textContent?.replace(/\d.*$/, '').trim())
    expect(names).toEqual([
      'Inicio',
      'Bandeja',
      'Por revisar',
      'Alertas',
      'Procesos',
      'Calendario',
      'Respuestas',
      'Embudo',
      'Skills',
      'Fuentes',
      'Plantillas',
      'Mi perfil',
      'Agente',
    ])
    expect(await within(nav).findByRole('link', { name: 'Por revisar (3 por revisar)' })).toBeInTheDocument()
    expect(within(nav).getByRole('link', { name: 'Alertas (2 por completar)' })).toBeInTheDocument()
    expect(await within(nav).findByRole('link', { name: 'Respuestas (1 por revisar)' })).toBeInTheDocument()
    expect(within(nav).getByRole('link', { name: 'Bandeja' })).toHaveAttribute('aria-current', 'page')
  })

  it('se pliega a solo iconos y lo recuerda', async () => {
    mockApi(routes())
    const { unmount } = renderApp('/bandeja')
    await userEvent.click(screen.getByRole('button', { name: 'Plegar el menú' }))
    const nav = screen.getByRole('navigation', { name: 'Navegación principal' })
    // Plegada, cada enlace conserva su nombre accesible aunque solo se vea el icono.
    expect(within(nav).getByRole('link', { name: 'Embudo' })).toBeInTheDocument()
    expect(within(nav).queryByText('Embudo')).not.toBeInTheDocument()
    expect(localStorage.getItem('cai-sidebar-collapsed')).toBe('1')
    unmount()

    renderApp('/bandeja')
    expect(screen.getByRole('button', { name: 'Desplegar el menú' })).toBeInTheDocument()
  })

  it('en el móvil se abre como cajón y se cierra al navegar', async () => {
    mockApi(routes())
    renderApp('/bandeja')
    await userEvent.click(screen.getByRole('button', { name: 'Abrir el menú' }))
    const drawer = await screen.findByRole('dialog')
    await userEvent.click(within(drawer).getByRole('link', { name: 'Embudo' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('las rutas antiguas de Empresas y Plataformas llevan a Fuentes', async () => {
    mockApi({ ...routes(), 'GET /sources': { sources: [], agent_browse: { max_result_pages: 2, delay_seconds: 5, default_max_offers: 15 } } })
    renderApp('/empresas')
    expect(await screen.findByRole('heading', { name: 'Empresas objetivo' })).toBeInTheDocument()
    const tabs = screen.getByRole('navigation', { name: 'Fuentes de ofertas' })
    expect(within(tabs).getByRole('link', { name: 'Empresas objetivo' })).toHaveAttribute('aria-current', 'page')
    await userEvent.click(within(tabs).getByRole('link', { name: 'Plataformas' }))
    expect(await screen.findByRole('heading', { name: 'Plataformas' })).toBeInTheDocument()
  })

  it('Fuentes abre en Plataformas, la primera pestaña', async () => {
    mockApi({ ...routes(), 'GET /sources': { sources: [], agent_browse: { max_result_pages: 2, delay_seconds: 5, default_max_offers: 15 } } })
    renderApp('/fuentes')
    expect(await screen.findByRole('heading', { name: 'Plataformas' })).toBeInTheDocument()
    const tabs = screen.getByRole('navigation', { name: 'Fuentes de ofertas' })
    expect(within(tabs).getAllByRole('link').map((link) => link.textContent)).toEqual(['Plataformas', 'Empresas objetivo'])
  })
})

describe('Barra lateral: detalles (fase 23.3)', () => {
  it('la ficha de una oferta cuenta como Bandeja y el cajón se cierra al pulsar la marca', async () => {
    mockApi({ 'GET /status': status(), 'GET /jobs': emptyPage, 'GET /jobs/7': { status: 404, body: {} } })
    renderApp('/jobs/7')
    const nav = screen.getByRole('navigation', { name: 'Navegación principal' })
    expect(within(nav).getByRole('link', { name: 'Bandeja' })).toHaveAttribute('aria-current', 'page')

    await userEvent.click(screen.getByRole('button', { name: 'Abrir el menú' }))
    const drawer = await screen.findByRole('dialog')
    await userEvent.click(within(drawer).getByRole('link', { name: 'CandidatAI' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})

describe('«Nueva oferta»', () => {
  it('en Inicio va con las acciones de la página; en el resto, arriba en la cabecera', async () => {
    mockApi({
      'GET /status': status(),
      'GET /jobs': emptyPage,
      'GET /followups': { days_without_reply: 7, followups: [] },
      'GET /upcoming': { days: 7, items: [] },
    })
    const { unmount } = renderApp('/')
    const main = await screen.findByRole('main')
    expect(await within(main).findByRole('link', { name: 'Nueva oferta' })).toHaveAttribute('href', '/nueva')
    expect(within(screen.getByRole('banner')).queryByRole('link', { name: 'Nueva oferta' })).not.toBeInTheDocument()
    unmount()
    renderApp('/bandeja')
    expect(await within(screen.getByRole('banner')).findByRole('link', { name: 'Nueva oferta' })).toBeInTheDocument()
  })
})
