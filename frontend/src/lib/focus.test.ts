import { describe, expect, it } from 'vitest'
import { focusArrival } from './focus'

describe('focusArrival', () => {
  it('da el foco y marca el bloque hasta que lo pierde', () => {
    document.body.innerHTML = '<section id="b" tabindex="-1"></section><button>Otro</button>'
    const block = document.getElementById('b')!
    focusArrival(block)
    expect(block).toHaveFocus()
    expect(block).toHaveAttribute('data-arrived')

    document.querySelector('button')!.focus()
    expect(block).not.toHaveAttribute('data-arrived')
  })

  it('no marca lo que no acepta el foco', () => {
    document.body.innerHTML = '<button disabled>Desactivado</button>'
    const button = document.querySelector('button')!
    focusArrival(button)
    expect(button).not.toHaveFocus()
    expect(button).not.toHaveAttribute('data-arrived')
  })

  it('dos llegadas seguidas se quitan con un solo blur', () => {
    document.body.innerHTML = '<section id="b" tabindex="-1"></section><button>Otro</button>'
    const block = document.getElementById('b')!
    focusArrival(block)
    focusArrival(block)
    document.querySelector('button')!.focus()
    expect(block).not.toHaveAttribute('data-arrived')
    focusArrival(block)
    expect(block).toHaveAttribute('data-arrived')
  })

  it('sin destino no hace nada', () => {
    expect(() => focusArrival(null)).not.toThrow()
  })
})
