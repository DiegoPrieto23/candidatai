import { useState } from 'react'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { i18n } from '@/lib/i18n'
import { DatePicker, DateTimePicker, TimeInput } from './date-time-picker'

function Controlled({ initial = '', ...rest }: { initial?: string; required?: boolean; spy?: (v: string) => void }) {
  const [value, setValue] = useState(initial)
  return (
    <>
      <label htmlFor="d">Cuándo</label>
      <DateTimePicker
        id="d"
        value={value}
        required={rest.required}
        onChange={(v) => {
          rest.spy?.(v)
          setValue(v)
        }}
      />
    </>
  )
}

const popup = () => screen.findByRole('dialog', { name: /Elegir fecha/ })

describe('DateTimePicker', () => {
  it('enseña la fecha elegida y su hora, y pide elegirla mientras está vacío', () => {
    const { rerender } = render(<DateTimePicker id="d" value="" onChange={() => {}} />)
    expect(screen.getByRole('button')).toHaveTextContent('Elegir fecha y hora')
    rerender(<DateTimePicker id="d" value="2026-11-04T17:55" onChange={() => {}} />)
    expect(screen.getByRole('button')).toHaveTextContent('mié, 4 nov 2026 · 17:55')
  })

  it('elegir un día mantiene la hora', async () => {
    const spy = vi.fn()
    render(<Controlled initial="2026-11-04T17:55" spy={spy} />)
    await userEvent.click(screen.getByLabelText('Cuándo'))
    const dialog = await popup()
    await userEvent.click(dialog.querySelector<HTMLElement>('[data-day="2026-11-12"]')!)
    expect(spy).toHaveBeenLastCalledWith('2026-11-12T17:55')
  })

  it('sin hora, elegir un día pone las 14:00 y «Sin hora concreta» las devuelve', async () => {
    const spy = vi.fn()
    render(<Controlled spy={spy} />)
    await userEvent.click(screen.getByLabelText('Cuándo'))
    const dialog = await popup()
    await userEvent.click(dialog.querySelector<HTMLElement>('[data-day="2026-11-12"]')!)
    expect(spy).toHaveBeenLastCalledWith('2026-11-12T14:00')
    const hours = within(dialog).getByRole('textbox', { name: 'Horas' })
    await userEvent.clear(hours)
    await userEvent.type(hours, '08')
    expect(spy).toHaveBeenLastCalledWith('2026-11-12T08:00')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Sin hora concreta (14:00)' }))
    expect(spy).toHaveBeenLastCalledWith('2026-11-12T14:00')
  })

  it('pasa de mes con las flechas y con el teclado, y marca el día elegido', async () => {
    render(<Controlled initial="2026-11-04T10:00" />)
    await userEvent.click(screen.getByLabelText('Cuándo'))
    const dialog = await popup()
    expect(within(dialog).getByText('Noviembre de 2026')).toBeInTheDocument()
    expect(dialog.querySelector('[data-day="2026-11-04"]')).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Mes siguiente' }))
    expect(within(dialog).getByText('Diciembre de 2026')).toBeInTheDocument()
    // Con el foco en un día, PageUp vuelve al mes anterior y las flechas mueven el día.
    dialog.querySelector<HTMLElement>('[data-day="2026-12-10"]')!.focus()
    await userEvent.keyboard('{ArrowRight}{ArrowDown}')
    expect(dialog.querySelector('[data-day="2026-12-18"]')).toHaveFocus()
    await userEvent.keyboard('{PageUp}')
    expect(within(dialog).getByText('Noviembre de 2026')).toBeInTheDocument()
  })

  it('escribir la hora acepta «30» entera y se puede subir con ↑', async () => {
    const spy = vi.fn()
    render(<Controlled initial="2026-11-04T10:00" spy={spy} />)
    await userEvent.click(screen.getByLabelText('Cuándo'))
    const dialog = await popup()
    const minutes = within(dialog).getByRole('textbox', { name: 'Minutos' })
    await userEvent.clear(minutes)
    await userEvent.type(minutes, '30')
    expect(spy).toHaveBeenLastCalledWith('2026-11-04T10:30')
    expect(minutes).toHaveValue('30')
    await userEvent.keyboard('{ArrowUp}')
    expect(spy).toHaveBeenLastCalledWith('2026-11-04T10:35')
    const hours = within(dialog).getByRole('textbox', { name: 'Horas' })
    await userEvent.clear(hours)
    await userEvent.type(hours, '25') // fuera de rango: no se confirma
    expect(spy).toHaveBeenLastCalledWith('2026-11-04T10:35')
  })

  it('«Listo» cierra y «Borrar» solo sale si no es obligatorio', async () => {
    const spy = vi.fn()
    const { unmount } = render(<Controlled initial="2026-11-04T10:00" spy={spy} />)
    await userEvent.click(screen.getByLabelText('Cuándo'))
    let dialog = await popup()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Borrar' }))
    expect(spy).toHaveBeenLastCalledWith('')
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    unmount()

    render(<Controlled initial="2026-11-04T10:00" required />)
    await userEvent.click(screen.getByLabelText('Cuándo'))
    dialog = await popup()
    expect(within(dialog).queryByRole('button', { name: 'Borrar' })).not.toBeInTheDocument()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Listo' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('con required, el formulario no se envía sin fecha', () => {
    render(
      <form>
        <DateTimePicker id="d" value="" onChange={() => {}} required />
      </form>,
    )
    expect(document.querySelector('form')!.checkValidity()).toBe(false)
  })

  it('sale en inglés cuando la UI está en inglés', async () => {
    await i18n.changeLanguage('en')
    render(<DateTimePicker id="d" value="2026-11-04T17:55" onChange={() => {}} />)
    expect(screen.getByRole('button')).toHaveTextContent(/Wed, 4 Nov 2026 · 17:55/)
    await userEvent.click(screen.getByRole('button'))
    const dialog = await screen.findByRole('dialog', { name: 'Pick a date and time' })
    expect(within(dialog).getByText('November 2026')).toBeInTheDocument()
  })
})

describe('DatePicker', () => {
  it('elige un día y se cierra', async () => {
    const spy = vi.fn()
    render(<DatePicker id="d" value="" onChange={spy} />)
    await userEvent.click(screen.getByRole('button'))
    const dialog = await popup()
    expect(within(dialog).queryByRole('textbox')).not.toBeInTheDocument() // sin hora
    await userEvent.click(within(dialog).getByRole('button', { name: 'Hoy' }))
    expect(spy).toHaveBeenCalledWith(expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })
})

describe('TimeInput', () => {
  it('completa los minutos al salir de la hora y se vacía del todo', async () => {
    const spy = vi.fn()
    function Wrapper() {
      const [v, setV] = useState('')
      return (
        <TimeInput
          value={v}
          onChange={(x) => {
            spy(x)
            setV(x)
          }}
        />
      )
    }
    render(<Wrapper />)
    const hours = screen.getByRole('textbox', { name: 'Horas' })
    await userEvent.type(hours, '9')
    expect(spy).not.toHaveBeenCalled() // un dígito: se espera
    await userEvent.tab() // pasa a los minutos: aún no se completa
    expect(spy).not.toHaveBeenCalled()
    await userEvent.tab() // sale de la hora: minutos a 00
    expect(spy).toHaveBeenLastCalledWith('09:00')
    await userEvent.clear(hours)
    await userEvent.clear(screen.getByRole('textbox', { name: 'Minutos' }))
    await userEvent.tab()
    expect(spy).toHaveBeenLastCalledWith('')
  })
})
