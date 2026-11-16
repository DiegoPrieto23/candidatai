/** Sin tildes, mayúsculas ni signos: «Reino  Unido» y «reino unido» son lo mismo. */
export const fold = (text: string) =>
  text
    .normalize('NFD')
    .replace(/\p{M}/gu, '')
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, ' ')
    .trim()

/**
 * Si el texto contiene todas las palabras de la búsqueda, sin tildes ni mayúsculas. Una búsqueda vacía
 * (o solo de signos) coincide siempre.
 */
export function matchesQuery(text: string, query: string): boolean {
  const haystack = fold(text)
  return fold(query)
    .split(' ')
    .filter(Boolean)
    .every((word) => haystack.includes(word))
}
