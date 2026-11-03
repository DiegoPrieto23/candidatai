/** Lo quitado y lo añadido entre dos versiones de un texto (CV o guía), línea a línea. */
export function ChangeLines({
  removed,
  added,
  removedLabel,
  addedLabel,
}: {
  removed: string[]
  added: string[]
  removedLabel: string
  addedLabel: string
}) {
  return (
    <>
      {removed.map((text, i) => (
        <p key={`r${i}`} className="break-words rounded-sm bg-destructive/10 px-2 py-1">
          <span className="font-mono text-muted-foreground" aria-label={removedLabel}>− </span>
          <span className="line-through decoration-foreground/40">{text}</span>
        </p>
      ))}
      {added.map((text, i) => (
        <p key={`a${i}`} className="break-words rounded-sm bg-primary/10 px-2 py-1">
          <span className="font-mono text-muted-foreground" aria-label={addedLabel}>+ </span>
          {text}
        </p>
      ))}
    </>
  )
}
