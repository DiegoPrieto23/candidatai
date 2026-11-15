import { useEffect, useId, useMemo, useState } from 'react'
import Cropper, { type Area } from 'react-easy-crop'
import { MagnifyingGlassMinusIcon, MagnifyingGlassPlusIcon } from '@phosphor-icons/react'
import { useTranslation } from 'react-i18next'
import type { PhotoCrop, PhotoUpload } from '@/api/queries'
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
import { cropToBlob } from '@/lib/cropImage'

export type PhotoShape = 'circle' | 'square' | 'rounded'

/** Lo que se encuadra: una foto recién elegida o la original guardada, con su último recuadro. */
export interface CropSource {
  blob: Blob
  initial?: PhotoCrop | null
}

const MIN_ZOOM = 1
const MAX_ZOOM = 3

/**
 * Encuadre de la foto del CV: arrastrar y zoom sobre un recuadro cuadrado (la proporción del CV),
 * redondo o cuadrado según la plantilla por defecto. Todo en el navegador: lo que sale de aquí es
 * el recorte, más la original y el recuadro para volver a encuadrar después.
 */
export function PhotoCropDialog({
  source,
  shape,
  saving,
  error,
  onCancel,
  onSave,
}: {
  source: CropSource | null
  shape: PhotoShape
  saving: boolean
  error?: string | null
  onCancel: () => void
  onSave: (upload: PhotoUpload) => void
}) {
  const { t } = useTranslation('profileEditor', { keyPrefix: 'blocks.photo.crop' })
  const zoomId = useId()
  const url = useMemo(() => (source ? URL.createObjectURL(source.blob) : null), [source])
  const [crop, setCrop] = useState({ x: 0, y: 0 })
  const [zoom, setZoom] = useState(MIN_ZOOM)
  const [area, setArea] = useState<{ percent: Area; pixels: Area } | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => () => {
    if (url) URL.revokeObjectURL(url)
  }, [url])
  // Otra foto: el encuadre empieza de cero.
  const [shown, setShown] = useState(source)
  if (shown !== source) {
    setShown(source)
    setCrop({ x: 0, y: 0 })
    setZoom(MIN_ZOOM)
    setArea(null)
    setFailed(false)
  }

  const save = async () => {
    if (!source || !url || !area) return
    try {
      const photo = await cropToBlob(url, area.pixels)
      onSave({ photo, original: source.blob, crop: area.percent })
    } catch {
      setFailed(true)
    }
  }

  return (
    <Dialog open={source !== null} onOpenChange={(open) => !open && !saving && onCancel()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{t('title')}</DialogTitle>
          <DialogDescription>{t('description')}</DialogDescription>
        </DialogHeader>
        <div className="relative h-72 overflow-hidden rounded-lg bg-muted" data-testid="photo-cropper">
          {url && (
            <Cropper
              image={url}
              crop={crop}
              zoom={zoom}
              minZoom={MIN_ZOOM}
              maxZoom={MAX_ZOOM}
              aspect={1}
              cropShape={shape === 'circle' ? 'round' : 'rect'}
              showGrid={false}
              initialCroppedAreaPercentages={source?.initial ?? undefined}
              onCropChange={setCrop}
              onZoomChange={setZoom}
              onCropComplete={(percent, pixels) => setArea({ percent, pixels })}
              cropperProps={{ 'aria-label': t('area') }}
            />
          )}
        </div>
        <div className="flex items-center gap-3">
          <label htmlFor={zoomId} className="text-sm font-medium">
            {t('zoom')}
          </label>
          <MagnifyingGlassMinusIcon className="size-4 text-muted-foreground" aria-hidden />
          <input
            id={zoomId}
            type="range"
            min={MIN_ZOOM}
            max={MAX_ZOOM}
            step={0.01}
            value={zoom}
            onChange={(e) => setZoom(Number(e.target.value))}
            className="min-w-0 flex-1 accent-primary"
          />
          <MagnifyingGlassPlusIcon className="size-4 text-muted-foreground" aria-hidden />
        </div>
        {(failed || error) && (
          <p role="alert" className="text-sm text-destructive">
            {failed ? t('failed') : error}
          </p>
        )}
        <DialogFooter>
          <Button type="button" variant="outline" disabled={saving} onClick={onCancel}>
            {t('cancel')}
          </Button>
          <Button type="button" disabled={saving || !area} onClick={() => void save()}>
            <BusyLabel busy={saving} busyText={t('saving')} text={t('save')} />
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
