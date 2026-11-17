/** Filtros de la lista de skills de «Mi perfil»: por nivel y por categoría, combinados. */

/** Con más categorías que estas, el filtro pasa de chips a un desplegable con búsqueda. */
export const CATEGORY_CHIPS_MAX = 8

/** Valores de «Sin categoría» y «Todas». No chocan con ninguna categoría real (ni con una llamada
 *  «All»): las claves de las categorías van recortadas y estos empiezan por un espacio. */
export const NO_CATEGORY = ' none'
export const ALL = ' all'

interface FilterableSkill {
  level: string
  category?: string | null
}

/** Clave de una categoría: sin espacios sobrantes ni mayúsculas, para que «Cloud» y «cloud » sean la misma. */
export function categoryKey(category: string | null | undefined): string {
  const key = (category ?? '').trim().replace(/\s+/g, ' ').toLocaleLowerCase()
  return key || NO_CATEGORY
}

export interface CategoryOption {
  key: string
  /** Como aparece la primera vez en el perfil; vacío para «Sin categoría». */
  label: string
}

/** Las categorías del perfil en el orden en que aparecen, con «Sin categoría» al final si hace falta. */
export function categoriesOf(skills: FilterableSkill[]): CategoryOption[] {
  const seen = new Map<string, string>()
  let uncategorized = false
  for (const skill of skills) {
    const key = categoryKey(skill.category)
    if (key === NO_CATEGORY) uncategorized = true
    else if (!seen.has(key)) seen.set(key, (skill.category ?? '').trim().replace(/\s+/g, ' '))
  }
  const options = [...seen].map(([key, label]) => ({ key, label }))
  return uncategorized ? [...options, { key: NO_CATEGORY, label: '' }] : options
}

export interface SkillFilter {
  level: string
  category: string
}

export const NO_FILTER: SkillFilter = { level: ALL, category: ALL }

export function isFiltered(filter: SkillFilter): boolean {
  return filter.level !== ALL || filter.category !== ALL
}

export function matches(skill: FilterableSkill, filter: SkillFilter): boolean {
  return (
    (filter.level === ALL || skill.level === filter.level) &&
    (filter.category === ALL || categoryKey(skill.category) === filter.category)
  )
}

/** Cuántas quedarían al elegir ese nivel, con la categoría elegida (y al revés). */
export function countWith(skills: FilterableSkill[], filter: SkillFilter): number {
  return skills.filter((skill) => matches(skill, filter)).length
}
