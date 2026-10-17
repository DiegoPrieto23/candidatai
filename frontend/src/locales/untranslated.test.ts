import { describe, expect, it } from 'vitest'

/**
 * Que no se cuelen textos en español fuera de `src/locales/` (fase 23.6). Es una heurística: busca
 * en el código (sin comentarios) cadenas y textos JSX con letras acentuadas, «¿», «¡», ««» o
 * palabras muy frecuentes de la UI en español. Las rutas (`/por-revisar`) y los nombres de carpetas
 * de datos (`empresas`) no son textos de la UI.
 */
const sources = import.meta.glob<string>(['/src/**/*.{ts,tsx}', '!/src/**/*.test.{ts,tsx}', '!/src/test/**'], {
  query: '?raw',
  import: 'default',
  eager: true,
})

const SPANISH = /[áéíóúñÁÉÍÓÚÑ¿¡«»]|\b(oferta|ofertas|candidatura|candidaturas|guardar|cancelar|cerrar|abrir|ver|buscar|descartar|añadir|pendiente|pendientes|perfil|correo|plantilla|entrevista|sin|con|para|tu|tus|el|la|los|las|del|de|una|uno|que|hay|nueva|nuevo|todas|todos|siguiente|anterior|volver|enviar|enviada)\b/i

/** Cadenas que son datos, no textos: rutas, carpetas, claves y valores que también usa la API. */
const ALLOWED = [
  /^\/[\w\-/?=&.:%{}$]*$/, // rutas internas
  /^(empresas|entrevistas|candidatura|contexto|documentos|plataformas)$/, // carpetas de datos (`OpenFolderButton`)
  /^[a-z0-9_.:-]+$/, // identificadores, claves, ids (en minúsculas)
  /^https?:\/\/\S+$/, // URLs de ejemplo
  /^[a-z0-9.\-/]*<slug>[a-z0-9.\-/]*$/, // dónde está el slug de un ATS (`<slug>.jobs.personio.de`)
]

function stripComments(code: string): string {
  return code
    .replace(/\{\/\*[\s\S]*?\*\/\}/g, '')
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/(^|[^:'"`\\])\/\/.*$/gm, '$1')
}

function suspicious(code: string): string[] {
  const found: string[] = []
  const strings = code.matchAll(/'([^'\n\\]*(?:\\.[^'\n\\]*)*)'|"([^"\n\\]*(?:\\.[^"\n\\]*)*)"|`([^`\\]*(?:\\.[^`\\]*)*)`/g)
  for (const m of strings) {
    const text = m[1] ?? m[2] ?? m[3] ?? ''
    if (!SPANISH.test(text) || ALLOWED.some((re) => re.test(text))) continue
    found.push(text)
  }
  // Texto entre etiquetas JSX: `>Guardar<`.
  for (const m of code.matchAll(/>([^<>{}`]*[A-Za-zÁ-ú][^<>{}`]*)</g)) {
    const text = m[1]!.trim()
    if (text && SPANISH.test(text) && !/[=;()]/.test(text)) found.push(text)
  }
  return found
}

describe('sin textos en español fuera de src/locales', () => {
  it('ningún fichero de la UI tiene textos sin traducir', () => {
    const report: Record<string, string[]> = {}
    for (const [path, code] of Object.entries(sources)) {
      if (path.startsWith('/src/locales/')) continue
      const hits = suspicious(stripComments(code))
      if (hits.length) report[path] = hits
    }
    expect(report).toEqual({})
  })
})
