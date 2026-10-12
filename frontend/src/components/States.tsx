import type { ReactNode } from 'react'
import { PlugsIcon, WarningCircleIcon } from '@phosphor-icons/react'
import { ApiError } from '@/api/client'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export function ErrorState({
  error,
  onRetry,
  className,
}: {
  error: unknown
  onRetry?: () => void
  className?: string
}) {
  const offline = error instanceof ApiError && error.type === 'offline'
  const message = error instanceof Error ? error.message : 'Algo ha fallado.'
  const Icon = offline ? PlugsIcon : WarningCircleIcon
  return (
    <div
      role="alert"
      className={cn(
        'flex flex-col items-start gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-5 sm:flex-row sm:items-center',
        className,
      )}
    >
      <Icon className="size-6 shrink-0 text-destructive" weight="duotone" />
      <div className="min-w-0 flex-1">
        <p className="font-medium">{offline ? 'La API no responde' : 'No se ha podido cargar'}</p>
        <p className="mt-0.5 text-sm text-muted-foreground">
          <InlineCode text={message} />
        </p>
      </div>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          Reintentar
        </Button>
      )}
    </div>
  )
}

export function EmptyState({
  icon,
  title,
  children,
  action,
}: {
  icon: ReactNode
  title: string
  children?: ReactNode
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center px-6 py-16 text-center">
      <div className="mb-5 grid size-14 place-items-center rounded-xl border bg-card text-primary shadow-sm">
        {icon}
      </div>
      <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
      {children && (
        <div className="mt-1.5 max-w-[46ch] text-sm leading-relaxed text-muted-foreground">
          {children}
        </div>
      )}
      {action && <div className="mt-6">{action}</div>}
    </div>
  )
}

/** Pinta como código lo que va entre acentos graves: «ejecuta `cai serve`». */
export function InlineCode({ text }: { text: string }) {
  const parts = text.split(/`([^`]+)`/g)
  return (
    <>
      {parts.map((part, i) =>
        i % 2 === 1 ? (
          <code key={i} className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em] text-foreground">
            {part}
          </code>
        ) : (
          part
        ),
      )}
    </>
  )
}
