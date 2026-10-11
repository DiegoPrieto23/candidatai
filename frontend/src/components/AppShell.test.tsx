import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
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
