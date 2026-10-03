/** Palabras del cuerpo de una carta, como las cuenta la app (`\w+` en Unicode). */
export function countWords(paragraphs: string[]): number {
  return paragraphs.reduce((total, text) => total + (text.match(/[\p{L}\p{N}_]+/gu)?.length ?? 0), 0)
}
