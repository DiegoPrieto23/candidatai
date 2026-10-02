import type { ReactNode } from 'react'

export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="inline-grid h-5 min-w-5 place-items-center rounded border bg-background px-1 font-mono text-[0.7rem] text-muted-foreground">
      {children}
    </kbd>
  )
}
