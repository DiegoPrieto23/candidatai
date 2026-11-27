import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { AgentTaskView } from '@/api/client'
import { cn } from '@/lib/utils'

/** El tiempo que lleva (mm:ss), al segundo mientras sigue. */
export function Elapsed({ from, until }: { from: string; until?: string | null }) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (until) return
    const timer = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(timer)
  }, [until])
  const end = until ? Date.parse(until) : now
  const seconds = Math.max(0, Math.floor((end - Date.parse(from)) / 1000))
  const two = (value: number) => String(value).padStart(2, '0')
  const hours = Math.floor(seconds / 3600)
  const clock = `${two(Math.floor((seconds % 3600) / 60))}:${two(seconds % 60)}`
  const text = hours > 0 ? `${hours}:${clock}` : clock
  return <span className="tabular">{text}</span>
}

/** La barra de pasos: hechos en color, el actual a medias. `labelled`: con el nombre debajo. */
export function StepBar({ steps, labelled = false }: { steps: AgentTaskView['steps']; labelled?: boolean }) {
  const { t } = useTranslation('nav', { keyPrefix: 'tasks' })
  return (
    <ol
      className="grid gap-1"
      style={{ gridTemplateColumns: `repeat(${steps.length}, minmax(0, 1fr))` }}
      aria-label={labelled ? t('steps.label') : undefined}
      aria-hidden={labelled ? undefined : true}
    >
      {steps.map((step) => (
        <li key={step.id} className="flex min-w-0 flex-col gap-1">
          <span
            className={cn(
              'h-1 rounded-sm bg-foreground/10 transition-colors duration-300',
              step.state === 'done' && 'bg-primary',
              step.state === 'current' && 'bg-primary/45',
            )}
          />
          {labelled && (
            <span
              className={cn(
                'truncate text-[11px]',
                step.state === 'pending' ? 'text-muted-foreground' : 'font-medium text-foreground',
              )}
            >
              {t(`steps.${step.id}` as never)}
              <span className="sr-only">{` · ${t(`steps.state.${step.state}` as never)}`}</span>
            </span>
          )}
        </li>
      ))}
    </ol>
  )
}
