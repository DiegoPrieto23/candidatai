import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { PlusIcon, WarningIcon } from '@phosphor-icons/react'
import type { BrowseAccess } from '@/api/client'
import { useAddPlatform, usePlatforms } from '@/api/queries'
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
  const [urls, setUrls] = useState('')
  const [access, setAccess] = useState<BrowseAccess>('free')
  const [chosen, setChosen] = useState<number | null>(null) // sin elegir: la última
  const priority = chosen ?? last
  const linkedin = platform === 'linkedin'
  const searchUrls = urls
    .split('\n')
    .map((u) => u.trim())
    .filter(Boolean)
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
          <div className="grid gap-1.5">
            <Label htmlFor="platform-urls">{t('urls')}</Label>
            <Textarea
              id="platform-urls"
              value={urls}
              onChange={(e) => setUrls(e.target.value)}
              placeholder={example}
              rows={3}
            />
            <p className="text-xs text-muted-foreground">
              {t('urlsHint')}
            </p>
          </div>
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
