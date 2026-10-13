import { Fragment, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { ArrowSquareOutIcon, BuildingsIcon, WarningIcon } from '@phosphor-icons/react'
import type { CompanyResearchContent, JobView, Stage } from '@/api/client'
import { useCompanyResearch } from '@/api/queries'
import { AgentButton } from '@/components/AgentButton'
import { OpenFolderButton } from '@/components/OpenFolderButton'
import { formatDate } from '@/lib/labels'
import { errorMessage } from '@/lib/errors'

/** Las que admite el botón (`research-company`): ofertas abiertas ya extraídas. */
const RESEARCH_STAGES: ReadonlySet<Stage> = new Set([
  'pending_triage',
  'approved',
  'cv_ready',
  'applied',
  'in_process',
])
const OLD_DAYS = 30

const SECTIONS = ['product', 'news', 'engineering_culture', 'notes'] as const satisfies readonly (keyof CompanyResearchContent)[]

function isUrl(value: string): boolean {
  return /^https?:\/\//i.test(value)
}

/** El texto con sus citas `[n]` como enlaces a la fuente. Es texto de webs: nunca HTML. */
function Cited({ text, sources }: { text: string; sources: CompanyResearchContent['sources'] }) {
  const parts = text.split(/(\[\d{1,2}\])/g)
  return (
    <>
      {parts.map((part, i): ReactNode => {
        const n = /^\[(\d{1,2})\]$/.exec(part)?.[1]
        const source = n ? sources[Number(n) - 1] : undefined
        if (!source || !isUrl(source.url)) return <Fragment key={i}>{part}</Fragment>
        return (
          <a
            key={i}
            href={source.url}
            target="_blank"
            rel="noopener noreferrer nofollow"
            title={source.title}
            className="align-super text-[0.7rem] text-primary underline-offset-2 hover:underline"
          >
            {part}
          </a>
        )
      })}
    </>
  )
}

/**
 * Ficha (fase 18): el dosier de la empresa que guarda tu agente con `research-company`. Sale de
 * webs públicas: se muestra como texto, con sus fuentes. La carta no lo usa (POLICIES §7).
 */
export function CompanyResearchSection({ job }: { job: JobView }) {
  const { t } = useTranslation('research')
  const { data, isError, error } = useCompanyResearch(job.id)
  const canResearch = job.stage !== null && RESEARCH_STAGES.has(job.stage)
  const research = data?.research
  if (!research && !canResearch) return null
  const content = research?.content
  return (
    <section aria-label={t('title')} className="rounded-xl border bg-card p-5 sm:p-6">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 font-semibold">
            <BuildingsIcon className="size-[18px] text-primary" weight="duotone" />
            {t('title')}
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {research
              ? `${t('dossier', { date: formatDate(research.updated_at) })}${research.agent_name ? t('by', { agent: research.agent_name }) : ''}${t('fromWeb')}`
              : t('intro')}
          </p>
        </div>
        {canResearch && (
          <AgentButton action="research-company" jobId={job.id}>
            {research ? t('update') : t('research')}
          </AgentButton>
        )}
      </div>
      {isError ? (
        // Sección secundaria: el fallo se dice sin `alert`, para no tapar los avisos de la ficha.
        <p className="text-sm text-muted-foreground">{t('loadFailed', { error: errorMessage(error) })}</p>
      ) : (
        research &&
        content && (
          <div className="space-y-4 text-sm">
            {research.risk_flags.length > 0 && (
              <p className="flex items-start gap-2 rounded-md border border-warning-border bg-warning px-3 py-2 text-warning-foreground">
                <WarningIcon className="mt-0.5 size-4 shrink-0" weight="fill" />
                {t('risk')}
              </p>
            )}
            {research.age_days > OLD_DAYS && (
              <p className="text-xs text-muted-foreground">{t('old', { count: research.age_days })}</p>
            )}
            <p className="leading-relaxed whitespace-pre-line">
              <Cited text={content.summary} sources={content.sources} />
            </p>
            {SECTIONS.map((key) => {
              const text = content[key]
              if (typeof text !== 'string' || !text) return null
              return (
                <div key={key}>
                  <h3 className="mb-1 text-xs font-medium tracking-wide text-muted-foreground uppercase">{t(`sections.${key}`)}</h3>
                  <p className="leading-relaxed whitespace-pre-line">
                    <Cited text={text} sources={content.sources} />
                  </p>
                </div>
              )
            })}
            {content.stack && content.stack.length > 0 && (
              <div>
                <h3 className="mb-1.5 text-xs font-medium tracking-wide text-muted-foreground uppercase">{t('stack')}</h3>
                <ul className="flex flex-wrap gap-1.5" aria-label={t('stack')}>
                  {content.stack.map((tech) => (
                    <li key={tech} className="rounded-full border px-2 py-0.5 text-xs">
                      {tech}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <div>
              <h3 className="mb-1.5 text-xs font-medium tracking-wide text-muted-foreground uppercase">{t('sources')}</h3>
              <ol className="list-decimal space-y-1 pl-5" aria-label={t('sources')}>
                {content.sources.map((source, i) => (
                  <li key={i}>
                    {isUrl(source.url) ? (
                      <a
                        href={source.url}
                        target="_blank"
                        rel="noopener noreferrer nofollow"
                        className="inline-flex items-center gap-1 underline-offset-4 hover:underline"
                      >
                        {source.title}
                        <ArrowSquareOutIcon className="size-3.5 text-muted-foreground" />
                      </a>
                    ) : (
                      source.title
                    )}
                    {source.accessed_on && (
                      <span className="text-xs text-muted-foreground"> · {formatDate(source.accessed_on)}</span>
                    )}
                  </li>
                ))}
              </ol>
            </div>
            <div className="flex flex-wrap items-center gap-3 border-t pt-3">
              <OpenFolderButton folder="empresas" label={t('openFolder')} />
              <p className="text-xs text-muted-foreground">
                {t('letterHint')}
              </p>
            </div>
          </div>
        )
      )}
    </section>
  )
}
