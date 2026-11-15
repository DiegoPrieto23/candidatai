/** Una caja donde soltar un fichero (o hacer clic para elegirlo). Se encarga del arrastre, del
 * selector oculto y de rechazar las extensiones que no están en `accept`; lo que se pinta dentro lo
 * decide quien la usa. */
import { useRef, useState, type DragEvent, type ReactNode } from 'react'
import { cn } from '@/lib/utils'

export function FileDropZone({
  accept,
  label,
  disabled = false,
  onFile,
  onWrongType,
  className,
  children,
}: {
  /** Extensiones admitidas, como en `<input accept>`: `.pdf,.docx`. */
  accept: string
  /** Nombre accesible del selector de ficheros. */
  label: string
  disabled?: boolean
  onFile: (file: File) => void
  onWrongType: (file: File) => void
  className?: string
  /** Lo de dentro; un botón dentro no necesita `onClick`: su clic llega a la caja y la abre. */
  children: (dragging: boolean) => ReactNode
}) {
  const input = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const extensions = accept.split(',').map((ext) => ext.trim().toLowerCase())
  const open = () => {
    if (!disabled) input.current?.click()
  }
  const choose = (file: File | undefined) => {
    if (!file || disabled) return
    if (extensions.some((ext) => file.name.toLowerCase().endsWith(ext))) onFile(file)
    else onWrongType(file)
  }
  const onDragOver = (event: DragEvent) => {
    if (disabled || !event.dataTransfer.types.includes('Files')) return
    event.preventDefault()
    event.dataTransfer.dropEffect = 'copy'
    setDragging(true)
  }
  return (
    <div
      data-dragging={dragging || undefined}
      className={cn(
        'cursor-pointer rounded-xl border border-dashed transition-colors hover:border-foreground/30',
        dragging && 'border-primary bg-accent/60 ring-2 ring-primary/30',
        disabled && 'cursor-default opacity-70',
        className,
      )}
      // El clic en cualquier punto de la caja abre el selector; con teclado, el botón de dentro
      // (su clic sube hasta aquí).
      onClick={open}
      onDragOver={onDragOver}
      onDragLeave={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setDragging(false)
      }}
      onDrop={(event) => {
        event.preventDefault()
        setDragging(false)
        choose(event.dataTransfer.files?.[0])
      }}
    >
      <input
        ref={input}
        type="file"
        accept={accept}
        className="sr-only"
        aria-label={label}
        tabIndex={-1}
        onClick={(event) => event.stopPropagation()}
        onChange={(event) => {
          choose(event.target.files?.[0])
          event.target.value = '' // permite volver a elegir el mismo fichero
        }}
      />
      {children(dragging)}
    </div>
  )
}
