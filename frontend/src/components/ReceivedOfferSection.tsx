import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { HandshakeIcon, LockSimpleIcon } from '@phosphor-icons/react'
import type { JobView, ReceivedOffer, ReceivedOfferFields, Stage } from '@/api/client'
import { useDeleteReceivedOffer, useReceivedOffer, useSaveReceivedOffer } from '@/api/queries'
import { AgentButton } from '@/components/AgentButton'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { formatDate, formatMoney, REMOTE_LABEL } from '@/lib/labels'
import { errorMessage } from '@/lib/errors'

/** Etapas en las que la empresa puede haberte hecho una oferta (`offer_received`). */
const OFFER_STAGES: ReadonlySet<Stage> = new Set(['applied', 'in_process'])
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
  const { t } = useTranslation('offers', { keyPrefix: 'received.form' })
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
        {input('base_salary', t('base'), 'number')}
        {input('variable', t('variable'), 'number')}
        {input('currency', t('currency'))}
        <div className="space-y-1.5">
          <Label htmlFor="offer-period">{t('period')}</Label>
          <select
            id="offer-period"
            value={f.period}
            onChange={(e) => set('period', e.target.value as FormState['period'])}
            className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
          >
            <option value="year">{t('yearly')}</option>
            <option value="month">{t('monthly')}</option>
          </select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="offer-work_mode">{t('mode')}</Label>
          <select
            id="offer-work_mode"
            value={f.work_mode}
            onChange={(e) => set('work_mode', e.target.value as FormState['work_mode'])}
            className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
          >
            <option value="">{t('noMode')}</option>
            {WORK_MODES.map((m) => (
              <option key={m} value={m}>
                {REMOTE_LABEL[m]}
              </option>
            ))}
          </select>
        </div>
        {input('location', t('location'))}
        {input('start_date', t('start'), 'date')}
        {input('respond_by', t('respondBy'), 'date')}
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="offer-benefits">{t('benefits')}</Label>
        <Textarea id="offer-benefits" rows={2} value={f.benefits} onChange={(e) => set('benefits', e.target.value)} />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="offer-notes">{t('notes')}</Label>
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
          {t('private')}
          <span className="block text-xs text-muted-foreground">{t('privateHint')}</span>
        </span>
      </label>
      {save.error && (
        <p role="alert" className="text-sm text-destructive">
          {errorMessage(save.error)}
        </p>
      )}
      <div className="flex justify-end gap-2">
        <Button type="button" variant="outline" size="sm" onClick={onDone}>
          {t('cancel')}
        </Button>
        <Button type="submit" size="sm" disabled={save.isPending}>
          {save.isPending ? t('saving') : t('save')}
        </Button>
      </div>
    </form>
  )
}

function OfferSummary({ offer }: { offer: ReceivedOffer }) {
  const { t } = useTranslation('offers', { keyPrefix: 'received.summary' })
  const per = (amount: number, period: 'year' | 'month') =>
    t(period === 'year' ? 'perYear' : 'perMonth', { amount: formatMoney(amount, offer.currency) })
  const rows: [string, string | null][] = [
    [t('base'), offer.base_salary != null ? per(offer.base_salary, offer.period) : null],
    [t('variable'), offer.variable != null ? per(offer.variable, 'year') : null],
    [t('mode'), offer.work_mode ? REMOTE_LABEL[offer.work_mode] : null],
    [t('location'), offer.location],
    [t('start'), offer.start_date ? formatDate(offer.start_date) : null],
    [t('respondBy'), offer.respond_by ? formatDate(offer.respond_by) : null],
    [t('benefits'), offer.benefits],
    [t('notes'), offer.notes],
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
  const { t } = useTranslation('offers', { keyPrefix: 'received' })
  const canHave = job.stage !== null && OFFER_STAGES.has(job.stage)
  const { data: offer, isPending } = useReceivedOffer(job.id)
  const remove = useDeleteReceivedOffer(job.id)
  const [editing, setEditing] = useState(false)
  if (isPending || (!offer && !canHave)) return null
  return (
    <section aria-label={t('title')} className="rounded-xl border bg-card p-5 sm:p-6">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 font-semibold">
            <HandshakeIcon className="size-[18px] text-primary" weight="duotone" />
            {t('title')}
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {offer
              ? t('noted', { date: formatDate(offer.updated_at) })
              : t('prompt')}
          </p>
        </div>
        {offer && offer.amounts_private && (
          <span className="inline-flex items-center gap-1 rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
            <LockSimpleIcon className="size-3.5" />
            {t('private')}
          </span>
        )}
      </div>
      {editing ? (
        <OfferForm jobId={job.id} offer={offer ?? null} onDone={() => setEditing(false)} />
      ) : (
        <div className="space-y-4">
          {offer && <OfferSummary offer={offer} />}
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
              {offer ? t('edit') : t('add')}
            </Button>
            {offer && job.stage === 'in_process' && (
              <AgentButton action="prepare-negotiation" jobId={job.id}>
                {t('negotiate')}
              </AgentButton>
            )}
            {offer && (
              <Button variant="ghost" size="sm" disabled={remove.isPending} onClick={() => remove.mutate()}>
                {t('delete')}
              </Button>
            )}
          </div>
          {remove.error && (
            <p role="alert" className="text-sm text-destructive">
              {errorMessage(remove.error)}
            </p>
          )}
        </div>
      )}
    </section>
  )
}
