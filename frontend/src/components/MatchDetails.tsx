import type { ReactNode } from 'react'
import { ChatCircleDotsIcon, CheckIcon, InfoIcon, ProhibitIcon, RobotIcon } from '@phosphor-icons/react'
import type { MatchView, Schemas } from '@/api/client'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { COMPONENT_LABEL, LEVEL_LABEL, VERDICT_LABEL } from '@/lib/labels'
import { cn } from '@/lib/utils'

/** Score 0-100: número tabular con una barra fina. Por debajo del umbral, atenuado. */
export function ScoreBadge({
  score,
  threshold,
  size = 'md',
  className,
}: {
  score: number | null | undefined
  threshold?: number
  size?: 'md' | 'lg'
  className?: string
}) {
  if (score == null) {
    return <span className={cn('text-xs text-muted-foreground/70', className)}>Sin score</span>
  }
  const low = threshold != null && score < threshold
  return (
    <span
      className={cn('inline-flex flex-col items-end gap-1', className)}
      aria-label={`Score ${score} de 100${low ? ', por debajo del umbral' : ''}`}
    >
      <span
        className={cn(
          'tabular leading-none font-semibold',
          size === 'lg' ? 'text-4xl tracking-tight' : 'text-base',
          low ? 'text-muted-foreground' : 'text-foreground',
        )}
      >
        {score}
      </span>
      <span className={cn('h-1 overflow-hidden rounded-full bg-foreground/[0.07]', size === 'lg' ? 'w-16' : 'w-9')}>
        <span
          className={cn('block h-full rounded-full', low ? 'bg-muted-foreground/40' : 'bg-primary')}
          style={{ width: `${score}%` }}
        />
      </span>
    </span>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="space-y-2.5">
      <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">{title}</h3>
      {children}
    </div>
  )
}

function Components({ components }: { components: Schemas['ScoreComponent'][] }) {
  return (
    <dl className="space-y-2">
      {components.map((c) => (
        <div key={c.name} className="grid grid-cols-[7.5rem_minmax(0,1fr)_2.5rem] items-center gap-3 text-sm">
          <dt className={cn(c.value == null && 'text-muted-foreground')}>{COMPONENT_LABEL[c.name]}</dt>
          <dd className="h-1.5 overflow-hidden rounded-full bg-foreground/[0.06]">
            {c.value != null && (
              <span className="block h-full rounded-full bg-primary/70" style={{ width: `${c.value * 100}%` }} />
            )}
          </dd>
          <dd className="tabular text-right text-xs text-muted-foreground">
            {c.value == null ? '—' : `+${Math.round(c.points)}`}
          </dd>
        </div>
      ))}
    </dl>
  )
}

function SkillCoverage({ coverage }: { coverage: Schemas['SkillCoverage'] }) {
  if (!coverage.covered.length && !coverage.missing.length) {
    return <p className="text-sm text-muted-foreground">La oferta no indica ninguna.</p>
  }
  return (
    <ul className="flex flex-wrap gap-1.5">
      {coverage.covered.map((c) => (
        <li key={c.skill}>
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="inline-flex items-center gap-1.5 rounded-md bg-accent px-2 py-1 text-[0.8rem] leading-none font-medium text-accent-foreground ring-1 ring-primary/15 ring-inset">
                <CheckIcon className="size-3" weight="bold" />
                {c.skill}
                <span className="font-mono text-[0.7rem] opacity-70">{c.level === 'basic' ? 'bás.' : c.level}</span>
              </span>
            </TooltipTrigger>
            <TooltipContent>
              {c.profile_skill !== c.skill && <>En tu perfil: {c.profile_skill}. </>}
              {LEVEL_LABEL[c.level]}
            </TooltipContent>
          </Tooltip>
        </li>
      ))}
      {coverage.missing.map((skill) => (
        <li
          key={skill}
          className="rounded-md border border-dashed border-input px-2 py-[3px] text-[0.8rem] leading-none text-muted-foreground"
          title="No está en tu perfil"
        >
          <span className="sr-only">Falta: </span>
          {skill}
        </li>
      ))}
    </ul>
  )
}

function Assessment({ match }: { match: MatchView }) {
  const a = match.assessment
  if (!a) {
    return (
      <p className="flex items-start gap-2 text-sm text-muted-foreground">
        <RobotIcon className="mt-0.5 size-4 shrink-0" />
        <span>
          Sin valorar. Ejecuta el skill{' '}
          <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em] text-foreground">evaluar-encaje</code>{' '}
          en tu agente.
        </span>
      </p>
    )
  }
  return (
    <div className="space-y-3">
      <p className="flex flex-wrap items-center gap-2">
        <span
          className={cn(
            'inline-flex h-6 items-center rounded-full border px-2.5 text-xs font-medium',
            a.verdict === 'strong' && 'border-primary/25 bg-accent text-accent-foreground',
            a.verdict === 'possible' && 'border-input text-foreground',
            a.verdict === 'weak' && 'border-transparent bg-muted text-muted-foreground',
          )}
        >
          {VERDICT_LABEL[a.verdict]}
        </span>
        {match.assessment_stale && (
          <span className="text-xs text-muted-foreground">De un cálculo anterior: el perfil o la oferta cambiaron.</span>
        )}
      </p>
      <p className="text-sm leading-relaxed text-foreground/90">{a.rationale}</p>
      {a.risks.length > 0 && (
        <ul className="space-y-1 text-sm text-foreground/85">
          {a.risks.map((risk) => (
            <li key={risk} className="flex gap-2">
              <InfoIcon className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
              {risk}
            </li>
          ))}
        </ul>
      )}
      {a.questions_for_user.length > 0 && (
        <div className="rounded-lg border border-primary/20 bg-accent/50 p-3">
          <p className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-accent-foreground">
            <ChatCircleDotsIcon className="size-4" weight="duotone" />
            Preguntas para ti
          </p>
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {a.questions_for_user.map((q) => (
              <li key={q}>{q}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

export function FilterFailures({ failures }: { failures: Schemas['FilterFailure'][] }) {
  if (!failures.length) return null
  return (
    <div role="note" aria-label="No pasa los filtros" className="rounded-lg border border-foreground/15 bg-muted/60 p-3">
      <p className="mb-1.5 flex items-center gap-1.5 text-sm font-medium">
        <ProhibitIcon className="size-4" weight="bold" />
        No pasa los filtros duros
      </p>
      <ul className="space-y-1 pl-5.5 text-sm text-foreground/85">
        {failures.map((f) => (
          <li key={f.filter}>{f.reason}</li>
        ))}
      </ul>
    </div>
  )
}

/** Desglose completo de un match: filtros, componentes, skills, notas y valoración del agente. */
export function MatchDetails({ match }: { match: MatchView }) {
  const b = match.breakdown
  return (
    <div className="space-y-6">
      <FilterFailures failures={match.hard_filters.failures} />
      <Section title="Desglose">
        <Components components={b.components} />
      </Section>
      <Section title="Skills obligatorias">
        <SkillCoverage coverage={b.must_have} />
      </Section>
      <Section title="Skills deseables">
        <SkillCoverage coverage={b.nice_to_have} />
      </Section>
      {b.notes.length > 0 && (
        <ul className="space-y-1 text-xs text-muted-foreground">
          {b.notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      )}
      <Section title="Valoración del agente">
        <Assessment match={match} />
      </Section>
    </div>
  )
}
