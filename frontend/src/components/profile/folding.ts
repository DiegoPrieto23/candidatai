/** Qué elementos de las listas de «Mi perfil» están desplegados (ver `fold.tsx`). */
import { useState } from 'react'
import type { BlockEditor } from './editor'

/**
 * Qué elementos de una lista (`prefix`: `projects`, `education`…) están desplegados. Se abren
 * solos el que acabas de añadir y los que tienen un error de validación, para que no quede
 * escondido. Un elemento guardado cambia su clave provisional por su id y vuelve a plegarse.
 */
export function useListFolding<T extends { id?: string }>(block: BlockEditor<T[]>, prefix: string) {
  const [expanded, setExpanded] = useState<ReadonlySet<string>>(new Set())
  const keyOf = (item: T, i: number) => item.id ?? `new-${i}`
  const keys = block.draft.map(keyOf)
  const paths = [...block.errors.keys()]
  const withError = (i: number) => paths.some((k) => k === `${prefix}.${i}` || k.startsWith(`${prefix}.${i}.`))
  const isOpen = (item: T, i: number) => expanded.has(keyOf(item, i)) || withError(i)
  const allOpen = keys.length > 0 && block.draft.every(isOpen)
  return {
    keyOf,
    isOpen,
    allOpen,
    setOpen: (item: T, i: number, open: boolean) =>
      setExpanded((prev) => {
        const next = new Set(prev)
        if (open) next.add(keyOf(item, i))
        else next.delete(keyOf(item, i))
        return next
      }),
    toggleAll: () => setExpanded(allOpen ? new Set() : new Set(keys)),
    /** Al añadir un elemento en `index` (sin id todavía): se abre el nuevo. */
    openNew: (index: number) => setExpanded((prev) => new Set(prev).add(`new-${index}`)),
  }
}

export type ListFolding<T extends { id?: string }> = ReturnType<typeof useListFolding<T>>
