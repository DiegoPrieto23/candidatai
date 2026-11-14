/**
 * Recorta una imagen en el navegador (canvas), sin subirla a ningún sitio para hacerlo. Lo usa el
 * encuadre de la foto del CV: lo que se sube después es ya el recorte.
 */

export interface PixelArea {
  x: number
  y: number
  width: number
  height: number
}

/** Lado máximo del recorte: de sobra para una foto de CV impresa (≈ 35 mm a 300 ppp son 413 px). */
export const MAX_SIDE = 1200

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = () => reject(new Error('image'))
    img.src = src
  })
}

/** El trozo `area` (en píxeles de la original) de `src`, como JPEG cuadrado sobre fondo blanco. */
export async function cropToBlob(src: string, area: PixelArea): Promise<Blob> {
  const img = await loadImage(src)
  const side = Math.max(1, Math.round(Math.min(area.width, area.height, MAX_SIDE)))
  const canvas = document.createElement('canvas')
  canvas.width = side
  canvas.height = side
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('canvas')
  // Un PNG con transparencia saldría negro en JPEG.
  ctx.fillStyle = '#ffffff'
  ctx.fillRect(0, 0, side, side)
  ctx.imageSmoothingQuality = 'high'
  ctx.drawImage(img, area.x, area.y, area.width, area.height, 0, 0, side, side)
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error('canvas'))), 'image/jpeg', 0.92)
  })
}
