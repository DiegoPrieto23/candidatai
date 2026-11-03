/**
 * «Mi perfil» sin perfil y sin agente: «Empezar a mano». Lo justo para que el perfil valide (tu
 * nombre, tu titular, el puesto y los niveles que buscas) y, al crearlo, «Mi perfil» abre el editor
 * para seguir bloque a bloque. Las preferencias que no se preguntan arrancan amplias.
 */
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { PencilSimpleLineIcon } from '@phosphor-icons/react'
import { ApiError } from '@/api/client'
import { useCreateProfile } from '@/api/queries'
import { Button } from '@/components/ui/button'
import { errorMessage } from '@/lib/errors'
import { i18n } from '@/lib/i18n'
import { ChoicesField, TextField } from './fields'
import { SENIORITIES } from './types'
import { BusyLabel } from '@/components/StableLabel'

type Seniority = (typeof SENIORITIES)[number]

export function StartByHand() {
  const { t } = useTranslation('profileEditor')
  const create = useCreateProfile()
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [headline, setHeadline] = useState('')
  const [role, setRole] = useState('')
  const [seniority, setSeniority] = useState<Seniority[]>([])
  const [summary, setSummary] = useState('')
  const [tried, setTried] = useState(false)
  const required = (value: string) => (tried && !value.trim() ? t('noProfile.byHand.required') : undefined)
  const ready = Boolean(name.trim() && headline.trim() && role.trim() && seniority.length)

  const submit = (e: FormEvent) => {
    e.preventDefault()
    setTried(true)
    if (!ready) return
    create.mutate({
      name,
      headline,
      role,
      seniority,
      summary: summary.trim() || null,
      // El resumen va en español o en inglés: con la UI en otro idioma, en español.
      language: i18n.language.startsWith('en') ? 'en' : 'es',
    })
  }

  return (
    <section aria-labelledby="start-by-hand" className="rounded-xl border bg-card p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <PencilSimpleLineIcon className="size-7 shrink-0 text-muted-foreground" weight="duotone" aria-hidden />
          <div>
            <h2 id="start-by-hand" className="font-semibold tracking-tight">
              {t('noProfile.byHand.title')}
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">{t('noProfile.byHand.intro')}</p>
          </div>
        </div>
        {!open && (
          <Button type="button" size="sm" variant="outline" onClick={() => setOpen(true)}>
            {t('noProfile.byHand.open')}
          </Button>
        )}
      </div>
      {open && (
        <form onSubmit={submit} noValidate className="mt-5 grid gap-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField label={t('fields.name')} value={name} onChange={setName} error={required(name)} autoFocus />
            <TextField
              label={t('fields.headline')}
              hint={t('noProfile.byHand.headlineHint')}
              value={headline}
              onChange={setHeadline}
              error={required(headline)}
            />
          </div>
          <TextField
            label={t('noProfile.byHand.role')}
            hint={t('noProfile.byHand.roleHint')}
            value={role}
            onChange={setRole}
            error={required(role)}
          />
          <ChoicesField
            label={t('fields.seniority')}
            value={seniority}
            options={SENIORITIES.map((s) => ({ value: s, label: t(`seniority.${s}`) }))}
            onChange={setSeniority}
            error={tried && !seniority.length ? t('noProfile.byHand.pickOne') : undefined}
          />
          <TextField
            label={t('noProfile.byHand.summary')}
            hint={t('noProfile.byHand.summaryHint')}
            value={summary}
            onChange={setSummary}
            multiline
          />
          <p className="text-xs text-muted-foreground">{t('noProfile.byHand.defaults')}</p>
          {create.error && (
            <p role="alert" className="text-sm text-destructive">
              {create.error instanceof ApiError && create.error.type === 'conflict'
                ? t('noProfile.byHand.exists')
                : errorMessage(create.error)}
            </p>
          )}
          <div className="flex flex-wrap gap-2 border-t pt-4">
            <Button type="submit" disabled={create.isPending}>
              <BusyLabel busy={create.isPending} busyText={t('noProfile.byHand.creating')} text={t('noProfile.byHand.create')} />
            </Button>
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
              {t('noProfile.byHand.cancel')}
            </Button>
          </div>
        </form>
      )}
    </section>
  )
}
