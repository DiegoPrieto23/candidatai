import { useState, type FormEvent, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import {
  ArrowSquareOutIcon,
  BuildingsIcon,
  CaretDownIcon,
  CheckCircleIcon,
  ClockIcon,
  MapPinIcon,
  PauseIcon,
  PlayIcon,
  WarningCircleIcon,
} from '@phosphor-icons/react'
import {
  ApiError,
  type ConnectorKind,
  type SourceInput,
  type SourceRunResult,
  type SourceTestResult,
  type SourceView,
} from '@/api/client'
import {
  useAddSource,
  usePreviewSource,
  useRunSource,
  useSetSourceActive,
  useSetSourceLocations,
  useSetSourceWebsite,
  useSources,
} from '@/api/queries'
import { SiteIcon } from '@/components/SiteIcon'
import { EmptyState, ErrorState, InlineCode } from '@/components/States'
import { Button } from '@/components/ui/button'
import { CodeInput } from '@/components/CodeInput'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { errorMessage } from '@/lib/errors'
import { i18n } from '@/lib/i18n'
import { formatRelative, SOURCE_KIND_LABEL } from '@/lib/labels'
import { platformHome } from '@/lib/searches'
import { cn } from '@/lib/utils'
import { BusyLabel } from '@/components/StableLabel'

type Portal = 'infojobs' | 'adzuna' | 'manfred' | 'freehire'
/** «Detectarla sola»: la app deduce el ATS de la dirección de su web de empleo. */
type FormKind = ConnectorKind | 'auto'

/** Las búsquedas (portales) toman su nombre y su pista de los textos: `kinds.*`. */
const KINDS: { value: ConnectorKind; label: string | null; hint: string | null }[] = [
  { value: 'greenhouse', label: 'Greenhouse', hint: 'boards.greenhouse.io/<slug>' },
  { value: 'lever', label: 'Lever', hint: 'jobs.lever.co/<slug>' },
  { value: 'ashby', label: 'Ashby', hint: 'jobs.ashbyhq.com/<slug>' },
  { value: 'personio', label: 'Personio', hint: '<slug>.jobs.personio.de' },
  { value: 'teamtailor', label: 'Teamtailor', hint: '<slug>.teamtailor.com' },
  { value: 'workable', label: 'Workable', hint: 'apply.workable.com/<slug>' },
  { value: 'smartrecruiters', label: 'SmartRecruiters', hint: 'jobs.smartrecruiters.com/<slug>' },
  { value: 'recruitee', label: 'Recruitee', hint: '<slug>.recruitee.com' },
  { value: 'infojobs', label: null, hint: null },
  { value: 'adzuna', label: null, hint: null },
  { value: 'manfred', label: null, hint: null },
  { value: 'freehire', label: null, hint: null },
]

function kindLabel(kind: (typeof KINDS)[number]): string {
  return kind.label ?? i18n.t(`sources:kinds.${kind.value as Portal}`)
}

function kindHint(kind: (typeof KINDS)[number]): string {
  if (kind.hint) return kind.hint.replace('<slug>', `<${i18n.t('sources:form.slugPart')}>`)
  if (kind.value === 'manfred') return i18n.t('sources:kinds.manfredHint')
  if (kind.value === 'freehire') return i18n.t('sources:kinds.freehireHint')
  return i18n.t('sources:kinds.keysHint')
}
const ATS: ConnectorKind[] = KINDS.filter((k) => k.label !== null).map((k) => k.value)
/** Cómo encontrar el nombre de la empresa en la dirección de cada ATS (`docs/FUENTES_OFERTAS.md`). */
const SLUG_HELP_URL = 'https://github.com/DiegoPrieto23/candidatai/blob/main/docs/FUENTES_OFERTAS.md#cómo-encontrar-el-slug'
const CONNECTOR_KINDS = new Set<string>(KINDS.map((k) => k.value))

function fieldErrors(error: unknown): Record<string, string> {
  if (!(error instanceof ApiError)) return {}
  return Object.fromEntries(error.details.map((d) => [d.field || 'form', d.reason]))
}

/** «Hoy», «Ayer», «Hace 3 días»… al principio de una línea. */
function whenLabel(iso: string): string {
  const text = formatRelative(iso)
  return text.charAt(0).toLocaleUpperCase() + text.slice(1)
}

function placesOf(source: SourceView): string[] {
  const places = source.config.locations
  return Array.isArray(places) ? places.map(String) : []
}

// --- Resultado de una prueba o de una ejecución ---------------------------------------------------

function Notice({ tone, children }: { tone: 'ok' | 'warn' | 'error'; children: ReactNode }) {
  const Icon = tone === 'ok' ? CheckCircleIcon : WarningCircleIcon
  return (
    <div
      role={tone === 'error' ? 'alert' : 'status'}
      className={cn(
        'flex items-start gap-2.5 rounded-lg border px-3.5 py-3 text-sm',
        tone === 'ok' && 'border-primary/25 bg-primary/5',
        tone === 'warn' && 'border-amber-500/30 bg-amber-500/5',
        tone === 'error' && 'border-destructive/30 bg-destructive/5',
      )}
    >
      <Icon
        weight="fill"
        className={cn(
          'mt-0.5 size-4 shrink-0',
          tone === 'ok' && 'text-primary',
          tone === 'warn' && 'text-amber-600 dark:text-amber-400',
          tone === 'error' && 'text-destructive',
        )}
      />
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  )
}

function Issues({ issues }: { issues: { message: string }[] }) {
  const { t } = useTranslation('sources')
  if (issues.length === 0) return null
  return (
    <ul className="mt-1.5 space-y-0.5 text-xs text-muted-foreground">
      {issues.slice(0, 5).map((issue, i) => (
        <li key={i}>
          <InlineCode text={issue.message} />
        </li>
      ))}
      {issues.length > 5 && <li>{t('more', { count: issues.length - 5 })}</li>}
    </ul>
  )
}

/** Lo que encaja contigo y nada más: los recuentos totales quedan en el registro y en la CLI. */
function PreviewResult({ result }: { result: SourceTestResult }) {
  const { t } = useTranslation('sources')
  const found = result.resolution
  if (found?.how === 'none') {
    return (
      <Notice tone="warn">
        <p>{t('resolve.none')}</p>
        <Issues issues={found.issues.map((message) => ({ message }))} />
      </Notice>
    )
  }
  if (result.found === 0 && result.errors.length > 0) {
    return (
      <Notice tone="error">
        <InlineCode text={result.message} />
      </Notice>
    )
  }
  const jobs = result.jobs.filter((j) => j.passed)
  const forYou = t('forYou', { count: result.after_filters })
  const places = found?.locations ?? []
  return (
    <div className="grid gap-3">
      <Notice tone={result.after_filters ? 'ok' : 'warn'}>
        <p className="font-medium">
          {found?.kind_label ? `${t('resolve.found', { ats: found.kind_label })} · ${forYou}` : forYou}
        </p>
        {places.length > 0 && (
          <p className="mt-0.5 flex items-center gap-1 text-xs text-muted-foreground">
            <MapPinIcon className="size-3.5" aria-hidden />
            {t('onlyIn', { places: places.join(', ') })}
          </p>
        )}
        {found?.kind_label && found.slug && (
          <p className="mt-0.5 text-xs text-muted-foreground">
            {t('resolve.detail', { board: `${found.kind_label} · ${found.slug}`, how: t(`resolve.how.${found.how}`) })}
          </p>
        )}
        <Issues issues={result.errors} />
      </Notice>
      <div className="rounded-lg border">
        <ul className="max-h-72 divide-y overflow-y-auto text-sm">
          {jobs.map((job) => (
            <li key={job.external_id} className="px-3.5 py-2.5">
              <a href={job.url} target="_blank" rel="noreferrer noopener" className="font-medium hover:underline">
                {job.title}
              </a>
              {job.location && <p className="text-xs text-muted-foreground">{job.location}</p>}
            </li>
          ))}
          {jobs.length === 0 && <li className="px-3.5 py-2.5 text-muted-foreground">{t('nonePass')}</li>}
        </ul>
      </div>
    </div>
  )
}

function RunResult({ result }: { result: SourceRunResult }) {
  const { t } = useTranslation('sources')
  const failed = !!result.skipped || (result.errors.length > 0 && result.found === 0)
  return (
    <Notice tone={failed ? 'error' : 'ok'}>
      <p>
        {failed ? (
          <InlineCode text={result.message} />
        ) : result.created ? (
          t('run.created', { count: result.created })
        ) : (
          t('run.none')
        )}
      </p>
      {result.job_ids.length > 0 && (
        <p className="mt-1 text-xs text-muted-foreground">
          <InlineCode text={t('runHint')} />{' '}
          <Link to="/bandeja?stage=pending_extraction" className="font-medium text-primary hover:underline">
            {t('see')}
          </Link>
        </p>
      )}
      {!failed && <Issues issues={result.errors} />}
    </Notice>
  )
}

// --- Formulario de alta --------------------------------------------------------------------------

function Field({ id, label, error, hint, children }: { id: string; label: string; error?: string; hint?: ReactNode; children: ReactNode }) {
  return (
    <div className="grid content-start gap-2">
      <Label htmlFor={id}>{label}</Label>
      {children}
      {error ? (
        <p className="text-sm text-destructive">{error}</p>
      ) : (
        hint && <p className="text-xs text-muted-foreground">{hint}</p>
      )}
    </div>
  )
}

const EMPTY = {
  kind: 'auto' as FormKind,
  name: '',
  url: '',
  slug: '',
  region: 'global' as 'global' | 'eu',
  query: '',
  where: '',
  province: '',
  language: '',
  lang: 'ES' as 'ES' | 'EN',
  country: 'es',
  remoteOnly: false,
}
type TextKey = 'name' | 'url' | 'slug' | 'query' | 'where' | 'province' | 'language' | 'country'
/** Los valores por defecto de `SourceInput`, que el cliente generado pide siempre. */
const DEFAULTS = { region: 'global', country: 'es', lang: 'ES', remote_only: false, title_keywords: [] } as const satisfies Partial<SourceInput>

/** Lo normal: el nombre de la empresa y la dirección de su web de empleo, y la app hace el resto.
 * «Más opciones» deja elegir el ATS y su slug (si la detección falla) o una búsqueda en un portal. */
function AddSourceForm({ onAdded }: { onAdded?: () => void }) {
  const { t } = useTranslation('sources', { keyPrefix: 'form' })
  const [form, setForm] = useState(EMPTY)
  const [more, setMore] = useState(false)
  const preview = usePreviewSource()
  const add = useAddSource()
  const auto = form.kind === 'auto'
  const isAts = auto || ATS.includes(form.kind as ConnectorKind)
  const kind = KINDS.find((k) => k.value === form.kind)
  const errors = { ...fieldErrors(preview.error), ...fieldErrors(add.error) }
  // Cambiar un campo descarta la prueba: lo detectado siempre corresponde a lo que se ve.
  const detected = preview.data?.resolution ?? null
  const update = (patch: Partial<typeof EMPTY>) => {
    setForm((prev) => ({ ...prev, ...patch }))
    preview.reset()
  }
  const set = (key: TextKey) => (e: { target: { value: string } }) =>
    // Otra dirección es otra empresa: lo que se trajo de la detección anterior ya no vale.
    update(key === 'url' && auto ? { url: e.target.value, slug: '', region: 'global' } : { [key]: e.target.value })
  const ready = form.name.trim() && (auto ? form.url.trim() : isAts ? form.slug.trim() : form.query.trim())

  const body = (): SourceInput => {
    const name = form.name.trim()
    const url = form.url.trim() || null
    if (auto) {
      // Tras «Probar», lo detectado: así «Añadir» no vuelve a buscar su web de empleo.
      if (detected?.kind && detected.slug) {
        return {
          ...DEFAULTS,
          kind: detected.kind as ConnectorKind,
          name,
          slug: detected.slug,
          region: detected.region,
          url: detected.url,
          locations: detected.locations,
          website: detected.website,
        }
      }
      return { ...DEFAULTS, name, url }
    }
    const ck = form.kind as ConnectorKind
    if (isAts) {
      return {
        ...DEFAULTS,
        kind: ck,
        name,
        slug: form.slug.trim(),
        region: ck === 'lever' ? form.region : 'global',
        language: ck === 'personio' ? form.language.trim().toLowerCase() || null : null,
        url,
      }
    }
    return {
      ...DEFAULTS,
      kind: ck,
      name,
      slug: null,
      query: form.query.trim(),
      where: ck === 'adzuna' ? form.where.trim() || null : null,
      province: ck === 'infojobs' ? form.province.trim() || null : null,
      country: ck === 'freehire' ? form.country.trim().toLowerCase() || 'es' : 'es',
      lang: ck === 'manfred' ? form.lang : 'ES',
      remote_only: ck === 'freehire' && form.remoteOnly,
    }
  }

  const test = () => {
    add.reset()
    preview.mutate(auto ? { ...DEFAULTS, name: form.name.trim(), url: form.url.trim() } : body())
  }
  const save = (e: FormEvent) => {
    e.preventDefault()
    add.mutate(body(), {
      onSuccess: () => {
        setForm(EMPTY)
        setMore(false)
        preview.reset()
        onAdded?.()
      },
    })
  }
  const toggleMore = () => {
    if (more) {
      update({ kind: 'auto' })
    } else if (detected?.kind && detected.slug) {
      // Lo detectado, ya puesto, para corregirlo si no es.
      update({ kind: detected.kind as ConnectorKind, slug: detected.slug, region: detected.region })
    }
    setMore(!more)
  }
  const formError = [preview.error, add.error].find(
    (error) => error && !(error instanceof ApiError && error.details.length > 0),
  )

  return (
    <form onSubmit={save} className="grid gap-5" noValidate aria-label={t('label')}>
      <div className="grid gap-5 sm:grid-cols-2">
        <Field id="source-name" label={isAts ? t('company') : t('searchName')} error={errors.name}>
          <Input id="source-name" value={form.name} onChange={set('name')} className="h-10 bg-background" />
        </Field>
        {isAts && (
          <Field id="source-url" label={t('url')} error={errors.url ?? (auto ? errors.form : undefined)} hint={t('urlHint')}>
            <Input
              id="source-url"
              type="url"
              value={form.url}
              onChange={set('url')}
              placeholder="https://careers.acme.com/madrid/"
              spellCheck={false}
              className="h-10 bg-background"
            />
          </Field>
        )}
      </div>

      <div className="grid gap-5">
        <button
          type="button"
          onClick={toggleMore}
          aria-expanded={more}
          className="inline-flex w-fit items-center gap-1 text-sm font-medium text-muted-foreground hover:text-foreground"
        >
          <CaretDownIcon className={cn('size-3.5 transition-transform', more && 'rotate-180')} aria-hidden />
          {t('more')}
        </button>
        {more && (
          <div className="grid gap-5 sm:grid-cols-2">
            <Field id="source-kind" label={t('origin')}>
              <Select value={form.kind} onValueChange={(value) => update({ kind: value as FormKind })}>
                <SelectTrigger id="source-kind" className="h-10 w-full bg-background">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="auto">{t('auto')}</SelectItem>
                  {KINDS.map((k) => (
                    <SelectItem key={k.value} value={k.value}>
                      {kindLabel(k)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            {kind && isAts && (
              <>
                <Field
                  id="source-slug"
                  label={t('slug')}
                  error={errors.slug ?? errors.form}
                  hint={
                    <>
                      {t('slugHint')} <span className="font-mono">{kindHint(kind)}</span>.{' '}
                      <a href={SLUG_HELP_URL} target="_blank" rel="noreferrer noopener" className="font-medium text-primary hover:underline">
                        {t('slugHelp')}
                      </a>
                    </>
                  }
                >
                  <Input id="source-slug" value={form.slug} onChange={set('slug')} spellCheck={false} className="h-10 bg-background font-mono" />
                </Field>
                {form.kind === 'personio' && (
                  <Field id="source-language" label={t('language')} error={errors.language} hint={t('languageHint')}>
                    <CodeInput id="source-language" kind="language" value={form.language} invalid={!!errors.language} onChange={(language) => update({ language })} />
                  </Field>
                )}
                {form.kind === 'lever' && (
                  <Field id="source-region" label={t('region')}>
                    <Select value={form.region} onValueChange={(value) => update({ region: value as 'global' | 'eu' })}>
                      <SelectTrigger id="source-region" className="h-10 w-full bg-background">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="global">{t('global')}</SelectItem>
                        <SelectItem value="eu">{t('eu')}</SelectItem>
                      </SelectContent>
                    </Select>
                  </Field>
                )}
              </>
            )}
            {kind && !isAts && (
              <>
                <Field id="source-query" label={t('query')} error={errors.query ?? errors.form} hint={kindHint(kind)}>
                  <Input id="source-query" value={form.query} onChange={set('query')} className="h-10 bg-background" />
                </Field>
                {form.kind === 'adzuna' && (
                  <Field id="source-where" label={t('where')}>
                    <Input id="source-where" value={form.where} onChange={set('where')} className="h-10 bg-background" />
                  </Field>
                )}
                {form.kind === 'infojobs' && (
                  <Field id="source-province" label={t('province')} hint={t('provinceHint')}>
                    <Input id="source-province" value={form.province} onChange={set('province')} className="h-10 bg-background" />
                  </Field>
                )}
                {form.kind === 'manfred' && (
                  <Field id="source-lang" label={t('lang')}>
                    <Select value={form.lang} onValueChange={(value) => update({ lang: value as 'ES' | 'EN' })}>
                      <SelectTrigger id="source-lang" className="h-10 w-full bg-background">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="ES">{t('langEs')}</SelectItem>
                        <SelectItem value="EN">{t('langEn')}</SelectItem>
                      </SelectContent>
                    </Select>
                  </Field>
                )}
                {form.kind === 'freehire' && (
                  <Field id="source-country" label={t('country')} error={errors.country}>
                    <CodeInput id="source-country" kind="region" value={form.country.toUpperCase()} invalid={!!errors.country} onChange={(country) => update({ country })} />
                    <label className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={form.remoteOnly}
                        onChange={(e) => update({ remoteOnly: e.target.checked })}
                        className="size-4 accent-primary"
                      />
                      {t('remoteOnly')}
                    </label>
                  </Field>
                )}
              </>
            )}
          </div>
        )}
      </div>

      {preview.data && <PreviewResult result={preview.data} />}
      {formError && (
        <Notice tone="error">
          <InlineCode text={errorMessage(formError)} />
        </Notice>
      )}
      {add.isSuccess && (
        <Notice tone="ok">
          {add.data.kind === 'agent_browse' ? t('addedBrowse', { name: add.data.name }) : t('added', { name: add.data.name })}
        </Notice>
      )}

      <div className="flex flex-wrap justify-end gap-2">
        <Button type="button" variant="outline" disabled={!ready || preview.isPending} onClick={test} className="h-10">
          <BusyLabel busy={preview.isPending} busyText={t('testing')} text={t('test')} />
        </Button>
        <Button type="submit" disabled={!ready || add.isPending} className="h-10 px-5 active:translate-y-px">
          <BusyLabel busy={add.isPending} busyText={t('saving')} text={t('add')} />
        </Button>
      </div>
    </form>
  )
}

// --- Lista de fuentes ----------------------------------------------------------------------------

/** Un campo de una línea que se abre al pulsar «Cambiar» en la tarjeta de una empresa. */
function InlineEdit({
  label,
  hint,
  initial,
  placeholder,
  pending,
  error,
  onSave,
  onCancel,
}: {
  label: string
  hint: string
  initial: string
  placeholder: string
  pending: boolean
  error: unknown
  onSave: (value: string) => void
  onCancel: () => void
}) {
  const { t } = useTranslation('sources', { keyPrefix: 'row' })
  const [value, setValue] = useState(initial)
  const submit = (e: FormEvent) => {
    e.preventDefault()
    onSave(value.trim())
  }
  return (
    <form onSubmit={submit} className="mt-1.5 grid gap-1.5" aria-label={label}>
      <div className="flex flex-wrap items-center gap-1.5">
        <Input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={placeholder}
          spellCheck={false}
          autoFocus
          aria-label={label}
          className="h-8 w-56 bg-background text-sm"
        />
        <Button type="submit" size="sm" disabled={pending}>
          <BusyLabel busy={pending} busyText={t('saving')} text={t('save')} />
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={onCancel}>
          {t('cancel')}
        </Button>
      </div>
      <p className="text-xs text-muted-foreground">{hint}</p>
      {!!error && <p className="text-xs text-destructive">{errorMessage(error)}</p>}
    </form>
  )
}

/** La web de una empresa con portal propio, para su logo, y los lugares a los que se limita
 * («Solo Madrid», que suele salir de la dirección de su web de empleo). */
function CompanyDetails({ source }: { source: SourceView }) {
  const { t } = useTranslation('sources', { keyPrefix: 'row' })
  const { t: tRoot } = useTranslation('sources')
  const saveWebsite = useSetSourceWebsite()
  const savePlaces = useSetSourceLocations()
  const [editing, setEditing] = useState<'website' | 'places' | null>(null)
  const home = source.website ? platformHome([source.website]) : null
  const editable = ATS.includes(source.kind as ConnectorKind)
  const places = placesOf(source)

  if (editing === 'website') {
    return (
      <InlineEdit
        label={t('websiteLabel', { name: source.name })}
        hint={t('websiteHint')}
        initial={home?.host ?? ''}
        placeholder="acme.com"
        pending={saveWebsite.isPending}
        error={saveWebsite.error}
        onCancel={() => setEditing(null)}
        onSave={(website) =>
          saveWebsite.mutate({ sourceId: source.id, website: website || null }, { onSuccess: () => setEditing(null) })
        }
      />
    )
  }
  if (editing === 'places') {
    return (
      <InlineEdit
        label={t('placesLabel', { name: source.name })}
        hint={t('placesHint')}
        initial={places.join(', ')}
        placeholder="Madrid"
        pending={savePlaces.isPending}
        error={savePlaces.error}
        onCancel={() => setEditing(null)}
        onSave={(value) =>
          savePlaces.mutate(
            { sourceId: source.id, locations: value.split(',').map((p) => p.trim()).filter(Boolean) },
            { onSuccess: () => setEditing(null) },
          )
        }
      />
    )
  }
  const open = (what: 'website' | 'places') => {
    saveWebsite.reset()
    savePlaces.reset()
    setEditing(what)
  }
  const link = 'underline-offset-2 hover:text-foreground hover:underline'
  return (
    <>
      {places.length > 0 && (
        <p className="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-muted-foreground">
          <span className="inline-flex items-center gap-1 text-foreground/80">
            <MapPinIcon className="size-3.5" aria-hidden />
            {tRoot('onlyIn', { places: places.join(', ') })}
          </span>
          <button type="button" onClick={() => open('places')} className={link}>
            {t('changePlaces')}
          </button>
        </p>
      )}
      <p className="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-muted-foreground">
        {home && (
          <a
            href={home.origin}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-foreground/80 underline-offset-2 hover:text-foreground hover:underline"
          >
            {home.host}
            <ArrowSquareOutIcon className="size-3" aria-hidden />
          </a>
        )}
        {editable && (
          <button type="button" onClick={() => open('website')} className={link}>
            {home ? t('changeWebsite') : t('addWebsite')}
          </button>
        )}
        {editable && places.length === 0 && (
          <button type="button" onClick={() => open('places')} className={link}>
            {t('addPlaces')}
          </button>
        )}
      </p>
    </>
  )
}

function SourceRow({ source }: { source: SourceView }) {
  const { t } = useTranslation('sources', { keyPrefix: 'row' })
  const preview = usePreviewSource()
  const run = useRunSource()
  const toggle = useSetSourceActive()
  // El nombre de la empresa en su ATS ya está en el título; de un portal, se enseña qué busca.
  const query = source.config.query ? String(source.config.query) : null
  const last = source.last_run
  const busy = preview.isPending || run.isPending
  const error = preview.error ?? run.error ?? toggle.error

  return (
    <li className={cn('grid gap-3 px-4 py-4 sm:px-5', !source.active && 'opacity-70')}>
      <div className="flex flex-wrap items-start gap-x-4 gap-y-2">
        <SiteIcon
          key={source.website ?? ''}
          name={source.name}
          sourceId={source.id}
          host={source.website ? (platformHome([source.website])?.host ?? null) : null}
        />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h5 className="font-medium">{source.name}</h5>
            <span className="rounded-md border px-1.5 py-0.5 text-xs text-muted-foreground">
              {SOURCE_KIND_LABEL[source.kind] ?? source.kind_label}
            </span>
            {!source.active && <span className="rounded-md bg-muted px-1.5 py-0.5 text-xs">{t('paused')}</span>}
            {source.keys_missing && (
              <span className="rounded-md bg-amber-500/10 px-1.5 py-0.5 text-xs text-amber-700 dark:text-amber-400">
                {t('noKeys')}
              </span>
            )}
          </div>
          {query && <p className="mt-0.5 text-xs text-muted-foreground">«{query}»</p>}
          <CompanyDetails source={source} />
          <p className="mt-1.5 flex items-center gap-1.5 text-xs text-muted-foreground">
            <ClockIcon className="size-3.5" />
            {last ? (
              <span>
                {t('last', { when: whenLabel(last.started_at), count: last.created })}
                {last.errors.length > 0 && last.found === 0 && (
                  <span className="text-destructive"> · {last.errors[0]!.message}</span>
                )}
              </span>
            ) : (
              <span>{t('notRun')}</span>
            )}
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <Button variant="outline" size="sm" disabled={busy} onClick={() => preview.mutate(source.id)}>
            <BusyLabel busy={preview.isPending} busyText={t('testing')} text={t('test')} />
          </Button>
          <Button variant="outline" size="sm" disabled={busy || !source.active} onClick={() => run.mutate(source.id)}>
            <PlayIcon weight="fill" />
            <BusyLabel busy={run.isPending} busyText={t('running')} text={t('run')} />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            disabled={toggle.isPending}
            onClick={() => toggle.mutate({ sourceId: source.id, active: !source.active })}
          >
            {source.active ? <PauseIcon /> : <PlayIcon />}
            {source.active ? t('pause') : t('resume')}
          </Button>
        </div>
      </div>
      {preview.data && <PreviewResult result={preview.data} />}
      {run.data && <RunResult result={run.data} />}
      {error && (
        <Notice tone="error">
          <InlineCode text={errorMessage(error)} />
        </Notice>
      )}
    </li>
  )
}

function SourceList() {
  const sources = useSources()
  if (sources.isPending) {
    return (
      <div className="grid gap-3">
        <Skeleton className="h-20" />
        <Skeleton className="h-20" />
      </div>
    )
  }
  if (sources.isError) return <ErrorState error={sources.error} onRetry={() => sources.refetch()} />
  const items = sources.data.sources.filter((s) => CONNECTOR_KINDS.has(s.kind))
  return (
    <ul className="divide-y rounded-xl border bg-card">
      {items.map((source) => (
        <SourceRow key={source.id} source={source} />
      ))}
    </ul>
  )
}

/** Lo habitual es repasar las que ya sigues: el alta, tras un botón (la acción destacada). */
export function SourcesPage() {
  const { t } = useTranslation('sources')
  const sources = useSources()
  const [adding, setAdding] = useState(false)
  const none = sources.isSuccess && !sources.data.sources.some((s) => CONNECTOR_KINDS.has(s.kind))
  return (
    <div className="max-w-3xl">
      <h3 className="sr-only">{t('title')}</h3>
      <div className="mb-6 grid justify-items-start gap-3">
        <p className="text-sm leading-relaxed text-muted-foreground">
          <InlineCode text={t('intro')} />
        </p>
        {sources.isSuccess && !none && (
          <Button variant={adding ? 'outline' : 'default'} onClick={() => setAdding(!adding)} aria-expanded={adding}>
            {adding ? t('closeAdd') : t('empty.add')}
          </Button>
        )}
      </div>
      {none && (
        <div className="mb-6">
          <EmptyState icon={<BuildingsIcon className="size-6" weight="duotone" />} title={t('empty.title')}>
            {t('empty.body')}
          </EmptyState>
        </div>
      )}
      {(adding || none) && (
        <section className="mb-10 rounded-xl border bg-card p-5 sm:p-6">
          <h4 className="mb-4 font-medium">{t('addTitle')}</h4>
          <AddSourceForm onAdded={() => setAdding(false)} />
        </section>
      )}
      {!none && (
        <section>
          <h4 className="mb-3 font-medium">{t('following')}</h4>
          <SourceList />
        </section>
      )}
    </div>
  )
}
