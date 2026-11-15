import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { Stage } from '@/api/client'
import { Switch } from '@/components/Switch'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import {
  BOARD_STAGES,
  columnId,
  columnName,
  joinsOf,
  layoutFromJoins,
  MAX_COLUMNS,
  MAX_NAME,
  MIN_COLUMNS,
  resetLayout,
  saveLayout,
  type BoardColumnSetting,
} from '@/lib/boardColumns'
import { STAGE_LABEL } from '@/lib/labels'

/** Elegir cuántas columnas tiene el Tablero (juntando etapas seguidas) y cómo se llaman. */
export function BoardColumnsDialog({
  open,
  layout,
  onOpenChange,
}: {
  open: boolean
  layout: BoardColumnSetting[]
  onOpenChange: (open: boolean) => void
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-lg">
        {open && <ColumnsForm layout={layout} onDone={() => onOpenChange(false)} />}
      </DialogContent>
    </Dialog>
  )
}

function ColumnsForm({ layout, onDone }: { layout: BoardColumnSetting[]; onDone: () => void }) {
  const { t } = useTranslation('processes', { keyPrefix: 'columns' })
  const [joins, setJoins] = useState(() => joinsOf(layout))
  const [names, setNames] = useState<Partial<Record<Stage, string>>>(() =>
    Object.fromEntries(layout.map((column) => [columnId(column), column.name])),
  )
  const draft = layoutFromJoins(joins, names)
  const count = draft.length

  const toggle = (i: number, value: boolean) => setJoins((current) => current.map((join, j) => (j === i ? value : join)))

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        saveLayout(draft)
        onDone()
      }}
      className="grid gap-5"
    >
      <DialogHeader>
        <DialogTitle>{t('title')}</DialogTitle>
        <DialogDescription>{t('description', { min: MIN_COLUMNS, max: MAX_COLUMNS })}</DialogDescription>
      </DialogHeader>

      <fieldset className="grid gap-1.5">
        <legend className="mb-2 text-sm font-medium">{t('stages', { count })}</legend>
        <ol className="grid gap-1.5">
          {BOARD_STAGES.map((stage, i) => (
            <li key={stage} className="grid gap-1.5">
              <span className="rounded-md border bg-muted/40 px-3 py-1.5 text-sm">{STAGE_LABEL[stage]}</span>
              {i < BOARD_STAGES.length - 1 && (
                <label className="flex items-center gap-2 pl-3 text-xs text-muted-foreground">
                  <Switch
                    checked={joins[i]}
                    // Siempre entre 3 y 5 columnas: con 3, no se junta nada más.
                    disabled={!joins[i] && count <= MIN_COLUMNS}
                    label={t('join', { a: STAGE_LABEL[stage], b: STAGE_LABEL[BOARD_STAGES[i + 1]] })}
                    onChange={(value) => toggle(i, value)}
                  />
                  {t('sameColumn')}
                </label>
              )}
            </li>
          ))}
        </ol>
      </fieldset>

      <fieldset className="grid gap-3">
        <legend className="mb-2 text-sm font-medium">{t('names')}</legend>
        {draft.map((column, i) => {
          const id = columnId(column)
          return (
            <div key={id} className="grid gap-1">
              <label htmlFor={`board-column-${id}`} className="text-xs text-muted-foreground">
                {t('column', { n: i + 1 })}
              </label>
              <Input
                id={`board-column-${id}`}
                value={names[id] ?? ''}
                maxLength={MAX_NAME}
                placeholder={columnName({ ...column, name: '' })}
                onChange={(e) => setNames((current) => ({ ...current, [id]: e.target.value }))}
              />
            </div>
          )
        })}
      </fieldset>

      <DialogFooter className="gap-2 sm:justify-between">
        <Button
          type="button"
          variant="ghost"
          onClick={() => {
            resetLayout()
            onDone()
          }}
        >
          {t('reset')}
        </Button>
        <div className="flex gap-2">
          <Button type="button" variant="outline" onClick={onDone}>
            {t('cancel')}
          </Button>
          <Button type="submit">{t('save')}</Button>
        </div>
      </DialogFooter>
    </form>
  )
}
