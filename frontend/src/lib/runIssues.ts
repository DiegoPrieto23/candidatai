/**
 * Lo que anota un recorrido por un portal no siempre es un fallo: con el código `other`, tu agente
 * apunta lo que conviene saber («leídas 3 de 6 búsquedas»). Se enseñan por separado para que un
 * recorrido que fue bien no parezca roto.
 */
const NOTE_CODE = 'other'

export function splitIssues<T extends { code: string }>(issues: readonly T[]): { problems: T[]; notes: T[] } {
  return {
    problems: issues.filter((issue) => issue.code !== NOTE_CODE),
    notes: issues.filter((issue) => issue.code === NOTE_CODE),
  }
}
