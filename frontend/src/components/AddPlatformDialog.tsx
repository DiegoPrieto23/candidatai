import { useState, type FormEvent } from 'react'
import { PlusIcon, WarningIcon } from '@phosphor-icons/react'
import type { BrowseAccess } from '@/api/client'
import { useAddPlatform } from '@/api/queries'
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
  return (
    <div role="note" className="flex gap-2 rounded-lg border border-amber-500/50 bg-amber-500/10 p-3 text-sm text-amber-900 dark:text-amber-200">
      <WarningIcon weight="fill" className="mt-0.5 size-4 shrink-0" />
      <div className="space-y-1.5">
        <p className="font-medium">Se guarda con la búsqueda desactivada, y es lo recomendable.</p>
        <p>
          Las condiciones de LinkedIn prohíben recorrer su web con herramientas automáticas y puede restringir o
          cerrar tu cuenta si lo detecta, aunque el agente use tu navegador y solo lea. Lo seguro es recibir sus
          ofertas por las alertas por correo (pantalla «Alertas») o con el botón «Enviar a CandidatAI».
        </p>
        <p>Si aun así quieres que el agente la recorra, actívala después con su interruptor, bajo tu responsabilidad.</p>
      </div>
    </div>
  )
}

function AddPlatformForm({ onDone }: { onDone: () => void }) {
  const add = useAddPlatform()
  const [known, setKnown] = useState('')
  const [name, setName] = useState('')
  const [platform, setPlatform] = useState('')
  const [urls, setUrls] = useState('')
  const [access, setAccess] = useState<BrowseAccess>('free')
  const [priority, setPriority] = useState(5)
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
        priority,
        // LinkedIn se crea siempre desactivada; el resto, activada (puedes desactivarla después).
        allow_agent_browsing: linkedin ? false : undefined,
      },
      { onSuccess: onDone },
    )
  }

  const example = KNOWN.find((k) => k.id === known)?.example ?? 'https://www.portal.com/empleos?q=data+engineer'
  return (
    <form onSubmit={submit} className="grid gap-4">
      <DialogHeader>
        <DialogTitle>Añadir plataforma</DialogTitle>
        <DialogDescription>
          Un portal donde tu agente busca ofertas con tu navegador cuando le pides «search-jobs».
        </DialogDescription>
      </DialogHeader>

      <div className="grid gap-1.5">
        <Label htmlFor="platform-known">Portal</Label>
        <select
          id="platform-known"
          value={known}
          onChange={(e) => pick(e.target.value)}
          className="h-9 rounded-md border border-input bg-background px-3 text-sm"
        >
          <option value="" disabled>
            Elige un portal…
          </option>
          {KNOWN.map((k) => (
            <option key={k.id} value={k.id}>
              {k.name}
            </option>
          ))}
          <option value={OTHER}>Otro portal</option>
        </select>
      </div>

      {known !== '' && (
        <>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="grid gap-1.5">
              <Label htmlFor="platform-name">Nombre</Label>
              <Input id="platform-name" value={name} onChange={(e) => setName(e.target.value)} maxLength={120} />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="platform-id">Id corto</Label>
              <Input
                id="platform-id"
                value={platform}
                onChange={(e) => setPlatform(e.target.value.toLowerCase())}
                disabled={known !== OTHER}
                placeholder="miportal"
                maxLength={40}
              />
            </div>
          </div>
          {linkedin && <LinkedInNotice />}
          <div className="grid gap-1.5">
            <Label htmlFor="platform-urls">Búsquedas (una URL por línea)</Label>
            <Textarea
              id="platform-urls"
              value={urls}
              onChange={(e) => setUrls(e.target.value)}
              placeholder={example}
              rows={3}
            />
            <p className="text-xs text-muted-foreground">
              Haz la búsqueda en el portal (puesto, ubicación, filtros) y copia aquí la dirección de los resultados.
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="grid gap-1.5">
              <Label htmlFor="platform-access">Acceso</Label>
              <select
                id="platform-access"
                value={access}
                onChange={(e) => setAccess(e.target.value as BrowseAccess)}
                className="h-9 rounded-md border border-input bg-background px-3 text-sm"
              >
                <option value="free">Libre (sin iniciar sesión)</option>
                <option value="login">Con sesión (inicias sesión tú)</option>
                <option value="blocked">Bloqueada (el agente la salta)</option>
              </select>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="platform-priority">Prioridad (1 = primero)</Label>
              <Input
                id="platform-priority"
                type="number"
                min={1}
                max={10}
                value={priority}
                onChange={(e) => setPriority(Math.min(10, Math.max(1, Number(e.target.value) || 1)))}
              />
            </div>
          </div>
        </>
      )}

      {add.error && (
        <p role="alert" className="text-sm text-destructive">
          {add.error.message}
        </p>
      )}
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onDone}>
          Cancelar
        </Button>
        <Button type="submit" disabled={!ready || add.isPending}>
          {add.isPending ? 'Guardando…' : 'Añadir'}
        </Button>
      </DialogFooter>
    </form>
  )
}

/** Botón y diálogo «Añadir plataforma». */
export function AddPlatformButton() {
  const [open, setOpen] = useState(false)
  return (
    <>
      <Button type="button" size="sm" onClick={() => setOpen(true)}>
        <PlusIcon />
        Añadir plataforma
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[90dvh] overflow-y-auto">
          {open && <AddPlatformForm onDone={() => setOpen(false)} />}
        </DialogContent>
      </Dialog>
    </>
  )
}
