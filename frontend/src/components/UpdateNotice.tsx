import { useEffect, useState } from 'react'
import { Trans, useTranslation } from 'react-i18next'
import { ArrowCircleUpIcon, ArrowSquareOutIcon, CircleNotchIcon } from '@phosphor-icons/react'
import { api, type Schemas } from '@/api/client'
import { useApplyUpdate, useStatus, useUpdateStatus } from '@/api/queries'
import { CommandBox } from '@/components/CommandBox'
import { BusyLabel } from '@/components/StableLabel'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { errorMessage } from '@/lib/errors'
import { desktopOs } from '@/lib/extension'
import { i18n, SOURCE_LANGUAGE } from '@/lib/i18n'

const STORAGE_KEY = 'candidatai.updateNotice.later'
const GUIDE = {
  es: 'https://github.com/DiegoPrieto23/candidatai/blob/main/docs/GUIA.md#13-actualizar',
  en: 'https://github.com/DiegoPrieto23/candidatai/blob/main/docs/GUIDE.md#13-updating',
}
/** Mientras se actualiza, cada cuánto se pregunta si la app ha vuelto, y cuándo se avisa de que tarda. */
const POLL_MS = 3000
const SLOW_MS = 15 * 60_000

/** La versión que se pospuso con «Ahora no»: esa no vuelve a avisarse; la siguiente, sí. */
function postponed(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

function postpone(version: string) {
  try {
    localStorage.setItem(STORAGE_KEY, version)
  } catch {
    // Sin almacenamiento, el aviso vuelve al recargar: nada se pierde.
  }
}

const LINK = 'inline-flex items-center gap-1 text-primary underline decoration-primary/30 underline-offset-4 hover:decoration-primary'

function GuideLink({ children }: { children?: React.ReactNode }) {
  return (
    <a href={i18n.language === SOURCE_LANGUAGE ? GUIDE.es : GUIDE.en} target="_blank" rel="noreferrer" className={LINK}>
      {children}
    </a>
  )
}

/** Cómo se actualiza a mano esta instalación: la orden con «Copiar» o, en el repositorio, la guía. */
function HowToUpdate({ update }: { update: Schemas['UpdateStatus'] }) {
  const { t } = useTranslation('home', { keyPrefix: 'update' })
  if (!update.command) {
    return (
      <p className="mt-1.5 text-pretty text-muted-foreground">
        <Trans t={t} i18nKey="howRepository" components={{ guide: <GuideLink /> }} />
      </p>
    )
  }
  const how = update.install === 'docker' ? 'howDocker' : desktopOs() === 'windows' ? 'howWindows' : 'howUnix'
  return (
    <div className="mt-2 space-y-2">
      <p className="text-pretty text-muted-foreground">{t(how)}</p>
      <CommandBox text={update.command} label={t('command')} mono />
    </div>
  )
}

/**
 * Tras «Actualizar»: la app se ha cerrado y la actualiza otra ventana. Se pregunta cada pocos
 * segundos si ha vuelto; en cuanto responde después de haberse ido, se recarga la página con la
 * versión nueva.
 */
function useReloadWhenBack(active: boolean) {
  const [slow, setSlow] = useState(false)
  useEffect(() => {
    if (!active) return
    let wentAway = false
    let stopped = false
    const started = Date.now()
    const timer = window.setInterval(() => {
      if (Date.now() - started > SLOW_MS) setSlow(true)
      api.GET('/status').then(
        ({ response }) => {
          if (!stopped && wentAway && response.ok) window.location.reload()
        },
        () => {
          wentAway = true
        },
      )
    }, POLL_MS)
    return () => {
      stopped = true
      window.clearInterval(timer)
    }
  }, [active])
  return slow
}

/**
 * Hay una versión nueva: una banda en Inicio, como la del llavero. Con el instalador de Windows,
 * «Actualizar ahora» la instala sin terminal; en el resto, la orden o la guía. «Ahora no» la
 * pospone hasta la siguiente versión. Nunca en la demo.
 */
export function UpdateNotice() {
  const { t } = useTranslation('home', { keyPrefix: 'update' })
  const demo = useStatus().data?.demo_mode
  const { data: update } = useUpdateStatus(demo === false)
  const apply = useApplyUpdate()
  const [later, setLater] = useState(postponed)
  const [confirming, setConfirming] = useState(false)
  const updating = apply.isSuccess
  const slow = useReloadWhenBack(updating)

  if (!update?.available || !update.latest || demo !== false) return null
  if (later === update.latest && !updating) return null
  const latest = update.latest

  if (updating) {
    return (
      <section
        role="status"
        aria-label={t('updating.title', { latest })}
        className="flex items-start gap-3 rounded-xl border bg-card px-4 py-3 text-sm animate-in fade-in duration-200"
      >
        <CircleNotchIcon className="mt-0.5 size-5 shrink-0 animate-spin text-primary" weight="bold" aria-hidden />
        <div className="min-w-0 flex-1">
          <p className="font-medium">{t('updating.title', { latest })}</p>
          <p className="mt-0.5 text-pretty text-muted-foreground">{t('updating.body')}</p>
          {slow && <p className="mt-1.5 text-pretty text-warning-foreground">{t('updating.slow')}</p>}
        </div>
      </section>
    )
  }

  const close = () => {
    setConfirming(false)
    apply.reset()
  }
  return (
    <section
      aria-label={t('label')}
      className="flex flex-wrap items-start gap-3 rounded-xl border bg-card px-4 py-3 text-sm animate-in fade-in duration-200"
    >
      <ArrowCircleUpIcon className="mt-0.5 size-5 shrink-0 text-primary" weight="duotone" aria-hidden />
      <div className="min-w-0 flex-1 basis-80">
        <p className="font-medium">{t('title', { latest })}</p>
        <p className="mt-0.5 text-pretty text-muted-foreground">
          {t('body', { current: update.current })}{' '}
          {update.release_url && (
            <a href={update.release_url} target="_blank" rel="noreferrer" className={LINK}>
              {t('notes')}
              <ArrowSquareOutIcon className="size-3.5" aria-hidden />
            </a>
          )}
        </p>
        {!update.can_apply && <HowToUpdate update={update} />}
      </div>
      {/* Sin relleno: en Inicio, la única acción rellena es la del titular. */}
      <div className="flex shrink-0 flex-wrap items-center gap-2">
        {update.can_apply && (
          <Button size="sm" variant="outline" onClick={() => setConfirming(true)}>
            {t('apply')}
          </Button>
        )}
        <Button
          size="sm"
          variant="ghost"
          onClick={() => {
            postpone(latest)
            setLater(latest)
          }}
        >
          {t('later')}
        </Button>
      </div>
      <Dialog open={confirming} onOpenChange={(open) => !open && close()}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('confirm.title', { latest })}</DialogTitle>
            <DialogDescription>{t('confirm.body')}</DialogDescription>
          </DialogHeader>
          <ul className="list-disc space-y-1 pl-5 text-sm">
            <li>{t('confirm.data')}</li>
            <li>{t('confirm.agent')}</li>
          </ul>
          {apply.error != null && (
            <p role="alert" className="text-sm text-destructive">
              {errorMessage(apply.error)}
            </p>
          )}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={close}>
              {t('confirm.cancel')}
            </Button>
            <Button type="button" disabled={apply.isPending} onClick={() => apply.mutate(latest)}>
              <BusyLabel busy={apply.isPending} busyText={t('confirm.confirming')} text={t('confirm.confirm')} />
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  )
}
