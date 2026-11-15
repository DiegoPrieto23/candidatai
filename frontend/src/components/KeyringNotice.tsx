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
 * Contraseñas guardadas en claro en un fichero (las de antes de la fase 41.5): se ofrece moverlas al
 * llavero del sistema. Solo se mueven al pulsar «Mover al llavero»; con «Ahora no» se quedan como
 * están y cada buzón lo sigue marcando.
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
    <div
      role="status"
      className="pointer-events-auto flex w-80 max-w-[calc(100vw-2rem)] items-start gap-3 rounded-lg border bg-card p-3 text-sm shadow-lg animate-in fade-in slide-in-from-bottom-1 duration-200"
    >
      <LockKeyIcon className="mt-0.5 size-4 shrink-0 text-primary" weight="duotone" aria-hidden />
      <div className="min-w-0 flex-1">
        <p className="font-medium">{t('title')}</p>
        <p className="mt-0.5 text-muted-foreground">{t('body', { count: secrets.length })}</p>
        <ul className="mt-1.5 list-disc pl-4 text-xs text-muted-foreground">
          {secrets.map((secret) => (
            <li key={secret.name}>{label(secret)}</li>
          ))}
        </ul>
        {failed && (
          <p role="alert" className="mt-1.5 text-xs text-destructive">
            {failed}
          </p>
        )}
        <div className="mt-2.5 flex flex-wrap gap-2">
          <Button size="sm" disabled={move.isPending} onClick={() => move.mutate(secrets.map((s) => s.name))}>
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
      </div>
    </div>
  )
}
