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
    expect(await screen.findByText('La bandeja está vacía')).toBeInTheDocument()
    expect(screen.queryByRole('note', { name: 'Modo demo' })).not.toBeInTheDocument()
  })
})

describe('Saltar al contenido (fase 36)', () => {
  it('es lo primero con Tab y deja el foco en el contenido', async () => {
    mockApi({ 'GET /status': status(), 'GET /jobs': emptyPage })
    renderApp('/bandeja')
    await screen.findByText('La bandeja está vacía')

    await userEvent.tab()
    const skip = screen.getByRole('link', { name: 'Saltar al contenido' })
    expect(skip).toHaveFocus()
    await userEvent.keyboard('{Enter}')
    expect(screen.getByRole('main')).toHaveFocus()
    // Sin tocar la URL: el `#` no es una ruta de la app.
    expect(window.location.hash).toBe('')
  })
})

describe('Al cambiar de página', () => {
  it('empieza por arriba, también si venías con scroll', async () => {
    mockApi({ 'GET /status': status(), 'GET /jobs': { items: [], total: 0, limit: 50, offset: 0 } })
    const scroll = vi.spyOn(window, 'scrollTo')
    renderApp('/como-funciona')
    const nav = await screen.findByRole('navigation', { name: 'Navegación principal' })
    expect(scroll).not.toHaveBeenCalled()
    await userEvent.click(within(nav).getByRole('link', { name: 'Bandeja de ofertas' }))
    await screen.findByRole('heading', { level: 1, name: 'Bandeja de ofertas' })
    expect(scroll).toHaveBeenCalledWith(0, 0)
    scroll.mockRestore()
  })
})

describe('Barra lateral (fase 23.3)', () => {
  const routes = () => ({
    'GET /status': status(0, 3, 2),
    'GET /jobs': emptyPage,
  })

  beforeEach(() => {
    localStorage.clear()
  })

  it('agrupa las páginas y enseña lo que te espera', async () => {
    mockApi(routes())
    renderApp('/bandeja')
    const nav = screen.getByRole('navigation', { name: 'Navegación principal' })
    for (const group of ['Búsqueda', 'Procesos', 'Ajustes']) {
      expect(within(nav).getByRole('list', { name: group })).toBeInTheDocument()
    }
    const names = within(nav)
      .getAllByRole('link')
      .map((link) => link.textContent?.replace(/\d.*$/, '').trim())
    expect(names).toEqual([
      'Inicio',
      'Mi perfil',
      'Buscar ofertas',
      'Bandeja de ofertas',
      'Tablero',
      'Calendario',
      'Respuestas',
      'Resultados',
      'Agente',
    ])
    expect(await within(nav).findByRole('link', { name: 'Bandeja de ofertas' })).toHaveAttribute('aria-current', 'page')
  })

  it('«Mi perfil» avisa de que falta el perfil, y «Cómo funciona» queda abajo, fuera de la lista', async () => {
    mockApi({
      ...routes(),
      'GET /profile/editable': { exists: false, file_hash: null, profile: null, issues: [], profile_version_id: null, undo_available: 0 },
    })
    renderApp('/bandeja')
    const nav = screen.getByRole('navigation', { name: 'Navegación principal' })
    expect(await within(nav).findByRole('link', { name: 'Mi perfil (aún sin crear)' })).toHaveAttribute('href', '/perfil')
    expect(within(nav).queryByRole('link', { name: 'Cómo funciona' })).not.toBeInTheDocument()
    const help = within(screen.getByRole('complementary', { name: 'Barra lateral' })).getByRole('link', { name: 'Cómo funciona' })
    expect(help).toHaveAttribute('href', '/como-funciona')
  })

  it.each([
    ['/por-revisar', /^Revisión rápida/],
    ['/triaje', /^Revisión rápida/],
    ['/alertas', /^Por completar/],
    ['/procesos/calendario?view=agenda', /^Calendario/],
    ['/skills', /^Habilidades por desarrollar/],
    ['/plantillas', /^Plantillas de CV/],
  ])('la ruta antigua %s abre su pestaña nueva', async (from, tab) => {
    mockApi(routes())
    renderApp(from)
    expect(await screen.findByRole('link', { name: tab, current: 'page' })).toBeInTheDocument()
  })

  it('cada sección enseña sus pestañas: la Bandeja, con lo que te espera en cada una', async () => {
    mockApi(routes())
    renderApp('/bandeja')
    const inbox = await screen.findByRole('navigation', { name: 'Vistas de la bandeja' })
    expect(await within(inbox).findByRole('link', { name: 'Revisión rápida (3)' })).toHaveAttribute('href', '/bandeja/revision')
    expect(within(inbox).getByRole('link', { name: 'Por completar (2)' })).toHaveAttribute('href', '/bandeja/por-completar')
    expect(within(inbox).getByRole('link', { name: 'Ofertas' })).toHaveAttribute('aria-current', 'page')
  })

  it('se pliega a solo iconos y lo recuerda', async () => {
    mockApi(routes())
    const { unmount } = renderApp('/bandeja')
    await userEvent.click(screen.getByRole('button', { name: 'Plegar el menú' }))
    const nav = screen.getByRole('navigation', { name: 'Navegación principal' })
    // Plegada, cada enlace conserva su nombre accesible aunque solo se vea el icono.
    expect(within(nav).getByRole('link', { name: 'Resultados' })).toBeInTheDocument()
    expect(within(nav).queryByText('Resultados')).not.toBeInTheDocument()
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
    await userEvent.click(within(drawer).getByRole('link', { name: 'Resultados' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('las rutas antiguas de Empresas y Plataformas llevan a «Dónde buscar»', async () => {
    mockApi({ ...routes(), 'GET /sources': { sources: [], agent_browse: { max_result_pages: 5, delay_seconds: 5, default_max_offers: 15, stop_after_known: 5 } } })
    renderApp('/empresas')
    expect(await screen.findByRole('heading', { name: 'Empresas con portal propio' })).toBeInTheDocument()
    const tabs = screen.getByRole('navigation', { name: 'Dónde buscar' })
    expect(within(tabs).getByRole('link', { name: 'Empresas con portal propio' })).toHaveAttribute('aria-current', 'page')
    await userEvent.click(within(tabs).getByRole('link', { name: 'Portales de empleo' }))
    expect(await screen.findByRole('heading', { name: 'Portales de empleo' })).toBeInTheDocument()
  })

  it('«Dónde buscar» abre en «Portales de empleo», la primera pestaña', async () => {
    mockApi({ ...routes(), 'GET /sources': { sources: [], agent_browse: { max_result_pages: 5, delay_seconds: 5, default_max_offers: 15, stop_after_known: 5 } } })
    renderApp('/fuentes')
    expect(await screen.findByRole('heading', { name: 'Portales de empleo' })).toBeInTheDocument()
    const tabs = screen.getByRole('navigation', { name: 'Dónde buscar' })
    expect(within(tabs).getAllByRole('link').map((link) => link.textContent)).toEqual([
      'Portales de empleo',
      'Empresas con portal propio',
      'Alertas por correo',
      'Botón del navegador',
    ])
  })

  it('«Buscar ofertas» tiene dos pestañas con su URL: cada una pinta solo lo suyo y sin mover la página', async () => {
    mockApi({ ...routes(), 'GET /sources': { sources: [], agent_browse: { max_result_pages: 5, delay_seconds: 5, default_max_offers: 15, stop_after_known: 5 } } })
    const scrolled: string[] = []
    const original = Element.prototype.scrollIntoView
    Element.prototype.scrollIntoView = function (this: Element) {
      scrolled.push(this.id)
    }
    try {
      renderApp('/fuentes/correo')
      expect(await screen.findByRole('heading', { level: 1, name: 'Buscar ofertas' })).toBeInTheDocument()
      const tabs = screen.getByRole('navigation', { name: 'Secciones de «Buscar ofertas»' })
      expect(within(tabs).getAllByRole('link').map((l) => l.textContent)).toEqual(['Buscar', 'Dónde buscar'])
      expect(within(tabs).getByRole('link', { name: 'Dónde buscar' })).toHaveAttribute('aria-current', 'page')
      expect(within(tabs).getByRole('link', { name: 'Dónde buscar' })).toHaveAttribute('href', '/fuentes')
      // Solo la pestaña abierta: el correo sí, la búsqueda no.
      expect(await screen.findByRole('heading', { level: 3, name: 'Alertas por correo' })).toBeInTheDocument()
      expect(screen.queryByRole('region', { name: 'Qué se va a buscar' })).not.toBeInTheDocument()

      await userEvent.click(within(tabs).getByRole('link', { name: 'Buscar' }))
      expect(await screen.findByRole('region', { name: 'Qué se va a buscar' })).toBeInTheDocument()
      expect(within(tabs).getByRole('link', { name: 'Buscar' })).toHaveAttribute('aria-current', 'page')
      expect(screen.queryByRole('navigation', { name: 'Dónde buscar' })).not.toBeInTheDocument()
      expect(screen.queryByRole('heading', { level: 3, name: 'Alertas por correo' })).not.toBeInTheDocument()
      // Ni índice fijo ni anclas a las que bajar.
      expect(scrolled).toEqual([])
    } finally {
      Element.prototype.scrollIntoView = original
    }
  })

  it('«Buscar» sigue activa con «Más ajustes» abierto y /buscar/donde lleva a «Dónde buscar»', async () => {
    mockApi({ ...routes(), 'GET /sources': { sources: [], agent_browse: { max_result_pages: 5, delay_seconds: 5, default_max_offers: 15, stop_after_known: 5 } } })
    const { unmount } = renderApp('/buscar/ajustes')
    const tabs = await screen.findByRole('navigation', { name: 'Secciones de «Buscar ofertas»' })
    expect(within(tabs).getByRole('link', { name: 'Buscar' })).toHaveAttribute('aria-current', 'page')
    unmount()
    renderApp('/buscar/donde')
    expect(await screen.findByRole('heading', { name: 'Portales de empleo' })).toBeInTheDocument()
    const again = screen.getByRole('navigation', { name: 'Secciones de «Buscar ofertas»' })
    expect(within(again).getByRole('link', { name: 'Dónde buscar' })).toHaveAttribute('aria-current', 'page')
  })
})

describe('Barra lateral: detalles (fase 23.3)', () => {
  it('la ficha de una oferta cuenta como Bandeja y el cajón se cierra al pulsar la marca', async () => {
    mockApi({ 'GET /status': status(), 'GET /jobs': emptyPage, 'GET /jobs/7': { status: 404, body: {} } })
    renderApp('/jobs/7')
    const nav = screen.getByRole('navigation', { name: 'Navegación principal' })
    expect(within(nav).getByRole('link', { name: 'Bandeja de ofertas' })).toHaveAttribute('aria-current', 'page')

    await userEvent.click(screen.getByRole('button', { name: 'Abrir el menú' }))
    const drawer = await screen.findByRole('dialog')
    await userEvent.click(within(drawer).getByRole('link', { name: 'CandidatAI' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})

describe('«Nueva oferta»', () => {
  it('va siempre en la barra lateral, en Inicio y en el resto', async () => {
    mockApi({
      'GET /status': status(),
      'GET /jobs': emptyPage,
      'GET /followups': { days_without_reply: 7, followups: [] },
      'GET /upcoming': { days: 7, items: [] },
    })
    const { unmount } = renderApp('/')
    const sidebar = await screen.findByRole('complementary', { name: 'Barra lateral' })
    expect(within(sidebar).getByRole('link', { name: 'Nueva oferta' })).toHaveAttribute('href', '/nueva')
    unmount()
    renderApp('/bandeja')
    const again = await screen.findByRole('complementary', { name: 'Barra lateral' })
    expect(within(again).getByRole('link', { name: 'Nueva oferta' })).toHaveAttribute('href', '/nueva')
  })

  it('en su página, el activo es el botón y no la Bandeja (H-013)', async () => {
    mockApi({ 'GET /status': status() })
    renderApp('/nueva')
    const sidebar = await screen.findByRole('complementary', { name: 'Barra lateral' })
    expect(within(sidebar).getByRole('link', { name: 'Nueva oferta' })).toHaveAttribute('aria-current', 'page')
    const nav = within(sidebar).getByRole('navigation', { name: 'Navegación principal' })
    expect(within(nav).getByRole('link', { name: 'Bandeja de ofertas' })).not.toHaveAttribute('aria-current')
  })
})
