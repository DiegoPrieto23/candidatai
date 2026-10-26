import { ArrowLeftIcon, ArrowRightIcon } from '@phosphor-icons/react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { LIST_PAGE_SIZE } from '@/lib/paging'
import { cn } from '@/lib/utils'

/** «26-50 de 212» con Anteriores y Siguientes. Con una sola página no se enseña. */
export function Pager({
  page,
  total,
  pageSize = LIST_PAGE_SIZE,
  onPage,
  className,
}: {
  page: number
  total: number
  pageSize?: number
  onPage: (page: number) => void
  className?: string
}) {
  const { t } = useTranslation('common', { keyPrefix: 'pager' })
  if (total <= pageSize) return null
  const from = (page - 1) * pageSize + 1
  const to = Math.min(page * pageSize, total)
  return (
    <nav
      aria-label={t('label')}
      className={cn('flex items-center justify-between text-sm text-muted-foreground', className)}
    >
      <span className="tabular">{t('range', { from, to, total })}</span>
      <div className="flex gap-2">
        <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>
          <ArrowLeftIcon />
          {t('previous')}
        </Button>
        <Button variant="outline" size="sm" disabled={to >= total} onClick={() => onPage(page + 1)}>
          {t('next')}
          <ArrowRightIcon />
        </Button>
      </div>
    </nav>
  )
}
