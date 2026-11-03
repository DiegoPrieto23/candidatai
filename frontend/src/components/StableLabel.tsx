/**
 * El texto de un botón que cambia («Guardar» → «Guardando…») sin que el botón cambie de ancho: el
 * hueco del texto más largo se reserva por CSS (`.stable-label`), así que ni el botón ni lo que tiene
 * al lado se mueven. La reserva no está en el DOM: ni se lee ni cuenta para el nombre accesible.
 */
export function StableLabel({ text, reserve }: { text: string; reserve: string | string[] }) {
  const longest = [reserve].flat().reduce((a, b) => (b.length > a.length ? b : a), '')
  return (
    <span className="stable-label" data-reserve={longest}>
      {text}
    </span>
  )
}

/** Atajo para lo más común: un texto y el que lo sustituye mientras trabaja. */
export function BusyLabel({ busy, busyText, text }: { busy: boolean; busyText: string; text: string }) {
  return <StableLabel text={busy ? busyText : text} reserve={busy ? text : busyText} />
}
