import { useState } from 'react'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { matchesQuery } from '@/lib/text'
import { Combobox, type ComboboxOption } from './combobox'

const MANY: ComboboxOption[] = [
  { value: '1', label: 'Brétema Analytics', description: 'Data Engineer', meta: 'En proceso' },
  { value: '2', label: 'Néboa Data', description: 'Analytics Engineer', meta: 'Aplicada' },
  ...Array.from({ length: 8 }, (_, i) => ({ value: String(10 + i), label: `Empresa ${i}`, description: `Puesto ${i}` })),
]
const FEW = MANY.slice(0, 3)

function Controlled({ options = MANY, spy }: { options?: ComboboxOption[]; spy?: (v: string) => void }) {
  const [value, setValue] = useState<string | null>(null)
  return (
    <>
      <label htmlFor="job">Oferta</label>
      <Combobox
        id="job"
        label="Oferta"
        value={value}
        onChange={(v) => {
          spy?.(v)
          setValue(v)
        }}
        options={options}
        placeholder="Elige una oferta…"
        searchLabel="Busca por empresa o puesto"
        noMatch={(q) => `Ninguna oferta coincide con «${q}»`}
      />
    </>
  )
}

const trigger = () => screen.getByRole('button', { name: 'Oferta' })
const search = () => screen.findByRole('combobox', { name: 'Busca por empresa o puesto' })

describe('matchesQuery', () => {
  it('busca todas las palabras, sin tildes ni mayúsculas', () => {
    expect(matchesQuery('Brétema Analytics Data Engineer', 'bretema')).toBe(true)
    expect(matchesQuery('Néboa Data Analytics Engineer', 'NEBOA analytics')).toBe(true)
    expect(matchesQuery('Néboa Data Analytics Engineer', 'neboa backend')).toBe(false)
    expect(matchesQuery('Lo que sea', '  ')).toBe(true)
  })
})

describe('Combobox', () => {
  it('pide elegir mientras está vacío y enseña empresa y puesto al elegir', async () => {
    render(<Controlled options={FEW} />)
    expect(trigger()).toHaveTextContent('Elige una oferta…')
    await userEvent.click(trigger())
    const list = await screen.findByRole('listbox', { name: 'Oferta' })
    const option = within(list).getByRole('option', { name: /Néboa Data/ })
    expect(option).toHaveTextContent('Analytics Engineer')
    expect(option).toHaveTextContent('Aplicada')
    await userEvent.click(option)
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
    expect(trigger()).toHaveTextContent('Néboa Data · Analytics Engineer')
    expect(trigger()).toHaveFocus()
  })

  it('con pocas opciones no hay caja de búsqueda y se elige con el teclado', async () => {
    const spy = vi.fn()
    render(<Controlled options={FEW} spy={spy} />)
    trigger().focus()
    await userEvent.keyboard('{ArrowDown}')
    const list = await screen.findByRole('listbox', { name: 'Oferta' })
    await waitFor(() => expect(list).toHaveFocus())
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
    await userEvent.keyboard('{ArrowDown}{ArrowDown}{ArrowDown}')
    // No pasa de la última.
    expect(list).toHaveAttribute('aria-activedescendant', within(list).getAllByRole('option')[2].id)
    await userEvent.keyboard('{Home}{ArrowDown}{Enter}')
    expect(spy).toHaveBeenCalledWith('2')
    expect(trigger()).toHaveFocus()
  })

  it('con muchas, filtra mientras escribes y marca la opción activa', async () => {
    render(<Controlled />)
    await userEvent.click(trigger())
    const box = await search()
    await waitFor(() => expect(box).toHaveFocus())
    expect(box).toHaveAttribute('aria-expanded', 'true')
    await userEvent.type(box, 'engineer')
    const options = within(screen.getByRole('listbox')).getAllByRole('option')
    expect(options).toHaveLength(2)
    expect(box).toHaveAttribute('aria-activedescendant', options[0].id)
    await userEvent.keyboard('{ArrowDown}')
    expect(box).toHaveAttribute('aria-activedescendant', options[1].id)
    await userEvent.keyboard('{Enter}')
    expect(trigger()).toHaveTextContent('Néboa Data · Analytics Engineer')
  })

  it('la etapa no cuenta en la búsqueda; Inicio y Fin mueven el texto y las flechas no se salen', async () => {
    render(<Controlled />)
    await userEvent.click(trigger())
    const box = await search()
    await userEvent.type(box, 'proceso')
    expect(screen.queryByRole('option')).not.toBeInTheDocument()
    await userEvent.clear(box)
    const options = within(screen.getByRole('listbox')).getAllByRole('option')
    await userEvent.keyboard('{ArrowUp}')
    expect(box).toHaveAttribute('aria-activedescendant', options[0].id)
    await userEvent.keyboard('{ArrowDown}{End}')
    expect(box).toHaveAttribute('aria-activedescendant', options[1].id)
  })

  it('con 7 opciones se recorre sin buscar y con 8 aparece la caja; las flechas del botón lo abren', async () => {
    const { unmount } = render(<Controlled options={MANY.slice(0, 7)} />)
    trigger().focus()
    await userEvent.keyboard('{ArrowUp}')
    expect(await screen.findByRole('listbox')).toBeInTheDocument()
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
    unmount()
    render(<Controlled options={MANY.slice(0, 8)} />)
    trigger().focus()
    await userEvent.keyboard('{ArrowDown}')
    await waitFor(async () => expect(await search()).toHaveFocus())
  })

  it('en la lista sin búsqueda, la barra espaciadora elige', async () => {
    const spy = vi.fn()
    render(<Controlled options={FEW} spy={spy} />)
    await userEvent.click(trigger())
    await waitFor(() => expect(screen.getByRole('listbox')).toHaveFocus())
    await userEvent.keyboard('{End} ')
    expect(spy).toHaveBeenCalledWith(FEW[2].value)
  })

  it('si la lista se acorta con el selector abierto, la opción activa sigue siendo válida', async () => {
    const spy = vi.fn()
    const props = {
      id: 'job',
      label: 'Oferta',
      value: null,
      onChange: spy,
      placeholder: 'Elige una oferta…',
      searchLabel: 'Busca por empresa o puesto',
      noMatch: (q: string) => q,
    }
    const { rerender } = render(<Combobox {...props} options={FEW} />)
    await userEvent.click(screen.getByRole('button'))
    const list = await screen.findByRole('listbox')
    await waitFor(() => expect(list).toHaveFocus())
    await userEvent.keyboard('{End}')
    rerender(<Combobox {...props} options={FEW.slice(0, 1)} />)
    expect(list).toHaveAttribute('aria-activedescendant', within(list).getByRole('option').id)
    await userEvent.keyboard('{Enter}')
    expect(spy).toHaveBeenCalledWith(FEW[0].value)
  })

  it('sin resultados lo dice con lo escrito, e Intro no elige nada', async () => {
    const spy = vi.fn()
    render(<Controlled spy={spy} />)
    await userEvent.click(trigger())
    await userEvent.type(await search(), 'zzz')
    expect(screen.getByText('Ninguna oferta coincide con «zzz»')).toBeInTheDocument()
    expect(screen.queryByRole('option')).not.toBeInTheDocument()
    await userEvent.keyboard('{Enter}')
    expect(spy).not.toHaveBeenCalled()
  })

  it('Esc cierra sin elegir y devuelve el foco al botón; al reabrir, la búsqueda está vacía', async () => {
    const spy = vi.fn()
    render(<Controlled spy={spy} />)
    await userEvent.click(trigger())
    await userEvent.type(await search(), 'neboa')
    await userEvent.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('listbox')).not.toBeInTheDocument())
    expect(trigger()).toHaveFocus()
    expect(spy).not.toHaveBeenCalled()
    await userEvent.click(trigger())
    expect(await search()).toHaveValue('')
  })

  it('la elegida lleva su marca al reabrir', async () => {
    render(<Controlled options={FEW} />)
    await userEvent.click(trigger())
    await userEvent.click(within(await screen.findByRole('listbox')).getByRole('option', { name: /Brétema/ }))
    await userEvent.click(trigger())
    const list = await screen.findByRole('listbox')
    expect(within(list).getByRole('option', { name: /Brétema/ })).toHaveAttribute('aria-selected', 'true')
    expect(within(list).getByRole('option', { name: /Néboa/ })).toHaveAttribute('aria-selected', 'false')
  })
})
