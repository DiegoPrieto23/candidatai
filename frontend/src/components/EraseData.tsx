import { useState, type FormEvent, type ReactElement } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router'
import { useQueryClient } from '@tanstack/react-query'
import { TrashIcon, WarningIcon } from '@phosphor-icons/react'
import { forgetErasedJob, useEraseAll, useEraseJob, useStatus } from '@/api/queries'
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
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { BusyLabel } from '@/components/StableLabel'
import { errorMessage } from '@/lib/errors'

/** Lo que se acaba de borrar, para el aviso de la página a la que se vuelve. */
export interface ErasedNotice {
  erased: string
}

const same = (a: string, b: string) => a.trim().toLocaleLowerCase() === b.trim().toLocaleLowerCase()

/**
 * Confirmación escrita, el último paso de los dos borrados: el botón solo se activa cuando lo
 * escrito coincide (la API lo comprueba también).
 */
function TypedConfirm({
  id,
  label,
  expected,
  exact = false,
  pending,
  error,
  eraseText,
  erasingText,
  cancelText,
  onCancel,
  onConfirm,
}: {
  id: string
  label: string
  expected: string
  exact?: boolean
  pending: boolean
  error: unknown
  eraseText: string
  erasingText: string
  cancelText: string
  onCancel: () => void
  onConfirm: (typed: string) => void
}) {
  const [typed, setTyped] = useState('')
  const matches = exact ? typed.trim() === expected : same(typed, expected)
  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (matches && !pending) onConfirm(typed)
  }
  return (
    <form onSubmit={submit} className="grid gap-4">
      <div className="space-y-2">
        <Label htmlFor={id}>{label}</Label>
        <Input id={id} value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" autoFocus />
      </div>
      {error != null && (
        <p role="alert" className="text-sm text-destructive">
          {errorMessage(error)}
        </p>
      )}
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onCancel}>
          {cancelText}
        </Button>
        <Button type="submit" variant="destructive" disabled={!matches || pending}>
          <TrashIcon />
          <BusyLabel busy={pending} busyText={erasingText} text={eraseText} />
        </Button>
      </DialogFooter>
    </form>
  )
}

/** Borrar no es descartar: lo dice el botón al pasar por él y el primer aviso. */
function WithTip({ tip, children }: { tip: string; children: ReactElement }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>{children}</TooltipTrigger>
      <TooltipContent className="max-w-xs text-balance">{tip}</TooltipContent>
    </Tooltip>
  )
}

const DANGER = 'border-destructive/40 text-destructive hover:bg-destructive/10 hover:text-destructive'

/** «Borrar oferta», arriba en la ficha: un aviso con lo que se va y, después, escribir la empresa. */
export function EraseJobButton({ jobId, title, company }: { jobId: number; title: string; company: string }) {
  const { t } = useTranslation('erase', { keyPrefix: 'job' })
  const [step, setStep] = useState<0 | 1 | 2>(0)
  const erase = useEraseJob()
  const client = useQueryClient()
  const navigate = useNavigate()
  const close = () => {
    setStep(0)
    erase.reset()
  }
  const confirm = (typed: string) =>
    erase.mutateAsync({ jobId, confirm: typed }).then(
      (result) => {
        // Primero se sale de la ficha, para que no vuelva a pedirse la oferta que ya no existe.
        navigate('/procesos', { state: { erased: t('done', { backup: result.backup }) } satisfies ErasedNotice })
        void forgetErasedJob(client, jobId)
      },
      () => undefined,
    )
  return (
    <>
      <WithTip tip={t('notDiscard')}>
        <Button variant="outline" size="sm" className={DANGER} onClick={() => setStep(1)}>
          <TrashIcon />
          {t('button')}
        </Button>
      </WithTip>
      <Dialog open={step > 0} onOpenChange={(open) => !open && close()}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-destructive">
              <WarningIcon weight="fill" />
              {t('title')}
            </DialogTitle>
            <DialogDescription>{t('lead', { title })}</DialogDescription>
          </DialogHeader>
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {([1, 2, 3, 4] as const).map((n) => (
              <li key={n}>{t(`goes${n}`)}</li>
            ))}
          </ul>
          <p className="rounded-lg border border-warning-border bg-warning px-3 py-2 text-sm text-warning-foreground">
            {t('notDiscard')}
          </p>
          <p className="text-sm text-muted-foreground">{t('stays')}</p>
          <p className="text-sm font-medium">{t('backup')}</p>
          {step === 1 ? (
            <DialogFooter>
              <Button type="button" variant="outline" onClick={close}>
                {t('cancel')}
              </Button>
              <Button type="button" variant="destructive" onClick={() => setStep(2)}>
                {t('continue')}
              </Button>
            </DialogFooter>
          ) : (
            <TypedConfirm
              id="erase-job-confirm"
              label={t('confirmLabel', { company })}
              expected={company}
              pending={erase.isPending}
              error={erase.error}
              eraseText={t('erase')}
              erasingText={t('erasing')}
              cancelText={t('cancel')}
              onCancel={close}
              onConfirm={(typed) => void confirm(typed)}
            />
          )}
        </DialogContent>
      </Dialog>
    </>
  )
}

/**
 * «Vaciar todo», en la barra de la Bandeja: dos avisos, escribir BORRAR (DELETE en inglés) y, al
 * final, el resultado con dónde quedó la copia.
 */
export function EraseAllButton() {
  const { t } = useTranslation('erase', { keyPrefix: 'all' })
  const jobs = useStatus().data?.total ?? 0
  const [step, setStep] = useState<0 | 1 | 2 | 3 | 4>(0)
  const [done, setDone] = useState('')
  const erase = useEraseAll()
  const word = t('word')
  const close = () => {
    setStep(0)
    erase.reset()
  }
  const confirm = (typed: string) =>
    erase.mutateAsync(typed).then(
      (result) => {
        setDone(t('done', { count: result.deleted_jobs, backup: result.backup }))
        setStep(4)
      },
      () => undefined,
    )
  const titles = { 1: t('step1Title'), 2: t('step2Title'), 3: t('step2Title'), 4: t('doneTitle') }
  return (
    <>
      <WithTip tip={t('intro')}>
        {/* Un botón deshabilitado no da el aviso: va envuelto para que salga igual. */}
        <span className="inline-flex">
          <Button variant="outline" size="sm" className={DANGER} disabled={jobs === 0} onClick={() => setStep(1)}>
            <TrashIcon />
            {t('button')}
          </Button>
        </span>
      </WithTip>
      <Dialog open={step > 0} onOpenChange={(open) => !open && close()}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className={step === 4 ? undefined : 'flex items-center gap-2 text-destructive'}>
              {step < 4 && <WarningIcon weight="fill" />}
              {step > 0 && titles[step as 1 | 2 | 3 | 4]}
            </DialogTitle>
            <DialogDescription>
              {step === 1 ? t('step1Body', { count: jobs }) : step === 4 ? done : t('step2Body')}
            </DialogDescription>
          </DialogHeader>
          {step === 1 && <p className="text-sm text-muted-foreground">{t('stays')}</p>}
          {step === 3 ? (
            <TypedConfirm
              id="erase-all-confirm"
              label={t('confirmLabel', { word })}
              expected={word}
              exact
              pending={erase.isPending}
              error={erase.error}
              eraseText={t('erase')}
              erasingText={t('erasing')}
              cancelText={t('cancel')}
              onCancel={close}
              onConfirm={(typed) => void confirm(typed)}
            />
          ) : step === 4 ? (
            <DialogFooter>
              <Button type="button" onClick={close}>
                {t('close')}
              </Button>
            </DialogFooter>
          ) : (
            <DialogFooter>
              <Button type="button" variant="outline" onClick={close}>
                {t('cancel')}
              </Button>
              <Button type="button" variant="destructive" onClick={() => setStep(step === 1 ? 2 : 3)}>
                {t('continue')}
              </Button>
            </DialogFooter>
          )}
        </DialogContent>
      </Dialog>
    </>
  )
}
