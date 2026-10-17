import { LockIcon } from '@phosphor-icons/react'
import { useTranslation } from 'react-i18next'
import { Block, BlockActions, TextField } from './fields'
import { useBlockEditor } from './editor'
import type { Localized, Personal, ProfileData } from './types'

interface Draft {
  personal: Personal
  headline: string
  summary: Localized
}

const read = (p: ProfileData): Draft => ({
  personal: p.personal ?? { name: '' },
  headline: p.headline ?? '',
  summary: p.summary ?? {},
})
const write = (d: Draft, p: ProfileData) => ({
  personal: d.personal,
  // Sin titular ni resumen en el fichero y sin escribirlos: no se manda nada (ni `''` ni `{}`).
  ...(d.headline || p.headline !== undefined ? { headline: d.headline } : {}),
  ...(d.summary.es || d.summary.en || p.summary !== undefined ? { summary: d.summary } : {}),
})

const PUBLIC_FIELDS = ['linkedin', 'github', 'city', 'profile_location', 'availability', 'mobility'] as const

/** Nombre, contacto (privado), enlaces, ciudad, disponibilidad, titular y resumen. */
export function PersonalBlock() {
  const { t } = useTranslation('profileEditor')
  const block = useBlockEditor('personal', read, write)
  const { personal, headline, summary } = block.draft
  const err = (path: string) => block.errors.get(path)
  const setPersonal = (key: string, value: string) => block.update((d) => ({ ...d, personal: { ...d.personal, [key]: value } }))
  return (
    <Block title={t('blocks.personal.title')} hint={t('blocks.personal.hint')}>
      <div className="grid gap-4 sm:grid-cols-2">
        <TextField label={t('fields.name')} value={personal.name} error={err('personal.name')} onChange={(v) => setPersonal('name', v)} />
        <TextField
          label={t('fields.headline')}
          hint={t('fields.headlineHint')}
          value={headline}
          error={err('headline')}
          onChange={(v) => block.update((d) => ({ ...d, headline: v }))}
        />
      </div>
      <div className="grid gap-4 rounded-lg border border-dashed p-3 sm:grid-cols-2">
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground sm:col-span-2">
          <LockIcon aria-hidden /> {t('fields.privateContact')}
        </p>
        <TextField label={t('fields.email')} type="email" value={personal.email} error={err('personal.email')} onChange={(v) => setPersonal('email', v)} />
        <TextField label={t('fields.phone')} value={personal.phone} error={err('personal.phone')} onChange={(v) => setPersonal('phone', v)} />
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        {PUBLIC_FIELDS.map((key) => (
          <TextField
            key={key}
            label={t(`fields.${key}`)}
            value={personal[key] as string | null | undefined}
            error={err(`personal.${key}`)}
            onChange={(v) => setPersonal(key, v)}
          />
        ))}
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        {(['es', 'en'] as const).map((lang) => (
          <TextField
            key={lang}
            multiline
            rows={5}
            label={t(`fields.summary.${lang}`)}
            value={summary[lang]}
            error={err(`summary.${lang}`) ?? err('summary')}
            onChange={(v) => block.update((d) => ({ ...d, summary: { ...d.summary, [lang]: v } }))}
          />
        ))}
      </div>
      <BlockActions block={block} />
    </Block>
  )
}
