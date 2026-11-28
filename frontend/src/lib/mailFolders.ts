import { i18n } from '@/lib/i18n'

/** `INBOX` es la bandeja de entrada: se enseña con su nombre en el idioma del portal (fase 48.3). */
export function folderLabel(folder: string): string {
  return folder.toUpperCase() === 'INBOX' ? i18n.t('mailboxes:inbox') : folder
}
