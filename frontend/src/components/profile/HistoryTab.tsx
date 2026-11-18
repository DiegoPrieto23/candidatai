/**
 * «Mi perfil › Historial»: una fila por versión (cuándo, de dónde viene y qué bloques cambió) que se
 * despliega con los cambios en texto normal, «Antes → Ahora», agrupados con los títulos del editor.
 * Cada versión se puede restaurar (como una versión nueva, que se deshace) y el diff de texto de
 * siempre queda plegado al final, para quien lo quiera.
 */
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ArrowCounterClockwiseIcon, ArrowsDownUpIcon, CaretRightIcon, MinusIcon, PencilSimpleIcon, PlusIcon } from '@phosphor-icons/react'
import { useProfileVersionChanges, useProfileVersions, useRestoreProfileVersion, useUndoProfile } from '@/api/queries'
import type { Schemas } from '@/api/client'
import { Hint } from '@/components/Hint'
import { ErrorState } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Skeleton } from '@/components/ui/skeleton'
import { codeName } from '@/lib/codes'
import { errorMessage } from '@/lib/errors'
import { blockTitle, byBlock, fieldLabel, valueText, versionSummary, versionWhen, type FieldChange, type ItemChange, type Say } from '@/lib/historyText'
import { intlLocale } from '@/lib/i18n'
import { cn } from '@/lib/utils'
import { useProfileState } from './editor'

type VersionEntry = Schemas['VersionEntry']

/** Más elementos que estos en un bloque, y el resto se pliega. */
const SHOWN = 5

const ADDED = 'bg-emerald-50 text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-300'
const REMOVED = 'bg-red-50 text-red-800 line-through decoration-1 dark:bg-red-950/50 dark:text-red-300'

function useSay(): { say: Say; locale: string } {
  const { t } = useTranslation('profileEditor')
  // Las claves se arman en `historyText` (`history.fields.${key}`): sin el tipo estricto de i18next.
  const translate = t as unknown as (key: string, values?: Record<string, unknown>) => string
  return { say: (key, values) => String(translate(key, values)), locale: intlLocale() }
}

function KindTag({ kind }: { kind: ItemChange['kind'] }) {
  const { t } = useTranslation('profileEditor', { keyPrefix: 'history.kinds' })
  const Icon = { added: PlusIcon, removed: MinusIcon, changed: PencilSimpleIcon, moved: ArrowsDownUpIcon }[kind]
  const tone = kind === 'added' ? ADDED : kind === 'removed' ? 'bg-red-50 text-red-800 dark:bg-red-950/50 dark:text-red-300' : 'bg-muted text-muted-foreground'
  return (
    <span className={cn('inline-flex items-center gap-1 rounded px-1.5 text-[11px] font-semibold', tone)}>
      <Icon className="size-3" weight="bold" aria-hidden />
      {t(kind)}
    </span>
  )
}

function Before({ children }: { children: string }) {
  const { t } = useTranslation('profileEditor', { keyPrefix: 'history' })
  return (
    <del className="text-red-700 decoration-1 dark:text-red-400">
      <span className="sr-only">{t('before')} </span>
      {children}
    </del>
  )
}

function After({ children }: { children: string }) {
  const { t } = useTranslation('profileEditor', { keyPrefix: 'history' })
  return (
    <ins className="text-emerald-700 no-underline dark:text-emerald-400">
      <span className="sr-only">{t('after')} </span>
      {children}
    </ins>
  )
}

function Chip({ text, added }: { text: string; added: boolean }) {
  const { t } = useTranslation('profileEditor', { keyPrefix: 'history' })
  const Icon = added ? PlusIcon : MinusIcon
  const Tag = added ? 'ins' : 'del'
  return (
    <Tag className={cn('mr-1 mb-1 inline-flex items-center gap-1 rounded px-1.5 text-[12.5px] no-underline', added ? ADDED : REMOVED)}>
      <Icon className="size-3" weight="bold" aria-hidden />
      <span className="sr-only">{t(added ? 'kinds.added' : 'kinds.removed')}: </span>
      {text}
    </Tag>
  )
}

function FieldRow({ field }: { field: FieldChange }) {
  const { say, locale } = useSay()
  const label = fieldLabel(field.path, say, (code) => codeName('region', code, locale))
  const text = (value: unknown) => valueText(field.path, value, say, locale)
  const chips = (field.added?.length ?? 0) + (field.removed?.length ?? 0) > 0
  const hasBefore = field.before !== null && field.before !== undefined
  const hasAfter = field.after !== null && field.after !== undefined
  return (
    <div className="grid gap-x-3 text-sm sm:grid-cols-[11rem_1fr]">
      <span className="text-muted-foreground">{label}</span>
      <span className="min-w-0 break-words">
        {chips ? (
          <>
            {field.added?.map((item) => <Chip key={`+${item}`} text={text(item)} added />)}
            {field.removed?.map((item) => <Chip key={`-${item}`} text={text(item)} added={false} />)}
          </>
        ) : (
          <>
            {hasBefore && <Before>{text(field.before)}</Before>}
            {hasBefore && hasAfter && (
              <span className="mx-1.5 text-muted-foreground" aria-hidden>
                →
              </span>
            )}
            {hasAfter && <After>{text(field.after)}</After>}
          </>
        )}
      </span>
    </div>
  )
}

function ChangeCard({ change }: { change: ItemChange }) {
  const { t } = useTranslation('profileEditor', { keyPrefix: 'history' })
  const title = change.within
    ? t(`within.${change.within}`, { parent: change.parent ?? '', defaultValue: t('withinOther', { parent: change.parent ?? '' }) })
    : change.label
  return (
    <div className="grid gap-1.5 rounded-lg border bg-card px-3 py-2">
      {(title || change.kind !== 'changed') && (
        <div className="flex flex-wrap items-baseline gap-2">
          {title && <span className="font-medium">{title}</span>}
          {/* Los logros se nombran por su experiencia: su texto va como etiqueta, si cabe. */}
          {change.within && change.label && change.kind === 'moved' && <span className="text-sm text-muted-foreground">{change.label}</span>}
          <KindTag kind={change.kind} />
        </div>
      )}
      {change.hidden && <p className="text-sm text-muted-foreground">{t('privateHidden')}</p>}
      {change.kind === 'moved' && change.position && (
        <div className="grid gap-x-3 text-sm sm:grid-cols-[11rem_1fr]">
          <span className="text-muted-foreground">{t('position')}</span>
          <span>
            <Before>{t('ordinal', { n: change.position[0] })}</Before>
            <span className="mx-1.5 text-muted-foreground" aria-hidden>
              →
            </span>
            <After>{t('ordinal', { n: change.position[1] })}</After>
          </span>
        </div>
      )}
      {change.fields?.map((field, i) => <FieldRow key={i} field={field} />)}
    </div>
  )
}

function BlockGroup({ title, changes }: { title: string; changes: ItemChange[] }) {
  const { t } = useTranslation('profileEditor', { keyPrefix: 'history' })
  const [all, setAll] = useState(false)
  const shown = all ? changes : changes.slice(0, SHOWN)
  const rest = changes.length - SHOWN
  return (
    <section aria-label={title} className="grid gap-1.5">
      <h3 className="text-sm font-semibold">{title}</h3>
      {shown.map((change, i) => (
        <ChangeCard key={i} change={change} />
      ))}
      {rest > 0 && (
        <button type="button" className="justify-self-start text-sm text-primary hover:underline" onClick={() => setAll((v) => !v)}>
          {all ? t('less') : t('more', { count: rest })}
        </button>
      )}
    </section>
  )
}

function VersionDetail({ entry, when, onRestore, blocked }: { entry: VersionEntry; when: string; onRestore: (blocks: string[]) => void; blocked: boolean }) {
  const { t } = useTranslation('profileEditor', { keyPrefix: 'history' })
  const { say } = useSay()
  const detail = useProfileVersionChanges(entry.id, true)
  const [technical, setTechnical] = useState(false)
  if (detail.isPending) return <Skeleton className="h-24" />
  if (detail.isError) return <ErrorState error={detail.error} onRetry={() => detail.refetch()} />
  const data = detail.data
  const restoreLabel = data.current ? t('isCurrent') : !data.restorable ? (data.restore_blocks.length ? t('notRestorable') : t('sameAsCurrent')) : null
  return (
    <div className="grid gap-4">
      {byBlock(data.changes).map(([block, changes]) => (
        <BlockGroup key={block} title={blockTitle(block, say)} changes={changes} />
      ))}
      <div className="flex flex-wrap items-center justify-between gap-2 border-t pt-3">
        {data.technical_diff ? (
          <Button type="button" size="sm" variant="ghost" aria-expanded={technical} onClick={() => setTechnical((v) => !v)}>
            <CaretRightIcon className={cn('transition-transform', technical && 'rotate-90')} aria-hidden />
            {technical ? t('hideTechnical') : t('technical')}
          </Button>
        ) : (
          <span />
        )}
        {restoreLabel ? (
          <span className="text-xs text-muted-foreground">{restoreLabel}</span>
        ) : (
          <Button type="button" size="sm" variant="outline" disabled={blocked} aria-label={`${t('restore')} (${when})`} onClick={() => onRestore(data.restore_blocks)}>
            {t('restore')}
          </Button>
        )}
      </div>
      {technical && (
        <pre aria-label={t('technicalLabel')} className="max-h-96 overflow-auto rounded-md bg-muted/50 p-3 font-mono text-xs leading-relaxed">
          {data.technical_diff}
        </pre>
      )}
    </div>
  )
}

function VersionRow({ entry, open, onToggle, onRestore, blocked }: { entry: VersionEntry; open: boolean; onToggle: () => void; onRestore: (entry: VersionEntry, when: string, blocks: string[]) => void; blocked: boolean }) {
  const { t } = useTranslation('profileEditor', { keyPrefix: 'history' })
  const { say, locale } = useSay()
  const when = versionWhen(entry.created_at, say, locale)
  const inline = versionWhen(entry.created_at, say, locale, { inline: true })
  const summary = versionSummary(entry, say)
  return (
    <Collapsible open={open} onOpenChange={onToggle} asChild>
      <li className={cn(open && 'bg-muted/30')}>
        <CollapsibleTrigger asChild>
          <button
            type="button"
            className="grid w-full grid-cols-[14px_1fr_auto] items-center gap-x-3 gap-y-0.5 px-4 py-2.5 text-left sm:grid-cols-[14px_9.5rem_1fr_auto]"
          >
            <CaretRightIcon className={cn('size-3.5 text-muted-foreground transition-transform', open && 'rotate-90')} weight="bold" aria-hidden />
            <span className="font-medium whitespace-nowrap">
              {when}
              {entry.current && <span className="ml-1.5 text-xs font-semibold text-primary">{t('current')}</span>}
            </span>
            <span className="col-start-2 row-start-2 truncate text-xs text-muted-foreground sm:col-start-3 sm:row-start-1" title={summary}>
              {summary}
            </span>
            {entry.origin ? (
              <span className="col-start-3 row-start-1 justify-self-end rounded-full bg-accent px-2 text-[11.5px] whitespace-nowrap text-accent-foreground sm:col-start-4">
                {t(`origin.${entry.origin}`)}
              </span>
            ) : (
              <span />
            )}
          </button>
        </CollapsibleTrigger>
        <CollapsibleContent className="px-4 pb-4 sm:pl-11">
          {open && <VersionDetail entry={entry} when={when} blocked={blocked} onRestore={(blocks) => onRestore(entry, inline, blocks)} />}
        </CollapsibleContent>
      </li>
    </Collapsible>
  )
}

function RestoreDialog({ target, onClose, onDone }: { target: { entry: VersionEntry; when: string; blocks: string[] } | null; onClose: () => void; onDone: (message: string) => void }) {
  const { t } = useTranslation('profileEditor', { keyPrefix: 'history' })
  const { say } = useSay()
  const { state } = useProfileState()
  const restore = useRestoreProfileVersion()
  const [error, setError] = useState<string | null>(null)
  const close = () => {
    setError(null)
    onClose()
  }
  return (
    <Dialog open={target !== null} onOpenChange={(open) => !open && close()}>
      <DialogContent className="sm:max-w-md">
        {target && (
          <>
            <DialogHeader>
              <DialogTitle>{t('confirmTitle', { when: target.when })}</DialogTitle>
              <DialogDescription>{t('confirmBlocks')}</DialogDescription>
            </DialogHeader>
            {target.blocks.length ? (
              <ul className="ml-5 list-disc text-sm">
                {target.blocks.map((block) => (
                  <li key={block}>{blockTitle(block as ItemChange['block'], say)}</li>
                ))}
              </ul>
            ) : (
              <p className="text-sm">{t('confirmInternal')}</p>
            )}
            {/* El historial no enseña la cifra: que no se cambie sin decirlo. */}
            {target.blocks.includes('private') && <p className="text-sm">{t('confirmPrivate')}</p>}
            <p className="text-xs text-muted-foreground">{t('confirmNote')}</p>
            {error && (
              <p role="alert" className="text-sm text-destructive">
                {error}
              </p>
            )}
            <DialogFooter>
              <Button type="button" variant="ghost" onClick={close}>
                {t('cancel')}
              </Button>
              <Button
                type="button"
                disabled={restore.isPending}
                onClick={() => {
                  setError(null)
                  restore.mutate(
                    { id: target.entry.id, fileHash: state.file_hash ?? null },
                    {
                      onSuccess: () => {
                        onDone(t('restored', { when: target.when }))
                        close()
                      },
                      onError: (e) => setError(errorMessage(e)),
                    },
                  )
                }}
              >
                {t('restore')}
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}

export function HistoryTab() {
  const { t } = useTranslation('profileEditor', { keyPrefix: 'history' })
  const { state, dirtyBlocks } = useProfileState()
  const dirty = dirtyBlocks.size > 0
  const versions = useProfileVersions()
  const undo = useUndoProfile()
  const [message, setMessage] = useState<string | null>(null)
  // Abiertas a mano; la actual empieza abierta (`toggled` la cierra).
  const [toggled, setToggled] = useState<ReadonlySet<number>>(new Set())
  const [target, setTarget] = useState<{ entry: VersionEntry; when: string; blocks: string[] } | null>(null)
  const entries = versions.data?.pages.flatMap((page) => page.versions) ?? []
  const isOpen = (entry: VersionEntry) => entry.current !== toggled.has(entry.id)
  const toggle = (id: number) =>
    setToggled((prev) => {
      const next = new Set(prev)
      if (!next.delete(id)) next.add(id)
      return next
    })
  return (
    <section aria-labelledby="profile-history" className="grid gap-3 rounded-xl border bg-card p-4 sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="profile-history" className="flex items-center gap-1.5 font-semibold">
          {t('title')}
          <Hint text={t('hint')} label={t('title')} />
        </h2>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-muted-foreground">{dirty ? t('saveFirst') : t('copies', { count: state.undo_available })}</span>
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={state.undo_available === 0 || undo.isPending || dirty}
            onClick={() => {
              setMessage(null)
              undo.mutate(state.file_hash ?? null, {
                onSuccess: () => setMessage(t('undone')),
                onError: (e) => setMessage(errorMessage(e)),
              })
            }}
          >
            <ArrowCounterClockwiseIcon /> {t('undo')}
          </Button>
        </div>
      </div>
      {message && (
        <p role="status" className="text-sm">
          {message}
        </p>
      )}
      {versions.isPending ? (
        <Skeleton className="h-40" />
      ) : versions.isError ? (
        <ErrorState error={versions.error} onRetry={() => versions.refetch()} />
      ) : (
        <ul aria-label={t('listLabel')} className="divide-y overflow-hidden rounded-lg border">
          {entries.map((entry) => (
            <VersionRow
              key={entry.id}
              entry={entry}
              open={isOpen(entry)}
              onToggle={() => toggle(entry.id)}
              blocked={dirty}
              onRestore={(e, when, blocks) => setTarget({ entry: e, when, blocks })}
            />
          ))}
        </ul>
      )}
      {versions.hasNextPage && (
        <Button type="button" size="sm" variant="ghost" className="justify-self-center" disabled={versions.isFetchingNextPage} onClick={() => versions.fetchNextPage()}>
          {t('older')}
        </Button>
      )}
      <RestoreDialog
        target={target}
        onClose={() => setTarget(null)}
        onDone={(text) => {
          setMessage(text)
          setToggled(new Set())
        }}
      />
    </section>
  )
}
