import { useState, type ReactNode } from 'react'
import { Trans, useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { BriefcaseIcon, CheckIcon, MapPinIcon, SlidersHorizontalIcon, StackIcon } from '@phosphor-icons/react'
import { useEditableProfile, useRoleSuggestions, useSaveProfileSection } from '@/api/queries'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import type { Preferences } from '@/components/profile/types'
import { errorMessage } from '@/lib/errors'
import { addPlace, hasItem, placesOf, removePlace } from '@/lib/searchStrip'
import type { SectionFocus } from '@/lib/searchFocus'
import { TagRow } from './TagRow'

const ICON = 'size-4 shrink-0'

/** Lo que dice la línea de abajo tras un cambio: qué se guardó y cómo volver atrás. */
type Notice =
  | { kind: 'added' | 'removed'; item: string; before: Pick<Preferences, 'roles' | 'locations'> }
  | { kind: 'undone' }
  | { kind: 'error'; message: string }

/**
 * Tus puestos y tus lugares, como etiquetas que se quitan y se añaden aquí mismo. Cada cambio se
 * guarda en tu perfil al momento (la sección `preferences`, como en «Configuración de tu búsqueda»),
 * con «Deshacer». Mientras se guarda y hasta que vuelve el perfil nuevo, no se puede tocar: así cada
 * cambio parte del fichero que hay.
 */
function SavedSearch({ count, links }: { count: ReactNode; links: ReactNode }) {
  const { t } = useTranslation('search', { keyPrefix: 'strip' })
  const { t: tProfile } = useTranslation('profileEditor')
  const editable = useEditableProfile()
  const save = useSaveProfileSection()
  const [notice, setNotice] = useState<Notice | null>(null)
  // Lo que acabas de cambiar, a la vista mientras llega el perfil guardado (con otro `file_hash`).
  const [shown, setShown] = useState<{ hash: string | null; prefs: Preferences } | null>(null)
  const state = editable.data
  const prefs = (state?.profile as { preferences?: Preferences } | null | undefined)?.preferences
  const hash = state?.file_hash ?? null
  const pending = shown !== null && shown.hash === hash
  const suggestions = useRoleSuggestions(Boolean(prefs))

  if (editable.isPending) {
    return (
      <>
        <div className="h-28" />
        {count}
      </>
    )
  }
  if (editable.isError || !state?.exists || !prefs) {
    return (
      <>
        <p className="px-5 py-4 text-sm text-muted-foreground">
          {editable.isError ? (
            <span role="alert">{errorMessage(editable.error)}</span>
          ) : (
            <Trans t={t} i18nKey="noProfile" components={{ to: <Link to="/perfil" className="text-primary underline-offset-4 hover:underline" /> }} />
          )}
        </p>
        {count}
        <StripNote links={links}>{null}</StripNote>
      </>
    )
  }

  const view = pending ? shown.prefs : prefs
  const busy = save.isPending || pending || editable.isFetching

  const change = (next: Partial<Preferences>, done: Notice) => {
    const content = { ...prefs, ...next }
    setShown({ hash, prefs: content })
    setNotice(null)
    save.mutate(
      { section: 'preferences', file_hash: hash, content },
      {
        onSuccess: (result) => {
          // Si el fichero no cambió, su `file_hash` tampoco: no hay perfil nuevo que esperar.
          if (!result.changed) setShown(null)
          setNotice(done)
        },
        onError: (error) => {
          setShown(null)
          setNotice({ kind: 'error', message: errorMessage(error) })
        },
      },
    )
  }
  const before = { roles: prefs.roles, locations: prefs.locations }

  return (
    <>
      <TagRow
        label={t('roles')}
        icon={<BriefcaseIcon className={ICON} aria-hidden />}
        tags={view.roles.map((value) => ({ value }))}
        empty={t('noRoles')}
        addLabel={t('addRole')}
        placeholder={t('rolePlaceholder')}
        suggestions={suggestions.data ?? []}
        suggestionsTitle={t('suggestions')}
        busy={busy}
        onAdd={(item) => change({ roles: [...prefs.roles, item] }, { kind: 'added', item, before })}
        onRemove={(item) => change({ roles: prefs.roles.filter((r) => !hasItem([r], item)) }, { kind: 'removed', item, before })}
      />
      <TagRow
        label={t('places')}
        icon={<MapPinIcon className={ICON} aria-hidden />}
        tags={placesOf(view.locations).map(({ place, onlyRemote }) => ({
          value: place,
          note: onlyRemote ? tProfile('fields.locations.allowed').toLocaleLowerCase() : undefined,
        }))}
        empty={t('noPlaces')}
        addLabel={t('addPlace')}
        placeholder={t('placePlaceholder')}
        busy={busy}
        onAdd={(item) => change({ locations: addPlace(prefs.locations, item) }, { kind: 'added', item, before })}
        onRemove={(item) => change({ locations: removePlace(prefs.locations, item) }, { kind: 'removed', item, before })}
      />
      {count}
      <StripNote links={links}>
        {notice?.kind === 'error' ? (
          <span role="alert" className="text-destructive">
            {notice.message}
          </span>
        ) : notice && notice.kind !== 'undone' ? (
          <span className="inline-flex flex-wrap items-center gap-x-2 text-primary">
            <CheckIcon className="size-3.5" aria-hidden />
            {t(notice.kind, { item: notice.item })}
            <button
              type="button"
              disabled={busy}
              className="underline-offset-4 hover:underline disabled:opacity-50"
              onClick={() => change(notice.before, { kind: 'undone' })}
            >
              {t('undo')}
            </button>
          </span>
        ) : (
          <span>{notice?.kind === 'undone' ? t('undone') : t('savesTo')}</span>
        )}
      </StripNote>
    </>
  )
}

/** La línea de abajo de la franja: a la izquierda lo que toque, a la derecha los enlaces. */
function StripNote({ children, links }: { children: ReactNode; links: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 border-t px-5 py-2.5 text-xs text-muted-foreground">
      {/* Lo que se guarda o falla se anuncia al momento. */}
      <span className="min-w-0" aria-live="polite">
        {children}
      </span>
      {links}
    </div>
  )
}

/** «Solo esta vez»: un puesto y un lugar que tu agente usa en vez de los de tu perfil, sin cambiarlo. */
function OneOffSearch({
  role,
  location,
  invalid,
  onRole,
  onLocation,
}: {
  role: string
  location: string
  invalid: { role: boolean; location: boolean }
  onRole: (value: string) => void
  onLocation: (value: string) => void
}) {
  const { t } = useTranslation('search', { keyPrefix: 'refine' })
  const row = 'grid items-center gap-x-4 gap-y-1.5 px-5 py-3 sm:grid-cols-[7rem_minmax(0,1fr)]'
  return (
    <>
      <div className={row}>
        <Label htmlFor="search-role" className="flex items-center gap-2 font-normal text-muted-foreground">
          <BriefcaseIcon className={ICON} aria-hidden />
          {t('role')}
        </Label>
        <Input id="search-role" autoFocus value={role} maxLength={80} aria-invalid={invalid.role} placeholder={t('rolePlaceholder')} className="max-w-sm" onChange={(e) => onRole(e.target.value)} />
      </div>
      <div className={row}>
        <Label htmlFor="search-location" className="flex items-center gap-2 font-normal text-muted-foreground">
          <MapPinIcon className={ICON} aria-hidden />
          {t('location')}
        </Label>
        <Input id="search-location" value={location} maxLength={80} aria-invalid={invalid.location} placeholder={t('locationPlaceholder')} className="max-w-sm" onChange={(e) => onLocation(e.target.value)} />
      </div>
      {(invalid.role || invalid.location) && (
        <p role="alert" className="px-5 pb-2 text-xs text-destructive">
          {t('badText')}
        </p>
      )}
    </>
  )
}

/**
 * La franja de «Buscar»: qué buscas, dónde y cuántas, cada cosa con su forma de cambiarla, y a la
 * derecha (`action`) el botón para empezar. Con `oneOff`, los puestos y lugares de tu perfil dejan
 * sitio a un puesto y un lugar solo para esta vez.
 */
export function SearchStrip({
  oneOff,
  onOneOff,
  role,
  location,
  invalid,
  onRole,
  onLocation,
  count,
  action,
}: {
  oneOff: boolean
  onOneOff: (on: boolean) => void
  role: string
  location: string
  invalid: { role: boolean; location: boolean }
  onRole: (value: string) => void
  onLocation: (value: string) => void
  /** La fila «Cuántas» (el control de ofertas por portal). */
  count: ReactNode
  action: ReactNode
}) {
  const { t } = useTranslation('search', { keyPrefix: 'strip' })
  const countRow = (
    <div className="grid items-center gap-x-4 gap-y-1.5 px-5 py-3 sm:grid-cols-[7rem_minmax(0,1fr)]">
      <span className="flex items-center gap-2 text-sm text-muted-foreground">
        <StackIcon className={ICON} aria-hidden />
        {t('count')}
      </span>
      <div className="min-w-0">{count}</div>
    </div>
  )
  const links = (
    <span className="flex flex-wrap items-center gap-x-4 gap-y-1">
      {!oneOff && (
        <button type="button" className="text-primary underline-offset-4 hover:underline" onClick={() => onOneOff(true)}>
          {t('oneOff')}
        </button>
      )}
      <Link
        to="/buscar/ajustes"
        state={{ focus: 'roles' } satisfies { focus: SectionFocus }}
        className="inline-flex items-center gap-1 text-primary underline-offset-4 hover:underline"
      >
        <SlidersHorizontalIcon className="size-3.5" aria-hidden />
        {t('moreFilters')}
      </Link>
    </span>
  )
  return (
    <section aria-label={t('label')} className="grid rounded-xl border bg-card lg:grid-cols-[minmax(0,1fr)_16rem] data-[one-off=true]:border-primary/50" data-one-off={oneOff}>
      <div className="min-w-0 py-1.5">
        {oneOff ? (
          <>
            <div className="-mt-1.5 flex flex-wrap items-center justify-between gap-2 rounded-tl-xl bg-accent px-5 py-2.5 text-sm text-accent-foreground max-lg:rounded-tr-xl">
              <span>
                <strong className="font-semibold">{t('oneOffTitle')}</strong> · {t('oneOffNote')}
              </span>
              <button type="button" className="text-primary underline-offset-4 hover:underline" onClick={() => onOneOff(false)}>
                {t('back')}
              </button>
            </div>
            <OneOffSearch role={role} location={location} invalid={invalid} onRole={onRole} onLocation={onLocation} />
            {countRow}
            <StripNote links={links}>{t('oneOffHint')}</StripNote>
          </>
        ) : (
          <SavedSearch count={countRow} links={links} />
        )}
      </div>
      <div className="grid content-center gap-2 border-t bg-accent/45 px-6 py-5 max-lg:rounded-b-xl lg:rounded-r-xl lg:border-t-0 lg:border-l">
        {action}
      </div>
    </section>
  )
}
