import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { jobPackage, jobView, mockApi, renderApp, status } from '@/test/utils'

const NAME = 'Candidatura archivada'
const FOLDER = 'documentos/candidaturas/Acme-Analytics_Data-Engineer_1'

describe('Candidatura archivada en la ficha', () => {
  it('una oferta enviada enlaza a su carpeta, fuera de lo plegado', async () => {
    const calls = mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView({ stage: 'applied', archive_folder: FOLDER }),
      'POST /folders/open': { status: 200, body: { path: `C:/cai/data/${FOLDER}`, opened: true } },
    })
    renderApp('/jobs/1?tab=application')
    const section = await screen.findByRole('region', { name: NAME })
    expect(within(section).getByText(`data/${FOLDER}`)).toBeInTheDocument()
    await userEvent.click(
      within(section).getByRole('button', { name: 'Abrir la carpeta archivada de la candidatura' }),
    )
    await waitFor(() => expect(calls.some((c) => c.path === '/folders/open')).toBe(true))
    expect(calls.find((c) => c.path === '/folders/open')?.body).toEqual({ folder: 'candidatura', job_id: 1 })
  })

  it('si aún no está archivada, explica cómo', async () => {
    mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView({ stage: 'applied', archive_folder: null }),
    })
    renderApp('/jobs/1?tab=application')
    expect(await screen.findByText(/Aún sin copia de lo enviado/)).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: NAME })).not.toBeInTheDocument()
  })

  it('antes de enviar no aparece', async () => {
    mockApi({
      'GET /status': status(),
      'GET /jobs/1': jobView({ stage: 'cv_ready' }),
      'GET /jobs/1/package': jobPackage(),
    })
    renderApp('/jobs/1?tab=application')
    await screen.findByRole('region', { name: 'Paquete de candidatura' })
    expect(screen.queryByRole('region', { name: NAME })).not.toBeInTheDocument()
    expect(screen.queryByText(/Aún sin copia/)).not.toBeInTheDocument()
  })
})

describe('Recién enviada', () => {
  it('vuelve a pedir la ficha hasta que el worker la archiva', async () => {
    let archived = false
    mockApi({
      'GET /status': status(),
      'GET /jobs/1': () => jobView({ stage: 'applied', archive_folder: archived ? FOLDER : null }),
    })
    renderApp('/jobs/1?tab=application')
    expect(await screen.findByText(/Aún sin copia de lo enviado/)).toBeInTheDocument()
    archived = true
    expect(await screen.findByRole('region', { name: NAME }, { timeout: 7000 })).toBeInTheDocument()
  }, 10000)
})
