/**
 * Cómo se usa la app, de principio a fin: quién hace qué (tú, tu agente y la app), el recorrido en
 * cinco pasos con un enlace a cada pantalla y las guías. A diferencia de «Primeros pasos» en Inicio,
 * sigue disponible cuando ya has empezado. No pide datos: es igual con la app vacía o en uso.
 */
import { Link } from 'react-router'
import { useTranslation } from 'react-i18next'
import { ArrowRightIcon, ArrowSquareOutIcon } from '@phosphor-icons/react'
import { i18n, SOURCE_LANGUAGE } from '@/lib/i18n'

type Actor = 'you' | 'agent' | 'app'

const ACTORS: Actor[] = ['you', 'agent', 'app']

// Las etiquetas de los enlaces son las del menú: si cambia un nombre, aquí cambia con él.
const STEPS = [
  {
    key: 'prepare',
    actors: ['you', 'agent'],
    links: [
      { to: '/perfil', label: 'entries.profile' },
      { to: '/fuentes', label: 'entries.sources' },
      { to: '/agente', label: 'entries.agent' },
    ],
  },
  {
    key: 'collect',
    actors: ['you', 'agent', 'app'],
    links: [
      { to: '/nueva', label: 'header.newJob' },
      { to: '/alertas', label: 'entries.alerts' },
      { to: '/bandeja', label: 'entries.inbox' },
    ],
  },
  {
    key: 'decide',
    actors: ['agent', 'app', 'you'],
    links: [
      { to: '/', label: 'entries.home' },
      { to: '/por-revisar', label: 'entries.triage' },
    ],
  },
  {
    key: 'apply',
    actors: ['agent', 'app', 'you'],
    links: [
      { to: '/bandeja?stage=approved', label: 'entries.inbox' },
      { to: '/plantillas', label: 'entries.templates' },
    ],
  },
  {
    key: 'follow',
    actors: ['you', 'agent'],
    links: [
      { to: '/procesos', label: 'entries.processes' },
      { to: '/respuestas', label: 'entries.replies' },
      { to: '/calendario', label: 'entries.calendar' },
      { to: '/embudo', label: 'entries.funnel' },
      { to: '/skills', label: 'entries.skills' },
    ],
  },
] as const satisfies readonly {
  key: string
  actors: readonly Actor[]
  links: readonly { to: string; label: string }[]
}[]

const REPO_DOCS = 'https://github.com/DiegoPrieto23/candidatai/blob/main/docs'

const GUIDES = [
  { key: 'start', es: 'EMPEZAR.md', en: 'START_HERE.md' },
  { key: 'guide', es: 'GUIA.md', en: 'GUIDE.md' },
  { key: 'features', es: 'FUNCIONALIDADES.md', en: 'FEATURES.md' },
] as const

export function HowItWorksPage() {
  const { t } = useTranslation('howItWorks')
  const { t: tNav } = useTranslation('nav')
  const { t: tHome } = useTranslation('home')
  const { t: tAgent } = useTranslation('agent')
  // Los nombres de botones y páginas, los de verdad: el texto no se queda atrás si cambian.
  const names = {
    newJob: tNav('header.newJob'),
    home: tNav('entries.home'),
    inbox: tNav('entries.inbox'),
    triage: tNav('entries.triage'),
    processes: tNav('entries.processes'),
    replies: tNav('entries.replies'),
    calendar: tNav('entries.calendar'),
    funnel: tNav('entries.funnel'),
    skills: tNav('entries.skills'),
    searchJobs: tHome('today.searchJobs'),
    processJobs: tHome('today.processJobs'),
    assessFit: tHome('today.assessFit'),
    generateCv: tAgent('actions.generate-cv'),
  }
  const docsLanguage = i18n.language === SOURCE_LANGUAGE ? 'es' : 'en'

  return (
    <div className="max-w-3xl space-y-10 animate-in fade-in duration-300">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">{t('title')}</h1>
        <p className="mt-2 max-w-prose text-sm text-muted-foreground">{t('intro')}</p>
      </header>

      <section aria-labelledby="how-who">
        <h2 id="how-who" className="text-lg font-semibold tracking-tight">
          {t('who.title')}
        </h2>
        <ul className="mt-3 grid gap-3 sm:grid-cols-3">
          {ACTORS.map((actor) => (
            <li key={actor} className="rounded-xl border bg-card p-4">
              <h3 className="text-sm font-medium">{t(`who.${actor}.name`)}</h3>
              <p className="mt-1 text-sm text-muted-foreground">{t(`who.${actor}.body`)}</p>
            </li>
          ))}
        </ul>
        <p className="mt-3 text-sm font-medium">{t('who.promise')}</p>
      </section>

      <section aria-labelledby="how-steps">
        <h2 id="how-steps" className="text-lg font-semibold tracking-tight">
          {t('steps.title')}
        </h2>
        <ol className="mt-4 grid gap-6">
          {STEPS.map((step, i) => (
            <li key={step.key} className="flex gap-3">
              <span
                aria-hidden
                className="grid size-6 shrink-0 place-items-center rounded-full border bg-background text-xs font-semibold"
              >
                {i + 1}
              </span>
              <div className="min-w-0 flex-1 pt-0.5">
                <h3 className="font-medium">{t(`steps.${step.key}.title`)}</h3>
                <p className="mt-1.5 flex flex-wrap gap-1.5">
                  {step.actors.map((actor) => (
                    <span
                      key={actor}
                      className="rounded-full bg-foreground/[0.07] px-2 py-0.5 text-xs text-muted-foreground"
                    >
                      {t(`who.${actor}.name`)}
                    </span>
                  ))}
                </p>
                <p className="mt-2 text-sm text-muted-foreground">{t(`steps.${step.key}.body`, names)}</p>
                <p className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
                  {step.links.map((link) => (
                    <Link
                      key={link.to}
                      to={link.to}
                      className="inline-flex items-center gap-1 text-sm text-primary underline decoration-primary/30 underline-offset-4 hover:decoration-primary"
                    >
                      {tNav(link.label)}
                      <ArrowRightIcon className="size-3" aria-hidden />
                    </Link>
                  ))}
                </p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section aria-labelledby="how-guides">
        <h2 id="how-guides" className="text-lg font-semibold tracking-tight">
          {t('guides.title')}
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">{t('guides.opensOnGithub')}</p>
        <ul className="mt-3 grid gap-3 sm:grid-cols-3">
          {GUIDES.map((guide) => (
            <li key={guide.key}>
              <a
                href={`${REPO_DOCS}/${guide[docsLanguage]}`}
                target="_blank"
                rel="noreferrer"
                className="block h-full rounded-xl border bg-card p-4 transition-colors hover:bg-foreground/[0.03] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <span className="inline-flex items-center gap-1 text-sm font-medium text-primary">
                  {t(`guides.${guide.key}.name`)}
                  <ArrowSquareOutIcon className="size-3.5" aria-hidden />
                </span>
                <span className="mt-1 block text-sm text-muted-foreground">{t(`guides.${guide.key}.body`)}</span>
              </a>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
