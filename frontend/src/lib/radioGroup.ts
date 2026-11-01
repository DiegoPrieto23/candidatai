import { useRef, type KeyboardEvent } from 'react'

/**
 * Una fila de filtros como un grupo de opciones (`radiogroup`): un solo Tab entra en el grupo (en la
 * opción elegida) y otro sale; las flechas, Inicio y Fin pasan de una a otra y la eligen, como en un
 * grupo de radio del sistema. Así nueve filtros no son nueve paradas de Tab.
 */
export function useRadioGroup<T>(
  values: readonly T[],
  selected: T,
  // `byKeys`: con las flechas, para no apilar una entrada del historial por pulsación.
  onSelect: (value: T, byKeys: boolean) => void,
) {
  const items = useRef<(HTMLElement | null)[]>([])
  const current = Math.max(0, values.indexOf(selected))

  function move(event: KeyboardEvent, from: number) {
    const last = values.length - 1
    const next =
      event.key === 'ArrowRight' || event.key === 'ArrowDown'
        ? (from + 1) % values.length
        : event.key === 'ArrowLeft' || event.key === 'ArrowUp'
          ? (from - 1 + values.length) % values.length
          : event.key === 'Home'
            ? 0
            : event.key === 'End'
              ? last
              : null
    if (next === null) return
    event.preventDefault()
    items.current[next]?.focus()
    onSelect(values[next]!, true)
  }

  return {
    group: { role: 'radiogroup' as const },
    item: (value: T, index: number) => ({
      role: 'radio' as const,
      'aria-checked': index === current,
      tabIndex: index === current ? 0 : -1,
      ref: (el: HTMLElement | null) => {
        items.current[index] = el
      },
      onClick: () => onSelect(value, false),
      onKeyDown: (event: KeyboardEvent) => move(event, index),
    }),
  }
}
