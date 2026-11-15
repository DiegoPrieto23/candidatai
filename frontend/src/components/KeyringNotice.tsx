import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { LockKeyIcon } from '@phosphor-icons/react'
import type { Schemas } from '@/api/client'
import { useMoveSecretsToKeyring, usePlaintextSecrets } from '@/api/queries'
import { Button } from '@/components/ui/button'
import { errorMessage } from '@/lib/errors'

const STORAGE_KEY = 'candidatai.keyringNotice.later'

/** Lo que se pospuso con «Ahora no»: las mismas contraseñas no vuelven a preguntarse; una nueva, sí. */
function postponed(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

function postpone(signature: string) {
  try {
    localStorage.setItem(STORAGE_KEY, signature)
  } catch {
    // Sin almacenamiento, el aviso vuelve al recargar: nada se pierde.
  }
}

function useItemLabel() {
  const { t } = useTranslation('mailboxes', { keyPrefix: 'keyringNotice.item' })
  return (secret: Schemas['PlaintextSecret']) => {
    if (secret.kind !== 'mailbox') return t(secret.kind)
    return secret.label ? t('mailbox', { name: secret.label }) : t('mailboxInstall')
  }
}

/**
 * Contraseñas guardadas en claro en un fichero (las de antes de guardarlas en el llavero): se ofrece
 * moverlas al llavero del sistema. Solo se mueven al pulsar «Mover al llavero»; con «Ahora no» se
 * quedan como están y cada buzón lo sigue marcando.
 *
 * Una banda en Inicio, no un aviso flotante: no corre prisa, y flotando tapaba la página y el
 * asistente de la esquina en todas las pantallas.
 */
export function KeyringNotice() {
  const { t } = useTranslation('mailboxes', { keyPrefix: 'keyringNotice' })
  const label = useItemLabel()
  const data = usePlaintextSecrets().data
  const move = useMoveSecretsToKeyring()
  const [later, setLater] = useState(postponed)

  const secrets = data?.secrets ?? []
  const signature = secrets.map((s) => s.name).sort().join(',')
  if (!data?.keyring || secrets.length === 0 || later === signature) return null
  const failed = move.error ? errorMessage(move.error) : move.data && move.data.failed.length > 0 ? t('failed') : null

  return (
    <section
      aria-label={t('title')}
      className="flex items-start gap-3 rounded-xl border bg-card px-4 py-3 text-sm animate-in fade-in duration-200"
    >
      <LockKeyIcon className="mt-0.5 size-5 shrink-0 text-primary" weight="duotone" aria-hidden />
      <div className="min-w-0 flex-1">
        <p className="font-medium">{t('title')}</p>
        <p className="mt-0.5 text-pretty text-muted-foreground">{t('body', { count: secrets.length })}</p>
        <p className="mt-1 text-xs text-muted-foreground">{secrets.map(label).join(' · ')}</p>
        {failed && (
          <p role="alert" className="mt-1.5 text-xs text-destructive">
            {failed}
          </p>
        )}
      </div>
      {/* Sin relleno: en Inicio, la única acción rellena es la del titular. */}
      <div className="flex shrink-0 flex-wrap items-center gap-2">
        <Button
          size="sm"
          variant="outline"
          disabled={move.isPending}
          onClick={() => move.mutate(secrets.map((s) => s.name))}
        >
          {move.isPending ? t('moving') : t('move')}
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => {
            postpone(signature)
            setLater(signature)
          }}
        >
          {t('later')}
        </Button>
      </div>
    </section>
  )
}
