import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router'
import { BellRingingIcon } from '@phosphor-icons/react'
import type { UpcomingItem } from '@/api/client'
import { useFollowups, useUpcoming } from '@/api/queries'
import { Hint } from '@/components/Hint'
import { Switch } from '@/components/Switch'
import { UPCOMING_KIND_LABEL } from '@/lib/labels'
import {
  dueReminders,
  markSent,
  notificationsSupported,
  readSent,
  refreshReminders,
  setRemindersEnabled,
  useReminderState,
  type Reminder,
} from '@/lib/reminders'
import { formatWhen } from '@/lib/time'

/** Interruptor de los avisos del navegador (Calendario). El permiso se pide solo al activarlo. */
export function BrowserReminders() {
  const { t } = useTranslation('calendar', { keyPrefix: 'reminders' })
  const { enabled, permission } = useReminderState()
  const [asking, setAsking] = useState(false)
  if (permission === 'unsupported') return null

  const toggle = async (on: boolean) => {
    if (!on) return setRemindersEnabled(false)
    if (Notification.permission === 'default') {
      setAsking(true)
      try {
        await Notification.requestPermission()
      } finally {
        setAsking(false)
      }
    }
    setRemindersEnabled(Notification.permission === 'granted')
    refreshReminders()
  }

  return (
    <div className="flex shrink-0 flex-col items-start gap-1 sm:items-end">
      <div className="inline-flex items-center gap-2 text-sm">
        <BellRingingIcon className="size-4 text-muted-foreground" />
        {t('label')}
        <Switch
          checked={enabled && permission === 'granted'}
          disabled={asking || permission === 'denied'}
          label={t('label')}
          onChange={(on) => void toggle(on)}
        />
        <Hint text={t('hint')} label={t('hintAria')} />
      </div>
      {permission === 'denied' && <p className="max-w-xs text-xs text-muted-foreground sm:text-right">{t('blocked')}</p>}
    </div>
  )
}

const CHECK_EVERY_MS = 60_000

/**
 * Lanza los avisos que tocan mientras la app está abierta, en cualquier página. Solo pide datos si
 * están activados y el navegador da permiso.
 */
function useBrowserReminders() {
  const { t } = useTranslation('calendar', { keyPrefix: 'reminders' })
  const navigate = useNavigate()
  const { enabled, permission } = useReminderState()
  const active = notificationsSupported() && enabled && permission === 'granted'
  const upcoming = useUpcoming(2, { enabled: active, poll: 5 * 60_000 })
  const followups = useFollowups(active)
  const latest = useRef({ items: [] as UpcomingItem[], followups: 0 })
  useEffect(() => {
    latest.current = { items: upcoming.data?.items ?? [], followups: followups.data?.followups.length ?? 0 }
  }, [upcoming.data, followups.data])

  useEffect(() => {
    if (!active || !upcoming.data) return
    const show = (reminder: Reminder) => {
      const item = reminder.item
      const title = item
        ? `${item.title !== UPCOMING_KIND_LABEL[item.kind] ? item.title : UPCOMING_KIND_LABEL[item.kind]} · ${item.company}`
        : t('followupsTitle')
      const body = item
        ? `${formatWhen(item.starts_at, item.all_day)} · ${item.job_title}`
        : t('followupsBody', { count: reminder.count ?? 0 })
      try {
        const n = new Notification(title, { body, tag: reminder.key })
        n.onclick = () => {
          window.focus()
          navigate(item ? `/jobs/${item.job_id}` : '/procesos')
          n.close()
        }
      } catch {
        // Algunos navegadores solo las crean desde un service worker: no se avisa.
      }
    }
    const check = () => {
      const sent = readSent()
      const due = dueReminders(latest.current.items, latest.current.followups, new Date(), sent)
      if (due.length === 0) return
      markSent(sent, due.map((r) => r.key))
      due.forEach(show)
    }
    check()
    const id = window.setInterval(check, CHECK_EVERY_MS)
    return () => window.clearInterval(id)
  }, [active, upcoming.data, navigate, t])
}

/** Sin interfaz: monta el vigilante de avisos en la estructura de la app. */
export function BrowserRemindersWatcher() {
  useBrowserReminders()
  return null
}
