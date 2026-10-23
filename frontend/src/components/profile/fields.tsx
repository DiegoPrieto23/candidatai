/** Campos de «Mi perfil» (fase 25.7b): etiqueta, pista y el error de validación de su ruta. */
import { useId, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { ArrowDownIcon, ArrowUpIcon, CheckIcon, TrashIcon, WarningIcon, XIcon } from '@phosphor-icons/react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'
import type { BlockEditor } from './editor'
import { PRESENT } from './types'

const SELECT = 'h-9 w-full rounded-md border border-input bg-background px-3 text-sm'

function FieldError({ id, error }: { id: string; error?: string }) {
  if (!error) return null
  return (
    <p id={id} className="flex items-start gap-1 text-xs text-destructive">
      <WarningIcon className="mt-0.5 size-3.5 shrink-0" aria-hidden />
      {error}
    </p>
  )
}

interface FieldProps {
  label: string
  hint?: ReactNode
  error?: string
  className?: string
}

function Field({ label, hint, error, className, children }: FieldProps & { children: (id: string, describedBy?: string) => ReactNode }) {
  const id = useId()
  const errorId = `${id}-error`
  return (
    <div className={cn('grid content-start gap-1.5', className)}>
      <Label htmlFor={id}>{label}</Label>
      {children(id, error ? errorId : undefined)}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
      <FieldError id={errorId} error={error} />
    </div>
  )
}

export function TextField({
  value,
  onChange,
  multiline,
  rows = 3,
  placeholder,
  type = 'text',
  autoFocus,
  ...props
}: FieldProps & {
  value: string | null | undefined
  onChange: (value: string) => void
  multiline?: boolean
  rows?: number
  placeholder?: string
  type?: 'text' | 'number' | 'url' | 'email'
  autoFocus?: boolean
}) {
  return (
    <Field {...props}>
      {(id, describedBy) =>
        multiline ? (
          <Textarea
            id={id}
            rows={rows}
            value={value ?? ''}
            placeholder={placeholder}
            autoFocus={autoFocus}
            aria-invalid={describedBy ? true : undefined}
            aria-describedby={describedBy}
            onChange={(e) => onChange(e.target.value)}
          />
        ) : (
          <Input
            id={id}
            type={type}
            value={value ?? ''}
            placeholder={placeholder}
            autoFocus={autoFocus}
            aria-invalid={describedBy ? true : undefined}
            aria-describedby={describedBy}
            onChange={(e) => onChange(e.target.value)}
          />
        )
      }
    </Field>
  )
}

export function SelectField({
  value,
  onChange,
  options,
  ...props
}: FieldProps & { value: string; onChange: (value: string) => void; options: { value: string; label: string }[] }) {
  return (
    <Field {...props}>
      {(id, describedBy) => (
        <select id={id} value={value} aria-describedby={describedBy} onChange={(e) => onChange(e.target.value)} className={SELECT}>
          {options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      )}
    </Field>
  )
}

/** Mes y año (`AAAA-MM`), con «Actualidad» (`present`) si se permite. */
export function MonthField({
  value,
  onChange,
  allowPresent,
  ...props
}: FieldProps & { value: string | null | undefined; onChange: (value: string) => void; allowPresent?: boolean }) {
  const { t } = useTranslation('profileEditor')
  const present = value === PRESENT
  return (
    <Field {...props}>
      {(id, describedBy) => (
        <div className="flex flex-wrap items-center gap-3">
          <Input
            id={id}
            type="month"
            className="w-44"
            value={present ? '' : (value ?? '')}
            disabled={present}
            aria-describedby={describedBy}
            onChange={(e) => onChange(e.target.value)}
          />
          {allowPresent && (
            <label className="flex items-center gap-1.5 text-sm">
              <input type="checkbox" checked={present} onChange={(e) => onChange(e.target.checked ? PRESENT : '')} />
              {t('fields.present')}
            </label>
          )}
        </div>
      )}
    </Field>
  )
}

export function CheckField({ label, checked, onChange }: { label: string; checked: boolean; onChange: (value: boolean) => void }) {
  return (
    <label className="flex items-center gap-2 text-sm">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      {label}
    </label>
  )
}

/** Varias casillas para una lista cerrada (modalidad, seniority…). */
export function ChoicesField<V extends string>({
  label,
  value,
  options,
  onChange,
  error,
}: {
  label: string
  value: V[]
  options: { value: V; label: string }[]
  onChange: (value: V[]) => void
  error?: string
}) {
  const id = useId()
  return (
    <fieldset className="grid gap-1.5" aria-describedby={error ? `${id}-error` : undefined}>
      <legend className="mb-1 text-sm font-medium">{label}</legend>
      <div className="flex flex-wrap gap-x-4 gap-y-1.5">
        {options.map((o) => (
          <label key={o.value} className="flex items-center gap-1.5 text-sm">
            <input
              type="checkbox"
              checked={value.includes(o.value)}
              onChange={(e) => onChange(e.target.checked ? [...value, o.value] : value.filter((v) => v !== o.value))}
            />
            {o.label}
          </label>
        ))}
      </div>
      <FieldError id={`${id}-error`} error={error} />
    </fieldset>
  )
}

/** Una lista de textos cortos como etiquetas: se añaden con Intro y se quitan con su «×». */
export function TagsField({
  value,
  onChange,
  suggestions,
  ...props
}: FieldProps & { value: string[] | undefined; onChange: (value: string[]) => void; suggestions?: string[] }) {
  const { t } = useTranslation('profileEditor')
  const [text, setText] = useState('')
  const listId = useId()
  const items = value ?? []
  const add = () => {
    const item = text.trim()
    if (item && !items.some((i) => i.toLowerCase() === item.toLowerCase())) onChange([...items, item])
    setText('')
  }
  return (
    <Field {...props}>
      {(id, describedBy) => (
        <div className="grid gap-2">
          {items.length > 0 && (
            <ul className="flex flex-wrap gap-1.5" aria-label={props.label}>
              {items.map((item) => (
                <li key={item} className="flex items-center gap-1 rounded-md bg-muted px-2 py-0.5 text-sm">
                  {item}
                  <button
                    type="button"
                    className="rounded text-muted-foreground hover:text-foreground"
                    aria-label={t('fields.removeTag', { item })}
                    onClick={() => onChange(items.filter((i) => i !== item))}
                  >
                    <XIcon className="size-3.5" />
                  </button>
                </li>
              ))}
            </ul>
          )}
          <div className="flex gap-2">
            <Input
              id={id}
              value={text}
              list={suggestions ? listId : undefined}
              aria-describedby={describedBy}
              placeholder={t('fields.addTag')}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault()
                  add()
                }
              }}
            />
            <Button type="button" variant="outline" size="sm" onClick={add} disabled={!text.trim()}>
              {t('fields.add')}
            </Button>
          </div>
          {suggestions && (
            <datalist id={listId}>
              {suggestions.map((s) => (
                <option key={s} value={s} />
              ))}
            </datalist>
          )}
        </div>
      )}
    </Field>
  )
}

/** Subir, bajar y borrar un elemento de una lista. */
export function ItemControls({
  label,
  index,
  count,
  onMove,
  onRemove,
}: {
  label: string
  index: number
  count: number
  onMove: (delta: number) => void
  onRemove: () => void
}) {
  const { t } = useTranslation('profileEditor')
  return (
    <div className="flex items-center gap-1">
      <Button type="button" variant="ghost" size="sm" aria-label={t('fields.moveUp', { item: label })} disabled={index === 0} onClick={() => onMove(-1)}>
        <ArrowUpIcon />
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        aria-label={t('fields.moveDown', { item: label })}
        disabled={index === count - 1}
        onClick={() => onMove(1)}
      >
        <ArrowDownIcon />
      </Button>
      <Button type="button" variant="ghost" size="sm" aria-label={t('fields.remove', { item: label })} onClick={onRemove}>
        <TrashIcon />
      </Button>
    </div>
  )
}

/** Guardar y descartar de un bloque, con su estado (guardado, error, conflicto, diff). */
export function BlockActions<T>({ block, blocked = false }: { block: BlockEditor<T>; blocked?: boolean }) {
  const { t } = useTranslation('profileEditor')
  return (
    <div className="grid gap-2 border-t pt-3">
      {block.preview !== null && (
        <div className="grid gap-2 rounded-lg border border-amber-300 bg-amber-50 p-3 dark:border-amber-800 dark:bg-amber-950/40">
          <p className="text-sm font-medium">{t('preview.title')}</p>
          <p className="text-xs text-muted-foreground">{t('preview.rescore')}</p>
          <pre aria-label={t('preview.diff')} className="max-h-72 overflow-auto rounded bg-background p-2 font-mono text-xs leading-relaxed">
            {block.preview}
          </pre>
          <div className="flex gap-2">
            <Button type="button" size="sm" onClick={block.confirmPreview} disabled={block.saving}>
              {t('preview.confirm')}
            </Button>
            <Button type="button" size="sm" variant="outline" onClick={block.cancelPreview}>
              {t('preview.cancel')}
            </Button>
          </div>
        </div>
      )}
      {block.message && (
        <p role="alert" className="text-sm text-destructive">
          {block.conflict ? t('errors.conflict') : block.message}
        </p>
      )}
      {block.warnings.map((warning) => (
        <p key={warning} className="text-xs text-amber-700 dark:text-amber-400">
          {warning}
        </p>
      ))}
      <div className="flex flex-wrap items-center gap-2">
        <Button type="button" size="sm" onClick={block.save} disabled={blocked || !block.dirty || block.saving || block.preview !== null}>
          {block.saving ? t('actions.saving') : t('actions.save')}
        </Button>
        {(block.dirty || block.conflict) && (
          <Button type="button" size="sm" variant="ghost" onClick={block.discard}>
            {block.conflict ? t('actions.reload') : t('actions.discard')}
          </Button>
        )}
        <span role="status" className="text-xs text-muted-foreground">
          {block.saved && !block.dirty ? (
            <span className="flex items-center gap-1 text-emerald-700 dark:text-emerald-400">
              <CheckIcon aria-hidden /> {t('actions.saved')}
            </span>
          ) : block.dirty ? (
            t('unsaved.badge')
          ) : null}
        </span>
      </div>
    </div>
  )
}

export function Block({ title, hint, actions, children }: { title: string; hint?: ReactNode; actions?: ReactNode; children: ReactNode }) {
  return (
    <section aria-label={title} className="grid gap-4 rounded-xl border bg-card p-4 sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="font-medium">{title}</h2>
          {hint && <p className="mt-0.5 text-sm text-muted-foreground">{hint}</p>}
        </div>
        {actions}
      </div>
      {children}
    </section>
  )
}

export { SELECT }
