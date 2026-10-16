import { i18n } from '@/lib/i18n'

/**
 * Las notas del desglose del score las escribe el servidor en español, sin código (fase 23.5b).
 * Son pocas y de texto fijo: aquí se reconocen y se traducen. Una que no se reconozca se enseña
 * tal cual. Mantener al día con `backend/app/services/matching/scorer.py` y `embeddings.py`.
 */
const KNOWN: readonly [RegExp, string][] = [
  [/^Similitud semántica desactivada \(CAI_EMBEDDINGS=off\)\.$/, 'off'],
  [/^Similitud semántica no disponible: instala el extra/, 'notInstalled'],
  [/^Similitud semántica no disponible\.$/, 'unavailable'],
  [/^No se pudo calcular la similitud semántica \((?<error>.+)\)\.$/s, 'failed'],
  [/^La oferta no lista skills obligatorias:/, 'noMust'],
  [/^La oferta no lista skills deseables:/, 'noNice'],
]

export function scoreNote(note: string): string {
  for (const [pattern, key] of KNOWN) {
    const match = pattern.exec(note)
    if (match) return String(i18n.t(`match:notes.${key}` as never, { error: match.groups?.error ?? '' } as never))
  }
  return note
}
