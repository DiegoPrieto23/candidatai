import { Fragment, type ReactNode } from 'react'
import { ArrowSquareOutIcon, BuildingsIcon, WarningIcon } from '@phosphor-icons/react'
import type { CompanyResearchContent, JobView, Stage } from '@/api/client'
import { useCompanyResearch } from '@/api/queries'
import { AgentButton } from '@/components/AgentButton'
import { OpenFolderButton } from '@/components/OpenFolderButton'
import { formatDate } from '@/lib/labels'

/** Las que admite el botón (`investigar-empresa`): ofertas abiertas ya extraídas. */
const RESEARCH_STAGES: ReadonlySet<Stage> = new Set([
  'pending_triage',
  'approved',
  'cv_ready',
  'applied',
  'in_process',
])
const OLD_DAYS = 30

const SECTIONS: { key: keyof CompanyResearchContent; label: string }[] = [
  { key: 'product', label: 'Producto' },
  { key: 'news', label: 'Noticias recientes' },
  { key: 'engineering_culture', label: 'Cultura de ingeniería' },
  { key: 'notes', label: 'Para ti' },
]

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
 * Ficha (fase 18): el dosier de la empresa que guarda tu agente con `investigar-empresa`. Sale de
 * webs públicas: se muestra como texto, con sus fuentes. La carta no lo usa (POLICIES §7).
 */
export function CompanyResearchSection({ job }: { job: JobView }) {
  const { data, isError, error } = useCompanyResearch(job.id)
  const canResearch = job.stage !== null && RESEARCH_STAGES.has(job.stage)
  const research = data?.research
  if (!research && !canResearch) return null
  const content = research?.content
  return (
    <section aria-label="Empresa" className="rounded-xl border bg-card p-5 sm:p-6">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 font-semibold">
            <BuildingsIcon className="size-[18px] text-primary" weight="duotone" />
            Empresa
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {research
              ? `Dosier del ${formatDate(research.updated_at)}${research.agent_name ? ` · de ${research.agent_name}` : ''}. Sacado de webs públicas: compruébalo en la fuente.`
              : 'Tu agente investiga la empresa en la web pública y deja aquí un dosier con fuentes.'}
          </p>
        </div>
        {canResearch && (
          <AgentButton action="investigar-empresa" jobId={job.id}>
            {research ? 'Actualizar dosier' : 'Investigar empresa'}
          </AgentButton>
        )}
      </div>
      {isError ? (
        // Sección secundaria: el fallo se dice sin `alert`, para no tapar los avisos de la ficha.
        <p className="text-sm text-muted-foreground">No se pudo cargar el dosier: {error.message}</p>
      ) : (
        research &&
        content && (
          <div className="space-y-4 text-sm">
            {research.risk_flags.length > 0 && (
              <p className="flex items-start gap-2 rounded-md border border-warning-border bg-warning px-3 py-2 text-warning-foreground">
                <WarningIcon className="mt-0.5 size-4 shrink-0" weight="fill" />
                El dosier contiene frases dirigidas a una IA (venían de alguna web). Revísalo antes de usarlo.
              </p>
            )}
            {research.age_days > OLD_DAYS && (
              <p className="text-xs text-muted-foreground">Tiene {research.age_days} días: puede estar desfasado.</p>
            )}
            <p className="leading-relaxed whitespace-pre-line">
              <Cited text={content.summary} sources={content.sources} />
            </p>
            {SECTIONS.map(({ key, label }) => {
              const text = content[key]
              if (typeof text !== 'string' || !text) return null
              return (
                <div key={key}>
                  <h3 className="mb-1 text-xs font-medium tracking-wide text-muted-foreground uppercase">{label}</h3>
                  <p className="leading-relaxed whitespace-pre-line">
                    <Cited text={text} sources={content.sources} />
                  </p>
                </div>
              )
            })}
            {content.stack && content.stack.length > 0 && (
              <div>
                <h3 className="mb-1.5 text-xs font-medium tracking-wide text-muted-foreground uppercase">Stack</h3>
                <ul className="flex flex-wrap gap-1.5" aria-label="Stack">
                  {content.stack.map((tech) => (
                    <li key={tech} className="rounded-full border px-2 py-0.5 text-xs">
                      {tech}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <div>
              <h3 className="mb-1.5 text-xs font-medium tracking-wide text-muted-foreground uppercase">Fuentes</h3>
              <ol className="list-decimal space-y-1 pl-5" aria-label="Fuentes">
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
              <OpenFolderButton folder="empresas" label="Abrir carpeta de dosieres" />
              <p className="text-xs text-muted-foreground">
                La carta no lo usa: si quieres que mencione algo, cópialo a sus indicaciones.
              </p>
            </div>
          </div>
        )
      )}
    </section>
  )
}
