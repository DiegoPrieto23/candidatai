/**
 * Idioma de la UI (fase 23.6), con i18next. Se elige así: el guardado en `cai-language`; si no hay,
 * el del navegador (`es*` → español; cualquier otro → inglés). Cambiar de idioma no recarga la
 * página y actualiza `<html lang>`.
 */
import { useCallback, useSyncExternalStore, type ReactNode } from 'react'
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import { LANGUAGES, NAMESPACES, SOURCE_LANGUAGE, loadTexts } from '@/locales'

export type Language = string

const STORAGE_KEY = 'cai-language'
const FALLBACK_LANGUAGE = 'en'

/** El locale de `Intl` de cada idioma (fechas y números). */
const INTL_LOCALE: Record<string, string> = { es: 'es-ES', en: 'en-GB' }

function storedLanguage(): Language | null {
  try {
    const value = localStorage.getItem(STORAGE_KEY)
    return value && LANGUAGES.includes(value) ? value : null
  } catch {
    return null
  }
}

/** El idioma con el que arranca la app. */
export function detectLanguage(): Language {
  const stored = storedLanguage()
  if (stored) return stored
  const browser = typeof navigator !== 'undefined' ? (navigator.languages?.[0] ?? navigator.language ?? '') : ''
  const base = browser.toLowerCase().split('-')[0]
  return LANGUAGES.includes(base) ? base : FALLBACK_LANGUAGE
}

void i18n.use(initReactI18next).init({
  resources: {}, // los textos llegan con `loadLanguage`
  partialBundledLanguages: true,
  lng: detectLanguage(),
  // Solo cuenta si su idioma ya se ha descargado: no se pide aparte, porque un test exige que todos
  // los idiomas tengan las mismas claves que el español.
  fallbackLng: SOURCE_LANGUAGE,
  supportedLngs: [...LANGUAGES],
  ns: [...NAMESPACES],
  defaultNS: 'common',
  interpolation: { escapeValue: false }, // React ya escapa
  returnNull: false,
  initAsync: false,
})

const loading = new Map<Language, Promise<void>>()

/** Descarga los textos de un idioma, una sola vez (si falla, el siguiente intento lo repite). */
export function loadLanguage(language: Language): Promise<void> {
  let pending = loading.get(language)
  if (!pending) {
    pending = loadTexts(language).then(
      (texts) => {
        for (const [namespace, bundle] of Object.entries(texts)) {
          i18n.addResourceBundle(language, namespace, bundle, true, true)
        }
      },
      (error: unknown) => {
        loading.delete(language)
        throw error
      },
    )
    loading.set(language, pending)
  }
  return pending
}

/** Los textos del idioma con el que arranca: `main.tsx` espera a tenerlos antes de pintar. */
export const i18nReady = loadLanguage(i18n.language)

function applyLanguage(language: string) {
  if (typeof document !== 'undefined') document.documentElement.lang = language
}
applyLanguage(i18n.language)
i18n.on('languageChanged', applyLanguage)

let requested: Language = i18n.language

/** Cambia el idioma (tras descargar sus textos) y lo recuerda. */
export function setLanguage(language: Language): void {
  requested = language
  loadLanguage(language)
    .then(() => {
      // Si mientras tanto se eligió otro, manda el último.
      if (requested !== language) return
      try {
        localStorage.setItem(STORAGE_KEY, language)
      } catch {
        // Sin almacenamiento (ventana privada): el idioma dura lo que la pestaña.
      }
      return i18n.changeLanguage(language)
    })
    .catch(() => {
      // Sin red (la app parada): se queda el idioma de ahora.
    })
}

function subscribe(notify: () => void): () => void {
  i18n.on('languageChanged', notify)
  return () => i18n.off('languageChanged', notify)
}

const currentLanguage = () => i18n.resolvedLanguage ?? i18n.language

export function useLanguage() {
  const language = useSyncExternalStore(subscribe, currentLanguage, currentLanguage)
  const change = useCallback((next: Language) => setLanguage(next), [])
  return { language, setLanguage: change, languages: LANGUAGES }
}

/** El locale de `Intl` del idioma activo: `es-ES` o `en-GB`. */
export function intlLocale(): string {
  return INTL_LOCALE[currentLanguage()] ?? currentLanguage()
}

/**
 * Un texto que genera el servidor (en español) con un código estable que la UI sí traduce: en
 * español, el texto tal cual; en otro idioma, la etiqueta traducida del código y el texto del
 * servidor como detalle.
 */
export function serverText(label: string | null | undefined, message: string): string {
  if (currentLanguage() === SOURCE_LANGUAGE || !label) return message
  return `${label}: ${message}`
}

/** La etiqueta traducida de un código del servidor (`ns:grupo.código`), o `null` si no la hay. */
export function codeLabel(key: string): string | null {
  return i18n.exists(key) ? String(i18n.t(key as never)) : null
}

/** «a, b y c» / «a, b and c», en el idioma activo. */
export function formatList(parts: readonly string[]): string {
  return new Intl.ListFormat(intlLocale(), { type: 'conjunction' }).format(parts)
}

/** Como `formatList`, pero con elementos de React (enlaces…) entre las comas y la «y». */
export function joinNodes(parts: readonly ReactNode[]): ReactNode[] {
  const placeholders = parts.map((_, i) => `\u0000${i}\u0000`)
  return new Intl.ListFormat(intlLocale(), { type: 'conjunction' })
    .formatToParts(placeholders)
    .map((part) => (part.type === 'element' ? parts[Number(part.value.slice(1, -1))] : part.value))
}

export { i18n, SOURCE_LANGUAGE }
