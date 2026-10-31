/**
 * Sin ningún agente instalado (`no_agent_installed` de `GET /agent`): qué es un agente, por qué lo
 * necesitas y cómo instalar Claude Code, el más probado, con los pasos de la guía para empezar. Lo
 * usan Inicio y «Agente».
 */
import { Trans, useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { ArrowSquareOutIcon, RobotIcon } from '@phosphor-icons/react'
import { useAgentsOverview } from '@/api/queries'
import { CommandBox } from '@/components/CommandBox'
import { desktopOs } from '@/lib/extension'
import { i18n, SOURCE_LANGUAGE } from '@/lib/i18n'

const GUIDE = {
  es: 'https://github.com/DiegoPrieto23/candidatai/blob/main/docs/EMPEZAR.md#3-instalar-tu-agente',
  en: 'https://github.com/DiegoPrieto23/candidatai/blob/main/docs/START_HERE.md#3-install-your-agent',
}
const INSTALL_KEY = { windows: 'windows', mac: 'macos', linux: 'linux' } as const

export function GetAnAgent({ linkToAgentPage = true }: { linkToAgentPage?: boolean }) {
  const { t } = useTranslation('agents', { keyPrefix: 'getAgent' })
  const overview = useAgentsOverview()
  const os = desktopOs()
  const claude = overview.data?.agents.find((a) => a.name === 'claude')
  const command = claude?.info.install[INSTALL_KEY[os]]
  const strong = { strong: <strong className="font-medium text-foreground" /> }
  return (
    <section
      aria-labelledby="get-an-agent"
      className="rounded-xl border border-warning-border bg-warning/40 p-5 text-sm sm:p-6"
    >
      <h2 id="get-an-agent" className="flex items-center gap-2 text-lg font-semibold tracking-tight">
        <RobotIcon className="size-6 text-warning-foreground" weight="duotone" aria-hidden />
        {t('title')}
      </h2>
      <p className="mt-2 max-w-prose text-muted-foreground">
        <Trans t={t} i18nKey="why" components={strong} />
      </p>
      <ol className="mt-4 grid max-w-prose list-decimal gap-3 pl-5 marker:font-semibold">
        <li>
          <Trans t={t} i18nKey="step1" components={strong} />
        </li>
        <li className="space-y-2">
          <p>
            <Trans t={t} i18nKey={`step2.${os}`} components={strong} />
          </p>
          {command && <CommandBox text={command} label={t('commandLabel')} mono />}
        </li>
        <li>
          <Trans t={t} i18nKey="step3" components={strong} />
        </li>
        <li>{t('step4')}</li>
      </ol>
      <p className="mt-4 flex flex-wrap gap-x-5 gap-y-2">
        <a
          href={i18n.language === SOURCE_LANGUAGE ? GUIDE.es : GUIDE.en}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1 text-primary underline decoration-primary/30 underline-offset-4 hover:decoration-primary"
        >
          {t('guide')}
          <ArrowSquareOutIcon className="size-3.5" aria-hidden />
        </a>
        {linkToAgentPage && (
          <Link to="/agente" className="text-primary underline decoration-primary/30 underline-offset-4 hover:decoration-primary">
            {t('otherAgents')}
          </Link>
        )}
      </p>
    </section>
  )
}
