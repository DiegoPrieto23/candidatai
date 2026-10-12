import { useState, type FormEvent } from 'react'
import { HandshakeIcon, LockSimpleIcon } from '@phosphor-icons/react'
import type { JobView, ReceivedOffer, ReceivedOfferFields, Stage } from '@/api/client'
import { useDeleteReceivedOffer, useReceivedOffer, useSaveReceivedOffer } from '@/api/queries'
import { AgentButton } from '@/components/AgentButton'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { formatDate, formatMoney, REMOTE_LABEL } from '@/lib/labels'

/** Etapas en las que la empresa puede haberte hecho una oferta (`offer_received`). */
const OFFER_STAGES: ReadonlySet<Stage> = new Set(['applied', 'in_process'])
const PERIOD_LABEL = { year: 'al año', month: 'al mes' } as const
const WORK_MODES = ['remote', 'hybrid', 'onsite'] as const

type FormState = {
  base_salary: string
  variable: string
  currency: string
  period: 'year' | 'month'
  benefits: string
  work_mode: '' | (typeof WORK_MODES)[number]
  location: string
  start_date: string
  respond_by: string
  notes: string
  amounts_private: boolean
}

function toForm(offer: ReceivedOffer | null | undefined): FormState {
  return {
    base_salary: offer?.base_salary?.toString() ?? '',
    variable: offer?.variable?.toString() ?? '',
    currency: offer?.currency ?? 'EUR',
    period: offer?.period ?? 'year',
    benefits: offer?.benefits ?? '',
    work_mode: offer?.work_mode ?? '',
    location: offer?.location ?? '',
    start_date: offer?.start_date ?? '',
    respond_by: offer?.respond_by ?? '',
    notes: offer?.notes ?? '',
    amounts_private: offer?.amounts_private ?? true,
  }
}

function toBody(f: FormState): ReceivedOfferFields {
  const amount = (v: string) => {
    const n = Number(v)
    return v.trim() && Number.isFinite(n) ? n : null
  }
  return {
    base_salary: amount(f.base_salary),
    variable: amount(f.variable),
    currency: f.currency.trim() || 'EUR',
    period: f.period,
    benefits: f.benefits || null,
    work_mode: f.work_mode || null,
    location: f.location || null,
    start_date: f.start_date || null,
    respond_by: f.respond_by || null,
    notes: f.notes || null,
    amounts_private: f.amounts_private,
  }
}

function OfferForm({ jobId, offer, onDone }: { jobId: number; offer: ReceivedOffer | null; onDone: () => void }) {
  const [f, setF] = useState<FormState>(() => toForm(offer))
  const save = useSaveReceivedOffer(jobId)
  const set = <K extends keyof FormState>(key: K, value: FormState[K]) => setF((prev) => ({ ...prev, [key]: value }))
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate(toBody(f), { onSuccess: onDone })
  }
  const input = (key: 'base_salary' | 'variable' | 'currency' | 'location' | 'start_date' | 'respond_by', label: string, type = 'text') => (
    <div className="space-y-1.5">
      <Label htmlFor={`offer-${key}`}>{label}</Label>
      <Input
        id={`offer-${key}`}
        type={type}
        min={type === 'number' ? 0 : undefined}
        value={f[key]}
        onChange={(e) => set(key, e.target.value)}
      />
    </div>
  )
  return (
    <form onSubmit={submit} className="grid gap-3 rounded-lg border bg-background p-3">
      <div className="grid gap-3 sm:grid-cols-2">
        {input('base_salary', 'Fijo bruto', 'number')}
        {input('variable', 'Variable bruto anual', 'number')}
        {input('currency', 'Moneda')}
        <div className="space-y-1.5">
          <Label htmlFor="offer-period">El fijo es</Label>
          <select
            id="offer-period"
            value={f.period}
            onChange={(e) => set('period', e.target.value as FormState['period'])}
            className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
          >
            <option value="year">Anual</option>
            <option value="month">Mensual</option>
          </select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="offer-work_mode">Modalidad</Label>
          <select
            id="offer-work_mode"
            value={f.work_mode}
            onChange={(e) => set('work_mode', e.target.value as FormState['work_mode'])}
            className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
          >
            <option value="">Sin indicar</option>
            {WORK_MODES.map((m) => (
              <option key={m} value={m}>
                {REMOTE_LABEL[m]}
              </option>
            ))}
          </select>
        </div>
        {input('location', 'Ubicación')}
        {input('start_date', 'Incorporación', 'date')}
        {input('respond_by', 'Responder antes de', 'date')}
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="offer-benefits">Beneficios</Label>
        <Textarea id="offer-benefits" rows={2} value={f.benefits} onChange={(e) => set('benefits', e.target.value)} />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="offer-notes">Notas (las lee tu agente: no pongas aquí tus cifras)</Label>
        <Textarea id="offer-notes" rows={2} value={f.notes} onChange={(e) => set('notes', e.target.value)} />
      </div>
      <label className="flex items-start gap-2 text-sm">
        <input
          type="checkbox"
          className="mt-0.5"
          checked={f.amounts_private}
          onChange={(e) => set('amounts_private', e.target.checked)}
        />
        <span>
          Importes privados: tu agente no ve el fijo ni el variable.
          <span className="block text-xs text-muted-foreground">
            Tu mínimo y la diferencia con él no los ve nunca.
          </span>
        </span>
      </label>
      {save.error && (
        <p role="alert" className="text-sm text-destructive">
          {save.error.message}
        </p>
      )}
      <div className="flex justify-end gap-2">
        <Button type="button" variant="outline" size="sm" onClick={onDone}>
          Cancelar
        </Button>
        <Button type="submit" size="sm" disabled={save.isPending}>
          {save.isPending ? 'Guardando…' : 'Guardar oferta'}
        </Button>
      </div>
    </form>
  )
}

function OfferSummary({ offer }: { offer: ReceivedOffer }) {
  const rows: [string, string | null][] = [
    ['Fijo', offer.base_salary != null ? `${formatMoney(offer.base_salary, offer.currency)} ${PERIOD_LABEL[offer.period]}` : null],
    ['Variable', offer.variable != null ? `${formatMoney(offer.variable, offer.currency)} al año` : null],
    ['Modalidad', offer.work_mode ? REMOTE_LABEL[offer.work_mode] : null],
    ['Ubicación', offer.location],
    ['Incorporación', offer.start_date ? formatDate(offer.start_date) : null],
    ['Responder antes de', offer.respond_by ? formatDate(offer.respond_by) : null],
    ['Beneficios', offer.benefits],
    ['Notas', offer.notes],
  ]
  return (
    <dl className="grid gap-x-4 gap-y-1.5 text-sm sm:grid-cols-[10rem_minmax(0,1fr)]">
      {rows
        .filter(([, v]) => v)
        .map(([label, value]) => (
          <div key={label} className="contents">
            <dt className="text-muted-foreground">{label}</dt>
            <dd className="whitespace-pre-line">{value}</dd>
          </div>
        ))}
    </dl>
  )
}

/**
 * Ficha (fase 21): la oferta que te ha hecho la empresa. La anotas tú; con «importes privados»
 * (por defecto) tu agente no ve el fijo ni el variable. La comparación con tu mínimo está en
 * Procesos → «Ofertas recibidas» y nunca sale hacia el agente.
 */
export function ReceivedOfferSection({ job }: { job: JobView }) {
  const canHave = job.stage !== null && OFFER_STAGES.has(job.stage)
  const { data: offer, isPending } = useReceivedOffer(job.id)
  const remove = useDeleteReceivedOffer(job.id)
  const [editing, setEditing] = useState(false)
  if (isPending || (!offer && !canHave)) return null
  return (
    <section aria-label="Oferta recibida" className="rounded-xl border bg-card p-5 sm:p-6">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 font-semibold">
            <HandshakeIcon className="size-[18px] text-primary" weight="duotone" />
            Oferta recibida
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {offer
              ? `Anotada el ${formatDate(offer.updated_at)}. Compárala con tu mínimo en Procesos.`
              : '¿Te han hecho una oferta? Anótala para compararla y preparar la negociación.'}
          </p>
        </div>
        {offer && offer.amounts_private && (
          <span className="inline-flex items-center gap-1 rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
            <LockSimpleIcon className="size-3.5" />
            Importes privados
          </span>
        )}
      </div>
      {editing ? (
        <OfferForm jobId={job.id} offer={offer ?? null} onDone={() => setEditing(false)} />
      ) : (
        <div className="space-y-4">
          {offer && <OfferSummary offer={offer} />}
          <div className="flex flex-wrap gap-2">
            <Button variant={offer ? 'outline' : 'default'} size="sm" onClick={() => setEditing(true)}>
              {offer ? 'Editar' : 'Anotar oferta'}
            </Button>
            {offer && job.stage === 'in_process' && (
              <AgentButton action="preparar-negociacion" jobId={job.id}>
                Preparar negociación
              </AgentButton>
            )}
            {offer && (
              <Button variant="ghost" size="sm" disabled={remove.isPending} onClick={() => remove.mutate()}>
                Borrar datos
              </Button>
            )}
          </div>
          {remove.error && (
            <p role="alert" className="text-sm text-destructive">
              {remove.error.message}
            </p>
          )}
        </div>
      )}
    </section>
  )
}
