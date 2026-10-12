import { useEffect, useRef, useState } from 'react'
import { ArrowSquareOutIcon, BellRingingIcon, ShieldWarningIcon } from '@phosphor-icons/react'
import type { PromptView } from '@/api/client'
import { useAnswerPrompt, usePendingPrompts } from '@/api/queries'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

function clock(seconds: number): string {
  const s = Math.max(0, seconds)
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

/** Segundos que quedan: desde lo que dijo el servidor en la última consulta, contados aquí. */
function useCountdown(prompt: PromptView | undefined): number {
  const [now, setNow] = useState(() => Date.now())
  const [anchor, setAnchor] = useState<{ key: string; end: number } | null>(null)
  const key = prompt ? `${prompt.id}:${prompt.seconds_left}` : ''
  if (prompt && anchor?.key !== key) {
    // Nueva lectura del servidor: se ancla aquí (patrón de «estado derivado» de React).
    setAnchor({ key, end: Date.now() + prompt.seconds_left * 1000 })
  }
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [])
  if (!prompt) return 0
  const end = anchor?.key === key ? anchor.end : now + prompt.seconds_left * 1000
  return Math.max(0, Math.round((end - now) / 1000))
}

function notificationsSupported(): boolean {
  return typeof window !== 'undefined' && 'Notification' in window
}

/** Notificación del sistema (en Windows, la del centro de actividades) para un aviso nuevo. */
function notify(prompt: PromptView) {
  if (!notificationsSupported() || Notification.permission !== 'granted') return
  try {
    const where = prompt.source_name ? ` · ${prompt.source_name}` : ''
    const n = new Notification(`CandidatAI: ${prompt.title}${where}`, {
      body: prompt.message,
      tag: `cai-prompt-${prompt.id}`,
      requireInteraction: true,
    })
    n.onclick = () => {
      window.focus()
      n.close()
    }
  } catch {
    // Algunos navegadores no dejan crear notificaciones fuera de un service worker: queda el pop-up.
  }
}

function EnableNotifications() {
  const [permission, setPermission] = useState(() =>
    notificationsSupported() ? Notification.permission : 'denied',
  )
  if (permission !== 'default') return null
  return (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      onClick={() => void Notification.requestPermission().then(setPermission)}
    >
      <BellRingingIcon />
      Avisarme también con notificaciones de Windows
    </Button>
  )
}

/**
 * Pop-up de los avisos que te pide el agente o el worker: «Completa el captcha en InfoJobs»,
 * «Inicia sesión…». Lo resuelves tú en el navegador y contestas «Ya está» o «Saltar». Si no
 * contestas a tiempo, el agente sigue sin ello. Nunca se resuelve un captcha por ti.
 */
export function UserPrompts() {
  const { data } = usePendingPrompts()
  const answer = useAnswerPrompt()
  const prompt = data?.prompts[0]
  const left = useCountdown(prompt)
  const [hidden, setHidden] = useState<number | null>(null)
  const notified = useRef(new Set<number>())

  useEffect(() => {
    for (const p of data?.prompts ?? []) {
      if (notified.current.has(p.id)) continue
      notified.current.add(p.id)
      notify(p)
    }
  }, [data])

  useEffect(() => {
    if (!prompt) return
    const original = document.title
    document.title = `(!) ${original}`
    return () => {
      document.title = original
    }
  }, [prompt?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!prompt) return null
  const send = (outcome: 'done' | 'skipped') => answer.mutate({ promptId: prompt.id, outcome })
  const open = hidden !== prompt.id
  const where = prompt.attempt_id
    ? 'en el navegador de CandidatAI'
    : prompt.source_name
      ? `en ${prompt.source_name}, en tu navegador`
      : 'en tu navegador'

  return (
    <>
      <Dialog open={open} onOpenChange={(next) => !next && setHidden(prompt.id)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <ShieldWarningIcon className="size-5 text-amber-600" weight="duotone" />
              {prompt.title}
            </DialogTitle>
            <DialogDescription>Hace falta que lo hagas tú, {where}. CandidatAI nunca lo resuelve por ti.</DialogDescription>
          </DialogHeader>
          <p className="text-sm">{prompt.message}</p>
          {prompt.url && !prompt.attempt_id && (
            <a
              href={prompt.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex w-fit items-center gap-1 text-sm underline underline-offset-4"
            >
              Abrir la página
              <ArrowSquareOutIcon className="size-3.5" />
            </a>
          )}
          <p role="timer" aria-live="off" className="text-sm text-muted-foreground">
            {left > 0
              ? `Si no contestas en ${clock(left)}, ${prompt.attempt_id ? 'el aviso caduca' : 'el agente sigue con lo siguiente'}.`
              : 'Se ha acabado el tiempo.'}
          </p>
          {answer.error && (
            <p role="alert" className="text-sm text-destructive">
              {answer.error.message}
            </p>
          )}
          <DialogFooter className="flex-wrap gap-2 sm:justify-between">
            <EnableNotifications />
            <div className="flex gap-2">
              <Button type="button" variant="outline" disabled={answer.isPending} onClick={() => send('skipped')}>
                Saltar
              </Button>
              <Button type="button" disabled={answer.isPending} onClick={() => send('done')}>
                Ya está
              </Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      {!open && (
        <button
          type="button"
          onClick={() => setHidden(null)}
          className="fixed right-4 bottom-4 z-40 inline-flex items-center gap-2 rounded-full border border-amber-500/60 bg-amber-50 px-4 py-2 text-sm font-medium text-amber-900 shadow-lg dark:bg-amber-950 dark:text-amber-200"
        >
          <ShieldWarningIcon className="size-4" weight="duotone" />
          {prompt.title} · {clock(left)}
        </button>
      )}
    </>
  )
}
