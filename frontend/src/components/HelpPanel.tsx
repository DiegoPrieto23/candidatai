import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router'
import { useTranslation } from 'react-i18next'
import { ArrowRightIcon, CaretDownIcon, MagnifyingGlassIcon, QuestionIcon, SparkleIcon, XIcon } from '@phosphor-icons/react'
import { AssistantTab } from '@/components/AssistantTab'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Hint } from '@/components/Hint'
import { Kbd } from '@/components/Kbd'
import { SafeTrans } from '@/components/SafeTrans'
import {
  buildIndex,
  GUIDE_SCREENS,
  HELP_GROUPS,
  HELP_SCREENS,
  HELP_TOPICS,
  loadGuide,
  snippet,
  type GuideSection,
  type Searchable,
} from '@/lib/helpSearch'
import { isTyping } from '@/lib/keyboard'
import { cn } from '@/lib/utils'

interface Question extends Searchable {
  id: string
  group: string
  screen: string | null
}

/** Con un diálogo o un menú abierto, las teclas son suyas: ni `?` abre la ayuda ni Esc la cierra. */
function overlayOpen(): boolean {
  return (
    document.querySelector(
      '[role="dialog"]:not([data-help-panel]), [role="alertdialog"], [role="menu"], [role="listbox"]',
    ) !== null
  )
}

function ScreenLink({ screen, onGo }: { screen: string | null; onGo: () => void }) {
  const { t } = useTranslation('help')
  const to = screen ? HELP_SCREENS[screen] : undefined
  if (!screen || !to) return null
  return (
    <Link
      to={to}
      onClick={onGo}
      className="mt-2 inline-flex items-center gap-1 rounded-sm text-sm font-medium text-primary underline-offset-4 outline-none hover:underline focus-visible:ring-[3px] focus-visible:ring-ring/50"
    >
      {t('goTo', { screen: t(`screens.${screen}` as never) })}
      <ArrowRightIcon className="size-3.5" weight="bold" aria-hidden />
    </Link>
  )
}

/** Una pregunta o un apartado de la guía: el título despliega su respuesta. */
function Entry({
  title,
  preview,
  open,
  onToggle,
  children,
}: {
  title: string
  preview?: string
  open: boolean
  onToggle: () => void
  children: React.ReactNode
}) {
  const id = useId()
  return (
    <li className="border-b last:border-b-0">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={id}
        onClick={onToggle}
        className="flex w-full items-start gap-2 rounded-sm py-2.5 text-left text-sm outline-none hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50"
      >
        <span className="min-w-0 flex-1">
          <span className="block font-medium text-pretty">{title}</span>
          {preview && !open && <span className="mt-0.5 line-clamp-2 block text-xs text-muted-foreground">{preview}</span>}
        </span>
        <CaretDownIcon
          className={cn('mt-0.5 size-4 shrink-0 text-muted-foreground transition-transform', open && 'rotate-180')}
          weight="bold"
          aria-hidden
        />
      </button>
      <div id={id} hidden={!open} className="pb-3 text-sm text-pretty text-muted-foreground">
        {open && children}
      </div>
    </li>
  )
}

function GuideBody({ section }: { section: GuideSection }) {
  return (
    <div className="grid gap-2">
      {section.blocks.map((block, index) =>
        block.kind === 'code' ? (
          <pre key={index} className="overflow-x-auto rounded-md bg-muted p-2 font-mono text-xs text-foreground">
            {block.text}
          </pre>
        ) : block.kind === 'item' ? (
          <p key={index} className="border-l-2 pl-2.5">
            {block.text}
          </p>
        ) : (
          <p key={index}>{block.text}</p>
        ),
      )}
    </div>
  )
}

type Tab = 'help' | 'assistant'
// La pestaña del agente, la primera: es lo que abre el botón principal de la esquina.
const TABS: Tab[] = ['assistant', 'help']

function Panel({ tab, setTab, onClose }: { tab: Tab; setTab: (tab: Tab) => void; onClose: () => void }) {
  const { t, i18n } = useTranslation('help')
  const [query, setQuery] = useState('')
  const [expanded, setExpanded] = useState<string | null>(null)
  const [guide, setGuide] = useState<GuideSection[] | null>(null)
  const input = useRef<HTMLInputElement>(null)
  const language = i18n.language

  useEffect(() => {
    if (tab === 'help') input.current?.focus()
  }, [tab])

  useEffect(() => {
    let current = true
    setGuide(null)
    loadGuide(language).then(
      (sections) => current && setGuide(sections),
      () => current && setGuide([]), // sin la guía, quedan las preguntas frecuentes
    )
    return () => {
      current = false
    }
  }, [language])

  const questions = useMemo<Question[]>(
    () =>
      HELP_TOPICS.map((topic) => ({
        ...topic,
        title: t(`faq.${topic.id}.q` as never),
        body: t(`faq.${topic.id}.a` as never),
        keywords: t(`faq.${topic.id}.keywords` as never),
      })),
    [t],
  )
  const faqIndex = useMemo(() => buildIndex(questions), [questions])
  const guideIndex = useMemo(() => buildIndex(guide ?? []), [guide])

  const searching = query.trim().length > 1
  const faqFound = searching ? faqIndex.search(query) : questions
  const guideFound = searching ? guideIndex.search(query).slice(0, 6) : []
  const toggle = (id: string) => setExpanded((now) => (now === id ? null : id))

  const question = (item: Question) => (
    <Entry key={item.id} title={item.title} open={expanded === item.id} onToggle={() => toggle(item.id)}>
      <p>{item.body}</p>
      <ScreenLink screen={item.screen} onGo={onClose} />
    </Entry>
  )

  const title = tab === 'assistant' ? t('assistantTitle') : t('title')
  const TitleIcon = tab === 'assistant' ? SparkleIcon : QuestionIcon

  return (
    <section
      role="dialog"
      aria-label={title}
      data-help-panel
      className={cn(
        'pointer-events-auto flex max-w-[calc(100vw-2rem)] flex-col rounded-xl border bg-card text-card-foreground animate-in fade-in slide-in-from-bottom-1 duration-200',
        // El asistente, como un chat: más ancho, de alto fijo (la caja abajo) y con borde, sombra y
        // cabecera propios para que no se confunda con la página.
        tab === 'assistant'
          ? 'h-[min(36rem,calc(100dvh-6rem))] w-[28rem] overflow-hidden border-primary/30 shadow-2xl dark:border-primary/40'
          : 'max-h-[min(34rem,calc(100dvh-6rem))] w-96 shadow-lg',
      )}
    >
      <header
        className={cn('flex items-center gap-2 border-b px-4 py-2.5', tab === 'assistant' && 'bg-primary/10 dark:bg-primary/15')}
      >
        <TitleIcon className="size-4 text-primary" weight={tab === 'assistant' ? 'fill' : 'bold'} aria-hidden />
        <h2 className="flex-1 text-sm font-semibold">{title}</h2>
        <Button variant="ghost" size="icon" className="size-7" aria-label={t('close')} onClick={onClose}>
          <XIcon weight="bold" aria-hidden />
        </Button>
      </header>
      <div
        role="tablist"
        aria-label={t('tabs.label')}
        className={cn('flex gap-1 border-b px-3 pt-1.5', tab === 'assistant' && 'bg-primary/10 dark:bg-primary/15')}
      >
        {TABS.map((name) => (
          <button
            key={name}
            type="button"
            role="tab"
            id={`help-tab-${name}`}
            aria-selected={tab === name}
            aria-controls="help-tabpanel"
            tabIndex={tab === name ? 0 : -1}
            onClick={() => setTab(name)}
            onKeyDown={(e) => {
              if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return
              e.preventDefault()
              const other = name === 'help' ? 'assistant' : 'help'
              setTab(other)
              document.getElementById(`help-tab-${other}`)?.focus()
            }}
            className={cn(
              '-mb-px rounded-t-sm border-b-2 px-2 py-1.5 text-sm outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50',
              tab === name
                ? 'border-primary font-medium text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground',
            )}
          >
            {t(`tabs.${name}`)}
          </button>
        ))}
      </div>
      <div
        role="tabpanel"
        id="help-tabpanel"
        aria-labelledby={`help-tab-${tab}`}
        className="flex min-h-0 flex-1 flex-col"
      >
      {tab === 'assistant' && <AssistantTab onGo={onClose} />}
      {tab === 'help' && (
      <>
      <div className="relative border-b px-4 py-3">
        <MagnifyingGlassIcon
          className="pointer-events-none absolute top-1/2 left-6.5 size-4 -translate-y-1/2 text-muted-foreground"
          weight="bold"
          aria-hidden
        />
        <Input
          ref={input}
          type="search"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            setExpanded(null)
          }}
          aria-label={t('searchLabel')}
          placeholder={t('searchPlaceholder')}
          className="pl-8"
        />
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-2">
        <p role="status" className="sr-only">
          {searching && t('results', { count: faqFound.length + guideFound.length })}
        </p>
        {!searching &&
          HELP_GROUPS.map((group) => (
            <section key={group} aria-label={t(`groups.${group}` as never)} className="py-1.5">
              <h3 className="pt-1 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
                {t(`groups.${group}` as never)}
              </h3>
              <ul>{questions.filter((item) => item.group === group).map(question)}</ul>
            </section>
          ))}
        {searching && faqFound.length > 0 && (
          <section aria-label={t('faqHeading')} className="py-1.5">
            <h3 className="pt-1 text-xs font-semibold tracking-wide text-muted-foreground uppercase">{t('faqHeading')}</h3>
            <ul>{faqFound.map(question)}</ul>
          </section>
        )}
        {searching && guideFound.length > 0 && (
          <section aria-label={t('guideHeading')} className="py-1.5">
            <h3 className="pt-1 text-xs font-semibold tracking-wide text-muted-foreground uppercase">{t('guideHeading')}</h3>
            <ul>
              {guideFound.map((section) => (
                <Entry
                  key={section.id}
                  title={section.title}
                  preview={snippet(section, query)}
                  open={expanded === section.id}
                  onToggle={() => toggle(section.id)}
                >
                  <GuideBody section={section} />
                  <ScreenLink screen={GUIDE_SCREENS[section.number] ?? null} onGo={onClose} />
                </Entry>
              ))}
            </ul>
          </section>
        )}
        {searching && guide === null && <p className="py-2 text-xs text-muted-foreground">{t('guideLoading')}</p>}
        {searching && guide !== null && faqFound.length + guideFound.length === 0 && (
          <p className="py-4 text-sm text-pretty text-muted-foreground">{t('none', { query: query.trim() })}</p>
        )}
      </div>
      </>
      )}
      </div>
      {/* El atajo `?` abre la ayuda: en la pestaña del agente no viene a cuento. */}
      {tab === 'help' && (
        <footer className="border-t px-4 py-2 text-xs text-muted-foreground">
          <SafeTrans t={t} i18nKey="shortcut" components={{ kbd: <Kbd>{null}</Kbd> }} />
        </footer>
      )}
    </section>
  )
}

/**
 * Abajo a la derecha, bajo los avisos flotantes, dos botones que abren el mismo panel: uno con
 * rótulo, «Asistente» (`AssistantTab`), para que se vea que ahí hay un asistente; y el
 * `?`, el buscador sobre las preguntas frecuentes y la guía de uso (sin red y sin agente). La tecla
 * `?` abre la ayuda y `Esc` cierra el panel, devolviendo el foco al botón que lo abrió.
 */
export function HelpPanel() {
  const { t } = useTranslation('help')
  const [open, setOpen] = useState(false)
  const [tab, setTab] = useState<Tab>('help')
  const helpButton = useRef<HTMLButtonElement>(null)
  const assistantButton = useRef<HTMLButtonElement>(null)
  const opener = useRef<HTMLButtonElement | null>(null)
  const wrapper = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== '?' || e.ctrlKey || e.metaKey || e.altKey || isTyping(e.target) || overlayOpen()) return
      e.preventDefault()
      opener.current = helpButton.current
      setTab('help')
      setOpen(true)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const button = () => opener.current ?? helpButton.current

  const close = () => {
    setOpen(false)
    button()?.focus()
  }

  /** Cada botón abre su pestaña; si ya está a la vista, cierra el panel. */
  const toggle = (which: Tab) => {
    opener.current = which === 'assistant' ? assistantButton.current : helpButton.current
    if (open && tab === which) {
      setOpen(false)
      return
    }
    setTab(which)
    setOpen(true)
  }

  // Esc la cierra desde cualquier sitio de la página (el panel no es modal). El foco vuelve al
  // botón solo si estaba dentro: si estabas en la página, se queda donde lo tenías.
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      // Sin mirar `defaultPrevented`: el globo de ayuda del botón también atiende Esc y lo marca.
      if (e.key !== 'Escape' || overlayOpen()) return
      const inside = wrapper.current?.contains(document.activeElement) ?? false
      setOpen(false)
      if (inside) button()?.focus()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  return (
    <div ref={wrapper} className="flex flex-col items-end gap-2">
      {open && <Panel tab={tab} setTab={setTab} onClose={close} />}
      <div className="flex items-center gap-2">
        <Hint text={t('launcherHint')} side="top">
          <Button
            ref={assistantButton}
            aria-expanded={open && tab === 'assistant'}
            onClick={() => toggle('assistant')}
            className="pointer-events-auto h-10 gap-2 rounded-full pr-4 pl-3.5 shadow-md active:translate-y-px"
          >
            <SparkleIcon className="size-5" weight="fill" aria-hidden />
            {t('launcher')}
          </Button>
        </Hint>
        <Hint text={t('buttonHint')} side="top">
          <Button
            ref={helpButton}
            variant="outline"
            size="icon"
            aria-label={t('button')}
            aria-expanded={open && tab === 'help'}
            aria-keyshortcuts="?"
            onClick={() => toggle('help')}
            className="pointer-events-auto size-10 rounded-full bg-card shadow-md"
          >
            <QuestionIcon className="size-5" weight="bold" aria-hidden />
          </Button>
        </Hint>
      </div>
    </div>
  )
}
