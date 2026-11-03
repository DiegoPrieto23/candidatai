import { useRef, useState } from 'react'
import { TrashIcon, UploadSimpleIcon, UserCircleIcon } from '@phosphor-icons/react'
import { useTranslation } from 'react-i18next'
import { fileUrls } from '@/api/client'
import { useDeleteProfilePhoto, useProfilePhoto, useSaveProfilePhoto } from '@/api/queries'
import { BusyLabel } from '@/components/StableLabel'
import { Button } from '@/components/ui/button'
import { errorMessage } from '@/lib/errors'
import { Block } from './fields'
import { useProfileState } from './editor'

const ACCEPT = '.jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp'

/** La foto del CV, opcional. Se guarda al elegirla: no pasa por «Guardar» porque no va en el YAML. */
export function PhotoBlock() {
  const { t } = useTranslation('profileEditor', { keyPrefix: 'blocks.photo' })
  const { profile } = useProfileState()
  const photo = useProfilePhoto()
  const save = useSaveProfilePhoto()
  const remove = useDeleteProfilePhoto()
  const input = useRef<HTMLInputElement>(null)
  const [confirming, setConfirming] = useState(false)
  const info = photo.data
  const policyOff = profile?.preferences?.cv?.photo_policy?.default === false
  const error = save.error ?? remove.error
  return (
    <Block id="photo" title={t('title')} hint={t('hint')}>
      <div className="flex flex-wrap items-center gap-4">
        {info?.exists ? (
          <img
            src={fileUrls.profilePhoto(info.version ?? '')}
            alt={t('preview')}
            className="size-20 rounded-lg border object-cover"
          />
        ) : (
          <span className="grid size-20 place-items-center rounded-lg border border-dashed text-muted-foreground">
            <UserCircleIcon className="size-8" weight="duotone" aria-hidden />
          </span>
        )}
        <div className="grid gap-2">
          <input
            ref={input}
            type="file"
            accept={ACCEPT}
            className="sr-only"
            aria-label={t('choose')}
            tabIndex={-1}
            onChange={(e) => {
              const file = e.target.files?.[0]
              e.target.value = ''
              if (file) {
                setConfirming(false)
                remove.reset()
                save.mutate(file)
              }
            }}
          />
          <div className="flex flex-wrap gap-2">
            <Button type="button" size="sm" variant="outline" disabled={save.isPending} onClick={() => input.current?.click()}>
              <UploadSimpleIcon />
              <BusyLabel busy={save.isPending} busyText={t('uploading')} text={info?.exists ? t('replace') : t('upload')} />
            </Button>
            {info?.exists && !confirming && (
              <Button type="button" size="sm" variant="ghost" onClick={() => setConfirming(true)}>
                <TrashIcon />
                {t('remove')}
              </Button>
            )}
            {info?.exists && confirming && (
              <>
                <Button
                  type="button"
                  size="sm"
                  variant="destructive"
                  disabled={remove.isPending}
                  onClick={() => {
                    save.reset()
                    remove.mutate(undefined, { onSettled: () => setConfirming(false) })
                  }}
                >
                  {t('confirmRemove')}
                </Button>
                <Button type="button" size="sm" variant="ghost" onClick={() => setConfirming(false)}>
                  {t('cancel')}
                </Button>
              </>
            )}
          </div>
          <p className="text-xs text-muted-foreground">{t('formats')}</p>
        </div>
      </div>
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {errorMessage(error)}
        </p>
      )}
      {info?.exists && policyOff && <p className="text-xs text-muted-foreground">{t('policyOff')}</p>}
    </Block>
  )
}
