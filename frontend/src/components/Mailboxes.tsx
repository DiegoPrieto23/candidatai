/**
 * Buzones de las alertas (fase 27.4): el panel con el estado de cada uno y el asistente
 * para añadirlos, con una pestaña por proveedor. La contraseña solo va hacia el servidor: la API
 * nunca la devuelve, solo si está puesta.
 */
import { useState, type FormEvent, type ReactNode } from 'react'
import type { ParseKeys } from 'i18next'
import { Trans, useTranslation } from 'react-i18next'
import { ArrowSquareOutIcon, CaretDownIcon, CheckCircleIcon, EnvelopeSimpleIcon, FolderIcon, LockKeyIcon, WarningIcon, XIcon } from '@phosphor-icons/react'
import type { MailSourceInput, MailSourceView, MailTestResult } from '@/api/client'
import {
  useCreateMailSource,
  useDeleteMailSource,
  useMailSources,
  useMoveSecretsToKeyring,
  useMailFolders,
  useNewMailFolders,
  useTestMailSource,
  useTestNewMailSource,
  useUpdateMailSource,
} from '@/api/queries'
import { Hint } from '@/components/Hint'
import { Reveal } from '@/components/Reveal'
import { InlineCode } from '@/components/States'
import { Switch } from '@/components/Switch'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { errorMessage } from '@/lib/errors'
import { formatList, i18n } from '@/lib/i18n'
import { formatRelative } from '@/lib/labels'
import { folderLabel } from '@/lib/mailFolders'
import { cn } from '@/lib/utils'


export type ProviderId = 'gmail' | 'outlook' | 'yahoo' | 'icloud' | 'imap' | 'folder'

type Key = ParseKeys<'mailboxes'>

interface Provider {
  host?: string
  port?: number
  steps: Key[]
  /** El enlace oficial que va dentro de un paso (su `<a>`): la página donde se hace lo que pide. */
  stepLinks?: Partial<Record<Key, string>>
  /** La sección de `docs/CONFIGURAR_CORREO.md` de este proveedor. */
  guide: string
  /** El texto del enlace y su URL oficial. */
  links: [Key, string][]
}

/** Servidores y enlaces comprobados en la ayuda oficial de cada proveedor el 2026-10-23. */
const PROVIDERS: Record<ProviderId, Provider> = {
  gmail: {
    host: 'imap.gmail.com',
    port: 993,
    steps: ['providers.gmail.step1', 'providers.gmail.step2', 'providers.gmail.step3', 'providers.gmail.step4'],
    stepLinks: {
      'providers.gmail.step1': 'https://myaccount.google.com/security',
      'providers.gmail.step2': 'https://myaccount.google.com/apppasswords',
      'providers.gmail.step3': 'https://support.google.com/mail/answer/6579',
    },
    guide: 'https://github.com/DiegoPrieto23/candidatai/blob/main/docs/CONFIGURAR_CORREO.md#gmail',
    links: [['providers.gmail.linkHelp', 'https://support.google.com/mail/answer/185833']],
  },
  outlook: {
    host: 'outlook.office365.com',
    port: 993,
    steps: [],
    guide: 'https://github.com/DiegoPrieto23/candidatai/blob/main/docs/CONFIGURAR_CORREO.md#outlook-y-hotmail',
    links: [
      [
        'providers.outlook.linkForwarding',
        'https://support.microsoft.com/en-us/office/turn-on-automatic-forwarding-in-outlook-7f2670a1-7fff-4475-8a3c-5822d63b0c8e',
      ],
      [
        'providers.outlook.linkBasicAuth',
        'https://support.microsoft.com/en-us/office/outlook-and-other-apps-are-unable-to-connect-to-outlook-com-when-using-basic-authentication-f4202ebf-89c6-4a8a-bec3-3d60cf7deaef',
      ],
    ],
  },
  yahoo: {
    host: 'imap.mail.yahoo.com',
    port: 993,
    steps: ['providers.yahoo.step1', 'providers.yahoo.step2'],
    stepLinks: { 'providers.yahoo.step1': 'https://help.yahoo.com/kb/SLN15241.html' },
    guide: 'https://github.com/DiegoPrieto23/candidatai/blob/main/docs/CONFIGURAR_CORREO.md#yahoo',
    links: [['providers.yahoo.linkImap', 'https://help.yahoo.com/kb/SLN4075.html']],
  },
  icloud: {
    host: 'imap.mail.me.com',
    port: 993,
    steps: ['providers.icloud.step1', 'providers.icloud.step2', 'providers.icloud.step3'],
    stepLinks: { 'providers.icloud.step2': 'https://support.apple.com/en-us/102654' },
    guide: 'https://github.com/DiegoPrieto23/candidatai/blob/main/docs/CONFIGURAR_CORREO.md#icloud',
    links: [['providers.icloud.linkImap', 'https://support.apple.com/en-us/102525']],
  },
  imap: { port: 993, steps: ['providers.imap.step1', 'providers.imap.step2', 'providers.imap.step3'], guide: 'https://github.com/DiegoPrieto23/candidatai/blob/main/docs/CONFIGURAR_CORREO.md#otro-proveedor-imap', links: [] },
  folder: { steps: ['providers.folder.step1', 'providers.folder.step2', 'providers.folder.step3'], guide: 'https://github.com/DiegoPrieto23/candidatai/blob/main/docs/CONFIGURAR_CORREO.md#carpeta-de-eml', links: [] },
}
const PROVIDER_IDS = Object.keys(PROVIDERS) as ProviderId[]

/** La ayuda de un `MailboxError.code`, si la hay (el mensaje del servidor va siempre). */
function errorHelp(code: string | null | undefined): string | null {
  const key = `mailboxes:errors.${code ?? ''}`
  return code && i18n.exists(key) ? i18n.t(key as 'mailboxes:errors.imap_auth') : null
}

function TestOutcome({ result }: { result: MailTestResult }) {
  const { t } = useTranslation('mailboxes')
  const help = errorHelp(result.code)
  return (
    <div
      role="status"
      className={cn(
        'flex gap-2 rounded-lg border p-3 text-sm',
        result.ok ? 'border-primary/30 bg-primary/5' : 'border-destructive/30 bg-destructive/5',
      )}
    >
      {result.ok ? (
        <CheckCircleIcon className="mt-0.5 size-4 shrink-0 text-primary" weight="fill" />
      ) : (
        <WarningIcon className="mt-0.5 size-4 shrink-0 text-destructive" weight="fill" />
      )}
      <div className="space-y-1">
        <p className="font-medium">{result.ok ? t('dialog.testOk') : t('dialog.testFailed')}</p>
        <p>{result.message}</p>
        {help && <p className="text-muted-foreground">{help}</p>}
      </div>
    </div>
  )
}

// --- Panel ---------------------------------------------------------------------------------------

/** Dónde está la contraseña: en el llavero, en un fichero (con el botón para moverla) o fuera de la app. */
function PasswordStorage({ source, keyring }: { source: MailSourceView; keyring: boolean }) {
  const { t } = useTranslation('mailboxes')
  const move = useMoveSecretsToKeyring()
  const storage = source.password_storage
  if (!storage || !source.secret_ref) return null
  if (storage !== 'file') {
    return (
      <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
        {storage === 'keyring' && <LockKeyIcon className="size-3.5 shrink-0" weight="duotone" aria-hidden />}
        {t(`row.storage.${storage}`)}
      </p>
    )
  }
  const ref = source.secret_ref
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-md border border-warning-border bg-warning px-2.5 py-1.5 text-xs text-warning-foreground">
      <WarningIcon className="size-3.5 shrink-0" weight="fill" />
      <span className="flex-1">{t(keyring ? 'row.storage.file' : 'row.storage.fileNoKeyring')}</span>
      {keyring && (
        <Button size="xs" disabled={move.isPending} onClick={() => move.mutate([ref])}>
          {move.isPending ? t('row.storage.moving') : t('row.storage.move')}
        </Button>
      )}
      {(move.error || (move.data && move.data.failed.length > 0)) && (
        <p role="alert" className="basis-full">
          {move.error ? errorMessage(move.error) : t('keyringNotice.failed')}
        </p>
      )}
    </div>
  )
}

/** Fase 48.3: de dónde salen las alertas y de dónde las respuestas, cada cosa por su lado. */
function MailboxFolders({ source }: { source: MailSourceView }) {
  const { t } = useTranslation('mailboxes')
  const replies = source.read_replies ? formatList(source.replies_folders.map(folderLabel)) : t('row.repliesOff')
  return (
    <p className="text-xs text-muted-foreground">
      <span>{t('row.alertsIn', { folder: folderLabel(source.folder) })}</span>
      <span aria-hidden> · </span>
      <span>{t('row.repliesIn', { folders: replies })}</span>
    </p>
  )
}

function MailboxRow({ source, keyring, onEdit }: { source: MailSourceView; keyring: boolean; onEdit: () => void }) {
  const { t } = useTranslation('mailboxes')
  const update = useUpdateMailSource()
  const remove = useDeleteMailSource()
  const test = useTestMailSource()
  const testReplies = useTestMailSource('replies')
  const [confirming, setConfirming] = useState(false)
  const where = source.kind === 'folder' ? source.path : `${source.user ?? ''} · ${source.host ?? ''}`
  const error = source.last_error
  const help = errorHelp(error?.code)
  const missingPassword = source.kind === 'imap' && !source.has_password

  return (
    <li className={cn('grid gap-2 px-4 py-3', !source.enabled && 'bg-muted/30')}>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        {source.kind === 'folder' ? (
          <FolderIcon className="size-4 shrink-0 text-muted-foreground" />
        ) : (
          <EnvelopeSimpleIcon className="size-4 shrink-0 text-muted-foreground" />
        )}
        <div className="min-w-0 flex-1">
          <p className="flex flex-wrap items-center gap-2 text-sm font-medium">
            {source.label}
            {source.kind === 'folder' && (
              <span className="text-xs font-normal text-muted-foreground">{t('row.folderKind')}</span>
            )}
          </p>
          <p className="truncate text-xs text-muted-foreground">{where}</p>
          {source.kind === 'imap' && <MailboxFolders source={source} />}
        </div>
        <Switch
          checked={source.enabled}
          disabled={update.isPending}
          label={t('row.switch', { name: source.label })}
          onChange={(enabled) => update.mutate({ sourceId: source.id, enabled })}
        />
      </div>
      <p className="text-xs text-muted-foreground">
        {source.last_polled_at ? t('row.lastPolled', { when: formatRelative(source.last_polled_at) }) : t('row.never')}
      </p>
      {missingPassword && (
        <div className="flex flex-wrap items-center gap-2 rounded-md border border-warning-border bg-warning px-2.5 py-1.5 text-xs text-warning-foreground">
          <WarningIcon className="size-3.5 shrink-0" weight="fill" />
          <span className="flex-1">{t('row.noPassword')}</span>
          <Button size="xs" onClick={onEdit}>
            {t('row.writePassword')}
          </Button>
        </div>
      )}
      <PasswordStorage source={source} keyring={keyring} />
      {error && (
        <div className="rounded-md bg-destructive/5 px-2.5 py-1.5 text-xs">
          <p className="font-medium">{t('row.lastError')}</p>
          <p className="text-muted-foreground">{help ?? error.message}</p>
        </div>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="outline" size="xs" onClick={() => test.mutate(source.id)} disabled={test.isPending}>
          {test.isPending ? t('row.testing') : source.kind === 'imap' ? t('row.testAlerts') : t('row.test')}
        </Button>
        {source.kind === 'imap' && source.read_replies && (
          <Button variant="outline" size="xs" onClick={() => testReplies.mutate(source.id)} disabled={testReplies.isPending}>
            {testReplies.isPending ? t('row.testing') : t('row.testReplies')}
          </Button>
        )}
        <Button variant="outline" size="xs" onClick={onEdit} aria-label={`${t('row.edit')} ${source.label}`}>
          {t('row.edit')}
        </Button>
        {!source.from_env &&
          (confirming ? (
            <>
              <Button
                variant="destructive"
                size="xs"
                disabled={remove.isPending}
                onClick={() => remove.mutate(source.id, { onSettled: () => setConfirming(false) })}
              >
                {t('row.confirmRemove')}
              </Button>
              <Button variant="ghost" size="xs" onClick={() => setConfirming(false)}>
                {t('row.cancelRemove')}
              </Button>
            </>
          ) : (
            <Button variant="ghost" size="xs" onClick={() => setConfirming(true)} aria-label={`${t('row.remove')} ${source.label}`}>
              {t('row.remove')}
            </Button>
          ))}
      </div>
      {test.data && <TestOutcome result={test.data} />}
      {testReplies.data && <TestOutcome result={testReplies.data} />}
      {(source.from_env || source.secret_ref || (error && help)) && (
        <Reveal label={t('technicalDetails', { ns: 'common' })} className="space-y-1.5 text-xs text-muted-foreground">
          {error && help && <p>{t('row.serverSaid', { message: error.message })}</p>}
          {source.secret_ref && <p>{t('row.secretRef', { ref: source.secret_ref })}</p>}
          {source.from_env && <p>{t('row.fromEnvHint')}</p>}
        </Reveal>
      )}
      {(update.error ?? remove.error ?? test.error ?? testReplies.error) && (
        <p role="alert" className="text-xs text-destructive">
          {errorMessage(update.error ?? remove.error ?? test.error ?? testReplies.error)}
        </p>
      )}
    </li>
  )
}

/** Panel plegable «Buzones», con el estado de cada uno. Se abre solo si alguno tiene un error o le falta la contraseña. */
export function MailboxesPanel({ onEdit, defaultOpen = false }: { onEdit: (source: MailSourceView) => void; defaultOpen?: boolean }) {
  const { t } = useTranslation('mailboxes')
  const query = useMailSources()
  const sources = query.data?.sources ?? []
  const failing = sources.filter((s) => s.enabled && s.last_error).length
  const needsPassword = sources.some((s) => s.enabled && s.kind === 'imap' && !s.has_password)
  const [open, setOpen] = useState<boolean | null>(null)
  if (query.isPending) return null
  if (query.isError) {
    return (
      <p role="alert" className="rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-2.5 text-sm">
        {t('panel.loadFailed', { error: errorMessage(query.error) })}
      </p>
    )
  }
  if (sources.length === 0) return null
  const expanded = open ?? (defaultOpen || failing > 0 || needsPassword)
  return (
    <Collapsible open={expanded} onOpenChange={setOpen} className="rounded-xl border bg-card">
      <CollapsibleTrigger className="group flex w-full items-center gap-2 px-4 py-2.5 text-left text-sm outline-none hover:bg-foreground/[0.03] focus-visible:ring-[3px] focus-visible:ring-ring/50">
        <EnvelopeSimpleIcon className="size-4 text-primary" weight="duotone" />
        <span className="font-medium">{t('panel.title')}</span>
        <span className="text-muted-foreground">· {t('panel.summary', { count: sources.length })}</span>
        {failing > 0 && <span className="text-destructive">· {t('panel.withErrors', { count: failing })}</span>}
        <CaretDownIcon className="ml-auto size-4 text-muted-foreground transition-transform group-data-[state=open]:rotate-180" />
      </CollapsibleTrigger>
      <CollapsibleContent className="border-t">
        {query.data?.demo && <p className="px-4 pt-3 text-xs text-muted-foreground">{t('panel.demo')}</p>}
        <ul className="divide-y">
          {sources.map((source) => (
            <MailboxRow key={source.id} source={source} keyring={query.data?.keyring ?? false} onEdit={() => onEdit(source)} />
          ))}
        </ul>
      </CollapsibleContent>
    </Collapsible>
  )
}

// --- Asistente -----------------------------------------------------------------------------------

interface Form {
  label: string
  user: string
  password: string
  host: string
  port: string
  security: 'ssl' | 'starttls'
  folder: string
  folderName: string
  readReplies: boolean
  repliesFolders: string[]
  allowPrivate: boolean
}

function initialForm(provider: ProviderId, source?: MailSourceView): Form {
  if (source) {
    return {
      label: source.label,
      user: source.user ?? '',
      password: '',
      host: source.host ?? '',
      port: String(source.port ?? 993),
      security: source.security,
      folder: source.kind === 'imap' ? source.folder : 'INBOX',
      folderName: source.kind === 'folder' ? source.folder : '',
      readReplies: source.read_replies,
      repliesFolders: source.replies_folders.length > 0 ? source.replies_folders : ['INBOX'],
      allowPrivate: source.allow_private,
    }
  }
  const preset = PROVIDERS[provider]
  return {
    label: i18n.t(`mailboxes:providers.${provider}.name`),
    user: '',
    password: '',
    host: preset.host ?? '',
    port: String(preset.port ?? 993),
    security: 'ssl',
    folder: 'INBOX',
    folderName: provider === 'folder' ? 'alertas' : '',
    readReplies: false,
    repliesFolders: ['INBOX'],
    allowPrivate: false,
  }
}

const MAX_REPLIES_FOLDERS = 10

/**
 * Fase 48.3: las carpetas de las que se leen las respuestas. Se eligen de las del buzón («Elegir
 * del buzón» las pide en solo lectura) o se escriben a mano; por defecto, la bandeja de entrada.
 */
function RepliesFolders({
  form,
  set,
  editing,
  draft,
}: {
  form: Form
  set: (patch: Partial<Form>) => void
  editing?: MailSourceView
  /** El buzón tal como está en el formulario, para pedir sus carpetas antes de guardarlo. */
  draft: () => MailSourceInput
}) {
  const { t } = useTranslation('mailboxes')
  const saved = useMailFolders()
  const fresh = useNewMailFolders()
  const listing = editing && !form.password ? saved : fresh
  const [typed, setTyped] = useState('')
  const chosen = form.repliesFolders
  const toggle = (folder: string) => {
    const next = chosen.includes(folder) ? chosen.filter((f) => f !== folder) : [...chosen, folder]
    set({ repliesFolders: next.slice(0, MAX_REPLIES_FOLDERS) })
  }
  const add = () => {
    const folder = typed.trim()
    if (!folder) return
    if (!chosen.some((f) => f.toLowerCase() === folder.toLowerCase())) toggle(folder)
    setTyped('')
  }
  const load = () => (editing && !form.password ? saved.mutate(editing.id) : fresh.mutate(draft()))
  const alerts = (editing?.from_env ? editing.folder : form.folder).trim().toLowerCase()
  const same = chosen.some((f) => f.trim().toLowerCase() === alerts)
  const offered = listing.data?.ok ? listing.data.folders : []
  return (
    <div className="grid gap-2">
      <p className="text-sm font-medium">{t('fields.repliesFolders')}</p>
      <ul className="flex flex-wrap gap-1.5" aria-label={t('fields.repliesFolders')}>
        {chosen.map((folder) => (
          <li key={folder} className="inline-flex items-center gap-1 rounded-md border bg-muted/40 py-0.5 pr-1 pl-2 text-xs">
            {folderLabel(folder)}
            {chosen.length > 1 && (
              <button
                type="button"
                className="rounded p-0.5 text-muted-foreground hover:text-foreground"
                aria-label={t('fields.removeFolder', { folder: folderLabel(folder) })}
                onClick={() => toggle(folder)}
              >
                <XIcon className="size-3" />
              </button>
            )}
          </li>
        ))}
      </ul>
      {same && (
        <p role="status" className="rounded-md border border-warning-border bg-warning px-2.5 py-1.5 text-xs text-warning-foreground">
          {t('fields.sameFolder')}
        </p>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <Button type="button" size="xs" variant="outline" disabled={listing.isPending} onClick={load}>
          {listing.isPending ? t('fields.loadingFolders') : t('fields.loadFolders')}
        </Button>
        <Input
          aria-label={t('fields.typeFolder')}
          placeholder={t('fields.typeFolder')}
          value={typed}
          className="h-7 w-44 text-xs"
          onChange={(e) => setTyped(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              add()
            }
          }}
        />
        <Button type="button" size="xs" variant="ghost" disabled={!typed.trim()} onClick={add}>
          {t('fields.addFolder')}
        </Button>
      </div>
      {listing.data && !listing.data.ok && (
        <p role="alert" className="text-xs text-destructive">
          {listing.data.message}
        </p>
      )}
      {listing.error && (
        <p role="alert" className="text-xs text-destructive">
          {errorMessage(listing.error)}
        </p>
      )}
      {offered.length > 0 && (
        <fieldset className="grid max-h-44 gap-1 overflow-y-auto rounded-md border p-2">
          <legend className="sr-only">{t('fields.mailboxFolders')}</legend>
          {offered.map((folder) => (
            <label key={folder} className="flex items-center gap-2 text-xs">
              <input type="checkbox" checked={chosen.includes(folder)} onChange={() => toggle(folder)} />
              {folderLabel(folder)}
            </label>
          ))}
        </fieldset>
      )}
    </div>
  )
}

function Field({ id, label, hint, children }: { id: string; label: string; hint?: ReactNode; children: ReactNode }) {
  return (
    <div className="grid gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      {children}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  )
}

/** Con `hintLabel`, la explicación va en una ayuda (ⓘ) junto a la etiqueta en vez de en un párrafo. */
function Check({
  id,
  label,
  hint,
  hintLabel,
  checked,
  onChange,
}: {
  id: string
  label: string
  hint: string
  hintLabel?: string
  checked: boolean
  onChange: (v: boolean) => void
}) {
  return (
    <div className="flex items-start gap-2">
      <input id={id} type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} className="mt-1" />
      {hintLabel ? (
        <div className="flex items-center gap-1.5">
          <Label htmlFor={id}>{label}</Label>
          <Hint text={hint} label={hintLabel} />
        </div>
      ) : (
        <div>
          <Label htmlFor={id}>{label}</Label>
          <p className="text-xs text-muted-foreground">{hint}</p>
        </div>
      )}
    </div>
  )
}

/** Pasos y enlaces oficiales de un proveedor. */
function ProviderGuide({ provider }: { provider: ProviderId }) {
  const { t } = useTranslation('mailboxes')
  const preset = PROVIDERS[provider]
  return (
    <div className="space-y-2 rounded-lg bg-muted/40 p-3 text-sm">
      {preset.steps.length > 0 && (
        <ol className="list-decimal space-y-1 pl-5">
          {preset.steps.map((key) => {
            const url = preset.stepLinks?.[key]
            return (
              <li key={key}>
                {url ? (
                  <Trans
                    t={t}
                    i18nKey={key}
                    components={{
                      a: (
                        // El texto del enlace lo pone la traducción.
                        // oxlint-disable-next-line jsx-a11y/anchor-has-content
                        <a href={url} target="_blank" rel="noopener noreferrer" className="font-medium underline underline-offset-2" />
                      ),
                    }}
                  />
                ) : (
                  t(key)
                )}
              </li>
            )
          })}
        </ol>
      )}
      <p className="flex flex-wrap gap-x-3 gap-y-1 text-xs">
        {preset.links.map(([key, url]) => (
          <a key={key} href={url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 underline underline-offset-2">
            {t(key)}
            <ArrowSquareOutIcon className="size-3" aria-hidden />
          </a>
        ))}
        <a href={preset.guide} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 underline underline-offset-2">
          {t('dialog.guide')}
          <ArrowSquareOutIcon className="size-3" aria-hidden />
        </a>
      </p>
    </div>
  )
}

function ImapFields({
  provider,
  form,
  set,
  editing,
}: {
  provider: ProviderId
  form: Form
  set: (patch: Partial<Form>) => void
  editing?: MailSourceView
}) {
  const draft = () => bodyOf(provider === 'folder' ? 'imap' : provider, form)
  const { t } = useTranslation('mailboxes')
  const fromEnv = editing?.from_env === true
  const custom = provider === 'imap' || (editing !== undefined && !fromEnv)
  // Sin contraseña guardada, no hay nada que conservar: el campo pide escribirla.
  const passwordField = (
    <Field id="mailbox-password" label={t('fields.password')} hint={editing?.has_password ? t('fields.passwordKeep') : undefined}>
      <Input
        id="mailbox-password"
        type="password"
        autoComplete="new-password"
        value={form.password}
        onChange={(e) => set({ password: e.target.value })}
      />
    </Field>
  )
  return (
    <div className="grid gap-3">
      {fromEnv && passwordField}
      {!fromEnv && (
        <>
          <Field id="mailbox-user" label={provider === 'icloud' ? t('fields.userIcloud') : t('fields.user')}>
            <Input id="mailbox-user" autoComplete="off" value={form.user} onChange={(e) => set({ user: e.target.value })} />
          </Field>
          {passwordField}
        </>
      )}
      <section aria-labelledby="mailbox-alerts-title" className="grid gap-2 rounded-lg border px-3 py-2.5">
        <h3 id="mailbox-alerts-title" className="text-sm font-medium">
          {t('fields.alertsBlock')}
        </h3>
        {fromEnv && editing ? (
          <p className="text-xs text-muted-foreground">{t('fields.alertsFromEnv', { folder: folderLabel(editing.folder) })}</p>
        ) : (
          <Field id="mailbox-folder" label={t('fields.folder')} hint={t('fields.folderHint')}>
            <Input id="mailbox-folder" value={form.folder} onChange={(e) => set({ folder: e.target.value })} />
          </Field>
        )}
      </section>
      <section aria-labelledby="mailbox-replies-title" className="grid gap-2 rounded-lg border px-3 py-2.5">
        <h3 id="mailbox-replies-title" className="text-sm font-medium">
          {t('fields.repliesBlock')}
        </h3>
        <Check
          id="mailbox-replies"
          label={t('fields.readReplies')}
          hint={t('fields.readRepliesHint')}
          hintLabel={t('fields.readRepliesHintAria')}
          checked={form.readReplies}
          onChange={(readReplies) => set({ readReplies })}
        />
        {form.readReplies && <RepliesFolders form={form} set={set} editing={editing} draft={draft} />}
      </section>
      {!fromEnv && (
        <details open={custom} className="rounded-lg border px-3 py-2">
          <summary className="cursor-pointer text-sm font-medium">{t('dialog.advanced')}</summary>
          <div className="mt-3 grid gap-3">
            <div className="grid grid-cols-[1fr_6rem] gap-3">
              <Field id="mailbox-host" label={t('fields.host')}>
                <Input id="mailbox-host" value={form.host} onChange={(e) => set({ host: e.target.value })} />
              </Field>
              <Field id="mailbox-port" label={t('fields.port')}>
                <Input id="mailbox-port" inputMode="numeric" value={form.port} onChange={(e) => set({ port: e.target.value })} />
              </Field>
            </div>
            <Field id="mailbox-security" label={t('fields.security')}>
              <select
                id="mailbox-security"
                value={form.security}
                onChange={(e) => {
                  const security = e.target.value as Form['security']
                  set({ security, port: security === 'starttls' ? '143' : '993' })
                }}
                className="h-9 rounded-md border border-input bg-background px-3 text-sm"
              >
                <option value="ssl">{t('fields.ssl')}</option>
                <option value="starttls">{t('fields.starttls')}</option>
              </select>
            </Field>
            <Check
              id="mailbox-private"
              label={t('fields.allowPrivate')}
              hint={t('fields.allowPrivateHint')}
              checked={form.allowPrivate}
              onChange={(allowPrivate) => set({ allowPrivate })}
            />
          </div>
        </details>
      )}
    </div>
  )
}

function bodyOf(provider: ProviderId, form: Form): MailSourceInput {
  const base = {
    label: form.label.trim(),
    port: Number(form.port) || 993,
    security: form.security,
    replies_folders: form.repliesFolders.length > 0 ? form.repliesFolders : ['INBOX'],
    enabled: true,
    read_replies: form.readReplies,
    allow_private: form.allowPrivate,
  }
  if (provider === 'folder') return { ...base, kind: 'folder', folder: form.folderName.trim(), read_replies: false }
  return {
    ...base,
    kind: 'imap',
    host: form.host.trim(),
    user: form.user.trim(),
    password: form.password || null,
    folder: form.folder.trim() || 'INBOX',
  }
}

function MailboxForm({
  editing,
  initialProvider,
  onDone,
}: {
  editing?: MailSourceView
  initialProvider: ProviderId
  onDone: () => void
}) {
  const { t } = useTranslation('mailboxes')
  const create = useCreateMailSource()
  const update = useUpdateMailSource()
  const test = useTestNewMailSource()
  const list = useMailSources().data
  const [provider, setProvider] = useState<ProviderId>(editing ? (editing.kind === 'folder' ? 'folder' : 'imap') : initialProvider)
  const [form, setForm] = useState<Form>(() => initialForm(provider, editing))
  const [envLine, setEnvLine] = useState<string | null>(null)
  const set = (patch: Partial<Form>) => {
    setForm((prev) => ({ ...prev, ...patch }))
    test.reset()
  }

  const choose = (next: string) => {
    const id = next as ProviderId
    const preset = PROVIDERS[id]
    setForm((prev) => {
      const fresh = initialForm(id)
      // El nombre, solo si sigue siendo el del proveedor anterior; lo escrito se conserva.
      const label = prev.label === initialForm(provider).label ? fresh.label : prev.label
      return { ...prev, label, host: preset.host ?? '', port: String(preset.port ?? 993), security: 'ssl', folderName: prev.folderName || fresh.folderName }
    })
    setProvider(id)
    test.reset()
  }

  const pending = create.isPending || update.isPending
  const error = create.error ?? update.error ?? test.error
  const ready = form.label.trim() !== '' && (provider === 'folder' ? form.folderName.trim() !== '' : editing?.from_env || (form.user.trim() !== '' && form.host.trim() !== ''))

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!ready) return
    const after = (result: { env_line?: string | null }) => {
      if (result.env_line) setEnvLine(result.env_line)
      else onDone()
    }
    if (!editing) {
      create.mutate(bodyOf(provider, form), { onSuccess: after })
      return
    }
    const body = editing.from_env
      ? {
          label: form.label.trim(),
          read_replies: form.readReplies,
          // Solo si cambian: si no, la cuenta de .env sigue con la carpeta de su configuración.
          ...(form.repliesFolders.join('\n') !== editing.replies_folders.join('\n') ? { replies_folders: form.repliesFolders } : {}),
          ...(form.password ? { password: form.password } : {}),
        }
      : editing.kind === 'folder'
        ? { label: form.label.trim(), folder: form.folderName.trim() }
        : (({ kind: _kind, password, ...rest }) => ({ ...rest, ...(password ? { password } : {}) }))(bodyOf('imap', form))
    update.mutate({ sourceId: editing.id, ...body }, { onSuccess: after })
  }

  const labelField = (
    <Field id="mailbox-label" label={t('fields.label')} hint={t('fields.labelHint')}>
      <Input id="mailbox-label" value={form.label} onChange={(e) => set({ label: e.target.value })} />
    </Field>
  )
  const folderFields = (
    <Field
      id="mailbox-folder-name"
      label={t('fields.folderName')}
      hint={<InlineCode text={t('fields.folderNameHint', { path: `\`data/inbox/${form.folderName.trim() || '…'}/\`` })} />}
    >
      <Input id="mailbox-folder-name" value={form.folderName} onChange={(e) => set({ folderName: e.target.value })} />
    </Field>
  )

  let body: ReactNode
  if (editing) {
    body = (
      <div className="grid gap-3">
        {labelField}
        {editing.kind === 'folder' ? folderFields : <ImapFields provider="imap" form={form} set={set} editing={editing} />}
      </div>
    )
  } else {
    body = (
      <Tabs value={provider} onValueChange={choose} className="gap-3">
        <TabsList aria-label={t('dialog.provider')} className="h-auto flex-wrap justify-start">
          {PROVIDER_IDS.map((id) => (
            <TabsTrigger key={id} value={id}>
              {t(`providers.${id}.name`)}
            </TabsTrigger>
          ))}
        </TabsList>
        {PROVIDER_IDS.map((id) => (
          <TabsContent key={id} value={id} className="grid gap-3">
            {id === 'outlook' ? (
              <OutlookGuide onChoose={choose}>
                {labelField}
                <ImapFields provider={id} form={form} set={set} />
              </OutlookGuide>
            ) : (
              <>
                <ProviderGuide provider={id} />
                {labelField}
                {id === 'folder' ? folderFields : <ImapFields provider={id} form={form} set={set} />}
              </>
            )}
          </TabsContent>
        ))}
      </Tabs>
    )
  }

  return (
    <form onSubmit={submit} className="grid gap-4">
      <DialogHeader>
        <DialogTitle>{editing ? t('dialog.editTitle', { name: editing.label }) : t('dialog.addTitle')}</DialogTitle>
        <DialogDescription>
          {list && !list.can_store_passwords
            ? t('dialog.descriptionDocker')
            : list && !list.keyring
              ? t('dialog.descriptionFile')
              : t('dialog.description')}
        </DialogDescription>
      </DialogHeader>
      {body}
      {test.data && <TestOutcome result={test.data} />}
      {envLine && (
        <div role="status" className="grid gap-1.5 rounded-lg border border-warning-border bg-warning p-3 text-sm text-warning-foreground">
          <p>{t('dialog.envLine')}</p>
          <Reveal label={t('technicalDetails', { ns: 'common' })} className="text-xs">
            <InlineCode text={t('dialog.envLineName', { line: `\`${envLine.replace(/=.*$/, '')}\`` })} />
          </Reveal>
        </div>
      )}
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {errorMessage(error)}
        </p>
      )}
      <DialogFooter className="gap-2">
        <Button type="button" variant="outline" onClick={onDone}>
          {t('dialog.cancel')}
        </Button>
        {!editing && provider !== 'folder' && (
          <Button type="button" variant="outline" disabled={!ready || test.isPending} onClick={() => test.mutate(bodyOf(provider, form))}>
            {test.isPending ? t('dialog.testing') : t('dialog.test')}
          </Button>
        )}
        {!envLine && (
          <Button type="submit" disabled={!ready || pending}>
            {pending ? t('dialog.saving') : t('dialog.save')}
          </Button>
        )}
      </DialogFooter>
    </form>
  )
}

/** Outlook: los dos caminos que funcionan y, plegado, IMAP como último recurso. */
function OutlookGuide({ onChoose, children }: { onChoose: (id: ProviderId) => void; children: ReactNode }) {
  const { t } = useTranslation('mailboxes')
  const links = PROVIDERS.outlook.links
  return (
    <div className="grid gap-3 text-sm">
      <p>{t('providers.outlook.intro')}</p>
      <div className="grid gap-2 sm:grid-cols-2">
        <div className="space-y-2 rounded-lg border p-3">
          <p className="font-medium">{t('providers.outlook.forwardTitle')}</p>
          <p className="text-muted-foreground">{t('providers.outlook.forwardBody')}</p>
          <Button type="button" variant="outline" size="xs" onClick={() => onChoose('gmail')}>
            {t('providers.outlook.forwardButton')}
          </Button>
        </div>
        <div className="space-y-2 rounded-lg border p-3">
          <p className="font-medium">{t('providers.outlook.exportTitle')}</p>
          <p className="text-muted-foreground">{t('providers.outlook.exportBody')}</p>
          <Button type="button" variant="outline" size="xs" onClick={() => onChoose('folder')}>
            {t('providers.outlook.exportButton')}
          </Button>
        </div>
      </div>
      <p className="flex flex-wrap gap-x-3 gap-y-1 text-xs">
        {links.map(([key, url]) => (
          <a key={key} href={url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 underline underline-offset-2">
            {t(key)}
            <ArrowSquareOutIcon className="size-3" aria-hidden />
          </a>
        ))}
        <a href={PROVIDERS.outlook.guide} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 underline underline-offset-2">
          {t('dialog.guide')}
          <ArrowSquareOutIcon className="size-3" aria-hidden />
        </a>
      </p>
      <details className="rounded-lg border px-3 py-2">
        <summary className="cursor-pointer font-medium">{t('providers.outlook.imapTitle')}</summary>
        <div className="mt-3 grid gap-3">
          <p className="text-muted-foreground">{t('providers.outlook.imapBody')}</p>
          {children}
        </div>
      </details>
    </div>
  )
}

export type MailboxDialogState = { mode: 'add'; provider?: ProviderId } | { mode: 'edit'; source: MailSourceView } | null

/** Diálogo para añadir (con pestañas por proveedor) o editar un buzón. */
export function MailboxDialog({ state, onClose }: { state: MailboxDialogState; onClose: () => void }) {
  return (
    <Dialog open={state !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        {state && (
          <MailboxForm
            key={state.mode === 'edit' ? `edit-${state.source.id}` : 'add'}
            editing={state.mode === 'edit' ? state.source : undefined}
            initialProvider={state.mode === 'add' ? (state.provider ?? 'gmail') : 'imap'}
            onDone={onClose}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}
