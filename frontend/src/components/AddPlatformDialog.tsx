import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { PencilSimpleIcon, PlusIcon, SparkleIcon, WarningIcon } from '@phosphor-icons/react'
import type { BrowseAccess, SourceView } from '@/api/client'
import { useAddPlatform, useEditableProfile, useEditPlatform, usePlatforms } from '@/api/queries'
import { Hint } from '@/components/Hint'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { errorMessage } from '@/lib/errors'
import { buildSearches, canBuildSearches, searchLabel, type SearchPreferences } from '@/lib/searches'

/** Portales conocidos: rellenan el id y una búsqueda de ejemplo. «Otra» deja escribir el id. */
const KNOWN: { id: string; name: string; example: string }[] = [
  { id: 'infojobs', name: 'InfoJobs', example: 'https://www.infojobs.net/ofertas-trabajo/madrid?keyword=data%20engineer' },
  { id: 'tecnoempleo', name: 'Tecnoempleo', example: 'https://www.tecnoempleo.com/ofertas-trabajo/?te=data+engineer' },
  { id: 'indeed', name: 'Indeed', example: 'https://es.indeed.com/jobs?q=data+engineer&l=Madrid' },
  { id: 'glassdoor', name: 'Glassdoor', example: 'https://www.glassdoor.es/Empleo/madrid-data-engineer-empleos-SRCH_IL.0,6_IC2664239_KO7,20.htm' },
  { id: 'manfred', name: 'Manfred', example: 'https://www.getmanfred.com/ofertas-empleo' },
  { id: 'linkedin', name: 'LinkedIn', example: 'https://www.linkedin.com/jobs/search/?keywords=data%20engineer&location=Madrid' },
]
const OTHER = 'otra'

function LinkedInNotice() {
  const { t } = useTranslation('platforms', { keyPrefix: 'add' })
  return (
    <div role="note" className="flex gap-2 rounded-lg border border-amber-500/50 bg-amber-500/10 p-3 text-sm text-amber-900 dark:text-amber-200">
      <WarningIcon weight="fill" className="mt-0.5 size-4 shrink-0" />
      <div className="space-y-1.5">
        <p className="font-medium">{t('linkedinTitle')}</p>
        <p>{t('linkedinP1')}</p>
        <p>{t('linkedinP2')}</p>
      </div>
    </div>
  )
}

/** `preferences` de tu perfil, para generar las búsquedas sin IA. */
function useSearchPreferences(): SearchPreferences | null {
  const profile = useEditableProfile()
  const prefs = (profile.data?.profile as { preferences?: SearchPreferences } | null | undefined)?.preferences
  return prefs ?? null
}

const toLines = (urls: string) =>
  urls
    .split('\n')
    .map((u) => u.trim())
    .filter(Boolean)

/**
 * Las búsquedas de la plataforma: en un portal conocido salen solas de tu perfil (los puestos que
 * buscas, en tus ubicaciones y en remoto) y se pueden retocar; debajo, cómo se leen.
 */
function SearchesField({
  platform,
  urls,
  setUrls,
  example,
}: {
  platform: string
  urls: string
  setUrls: (value: string) => void
  example: string
}) {
  const { t } = useTranslation('platforms', { keyPrefix: 'add' })
  const prefs = useSearchPreferences()
  const generated = buildSearches(platform, prefs)
  const lines = toLines(urls)
  const hint = !canBuildSearches(platform) ? 'urlsHint' : generated.length > 0 ? 'urlsHintGenerated' : 'urlsHintNoRoles'
  return (
    <div className="grid gap-1.5">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <Label htmlFor="platform-urls">{t('urls')}</Label>
        {generated.length > 0 && (
          <Button type="button" size="sm" variant="ghost" className="h-7 px-2" onClick={() => setUrls(generated.join('\n'))}>
            <SparkleIcon weight="duotone" className="text-primary" />
            {t('fromProfile')}
          </Button>
        )}
      </div>
      <Textarea id="platform-urls" value={urls} onChange={(e) => setUrls(e.target.value)} placeholder={example} rows={4} />
      <p className="text-xs text-muted-foreground">{t(hint)}</p>
      {lines.length > 0 && (
        <div className="text-xs">
          <p className="font-medium">{t('willSearch')}</p>
          <ul className="mt-1 flex flex-wrap gap-1.5">
            {lines.map((url) => (
              <li key={url} className="rounded-md border bg-muted/40 px-2 py-0.5">
                {searchLabel(url)}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function AddPlatformForm({ onDone }: { onDone: () => void }) {
  const { t } = useTranslation('platforms', { keyPrefix: 'add' })
  const add = useAddPlatform()
  // Fase 27.3: la prioridad es un puesto sin empates. Por defecto, la última; en otro puesto, se
  // inserta delante de la que lo tiene y las siguientes bajan uno.
  const platforms = usePlatforms()
  const taken = [...(platforms.data?.sources ?? [])]
    .flatMap((s) => (s.browse?.priority ? [{ name: s.name, priority: s.browse.priority }] : []))
    .sort((a, b) => a.priority - b.priority)
  const last = taken.length + 1
  const [known, setKnown] = useState('')
  const [name, setName] = useState('')
  const [platform, setPlatform] = useState('')
  // Lo que escribes; sin tocarlo, en un portal conocido, las búsquedas que salen de tu perfil.
  const [ownUrls, setUrls] = useState<string | null>(null)
  const [access, setAccess] = useState<BrowseAccess>('free')
  const [chosen, setChosen] = useState<number | null>(null) // sin elegir: la última
  const priority = chosen ?? last
  const linkedin = platform === 'linkedin'
  const prefs = useSearchPreferences()
  const urls = ownUrls ?? buildSearches(platform, prefs).join('\n')
  const searchUrls = toLines(urls)
  const ready = name.trim() !== '' && /^[a-z0-9][a-z0-9_-]{0,39}$/.test(platform) && searchUrls.length > 0

  const pick = (value: string) => {
    setKnown(value)
    const found = KNOWN.find((k) => k.id === value)
    if (found) {
      setName(found.name)
      setPlatform(found.id)
      if (found.id === 'linkedin') setAccess('login')
    } else {
      setPlatform('')
    }
  }

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!ready) return
    add.mutate(
      {
        name: name.trim(),
        platform,
        search_urls: searchUrls,
        access,
        // Sin elegir, no se manda: el servidor la pone al final (aunque otra pestaña haya
        // añadido alguna entre tanto).
        priority: chosen ?? undefined,
        // LinkedIn se crea siempre desactivada; el resto, activada (puedes desactivarla después).
        allow_agent_browsing: linkedin ? false : undefined,
      },
      { onSuccess: onDone },
    )
  }

  const example = KNOWN.find((k) => k.id === known)?.example ?? t('examplePlaceholder')
  return (
    <form onSubmit={submit} className="grid gap-4">
      <DialogHeader>
        <DialogTitle>{t('title')}</DialogTitle>
        <DialogDescription>
          {t('description')}
        </DialogDescription>
      </DialogHeader>

      <div className="grid gap-1.5">
        <Label htmlFor="platform-known">{t('portal')}</Label>
        <select
          id="platform-known"
          value={known}
          onChange={(e) => pick(e.target.value)}
          className="h-9 rounded-md border border-input bg-background px-3 text-sm"
        >
          <option value="" disabled>
            {t('pick')}
          </option>
          {KNOWN.map((k) => (
            <option key={k.id} value={k.id}>
              {k.name}
            </option>
          ))}
          <option value={OTHER}>{t('other')}</option>
        </select>
      </div>

      {known !== '' && (
        <>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="grid gap-1.5">
              <Label htmlFor="platform-name">{t('name')}</Label>
              <Input id="platform-name" value={name} onChange={(e) => setName(e.target.value)} maxLength={120} />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="platform-id">{t('id')}</Label>
              <Input
                id="platform-id"
                value={platform}
                onChange={(e) => setPlatform(e.target.value.toLowerCase())}
                disabled={known !== OTHER}
                placeholder={t('idPlaceholder')}
                maxLength={40}
              />
            </div>
          </div>
          {linkedin && <LinkedInNotice />}
          <SearchesField platform={platform} urls={urls} setUrls={setUrls} example={example} />
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="grid gap-1.5">
              <Label htmlFor="platform-access">{t('access')}</Label>
              <select
                id="platform-access"
                value={access}
                onChange={(e) => setAccess(e.target.value as BrowseAccess)}
                className="h-9 rounded-md border border-input bg-background px-3 text-sm"
              >
                <option value="free">{t('free')}</option>
                <option value="login">{t('login')}</option>
                <option value="blocked">{t('blocked')}</option>
              </select>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="platform-priority">{t('priority')}</Label>
              <select
                id="platform-priority"
                value={priority}
                onChange={(e) => setChosen(Number(e.target.value))}
                className="h-9 rounded-md border border-input bg-background px-3 text-sm"
              >
                {taken.map((slot) => (
                  <option key={slot.name} value={slot.priority}>
                    {t('before', { position: slot.priority, name: slot.name })}
                  </option>
                ))}
                <option value={last}>{t('last', { position: last })}</option>
              </select>
            </div>
          </div>
        </>
      )}

      {add.error && (
        <p role="alert" className="text-sm text-destructive">
          {errorMessage(add.error)}
        </p>
      )}
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onDone}>
          {t('cancel')}
        </Button>
        <Button type="submit" disabled={!ready || add.isPending}>
          {add.isPending ? t('saving') : t('submit')}
        </Button>
      </DialogFooter>
    </form>
  )
}

/** «Editar»: el nombre y las búsquedas. El portal no cambia (las búsquedas son de su sitio). */
function EditPlatformForm({ source, onDone }: { source: SourceView; onDone: () => void }) {
  const { t } = useTranslation('platforms', { keyPrefix: 'add' })
  const { t: te } = useTranslation('platforms', { keyPrefix: 'edit' })
  const edit = useEditPlatform()
  const platform = source.browse?.platform ?? ''
  const [name, setName] = useState(source.name)
  const [urls, setUrls] = useState((source.browse?.search_urls ?? []).join('\n'))
  const searchUrls = toLines(urls)
  const ready = name.trim() !== '' && searchUrls.length > 0
  const example = KNOWN.find((k) => k.id === platform)?.example ?? t('examplePlaceholder')
  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (ready) edit.mutate({ id: source.id, name: name.trim(), search_urls: searchUrls }, { onSuccess: onDone })
  }
  return (
    <form onSubmit={submit} className="grid gap-4">
      <DialogHeader>
        <DialogTitle>{te('title', { name: source.name })}</DialogTitle>
        <DialogDescription>{te('description')}</DialogDescription>
      </DialogHeader>
      <div className="grid gap-1.5">
        <Label htmlFor="platform-name">{t('name')}</Label>
        <Input id="platform-name" value={name} onChange={(e) => setName(e.target.value)} maxLength={120} />
      </div>
      <SearchesField platform={platform} urls={urls} setUrls={setUrls} example={example} />
      {edit.error && (
        <p role="alert" className="text-sm text-destructive">
          {errorMessage(edit.error)}
        </p>
      )}
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onDone}>
          {t('cancel')}
        </Button>
        <Button type="submit" disabled={!ready || edit.isPending}>
          {edit.isPending ? t('saving') : te('submit')}
        </Button>
      </DialogFooter>
    </form>
  )
}

/** Botón de icono y diálogo «Editar» de una plataforma. */
export function EditPlatformButton({ source }: { source: SourceView }) {
  const { t } = useTranslation('platforms', { keyPrefix: 'edit' })
  const [open, setOpen] = useState(false)
  const label = t('button', { name: source.name })
  return (
    <>
      <Hint text={label}>
        <Button type="button" size="icon" variant="ghost" className="size-8" aria-label={label} onClick={() => setOpen(true)}>
          <PencilSimpleIcon />
        </Button>
      </Hint>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[90dvh] overflow-y-auto">
          {open && <EditPlatformForm source={source} onDone={() => setOpen(false)} />}
        </DialogContent>
      </Dialog>
    </>
  )
}

/** Botón y diálogo «Añadir plataforma». */
/** `primary`: relleno, si es la acción destacada de la pantalla; si no, con borde. */
export function AddPlatformButton({ primary = false }: { primary?: boolean }) {
  const { t } = useTranslation('platforms', { keyPrefix: 'add' })
  const [open, setOpen] = useState(false)
  return (
    <>
      <Button type="button" size="sm" variant={primary ? 'default' : 'outline'} onClick={() => setOpen(true)}>
        <PlusIcon />
        {t('button')}
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[90dvh] overflow-y-auto">
          {open && <AddPlatformForm onDone={() => setOpen(false)} />}
        </DialogContent>
      </Dialog>
    </>
  )
}
