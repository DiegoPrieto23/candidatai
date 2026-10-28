/**
 * Inicio con la app recién instalada: los dos pasos para empezar, con su botón. Tu perfil (sube tu
 * CV y tu agente lo crea) y dónde buscar (tu agente configura los portales con los puestos de tu
 * perfil). Cada paso se marca al hacerlo y la tarjeta desaparece con los dos hechos.
 */
import type { ReactNode } from 'react'
import { Link } from 'react-router'
import { useTranslation } from 'react-i18next'
import { CheckCircleIcon } from '@phosphor-icons/react'
import { useEditableProfile, usePlatforms, useSourceDocuments } from '@/api/queries'
import { AgentButton } from '@/components/AgentButton'
import { UploadCv } from '@/components/profile/StartFromCv'
import { cn } from '@/lib/utils'

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
        <h3 className={cn('font-medium', done && 'text-muted-foreground line-through decoration-muted-foreground/40')}>{title}</h3>
        {children}
      </div>
    </li>
  )
}

const LINK = 'text-sm text-primary underline decoration-primary/30 underline-offset-4 hover:decoration-primary'

export function FirstSteps() {
  const { t } = useTranslation('home', { keyPrefix: 'firstSteps' })
  const { t: tAgent } = useTranslation('agent')
  const profile = useEditableProfile()
  const platforms = usePlatforms()
  const cvs = useSourceDocuments('cv')
  // Sin saberlo aún (o si falla), no se enseña: mejor nada que un aviso que no toca.
  if (!profile.isSuccess || !platforms.isSuccess) return null
  const hasProfile = profile.data.exists
  const hasPlatforms = platforms.data.sources.length > 0
  if (hasProfile && hasPlatforms) return null
  const hasCv = (cvs.data?.length ?? 0) > 0

  return (
    <section aria-labelledby="first-steps" className="rounded-xl border bg-card p-5 sm:p-6">
      <h2 id="first-steps" className="text-lg font-semibold tracking-tight">
        {t('title')}
      </h2>
      <p className="mt-1 text-sm text-muted-foreground">{t('intro')}</p>
      <ol className="mt-5 grid gap-6 text-sm">
        <Step n={1} done={hasProfile} title={t('profile.title')}>
          {hasProfile ? (
            <Link to="/perfil" className={LINK}>
              {t('profile.done')}
            </Link>
          ) : (
            <>
              <p className="text-muted-foreground">{t('profile.body')}</p>
              <UploadCv />
              <AgentButton action="create-profile" primary={hasCv}>
                {tAgent('actions.create-profile')}
              </AgentButton>
            </>
          )}
        </Step>
        <Step n={2} done={hasPlatforms} title={t('search.title')}>
          {hasPlatforms ? (
            <Link to="/fuentes/plataformas" className={LINK}>
              {t('search.done')}
            </Link>
          ) : (
            <>
              <p className="text-muted-foreground">{t('search.body')}</p>
              <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
                <AgentButton action="configure-platforms" primary={hasProfile}>
                  {tAgent('actions.configure-platforms')}
                </AgentButton>
                <Link to="/fuentes/plataformas" className={LINK}>
                  {t('search.manual')}
                </Link>
              </div>
            </>
          )}
        </Step>
      </ol>
    </section>
  )
}
