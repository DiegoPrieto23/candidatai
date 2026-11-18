/** La web de un portal o una empresa (para su icono): la suya o la de su primera búsqueda. */
export function hostOf(source: { website?: string | null; browse?: { search_urls: string[] } | null }): string | null {
  const url = source.website ?? source.browse?.search_urls[0]
  if (!url) return null
  try {
    return new URL(url).hostname
  } catch {
    return null
  }
}
