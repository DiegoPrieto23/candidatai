/**
 * Núcleo de «Mi perfil» editable (fase 25.7b): el perfil del fichero, un borrador por bloque y el
 * guardado por secciones contra `PUT /profile/sections/{section}` con el `file_hash` que se leyó.
 *
 * - Cada bloque edita una o varias secciones (o una parte de `preferences`) y se guarda solo.
 * - Los errores de validación llegan con la ruta del campo (`experience.0.start`) y se enseñan en
 *   ese campo; `conflict` (el fichero cambió) pide recargar y `referenced`, quitar antes la cita.
 * - Mientras haya cambios sin guardar, avisa al cerrar la pestaña y al seguir un enlace de la app.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { ApiError } from '@/api/client'
import { useSaveProfileSection, type EditableProfile, type ProfileSectionName } from '@/api/queries'
import { errorMessage } from '@/lib/errors'
import type { ProfileData } from './types'

interface EditorState {
  state: EditableProfile
  profile: ProfileData
  setDirty: (block: string, dirty: boolean) => void
  dirtyCount: number
  reload: () => void
}

const EditorContext = createContext<EditorState | null>(null)

export function useProfileState(): EditorState {
  const value = useContext(EditorContext)
  if (!value) throw new Error('useProfileState outside ProfileEditorProvider')
  return value
}

/** Avisa de los cambios sin guardar: al cerrar la pestaña y al pulsar un enlace de la app. */
function useUnsavedGuard(dirty: boolean, message: string) {
  useEffect(() => {
    if (!dirty) return
    const onUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault()
      event.returnValue = ''
    }
    // `BrowserRouter` no tiene `useBlocker`: se intercepta el clic en los enlaces internos.
    const onClick = (event: MouseEvent) => {
      const link = (event.target as Element | null)?.closest?.('a[href]')
      const href = link?.getAttribute('href') ?? ''
      if (!link || link.getAttribute('target') === '_blank' || href.startsWith('#') || link.hasAttribute('download')) return
      if (!window.confirm(message)) {
        event.preventDefault()
        event.stopPropagation()
      }
    }
    window.addEventListener('beforeunload', onUnload)
    document.addEventListener('click', onClick, true)
    return () => {
      window.removeEventListener('beforeunload', onUnload)
      document.removeEventListener('click', onClick, true)
    }
  }, [dirty, message])
}

export function ProfileEditorProvider({ state, reload, children }: { state: EditableProfile; reload: () => void; children: ReactNode }) {
  const { t } = useTranslation('profileEditor')
  const [dirty, setDirtySet] = useState<ReadonlySet<string>>(new Set())
  const setDirty = useCallback((block: string, value: boolean) => {
    setDirtySet((prev) => {
      if (prev.has(block) === value) return prev
      const next = new Set(prev)
      if (value) next.add(block)
      else next.delete(block)
      return next
    })
  }, [])
  useUnsavedGuard(dirty.size > 0, t('unsaved.confirm'))
  const value = useMemo(
    () => ({ state, profile: (state.profile ?? {}) as ProfileData, setDirty, dirtyCount: dirty.size, reload }),
    [state, setDirty, dirty.size, reload],
  )
  return <EditorContext.Provider value={value}>{children}</EditorContext.Provider>
}

type Sections = Partial<Record<ProfileSectionName, unknown>>

export interface BlockEditor<T> {
  draft: T
  update: (change: (draft: T) => T) => void
  dirty: boolean
  saving: boolean
  /** Errores por ruta (`experience.0.start`). */
  errors: ReadonlyMap<string, string>
  message: string | null
  conflict: boolean
  saved: boolean
  warnings: string[]
  preview: string | null
  save: () => void
  confirmPreview: () => void
  cancelPreview: () => void
  discard: () => void
}

const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b)

/**
 * Un bloque del formulario. `read` saca su borrador del perfil y `write` dice qué secciones
 * enteras se guardan con él (las demás claves de cada sección salen del perfil leído). Con
 * `preview`, primero se enseña el diff (`dry_run`) y se guarda al confirmarlo.
 */
export function useBlockEditor<T>(
  id: string,
  read: (profile: ProfileData) => T,
  write: (draft: T, profile: ProfileData) => Sections,
  options: { preview?: boolean } = {},
): BlockEditor<T> {
  const { t } = useTranslation('profileEditor')
  const { state, profile, setDirty, reload } = useProfileState()
  const mutation = useSaveProfileSection()
  const server = useMemo(() => read(profile), [profile, read])
  const [draft, setDraft] = useState<T>(server)
  const [errors, setErrors] = useState<ReadonlyMap<string, string>>(new Map())
  const [message, setMessage] = useState<string | null>(null)
  const [conflict, setConflict] = useState(false)
  const [saved, setSaved] = useState(false)
  const [warnings, setWarnings] = useState<string[]>([])
  const [preview, setPreview] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const dirty = !same(draft, server)
  const lastServer = useRef(server)
  // Tras guardar, lo que vuelve del servidor (con los ids que puso) pasa a ser el borrador.
  const adoptNext = useRef(false)

  // Si el perfil cambia (otro bloque guardó, se deshizo) y este bloque no tiene cambios, se
  // pone al día; con cambios, se conservan.
  useEffect(() => {
    if (same(lastServer.current, server)) return
    const adopt = adoptNext.current
    adoptNext.current = false
    setDraft((current) => (adopt || same(current, lastServer.current) ? server : current))
    lastServer.current = server
  }, [server])
  useEffect(() => setDirty(id, dirty), [id, dirty, setDirty])
  useEffect(() => () => setDirty(id, false), [id, setDirty])

  const changedSections = useCallback((): [ProfileSectionName, unknown][] => {
    const next = write(draft, profile)
    return (Object.entries(next) as [ProfileSectionName, unknown][]).filter(([section, content]) => !same(content, profile[section]))
  }, [draft, profile, write])

  const fail = (error: unknown) => {
    const map = new Map<string, string>()
    if (error instanceof ApiError) {
      if (error.type === 'conflict') setConflict(true)
      if (error.type === 'validation_error') for (const d of error.details) map.set(d.field, d.reason)
    }
    setErrors(map)
    setMessage(error instanceof ApiError && error.type === 'validation_error' ? t('errors.validation') : errorMessage(error))
  }

  const run = async (dryRun: boolean) => {
    const sections = changedSections()
    if (sections.length === 0) return
    setSaving(true)
    setErrors(new Map())
    setMessage(null)
    setSaved(false)
    let hash = state.file_hash
    const diffs: string[] = []
    const notes: string[] = []
    try {
      for (const [section, content] of sections) {
        const result = await mutation.mutateAsync({ section, file_hash: hash, content, dry_run: dryRun })
        if (!dryRun) hash = result.file_hash
        if (result.diff) diffs.push(result.diff)
        notes.push(...result.warnings)
      }
      if (dryRun) {
        setPreview(diffs.join('\n') || t('preview.noChanges'))
      } else {
        adoptNext.current = true
        setSaved(true)
        setWarnings(notes)
        setPreview(null)
      }
    } catch (error) {
      fail(error)
      setPreview(null)
      // Si ya se guardó alguna sección del bloque, el fichero cambió: se recarga y se dice.
      if (!dryRun && hash !== state.file_hash) {
        setMessage(t('errors.partial'))
        reload()
      }
    } finally {
      setSaving(false)
    }
  }

  return {
    draft,
    update: (change) => {
      setSaved(false)
      setDraft((current) => change(current))
    },
    dirty,
    saving,
    errors,
    message,
    conflict,
    saved,
    warnings,
    preview,
    save: () => void run(Boolean(options.preview)),
    confirmPreview: () => void run(false),
    cancelPreview: () => setPreview(null),
    discard: () => {
      setDraft(server)
      setErrors(new Map())
      setMessage(null)
      setConflict(false)
      setPreview(null)
      if (conflict) reload()
    },
  }
}

/** Una copia que se puede cambiar sin tocar el original (los borradores son objetos JSON). */
export function clone<T>(value: T): T {
  return value === undefined ? value : (JSON.parse(JSON.stringify(value)) as T)
}

/** Cambia el elemento `index` de una lista sin mutarla. */
export function replaceAt<T>(list: T[], index: number, item: T): T[] {
  return list.map((current, i) => (i === index ? item : current))
}

export function removeAt<T>(list: T[], index: number): T[] {
  return list.filter((_, i) => i !== index)
}

export function move<T>(list: T[], index: number, delta: number): T[] {
  const target = index + delta
  if (target < 0 || target >= list.length) return list
  const next = [...list]
  ;[next[index], next[target]] = [next[target], next[index]]
  return next
}
