import { Trans, useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { UserCircleIcon } from '@phosphor-icons/react'
import { useEditableProfile } from '@/api/queries'
import { ProfileEditorProvider } from '@/components/profile/editor'
import { SearchContractBlock, SearchExperienceBlock, SearchRoleBlock, SearchWhereBlock } from '@/components/profile/PreferencesBlocks'
import { EmptyState, ErrorState } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'

/**
 * «Qué buscas»: puestos, experiencia, sueldo, lugar y contrato. Se guardan en tu perfil como siempre,
 * pero se editan aquí, al lado de donde se usan: deciden qué busca tu agente y qué ofertas pasan.
 */
export function SearchSettingsPage() {
  const { t } = useTranslation('search', { keyPrefix: 'settings' })
  const editable = useEditableProfile()

  let body
  if (editable.isPending) {
    body = <Skeleton className="h-64" />
  } else if (editable.isError) {
    body = <ErrorState error={editable.error} onRetry={() => editable.refetch()} />
  } else if (!editable.data.exists || editable.data.profile === null) {
    body = (
      <EmptyState
        icon={<UserCircleIcon className="size-7" weight="duotone" />}
        title={t('noProfile.title')}
        action={
          <Button asChild size="sm">
            <Link to="/perfil">{t('noProfile.go')}</Link>
          </Button>
        }
      >
        {t('noProfile.body')}
      </EmptyState>
    )
  } else {
    body = (
      <ProfileEditorProvider state={editable.data} reload={() => void editable.refetch()}>
        {editable.data.issues.length > 0 && (
          <p role="alert" className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm dark:border-amber-800 dark:bg-amber-950/40">
            <Trans t={t} i18nKey="issues" components={{ to: <Link to="/perfil" className="underline underline-offset-4" /> }} />
          </p>
        )}
        <SearchRoleBlock />
        <SearchExperienceBlock />
        <SearchWhereBlock />
        <SearchContractBlock />
      </ProfileEditorProvider>
    )
  }

  return (
    <div className="max-w-4xl animate-in fade-in duration-300">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">{t('title')}</h1>
        <p className="mt-1.5 max-w-[65ch] text-sm leading-relaxed text-muted-foreground">{t('intro')}</p>
      </div>
      <div className="grid gap-6">{body}</div>
    </div>
  )
}
