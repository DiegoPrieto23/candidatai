import { useId, useState, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Trans, useTranslation } from 'react-i18next'
import { CheckCircleIcon, CircleNotchIcon, PlugsConnectedIcon, WarningIcon } from '@phosphor-icons/react'
import { useExtensionStatus, usePairExtension, type ExtensionStatus } from '@/api/queries'
import { CopyButton } from '@/components/CopyButton'
import { OpenFolderButton } from '@/components/OpenFolderButton'
import { ErrorState } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { errorMessage } from '@/lib/errors'
import { BrowserPicker } from '@/components/BrowserPicker'
import { supportsExtension, useBrowserChoice, type BrowserId } from '@/lib/browser'
import { DemoToggle, ExtensionDemo } from '@/components/ExtensionDemo'
import { askExtension, compareVersions, desktopOs, useExtensionReply, type ExtensionReply } from '@/lib/extension'
import { cn } from '@/lib/utils'

const strong = { strong: <strong className="font-medium text-foreground" /> }

function Step({
  n,
  done,
  title,
  aside,
  children,
}: {
  n: number
  done: boolean
  title: string
  aside?: ReactNode
  children: ReactNode
}) {
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
        <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
          <h4 className={cn('font-medium', done && 'text-muted-foreground')}>{title}</h4>
          {aside}
        </div>
        {children}
      </div>
    </li>
  )
}

/** La página de extensiones de cada navegador compatible. */
const EXTENSIONS_PAGE: Partial<Record<BrowserId, string>> = {
  chrome: 'chrome://extensions',
  edge: 'edge://extensions',
  brave: 'brave://extensions',
}

function Install({ status, browser }: { status: ExtensionStatus; browser: BrowserId }) {
  const { t } = useTranslation('extension', { keyPrefix: 'install' })
  const page = EXTENSIONS_PAGE[browser] ?? 'chrome://extensions'
  const edge = browser === 'edge'
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
        <Trans t={t} i18nKey={edge ? 'devModeEdge' : 'devMode'} components={strong} />
      </li>
      {/* La ventana de elegir carpeta no recuerda la del paso 1: se pega la ruta, que es lo que lía. */}
      <li className="space-y-2">
        <p>
          <Trans t={t} i18nKey={`load.${desktopOs()}`} values={{ button: t(edge ? 'loadButtonEdge' : 'loadButton') }} components={strong} />
        </p>
        {status.folder && (
          <div className="flex flex-wrap items-center gap-2">
            <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs break-all text-foreground">{status.folder}</code>
            <CopyButton text={status.folder} ariaLabel={t('copyFolder')} />
          </div>
        )}
        <p className="text-xs">
          <Trans t={t} i18nKey="load.whole" components={strong} />
        </p>
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
 * «Dónde buscar → Botón del navegador»: instalar y conectar el botón «Enviar a CandidatAI» sin
 * terminal. La página detecta la extensión sola, la conecta con un clic y avisa si es de una
 * versión antigua.
 */
export function ExtensionPage() {
  const { t } = useTranslation('extension')
  const client = useQueryClient()
  const status = useExtensionStatus()
  const reply = useExtensionReply(status.data?.extension_id)
  const { browser, detected, choose } = useBrowserChoice()
  const supported = supportsExtension(browser)
  const name = t(`browser.names.${browser}`)
  // «Ver cómo se hace» va junto al título del paso 3, a la vista; la animación se abre justo debajo.
  const [demoOpen, setDemoOpen] = useState(false)
  const demoId = useId()

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
        <BrowserPicker browser={browser} detected={detected} onChoose={choose} />
        {/* Lo que impide seguir, antes de los pasos: un navegador sin extensiones o la app abierta en otro. */}
        {!supported ? (
          <p role="status" className="flex gap-2 rounded-xl border border-amber-500/30 bg-amber-500/5 p-4 text-sm">
            <WarningIcon className="mt-0.5 size-4 shrink-0 text-amber-600 dark:text-amber-400" weight="fill" aria-hidden />
            {t('browser.unsupported', { name })}
          </p>
        ) : (
          browser !== detected && (
            <p role="status" className="flex gap-2 rounded-xl border border-amber-500/30 bg-amber-500/5 p-4 text-sm">
              <WarningIcon className="mt-0.5 size-4 shrink-0 text-amber-600 dark:text-amber-400" weight="fill" aria-hidden />
              {t('browser.openIn', { name })}
            </p>
          )
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
        {supported && (
        <ol className="grid gap-6 rounded-xl border bg-card p-5 text-sm sm:p-6">
          <Step n={1} done={found} title={t('steps.install')}>
            {found ? (
              <p className="text-muted-foreground">{t('installed', { version: reply.data?.version })}</p>
            ) : (
              <Install status={status.data} browser={browser} />
            )}
          </Step>
          <Step n={2} done={connected} title={t('steps.connect')}>
            <Connect
              status={status.data}
              reply={reply.data}
              onConnected={() => void client.invalidateQueries({ queryKey: ['extension'] })}
            />
          </Step>
          <Step
            n={3}
            done={false}
            title={t('steps.use')}
            aside={<DemoToggle open={demoOpen} onToggle={() => setDemoOpen(!demoOpen)} controls={demoId} />}
          >
            <ExtensionDemo controlled={{ open: demoOpen, id: demoId }} />
            <ul className="grid list-disc gap-1.5 pl-5 text-muted-foreground">
              <li>
                <Trans t={t} i18nKey={browser === 'edge' ? 'use.pinEdge' : 'use.pin'} components={strong} />
              </li>
              <li>
                <Trans t={t} i18nKey="use.send" components={strong} />
              </li>
              <li>{t('use.selection')}</li>
            </ul>
          </Step>
        </ol>
        )}
        <p className="text-xs text-muted-foreground">{t('privacy')}</p>
      </div>
    )
  }

  return (
    <div className="max-w-3xl">
      <h3 className="sr-only">{t('title')}</h3>
      <p className="mb-6 text-sm text-muted-foreground">{t('intro')}</p>
      {body}
    </div>
  )
}
