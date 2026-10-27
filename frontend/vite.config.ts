/// <reference types="vitest/config" />
import { fileURLToPath } from 'node:url'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { visualizer } from 'rollup-plugin-visualizer'
import { defineConfig, searchForWorkspaceRoot } from 'vite'

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
