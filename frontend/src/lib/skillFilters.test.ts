import { describe, expect, it } from 'vitest'
import { ALL, NO_CATEGORY, NO_FILTER, categoriesOf, categoryKey, countWith, isFiltered, matches } from './skillFilters'

const skills = [
  { level: 'F', category: 'Lenguajes' },
  { level: 'C', category: 'Cloud y DWH' },
  { level: 'F', category: ' lenguajes ' },
  { level: 'B', category: null },
  { level: 'C+', category: '' },
]

describe('skillFilters', () => {
  it('agrupa las categorías sin mayúsculas ni espacios, en el orden en que aparecen, y «Sin categoría» al final', () => {
    expect(categoriesOf(skills)).toEqual([
      { key: 'lenguajes', label: 'Lenguajes' },
      { key: 'cloud y dwh', label: 'Cloud y DWH' },
      { key: NO_CATEGORY, label: '' },
    ])
    expect(categoriesOf([{ level: 'F', category: 'IA' }])).toEqual([{ key: 'ia', label: 'IA' }])
    expect(categoryKey('  ')).toBe(NO_CATEGORY)
    // Una categoría llamada «All» no se confunde con «Todas».
    expect(categoryKey('All')).not.toBe(ALL)
    expect(countWith([{ level: 'F', category: 'All' }, { level: 'F', category: 'IA' }], { level: ALL, category: categoryKey('All') })).toBe(1)
  })

  it('combina nivel y categoría y cuenta lo que quedaría', () => {
    expect(isFiltered(NO_FILTER)).toBe(false)
    expect(countWith(skills, { level: 'F', category: 'lenguajes' })).toBe(2)
    expect(countWith(skills, { level: 'F', category: 'cloud y dwh' })).toBe(0)
    expect(countWith(skills, { level: ALL, category: NO_CATEGORY })).toBe(2)
    expect(countWith(skills, { level: 'B', category: ALL })).toBe(1)
    expect(matches(skills[3], { level: 'B', category: NO_CATEGORY })).toBe(true)
    expect(isFiltered({ level: ALL, category: 'ia' })).toBe(true)
  })
})
