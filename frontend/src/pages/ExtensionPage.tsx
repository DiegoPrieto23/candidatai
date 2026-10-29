import { useState, type ReactNode } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Trans, useTranslation } from 'react-i18next'
import { CheckCircleIcon, CircleNotchIcon, PlugsConnectedIcon, WarningIcon } from '@phosphor-icons/react'
import { useExtensionStatus, usePairExtension, type ExtensionStatus } from '@/api/queries'
import { CopyButton } from '@/components/CopyButton'
import { OpenFolderButton } from '@/components/OpenFolderButton'
import { ErrorState } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { errorMessage } from '@/lib/errors'
import { askExtension, compareVersions, isChromium, isEdge, type ExtensionReply } from '@/lib/extension'
import { cn } from '@/lib/utils'

const strong = { strong: <strong className="font-medium text-foreground" /> }

function Step({ n, done, title, children }: { n: number; done: boolean; title: string; children: ReactNode }) {
  return (
    <li className="flex gap-3">
      {done ? (
        <CheckCircleIcon className="size-6 shrink-0 text-emerald-600 dark:text-emerald-400" weight="fill" aria-hidden />
      ) : (
        <span aria-hidden className="grid size-6 shrink-0 place-items-center rounded-full border bg-background text-xs font-semibold">
          {n}
        </span>
      )}
      <div className="min-w-0 flex-1 space-y-3 pt-0.5">
        <h2 className={cn('font-medium', done && 'text-muted-foreground')}>{title}</h2>
        {children}
      </div>
    </li>
  )
}

/**
 * Lo que dice la extensión, preguntado cada 2 s hasta que está conectada: así la página avanza sola
 * mientras la cargas en el navegador. `null`: no responde (sin instalar o de una versión antigua).
 */
function useExtensionReply(extensionId: string | undefined) {
  return useQuery({
    queryKey: ['extension', 'reply', extensionId],
    queryFn: () => askExtension(extensionId ?? '', { type: 'ping' }),
    enabled: Boolean(extensionId),
    refetchInterval: (query) => (query.state.data?.connected ? false : 2000),
    refetchOnWindowFocus: true,
  })
}

function Install({ status }: { status: ExtensionStatus }) {
  const { t } = useTranslation('extension', { keyPrefix: 'install' })
  const page = isEdge() ? 'edge://extensions' : 'chrome://extensions'
  return (
    <ol className="grid list-decimal gap-3 pl-5 text-muted-foreground marker:text-xs">
      <li className="space-y-2">
        <p>{t('folder')}</p>
        <OpenFolderButton folder="extension" label={t('openFolder')} />
        {status.version === null && (
          <p className="text-xs text-destructive" role="alert">
            {t('noFolder')}
          </p>
        )}
      </li>
      <li className="space-y-2">
        <p>{t('page')}</p>
        <div className="flex flex-wrap items-center gap-2">
          <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs text-foreground">{page}</code>
          <CopyButton text={page} />
        </div>
      </li>
      <li>
        <Trans t={t} i18nKey={isEdge() ? 'devModeEdge' : 'devMode'} components={strong} />
      </li>
      <li>
        <Trans t={t} i18nKey="load" components={strong} />
      </li>
      <li>
        <Trans t={t} i18nKey="update" components={strong} />
      </li>
      <li className="list-none text-xs" role="status">
        <CircleNotchIcon className="mr-1.5 inline size-3.5 animate-spin motion-reduce:animate-none" aria-hidden />
        {t('waiting')}
      </li>
    </ol>
  )
}

function Connect({
  status,
  reply,
  onConnected,
}: {
  status: ExtensionStatus
  reply: ExtensionReply | null | undefined
  onConnected: () => void
}) {
  const { t } = useTranslation('extension', { keyPrefix: 'connect' })
  const pair = usePairExtension()
  const [problem, setProblem] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const found = Boolean(reply)
  const connected = Boolean(reply?.connected)

  const connect = async () => {
    setProblem(null)
    setBusy(true)
    try {
      const { token } = await pair.mutateAsync()
      const answer = await askExtension(status.extension_id, { type: 'pair', token })
      if (!answer) setProblem(t('noAnswer'))
      else if (!answer.connected) setProblem(answer.message || t('rejected'))
      onConnected()
    } catch (error) {
      setProblem(errorMessage(error))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-3">
      <p className="text-muted-foreground">{connected ? t('done') : t('body')}</p>
      {/* Conectada pero la app dice que no (se conectó desde otro navegador o se creó otro token). */}
      {found && !connected && reply?.kind !== 'no_token' && reply?.message && (
        <p className="text-xs text-amber-700 dark:text-amber-400">{reply.message}</p>
      )}
      <Button
        type="button"
        size="sm"
        variant={connected ? 'outline' : 'default'}
        disabled={!found || busy}
        onClick={() => void connect()}
      >
        <PlugsConnectedIcon />
        {busy ? t('connecting') : connected ? t('again') : t('button')}
      </Button>
      {connected && <p className="text-xs text-muted-foreground">{t('againHint')}</p>}
      {problem && (
        <p className="text-xs text-destructive" role="alert">
          {problem}
        </p>
      )}
    </div>
  )
}

/**
 * «Dónde buscar → Extensión»: instalar y conectar el botón «Enviar a CandidatAI» sin terminal. La
 * página detecta la extensión sola, la conecta con un clic y avisa si es de una versión antigua.
 */
export function ExtensionPage() {
  const { t } = useTranslation('extension')
  const client = useQueryClient()
  const status = useExtensionStatus()
  const reply = useExtensionReply(status.data?.extension_id)

  let body
  if (status.isPending) {
    body = <Skeleton className="h-64" />
  } else if (status.isError) {
    body = <ErrorState error={status.error} onRetry={() => status.refetch()} />
  } else {
    const found = Boolean(reply.data)
    const connected = Boolean(reply.data?.connected)
    const outdated =
      reply.data && status.data.version ? compareVersions(reply.data.version, status.data.version) < 0 : false
    body = (
      <div className="grid gap-6">
        {!isChromium() && (
          <p role="status" className="flex gap-2 rounded-xl border border-amber-500/30 bg-amber-500/5 p-4 text-sm">
            <WarningIcon className="mt-0.5 size-4 shrink-0 text-amber-600 dark:text-amber-400" weight="fill" aria-hidden />
            {t('notChromium')}
          </p>
        )}
        {outdated && (
          <p role="status" className="flex gap-2 rounded-xl border border-amber-500/30 bg-amber-500/5 p-4 text-sm">
            <WarningIcon className="mt-0.5 size-4 shrink-0 text-amber-600 dark:text-amber-400" weight="fill" aria-hidden />
            <span>
              <Trans
                t={t}
                i18nKey="outdated"
                values={{ installed: reply.data?.version, current: status.data.version }}
                components={strong}
              />
            </span>
          </p>
        )}
        <ol className="grid gap-6 rounded-xl border bg-card p-5 text-sm sm:p-6">
          <Step n={1} done={found} title={t('steps.install')}>
            {found ? (
              <p className="text-muted-foreground">{t('installed', { version: reply.data?.version })}</p>
            ) : (
              <Install status={status.data} />
            )}
          </Step>
          <Step n={2} done={connected} title={t('steps.connect')}>
            <Connect
              status={status.data}
              reply={reply.data}
              onConnected={() => void client.invalidateQueries({ queryKey: ['extension'] })}
            />
          </Step>
          <Step n={3} done={false} title={t('steps.use')}>
            <ul className="grid list-disc gap-1.5 pl-5 text-muted-foreground">
              <li>
                <Trans t={t} i18nKey="use.pin" components={strong} />
              </li>
              <li>
                <Trans t={t} i18nKey="use.send" components={strong} />
              </li>
              <li>{t('use.selection')}</li>
            </ul>
          </Step>
        </ol>
        <p className="text-xs text-muted-foreground">{t('privacy')}</p>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-3xl animate-in fade-in duration-300">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold tracking-tight">{t('title')}</h1>
        <p className="mt-1.5 text-sm text-muted-foreground">{t('intro')}</p>
      </div>
      {body}
    </div>
  )
}
