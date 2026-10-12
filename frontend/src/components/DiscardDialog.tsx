import { useState, type FormEvent, type KeyboardEvent } from 'react'
import type { DiscardReason } from '@/api/client'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { DISCARD_REASONS } from '@/lib/labels'
import { cn } from '@/lib/utils'

export interface DiscardChoice {
  reason: DiscardReason
  note?: string
}

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  jobTitle: string
  onConfirm: (choice: DiscardChoice) => void
  pending?: boolean
  error?: string | null
  /** Motivo ya elegido al abrir (p. ej. `closed` desde el aviso de oferta cerrada). */
  initialReason?: DiscardReason
}

/**
 * Descartar con motivo obligatorio. Atajos: 1-7 eligen motivo (fuera del campo de nota),
 * Intro confirma (Mayús+Intro, salto de línea en la nota) y Esc cancela.
 */
export function DiscardDialog({ open, onOpenChange, ...props }: Props) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {/* Radix desmonta el contenido al cerrar: cada apertura empieza con el formulario vacío. */}
      <DialogContent>
        <DiscardForm onCancel={() => onOpenChange(false)} {...props} />
      </DialogContent>
    </Dialog>
  )
}

function DiscardForm({
  jobTitle,
  onConfirm,
  onCancel,
  pending = false,
  error,
  initialReason,
}: Omit<Props, 'open' | 'onOpenChange'> & { onCancel: () => void }) {
  const [reason, setReason] = useState<DiscardReason | null>(initialReason ?? null)
  const [note, setNote] = useState('')

  const needsNote = reason === 'other' && !note.trim()
  const canSubmit = reason !== null && !needsNote && !pending

  const submit = (e?: FormEvent) => {
    e?.preventDefault()
    if (!canSubmit || reason === null) return
    onConfirm({ reason, note: note.trim() || undefined })
  }

  const onKeyDown = (e: KeyboardEvent<HTMLFormElement>) => {
    const target = e.target as HTMLElement
    const inNote = target.tagName === 'TEXTAREA'
    // Intro sobre «Cancelar» o «Descartar» hace lo de su botón, no lo pisamos.
    const onButton = target.tagName === 'BUTTON' && target.getAttribute('role') !== 'radio'
    if (!inNote && /^[1-7]$/.test(e.key)) {
      e.preventDefault()
      setReason(DISCARD_REASONS[Number(e.key) - 1].value)
    } else if (e.key === 'Enter' && !e.shiftKey && !onButton) {
      e.preventDefault()
      submit()
    }
  }

  return (
    <form onSubmit={submit} onKeyDown={onKeyDown} className="grid gap-5">
      <DialogHeader>
        <DialogTitle>Descartar oferta</DialogTitle>
        <DialogDescription className="truncate">{jobTitle}</DialogDescription>
      </DialogHeader>

      <fieldset>
        <legend className="mb-2 text-sm font-medium">Motivo</legend>
        <div role="radiogroup" aria-label="Motivo" className="grid gap-1.5 sm:grid-cols-2">
          {DISCARD_REASONS.map((option, i) => {
            const selected = reason === option.value
            return (
              <button
                key={option.value}
                type="button"
                role="radio"
                aria-checked={selected}
                onClick={() => setReason(option.value)}
                className={cn(
                  'flex items-center gap-2.5 rounded-md border px-3 py-2 text-left text-sm transition-colors outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50',
                  selected
                    ? 'border-primary/40 bg-accent text-accent-foreground'
                    : 'border-input hover:bg-foreground/[0.03]',
                )}
              >
                <kbd className="grid size-5 place-items-center rounded border bg-background font-mono text-[0.7rem] text-muted-foreground">
                  {i + 1}
                </kbd>
                {option.label}
              </button>
            )
          })}
        </div>
      </fieldset>

      <div className="space-y-2">
        <Label htmlFor="discard-note">
          Nota {reason === 'other' ? '(obligatoria con «Otro motivo»)' : '(opcional)'}
        </Label>
        <Textarea
          id="discard-note"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          maxLength={2000}
          rows={2}
          placeholder="Lo que quieras recordar de esta decisión"
          className="resize-y bg-background"
        />
      </div>

      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}

      <DialogFooter>
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancelar
        </Button>
        <Button type="submit" disabled={!canSubmit}>
          {pending ? 'Descartando…' : 'Descartar'}
        </Button>
      </DialogFooter>
    </form>
  )
}
