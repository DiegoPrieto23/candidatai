import { useRef, useState } from 'react'
import { CropIcon, TrashIcon, UploadSimpleIcon, UserCircleIcon } from '@phosphor-icons/react'
import { useTranslation } from 'react-i18next'
import { fileUrls } from '@/api/client'
import {
  useDefaultTemplate,
  useDeleteProfilePhoto,
  useProfilePhoto,
  useSaveProfilePhoto,
  useTemplates,
} from '@/api/queries'
import { BusyLabel } from '@/components/StableLabel'
import { Button } from '@/components/ui/button'
import { errorMessage } from '@/lib/errors'
import { cn } from '@/lib/utils'
import { Block } from './fields'
import { useProfileState } from './editor'
import { PhotoCropDialog, type CropSource, type PhotoShape } from './PhotoCropDialog'

const ACCEPT = '.jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp'

/** La forma de la foto en la plantilla por defecto: así se ve el encuadre. Redonda si no se sabe. */
function useDefaultPhotoShape(): PhotoShape {
  const templates = useTemplates()
  const chosen = useDefaultTemplate()
  const id = chosen.data?.template_id
  const shape = templates.data?.templates.find((tpl) => tpl.id === id)?.photo_shape
  return shape === 'square' || shape === 'rounded' ? shape : 'circle'
}

/**
 * La foto del CV, opcional. Al elegirla se encuadra (zoom y arrastre) y se guarda el recorte: no
 * pasa por «Guardar» porque no va en el YAML. Con la original guardada, se vuelve a encuadrar.
 */
export function PhotoBlock() {
  const { t } = useTranslation('profileEditor', { keyPrefix: 'blocks.photo' })
  const { profile } = useProfileState()
  const photo = useProfilePhoto()
  const save = useSaveProfilePhoto()
  const remove = useDeleteProfilePhoto()
  const input = useRef<HTMLInputElement>(null)
  const [confirming, setConfirming] = useState(false)
  const [cropping, setCropping] = useState<CropSource | null>(null)
  const [loadingOriginal, setLoadingOriginal] = useState(false)
  const [originalError, setOriginalError] = useState(false)
  const shape = useDefaultPhotoShape()
  const info = photo.data
  const policyOff = profile?.preferences?.cv?.photo_policy?.default === false
  const error = remove.error

  const reframe = async () => {
    if (!info?.exists) return
    setOriginalError(false)
    setLoadingOriginal(true)
    try {
      const response = await fetch(fileUrls.profilePhotoOriginal(info.version ?? ''))
      if (!response.ok) throw new Error(String(response.status))
      setCropping({ blob: await response.blob(), initial: info.has_original ? info.crop : null })
    } catch {
      setOriginalError(true)
    } finally {
      setLoadingOriginal(false)
    }
  }
  return (
    <Block id="photo" title={t('title')} hint={t('hint')}>
      <div className="flex flex-wrap items-center gap-4">
        {info?.exists ? (
          <img
            src={fileUrls.profilePhoto(info.version ?? '')}
            alt={t('preview')}
            className={cn('size-20 border object-cover', shape === 'circle' ? 'rounded-full' : 'rounded-lg')}
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
                save.reset()
                setCropping({ blob: file })
              }
            }}
          />
          <div className="flex flex-wrap gap-2">
            <Button type="button" size="sm" variant="outline" disabled={save.isPending} onClick={() => input.current?.click()}>
              <UploadSimpleIcon />
              {info?.exists ? t('replace') : t('upload')}
            </Button>
            {info?.exists && (
              <Button type="button" size="sm" variant="outline" disabled={loadingOriginal} onClick={() => void reframe()}>
                <CropIcon />
                <BusyLabel busy={loadingOriginal} busyText={t('opening')} text={t('reframe')} />
              </Button>
            )}
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
      {(error || originalError) && (
        <p role="alert" className="text-sm text-destructive">
          {originalError ? t('originalFailed') : errorMessage(error)}
        </p>
      )}
      <PhotoCropDialog
        source={cropping}
        shape={shape}
        saving={save.isPending}
        error={save.error ? errorMessage(save.error) : null}
        onCancel={() => {
          save.reset()
          setCropping(null)
        }}
        onSave={(upload) => save.mutate(upload, { onSuccess: () => setCropping(null) })}
      />
      {info?.exists && policyOff && <p className="text-xs text-muted-foreground">{t('policyOff')}</p>}
    </Block>
  )
}
