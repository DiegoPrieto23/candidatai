import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ChatCircleDotsIcon, LockKeyIcon } from '@phosphor-icons/react'
import type { PromptView } from '@/api/client'
import { useAnswerPrompt } from '@/api/queries'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { errorMessage } from '@/lib/errors'
import { cn } from '@/lib/utils'

function clock(seconds: number): string {
  const s = Math.max(0, seconds)
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

/** Lo que se contestó, en palabras. */
function Answered({ prompt }: { prompt: PromptView }) {
  const { t } = useTranslation('nav', { keyPrefix: 'tasks.prompt' })
  let text: string
  if (prompt.status === 'expired') text = prompt.kind === 'permission' ? t('expiredPermission') : t('expired')
  else if (prompt.kind === 'permission') text = t(`answers.${prompt.answer ?? 'deny'}` as never)
  else if (prompt.status === 'skipped') text = t('skipped')
  else text = t('answer', { answer: prompt.answer ?? '' })
  return <p className="text-xs text-muted-foreground">{text}</p>
}

function Question({ prompt }: { prompt: PromptView }) {
  const { t } = useTranslation('nav', { keyPrefix: 'tasks.prompt' })
  const answer = useAnswerPrompt()
  const [text, setText] = useState('')
  const send = (value: string) => answer.mutate({ promptId: prompt.id, outcome: 'done', answer: value })
  return (
    <form
      className="space-y-2"
      onSubmit={(event) => {
        event.preventDefault()
        if (text.trim()) send(text)
      }}
    >
      {prompt.options.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {prompt.options.map((option) => (
            <Button key={option} type="button" size="sm" variant="outline" disabled={answer.isPending} onClick={() => send(option)}>
              {option}
            </Button>
          ))}
        </div>
      )}
      <Textarea
        aria-label={t('label')}
        placeholder={prompt.options.length > 0 ? t('placeholderOther') : t('placeholder')}
        value={text}
        maxLength={2000}
        rows={2}
        onChange={(event) => setText(event.target.value)}
      />
      {answer.error && (
        <p role="alert" className="text-xs text-destructive">
          {errorMessage(answer.error)}
        </p>
      )}
      <div className="flex flex-wrap justify-between gap-2">
        <Button type="button" size="sm" variant="ghost" disabled={answer.isPending} onClick={() => answer.mutate({ promptId: prompt.id, outcome: 'skipped' })}>
          {t('skip')}
        </Button>
        <Button type="submit" size="sm" disabled={answer.isPending || !text.trim()}>
          {t('send')}
        </Button>
      </div>
    </form>
  )
}

function Permission({ prompt }: { prompt: PromptView }) {
  const { t } = useTranslation('nav', { keyPrefix: 'tasks.prompt' })
  const answer = useAnswerPrompt()
  const send = (choice: 'once' | 'always' | 'deny') =>
    answer.mutate({ promptId: prompt.id, outcome: 'done', answer: choice })
  return (
    <div className="space-y-2">
      {answer.error && (
        <p role="alert" className="text-xs text-destructive">
          {errorMessage(answer.error)}
        </p>
      )}
      <div className="flex flex-wrap gap-1.5">
        <Button size="sm" disabled={answer.isPending} onClick={() => send('once')}>
          {t('allowOnce')}
        </Button>
        {/* Solo donde la regla cubriría exactamente lo que se ve (lo decide la app). */}
        {prompt.options.includes('always') && (
          <Button size="sm" variant="outline" disabled={answer.isPending} onClick={() => send('always')}>
            {t('allowAlways')}
          </Button>
        )}
        <Button size="sm" variant="outline" className="text-destructive" disabled={answer.isPending} onClick={() => send('deny')}>
          {t('deny')}
        </Button>
      </div>
    </div>
  )
}

/**
 * Una pregunta o un permiso de una ejecución sin ventana (fase 48.1b), dentro de su conversación:
 * se contesta ahí. Lo que escribe el agente es texto plano, nunca HTML.
 */
export function PromptCard({ prompt }: { prompt: PromptView }) {
  const { t } = useTranslation('nav', { keyPrefix: 'tasks.prompt' })
  const pending = prompt.status === 'pending'
  const permission = prompt.kind === 'permission'
  const Icon = permission ? LockKeyIcon : ChatCircleDotsIcon
  return (
    <li
      aria-label={permission ? t('permissionTitle') : t('questionTitle')}
      className={cn(
        'space-y-2 rounded-lg border p-3 text-sm',
        pending ? 'border-warning-border bg-warning' : 'bg-card',
      )}
    >
      <p className={cn('flex items-center gap-1.5 text-xs font-semibold tracking-wide uppercase', pending ? 'text-warning-foreground' : 'text-muted-foreground')}>
        <Icon className="size-4" weight="bold" aria-hidden />
        {permission ? t('permissionTitle') : t('questionTitle')}
      </p>
      {permission ? (
        <>
          <p className="font-medium">{t('permissionAsk', { tool: prompt.tool ?? '?' })}</p>
          <code className="block overflow-x-auto rounded border bg-card px-2 py-1.5 font-mono text-xs whitespace-pre-wrap break-all">
            {prompt.message}
          </code>
        </>
      ) : (
        <p className="font-medium whitespace-pre-wrap break-words">{prompt.message}</p>
      )}
      {pending ? (
        <>
          {permission ? <Permission prompt={prompt} /> : <Question prompt={prompt} />}
          <p role="timer" aria-live="off" className="tabular text-xs text-muted-foreground">
            {permission ? t('permissionExpires', { time: clock(prompt.seconds_left) }) : t('expires', { time: clock(prompt.seconds_left) })}
          </p>
        </>
      ) : (
        <Answered prompt={prompt} />
      )}
    </li>
  )
}
