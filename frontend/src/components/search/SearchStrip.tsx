import { useId, useState, type ReactNode } from 'react'
import { useIsMutating } from '@tanstack/react-query'
import { Trans, useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { BriefcaseIcon, CaretDownIcon, CheckIcon, HouseLineIcon, MapPinIcon, SlidersHorizontalIcon, StackIcon, StepsIcon } from '@phosphor-icons/react'
import { useEditableProfile, useRoleSuggestions, useSalaryFloor, useSaveProfileSection } from '@/api/queries'
import { REMOTE_MODES, SENIORITIES, type Preferences } from '@/components/profile/types'
import { errorMessage } from '@/lib/errors'
import { countMore } from '@/lib/moreSettings'
import { addPlace, hasItem, PLACE_MODES, placesOf, removePlace, setPlaceMode, type PlaceMode } from '@/lib/searchStrip'
import { cn } from '@/lib/utils'
import { ChipChoices, StripRow } from './ChipChoices'
import { MoreSettings } from './MoreSettings'
import { TagRow } from './TagRow'

const ICON = 'size-4 shrink-0'

/** Lo que dice la línea de abajo tras un cambio: qué se guardó y cómo volver atrás. */
type Notice =
  | { kind: 'added' | 'removed' | 'changed'; item: string; before: Partial<Preferences> }
  | { kind: 'undone' }
  | { kind: 'error'; message: string }

/** El botón «Más ajustes · N», que despliega el resto de la configuración dentro de la franja. */
function MoreButton({ count, open, controls, onToggle }: { count: number; open: boolean; controls: string; onToggle: () => void }) {
  const { t } = useTranslation('search', { keyPrefix: 'more' })
  return (
    <button
      type="button"
      aria-expanded={open}
      aria-controls={controls}
      onClick={onToggle}
      className={cn(
        'inline-flex shrink-0 items-center gap-1.5 rounded-full border py-1 pr-2 pl-3 text-sm font-medium outline-none transition-colors',
        'focus-visible:ring-2 focus-visible:ring-ring',
        open ? 'border-primary/45 bg-accent text-accent-foreground' : 'border-input bg-card text-foreground hover:border-ring',
      )}
    >
      <SlidersHorizontalIcon className="size-3.5" aria-hidden />
      {t('button')}
      {count > 0 && (
        <span className="grid h-[1.125rem] min-w-[1.125rem] place-items-center rounded-full bg-primary px-1 text-[0.6875rem] font-semibold text-primary-foreground tabular-nums">
          <span aria-hidden>{count}</span>
          <span className="sr-only">{t('active', { count })}</span>
        </span>
      )}
      <CaretDownIcon className={cn('size-3.5 transition-transform', open && 'rotate-180')} aria-hidden />
    </button>
  )
}

/**
 * La franja de «Buscar»: lo que buscas, editable aquí mismo (puestos y lugares como etiquetas, modalidad
 * y nivel como chips, y cuántas ofertas por portal), y a la derecha (`action`) la columna para empezar.
 * Cada cambio de esas filas se guarda en tu perfil al momento (la sección `preferences`), con
 * «Deshacer». Mientras se guarda y hasta que vuelve el perfil nuevo, no se puede tocar: así cada cambio
 * parte del fichero que hay. «Más ajustes» se despliega debajo de las dos columnas, en la misma tarjeta,
 * y guarda con su propio botón.
 */
export function SearchStrip({
  count,
  action,
  moreOpen,
  onMore,
}: {
  /** El control de ofertas por portal (va en la fila «Cuántas»). */
  count: ReactNode
  action: ReactNode
  moreOpen: boolean
  onMore: (open: boolean) => void
}) {
  const { t } = useTranslation('search', { keyPrefix: 'strip' })
  const { t: tProfile } = useTranslation('profileEditor')
  const editable = useEditableProfile()
  const save = useSaveProfileSection()
  const floor = useSalaryFloor()
  const ids = useId()
  const moreId = `${ids}-more`
  const [notice, setNotice] = useState<Notice | null>(null)
  // Lo que acabas de cambiar, a la vista mientras llega el perfil guardado (con otro `file_hash`).
  const [shown, setShown] = useState<{ hash: string | null; prefs: Preferences } | null>(null)
  const state = editable.data
  const prefs = (state?.profile as { preferences?: Preferences } | null | undefined)?.preferences
  const hash = state?.file_hash ?? null
  const pending = shown !== null && shown.hash === hash
  const suggestions = useRoleSuggestions(Boolean(prefs))
  // Otro guardado en curso («Más ajustes», el número de ofertas…): cada uno parte del fichero que deja el anterior.
  const mutating = useIsMutating() > 0

  const countRow = (
    <StripRow id={`${ids}-count`} icon={<StackIcon className={ICON} aria-hidden />} label={t('count')}>
      <div className="min-w-0">{count}</div>
    </StripRow>
  )
  const frame = (rows: ReactNode, more: ReactNode = null) => (
    <section aria-label={t('label')} className="grid rounded-xl border bg-card lg:grid-cols-[minmax(0,1fr)_17rem]">
      <div className="min-w-0 pt-1.5">{rows}</div>
      <div
        className={cn(
          'grid border-t px-6 py-5 lg:border-t-0 lg:border-l',
          'bg-accent/35 bg-[radial-gradient(140%_70%_at_100%_0%,color-mix(in_oklch,var(--primary)_16%,transparent),transparent_62%),radial-gradient(90%_60%_at_0%_100%,color-mix(in_oklch,var(--primary)_7%,transparent),transparent_70%)]',
          moreOpen && more ? 'lg:rounded-tr-xl' : 'max-lg:rounded-b-xl lg:rounded-r-xl',
        )}
      >
        {action}
      </div>
      {more}
    </section>
  )

  if (editable.isPending) return frame(<><div className="h-52" />{countRow}</>)
  if (editable.isError || !state?.exists || !prefs) {
    return frame(
      <>
        <p className="px-5 py-4 text-sm text-muted-foreground">
          {editable.isError ? (
            <span role="alert">{errorMessage(editable.error)}</span>
          ) : (
            <Trans t={t} i18nKey="noProfile" components={{ to: <Link to="/perfil" className="text-primary underline-offset-4 hover:underline" /> }} />
          )}
        </p>
        {countRow}
      </>,
    )
  }

  const view = pending ? shown.prefs : prefs
  const busy = save.isPending || pending || editable.isFetching || mutating

  /** Guarda `next` sobre tu perfil. Lo que dice «Deshacer» son solo esas claves, con su valor de antes:
   *  deshacer no pisa lo que hayas guardado después en «Más ajustes». */
  const change = (next: Partial<Preferences>, done: Notice | ((before: Partial<Preferences>) => Notice)) => {
    const before = Object.fromEntries(Object.keys(next).map((key) => [key, prefs[key]])) as Partial<Preferences>
    const content = { ...prefs, ...next }
    setShown({ hash, prefs: content })
    setNotice(null)
    save.mutate(
      { section: 'preferences', file_hash: hash, content },
      {
        onSuccess: (result) => {
          // Si el fichero no cambió, su `file_hash` tampoco: no hay perfil nuevo que esperar.
          if (!result.changed) setShown(null)
          setNotice(typeof done === 'function' ? done(before) : done)
        },
        onError: (error) => {
          setShown(null)
          setNotice({ kind: 'error', message: errorMessage(error) })
        },
      },
    )
  }
  const placeModes = PLACE_MODES.map((mode) => ({ value: mode, label: tProfile(`fields.locations.${mode}`) }))
  const issues = state.issues.length > 0

  return frame(
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
        onAdd={(item) => change({ roles: [...prefs.roles, item] }, (before) => ({ kind: 'added', item, before }))}
        onRemove={(item) => change({ roles: prefs.roles.filter((r) => !hasItem([r], item)) }, (before) => ({ kind: 'removed', item, before }))}
      />
      <TagRow
        label={t('places')}
        icon={<MapPinIcon className={ICON} aria-hidden />}
        tags={placesOf(view.locations).map(({ place, mode }) => ({
          value: place,
          note: mode === 'preferred' ? undefined : tProfile(`fields.locations.${mode}`).toLocaleLowerCase(),
          struck: mode === 'excluded',
          choice: {
            label: tProfile('fields.locations.modeFor', { place }),
            value: mode,
            options: placeModes,
            onChange: (value: string) => {
              const next = value as PlaceMode
              change(
                { locations: setPlaceMode(prefs.locations, place, next) },
                (before) => ({ kind: 'changed', item: `${place}: ${tProfile(`fields.locations.${next}`).toLocaleLowerCase()}`, before }),
              )
            },
          },
        }))}
        empty={t('noPlaces')}
        addLabel={t('addPlace')}
        placeholder={t('placePlaceholder')}
        busy={busy}
        onAdd={(item) => change({ locations: addPlace(prefs.locations, item) }, (before) => ({ kind: 'added', item, before }))}
        onRemove={(item) => change({ locations: removePlace(prefs.locations, item) }, (before) => ({ kind: 'removed', item, before }))}
      />
      <StripRow id={`${ids}-modes`} icon={<HouseLineIcon className={ICON} aria-hidden />} label={t('modes')}>
        <ChipChoices
          labelledBy={`${ids}-modes`}
          value={view.remote_modes}
          disabled={busy}
          options={REMOTE_MODES.map((m) => ({ value: m, label: tProfile(`remote.${m}`) }))}
          onChange={(next, { label, checked }) => change({ remote_modes: next }, (before) => ({ kind: checked ? 'added' : 'removed', item: label, before }))}
        />
      </StripRow>
      <StripRow id={`${ids}-levels`} icon={<StepsIcon className={ICON} aria-hidden />} label={t('levels')}>
        <ChipChoices
          labelledBy={`${ids}-levels`}
          value={view.seniority_target}
          disabled={busy}
          options={SENIORITIES.map((s) => ({ value: s, label: tProfile(`seniority.${s}`) }))}
          onChange={(next, { label, checked }) => change({ seniority_target: next }, (before) => ({ kind: checked ? 'added' : 'removed', item: label, before }))}
        />
      </StripRow>
      {countRow}
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-t px-5 py-2.5 text-xs text-muted-foreground">
        {/* Lo que se guarda o falla se anuncia al momento. */}
        <span className="min-w-0" aria-live="polite">
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
          ) : issues ? (
            <span role="alert" className="text-warning-foreground">
              <Trans t={t} i18nKey="issues" components={{ to: <Link to="/perfil" className="underline underline-offset-4" /> }} />
            </span>
          ) : (
            <span>{notice?.kind === 'undone' ? t('undone') : t('savesTo')}</span>
          )}
        </span>
        <MoreButton count={countMore(prefs, floor.data?.salary_floor_eur ?? null)} open={moreOpen} controls={moreId} onToggle={() => onMore(!moreOpen)} />
      </div>
    </>,
    <MoreSettings id={moreId} state={state} prefs={prefs} hidden={!moreOpen} reload={() => void editable.refetch()} />,
  )
}
