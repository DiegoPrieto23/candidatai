import type { ReactNode } from 'react'
import { ChatCircleDotsIcon, CheckIcon, InfoIcon, ProhibitIcon, RobotIcon } from '@phosphor-icons/react'
import { Trans, useTranslation } from 'react-i18next'
import type { MatchView, Schemas } from '@/api/client'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { serverText } from '@/lib/i18n'
import { scoreNote } from '@/lib/scoreNotes'
import { useSalaryGap } from '@/api/queries'
import { COMPONENT_LABEL, HARD_FILTER_LABEL, LEVEL_LABEL, VERDICT_LABEL, formatMoney } from '@/lib/labels'
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
  const { t } = useTranslation('match')
  if (score == null) {
    return <span className={cn('text-xs text-muted-foreground/70', className)}>{t('noScore')}</span>
  }
  const low = threshold != null && score < threshold
  return (
    <span
      className={cn('inline-flex flex-col items-end gap-1', className)}
      aria-label={t('scoreAria', { score }) + (low ? t('belowThreshold') : '')}
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
  const { t } = useTranslation('match')
  if (!coverage.covered.length && !coverage.missing.length) {
    return <p className="text-sm text-muted-foreground">{t('noSkills')}</p>
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
                <span className="font-mono text-[0.7rem] opacity-70">{c.level === 'basic' ? t('basicShort') : c.level}</span>
              </span>
            </TooltipTrigger>
            <TooltipContent>
              {c.profile_skill !== c.skill && t('inProfile', { skill: c.profile_skill })}
              {LEVEL_LABEL[c.level]}
            </TooltipContent>
          </Tooltip>
        </li>
      ))}
      {coverage.missing.map((skill) => (
        <li
          key={skill}
          className="rounded-md border border-dashed border-input px-2 py-[3px] text-[0.8rem] leading-none text-muted-foreground"
          title={t('notInProfile')}
        >
          <span className="sr-only">{t('missing')}</span>
          {skill}
        </li>
      ))}
    </ul>
  )
}

function Assessment({ match, assessMinScore }: { match: MatchView; assessMinScore?: number }) {
  const { t } = useTranslation('match')
  const a = match.assessment
  if (!a) {
    // Fase 25.4: por debajo del umbral, «Evaluar encaje» en segundo plano no la valora.
    const below = assessMinScore != null && match.score < assessMinScore
    return (
      <div className="space-y-1.5">
        <p className="flex items-start gap-2 text-sm text-muted-foreground">
          <RobotIcon className="mt-0.5 size-4 shrink-0" />
          <span>
            <Trans
              t={t}
              i18nKey="notAssessed"
              components={{ code: <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em] text-foreground" /> }}
            />
          </span>
        </p>
        {below && (
          <p role="note" className="pl-6 text-xs text-muted-foreground">
            {t('belowAssessThreshold', { score: match.score, threshold: assessMinScore })}
          </p>
        )}
      </div>
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
          <span className="text-xs text-muted-foreground">
            {/* El texto del agente puede citar el score de entonces: se dice cuál era. */}
            {match.assessment_score != null && match.assessment_score !== match.score
              ? t('staleScore', { was: match.assessment_score, score: match.score })
              : t('stale')}
          </span>
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
            {t('questions')}
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

/** Con `jobId`, el fallo por sueldo dice cuánto queda por debajo de tu mínimo: solo la UI lo sabe
 * ; el motivo que guarda el servidor no lleva cifras. */
export function FilterFailures({ failures, jobId }: { failures: Schemas['FilterFailure'][]; jobId?: number }) {
  const { t } = useTranslation('match')
  const bySalary = jobId != null && failures.some((f) => f.filter === 'salary')
  const gap = useSalaryGap(jobId ?? 0, bySalary).data?.gap_eur
  if (!failures.length) return null
  return (
    <div role="note" aria-label={t('failsFilters')} className="rounded-lg border border-foreground/15 bg-muted/60 p-3">
      <p className="mb-1.5 flex items-center gap-1.5 text-sm font-medium">
        <ProhibitIcon className="size-4" weight="bold" />
        {t('failsHardFilters')}
      </p>
      <ul className="space-y-1 pl-5.5 text-sm text-foreground/85">
        {failures.map((f) => (
          <li key={f.filter}>
            {serverText(HARD_FILTER_LABEL[f.filter], f.reason)}
            {f.filter === 'salary' && gap != null && <span className="text-muted-foreground"> {t('salaryGap', { amount: formatMoney(gap) })}</span>}
          </li>
        ))}
      </ul>
    </div>
  )
}

/** Desglose completo de un match: filtros, componentes, skills, notas y valoración del agente. */
/** `assessMinScore`: el umbral de «Evaluar encaje» en segundo plano (fase 25.4), para decir por qué
 *  una oferta se queda sin valorar. */
export function MatchDetails({ match, assessMinScore }: { match: MatchView; assessMinScore?: number }) {
  const { t } = useTranslation('match')
  const b = match.breakdown
  return (
    <div className="space-y-6">
      <FilterFailures failures={match.hard_filters.failures} jobId={match.job_id} />
      <Section title={t('sections.breakdown')}>
        <Components components={b.components} />
      </Section>
      <Section title={t('sections.mustHave')}>
        <SkillCoverage coverage={b.must_have} />
      </Section>
      <Section title={t('sections.niceToHave')}>
        <SkillCoverage coverage={b.nice_to_have} />
      </Section>
      {b.notes.length > 0 && (
        <ul className="space-y-1 text-xs text-muted-foreground">
          {b.notes.map((note) => (
            <li key={note}>{scoreNote(note)}</li>
          ))}
        </ul>
      )}
      <Section title={t('sections.assessment')}>
        <Assessment match={match} assessMinScore={assessMinScore} />
      </Section>
    </div>
  )
}
