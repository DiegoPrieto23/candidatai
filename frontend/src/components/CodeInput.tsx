import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Input } from '@/components/ui/input'
import { codeName, codeOptions, findCode, type CodeKind } from '@/lib/codes'
import { cn } from '@/lib/utils'

/**
 * Un idioma o un país escrito por su nombre, con autocompletado en el idioma de la UI (fase 41.4).
 * `onChange` recibe el código (`fr`, `GB`) en cuanto lo que hay escrito es uno conocido; si no, el
 * texto tal cual, para que la validación del formulario diga que no vale. Vacío: `''`.
 */
export function CodeInput({
  id,
  kind,
  value,
  onChange,
  className,
  invalid,
  describedBy,
}: {
  id: string
  kind: CodeKind
  value: string
  onChange: (value: string) => void
  className?: string
  invalid?: boolean
  describedBy?: string
}) {
  const { i18n } = useTranslation()
  const locale = i18n.language
  const options = useMemo(() => codeOptions(kind, locale), [kind, locale])
  // Lo escrito; `null` mientras no se toca: se ve el nombre del código guardado.
  const [text, setText] = useState<string | null>(null)
  // Si el formulario se vacía desde fuera, el campo también.
  const [lastValue, setLastValue] = useState(value)
  if (value !== lastValue) {
    setLastValue(value)
    if (value === '') setText(null)
  }
  const shown = text ?? (value ? codeName(kind, value, locale) : '')
  return (
    <>
      <Input
        id={id}
        value={shown}
        list={`${id}-options`}
        autoComplete="off"
        aria-invalid={invalid ? true : undefined}
        aria-describedby={describedBy}
        className={cn('h-10 bg-background', className)}
        onChange={(e) => {
          setText(e.target.value)
          onChange(e.target.value.trim() ? (findCode(kind, e.target.value, locale) ?? e.target.value) : '')
        }}
        onBlur={() => {
          // Reconocido: se enseña con su nombre («fr» → «francés»).
          if (text !== null && findCode(kind, text, locale)) setText(null)
        }}
      />
      <datalist id={`${id}-options`}>
        {options.map((o) => (
          <option key={o.code} value={o.name} />
        ))}
      </datalist>
    </>
  )
}
