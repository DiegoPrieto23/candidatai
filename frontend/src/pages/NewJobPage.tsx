import { useState, type FormEvent, type ReactNode } from 'react'
import { Trans, useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router'
import { ClipboardTextIcon, LinkIcon, WarningCircleIcon } from '@phosphor-icons/react'
import { ApiError, type AddJobResult } from '@/api/client'
import { useAddFromText, useAddFromUrl } from '@/api/queries'
import { InlineCode } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { errorMessage } from '@/lib/errors'
import type { AddedState } from './JobPage'

function useGoToJob() {
  const navigate = useNavigate()
  return (added: AddJobResult) =>
    navigate(`/jobs/${added.job_id}`, { state: { added } satisfies AddedState })
}

/** Errores por campo que devuelve la API (`details[].field`). */
function fieldErrors(error: unknown): Record<string, string> {
  if (!(error instanceof ApiError)) return {}
  return Object.fromEntries(error.details.map((d) => [d.field, d.reason]))
}

function FormError({ error }: { error: unknown }) {
  const { t } = useTranslation('newJob')
  if (!error) return null
  const message = error instanceof Error ? errorMessage(error) : t('failed')
  return (
    <div
      role="alert"
      className="flex items-start gap-2.5 rounded-lg border border-destructive/30 bg-destructive/5 px-3.5 py-3 text-sm"
    >
      <WarningCircleIcon className="mt-0.5 size-4 shrink-0 text-destructive" weight="fill" />
      <p>
        <InlineCode text={message} />
      </p>
    </div>
  )
}

function Field({
  id,
  label,
  hint,
  error,
  optional,
  children,
}: {
  id: string
  label: string
  hint?: ReactNode
  error?: string
  optional?: boolean
  children: ReactNode
}) {
  const { t } = useTranslation('newJob')
  return (
    <div className="grid gap-2">
      <Label htmlFor={id} className="gap-1.5">
        {label}
        {optional && <span className="font-normal text-muted-foreground">{t('optional')}</span>}
      </Label>
      {children}
      {error ? (
        <p id={`${id}-error`} className="text-sm text-destructive">
          {error}
        </p>
      ) : (
        hint && (
          <p id={`${id}-hint`} className="text-xs leading-relaxed text-muted-foreground">
            {hint}
          </p>
        )
      )}
    </div>
  )
}

function UrlForm({ onUsePaste }: { onUsePaste: () => void }) {
  const { t } = useTranslation('newJob', { keyPrefix: 'url' })
  const [url, setUrl] = useState('')
  const add = useAddFromUrl()
  const goToJob = useGoToJob()
  const errors = fieldErrors(add.error)

  const submit = (e: FormEvent) => {
    e.preventDefault()
    add.mutate({ url: url.trim() }, { onSuccess: goToJob })
  }

  return (
    <form onSubmit={submit} className="grid gap-5" noValidate>
      <Field
        id="url"
        label={t('label')}
        error={errors.url}
        hint={
          <Trans
            t={t}
            i18nKey="hint"
            components={{
              paste: (
                <button
                  type="button"
                  onClick={onUsePaste}
                  className="font-medium text-primary underline-offset-4 hover:underline"
                />
              ),
            }}
          />
        }
      >
        <Input
          id="url"
          type="url"
          inputMode="url"
          autoFocus
          required
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://"
          aria-invalid={Boolean(errors.url) || undefined}
          className="h-10 bg-background"
        />
      </Field>
      <FormError error={add.error && !errors.url ? add.error : null} />
      <div className="flex justify-end">
        <Button type="submit" disabled={!url.trim() || add.isPending} className="h-10 px-5 active:translate-y-px">
          {add.isPending ? t('downloading') : t('submit')}
        </Button>
      </div>
    </form>
  )
}

function TextForm() {
  const { t } = useTranslation('newJob', { keyPrefix: 'text' })
  const [form, setForm] = useState({ title: '', company: '', location: '', url: '', text: '' })
  const add = useAddFromText()
  const goToJob = useGoToJob()
  const errors = fieldErrors(add.error)
  const set = (key: keyof typeof form) => (e: { target: { value: string } }) =>
    setForm((prev) => ({ ...prev, [key]: e.target.value }))
  const ready = form.title.trim() && form.company.trim() && form.text.trim()

  const submit = (e: FormEvent) => {
    e.preventDefault()
    add.mutate(
      {
        title: form.title.trim(),
        company: form.company.trim(),
        text: form.text.trim(),
        location: form.location.trim() || null,
        url: form.url.trim() || null,
      },
      { onSuccess: goToJob },
    )
  }
  const hasFieldError = Object.keys(errors).length > 0

  return (
    <form onSubmit={submit} className="grid gap-5" noValidate>
      <div className="grid gap-5 sm:grid-cols-2">
        <Field id="title" label={t('title')} error={errors.title}>
          <Input id="title" required value={form.title} onChange={set('title')} className="h-10 bg-background" />
        </Field>
        <Field id="company" label={t('company')} error={errors.company}>
          <Input id="company" required value={form.company} onChange={set('company')} className="h-10 bg-background" />
        </Field>
        <Field id="location" label={t('location')} optional error={errors.location}>
          <Input id="location" value={form.location} onChange={set('location')} className="h-10 bg-background" />
        </Field>
        <Field id="text-url" label={t('url')} optional error={errors.url}>
          <Input
            id="text-url"
            type="url"
            inputMode="url"
            value={form.url}
            onChange={set('url')}
            placeholder="https://"
            className="h-10 bg-background"
          />
        </Field>
      </div>
      <Field
        id="text"
        label={t('text')}
        error={errors.text}
        hint={t('hint')}
      >
        <Textarea
          id="text"
          required
          value={form.text}
          onChange={set('text')}
          rows={12}
          className="min-h-56 resize-y bg-background text-sm leading-relaxed"
        />
      </Field>
      <FormError error={add.error && !hasFieldError ? add.error : null} />
      <div className="flex justify-end">
        <Button type="submit" disabled={!ready || add.isPending} className="h-10 px-5 active:translate-y-px">
          {add.isPending ? t('saving') : t('submit')}
        </Button>
      </div>
    </form>
  )
}

export function NewJobPage() {
  const { t } = useTranslation('newJob')
  const [tab, setTab] = useState('url')
  return (
    <div className="mx-auto max-w-2xl animate-in fade-in duration-300">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold tracking-tight">{t('title')}</h1>
        <p className="mt-1.5 text-sm text-muted-foreground">
          {t('intro')}
        </p>
      </div>
      <Tabs value={tab} onValueChange={setTab} className="gap-0">
        <TabsList className="mb-5 h-10 w-full sm:w-auto">
          <TabsTrigger value="url" className="px-4">
            <LinkIcon />
            {t('byUrl')}
          </TabsTrigger>
          <TabsTrigger value="text" className="px-4">
            <ClipboardTextIcon />
            {t('pasteText')}
          </TabsTrigger>
        </TabsList>
        <div className="rounded-xl border bg-card p-5 sm:p-6">
          <TabsContent value="url">
            <UrlForm onUsePaste={() => setTab('text')} />
          </TabsContent>
          <TabsContent value="text">
            <TextForm />
          </TabsContent>
        </div>
      </Tabs>
    </div>
  )
}
