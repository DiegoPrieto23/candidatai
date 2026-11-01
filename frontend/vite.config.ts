/// <reference types="vitest/config" />
import { readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { gzipSync } from 'node:zlib'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { visualizer } from 'rollup-plugin-visualizer'
import { defineConfig, searchForWorkspaceRoot, type Plugin } from 'vite'
import { UNUSED_ICON_WEIGHTS } from './src/lib/iconWeights.ts'

/**
 * Junto a cada fichero de texto de `dist/assets`, su versión `.gz`: la API la sirve tal cual a quien
 * admite gzip, sin gastar CPU en comprimir en cada petición (en local, eso tardaba más que lo que
 * ahorraba).
 */
function precompress(): Plugin {
  return {
    name: 'candidatai-precompress',
    apply: 'build',
    writeBundle(options, bundle) {
      for (const fileName of Object.keys(bundle)) {
        if (!/^assets\/.+\.(js|css|svg|json)$/.test(fileName)) continue
        const path = join(options.dir ?? 'dist', fileName)
        writeFileSync(`${path}.gz`, gzipSync(readFileSync(path), { level: 9 }))
      }
    },
  }
}

// La entrada de un peso en la definición de un icono de Phosphor (`dist/defs/<Icono>.es.js`):
// `[ "light", <svg> ]` dentro de su `new Map([...])`.
const ICON_WEIGHT_ENTRY = new RegExp(
  String.raw`\r?\n  \[\r?\n    "(${UNUSED_ICON_WEIGHTS.join('|')})",[\s\S]*?\r?\n  \],?`,
  'g',
)

/**
 * Quita de cada icono de Phosphor los pesos que la app no usa (`src/lib/iconWeights.ts`): los iconos
 * de la barra lateral y de Inicio, que se descargan al arrancar, pesan un tercio menos. Si la
 * librería cambia el formato y no se encuentran, el build falla en vez de no quitar nada.
 */
function pruneIconWeights(): Plugin {
  return {
    name: 'candidatai-prune-icon-weights',
    apply: 'build',
    transform(code, id) {
      if (!/[\\/]@phosphor-icons[\\/]react[\\/]dist[\\/]defs[\\/]/.test(id)) return null
      const removed = (code.match(ICON_WEIGHT_ENTRY) ?? []).length
      const pruned = code.replace(ICON_WEIGHT_ENTRY, '')
      if (removed !== UNUSED_ICON_WEIGHTS.length) {
        throw new Error(`No se reconocen los pesos de ${id}: ¿ha cambiado el formato de Phosphor?`)
      }
      return { code: pruned, map: null }
    },
  }
}

/**
 * En `index.html`, un `modulepreload` del chunk de textos del idioma con el que arrancará la app:
 * así se descarga a la vez que el `index` y no cuando este ya ha llegado y lo pide. Solo el del
 * idioma en uso (el otro pesa lo mismo y no hace falta). Elige igual que `detectLanguage` de
 * `src/lib/i18n.ts`: el guardado, si no el del navegador, si no inglés.
 */
function preloadLanguage(): Plugin {
  return {
    name: 'candidatai-preload-language',
    apply: 'build',
    transformIndexHtml: {
      order: 'post',
      handler(_html, { bundle }) {
        const chunks: Record<string, string> = {}
        for (const file of Object.values(bundle ?? {})) {
          const language = file.type === 'chunk' ? /^locale-(.+)$/.exec(file.name)?.[1] : undefined
          if (language) chunks[language] = `/${file.fileName}`
        }
        if (Object.keys(chunks).length === 0) return
        const script = `(function(){var c=${JSON.stringify(chunks)},l;try{l=localStorage.getItem('cai-language')}catch(e){}
if(!c[l]){var b=((navigator.languages&&navigator.languages[0])||navigator.language||'').toLowerCase().split('-')[0];l=c[b]?b:'en'}
var k=document.createElement('link');k.rel='modulepreload';k.crossOrigin='';k.href=c[l];document.head.appendChild(k)})()`
        return [{ tag: 'script', children: script, injectTo: 'head' }]
      },
    },
  }
}

// Qué pesa cada chunk: `ANALYZE=1 pnpm build` deja `stats.html` (y `stats.json` con
// `ANALYZE=json`) junto a `dist/`.
const analyze = process.env.ANALYZE

// `src/locales/<idioma>/<espacio>.json`.
const LOCALE_FILE = /[\\/]src[\\/]locales[\\/]([^\\/]+)[\\/]([^\\/]+)\.json$/

/** El chunk de los textos de cada idioma, menos los que se importan siempre. */
function localeChunk(id: string): string | null {
  const [, language, namespace] = LOCALE_FILE.exec(id) ?? []
  if (!language) return null
  // `common` (el menú de idioma enseña el nombre de todos) y `es/labels`, de donde
  // `src/lib/labels.ts` saca sus claves: van con el código que los usa.
  if (namespace === 'common' || (language === 'es' && namespace === 'labels')) return null
  return `locale-${language}`
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    precompress(),
    preloadLanguage(),
    pruneIconWeights(),
    !!analyze &&
      visualizer({
        filename: analyze === 'json' ? 'stats.json' : 'stats.html',
        template: analyze === 'json' ? 'raw-data' : 'treemap',
        gzipSize: true,
      }),
  ],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  build: {
    rolldownOptions: {
      output: {
        codeSplitting: {
          // Los textos de cada idioma, en un solo chunk que se pide al usarlo (`src/locales`).
          groups: [{ name: localeChunk }],
        },
      },
    },
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true, // la API solo admite CORS desde este origen exacto
    // Los tests de la extensión (`src/extension/`) leen sus ficheros de `../extension`.
    fs: { allow: [searchForWorkspaceRoot(process.cwd()), '../extension'] },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    // Provisional (fase 23.3): con toda la suite en paralelo en Windows, algunas páginas tardan más
    // de 5 s (cada una pinta la barra lateral). Por separado pasan en < 2 s.
    testTimeout: 15_000,
  },
})
