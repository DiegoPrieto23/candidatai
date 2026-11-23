import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type Announcements,
  type DragEndEvent,
} from '@dnd-kit/core'
import { ArrowDownIcon, ArrowUpIcon, DotsSixVerticalIcon } from '@phosphor-icons/react'
import type { Stage } from '@/api/client'
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
  assignStage,
  BOARD_STAGES,
  canAssign,
  columnId,
  columnName,
  columnOf,
  defaultLayout,
  MAX_COLUMNS,
  MAX_NAME,
  MIN_COLUMNS,
  moveColumn,
  saveLayout,
  type BoardColumnSetting,
} from '@/lib/boardColumns'
import { STAGE_LABEL } from '@/lib/labels'
import { cn } from '@/lib/utils'

/**
 * Elegir las columnas del Tablero: qué etapas junta cada una, en qué orden van y cómo se llaman.
 * Es una vista: no cambia la etapa de ninguna oferta.
 */
export function BoardColumnsDialog({
  open,
  layout,
  totals,
  onOpenChange,
}: {
  open: boolean
  layout: BoardColumnSetting[]
  /** Ofertas por etapa, para la vista previa. */
  totals: Partial<Record<Stage, number>>
  onOpenChange: (open: boolean) => void
}) {
  // Esc mientras se arrastra una columna cancela el arrastre, no cierra el diálogo con lo hecho.
  const dragging = useRef(false)
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-h-[90dvh] overflow-y-auto sm:max-w-2xl"
        onEscapeKeyDown={(event) => dragging.current && event.preventDefault()}
      >
        {open && (
          <ColumnsForm
            layout={layout}
            totals={totals}
            onDragging={(value) => (dragging.current = value)}
            onDone={() => onOpenChange(false)}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}

function ColumnRow({
  column,
  index,
  total,
  onName,
  onMove,
}: {
  column: BoardColumnSetting
  index: number
  total: number
  onName: (name: string) => void
  onMove: (to: number) => void
}) {
  const { t } = useTranslation('processes', { keyPrefix: 'columns' })
  const id = columnId(column)
  const { attributes, listeners, setNodeRef: dragRef, transform, isDragging } = useDraggable({ id })
  const { setNodeRef: dropRef, isOver } = useDroppable({ id })
  const n = index + 1
  const shown = columnName(column)
  return (
    <li
      ref={dropRef}
      className={cn(
        'flex items-center gap-2 rounded-lg border bg-card p-2',
        isOver && !isDragging && 'border-primary ring-1 ring-primary',
        isDragging && 'opacity-60',
      )}
      style={transform ? { transform: `translate3d(0, ${transform.y}px, 0)`, zIndex: 10 } : undefined}
    >
      <button
        type="button"
        ref={dragRef}
        {...listeners}
        {...attributes}
        aria-label={t('drag', { name: shown })}
        title={t('drag', { name: shown })}
        className="cursor-grab touch-none rounded p-1 text-muted-foreground hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none active:cursor-grabbing"
      >
        <DotsSixVerticalIcon className="size-4" weight="bold" />
      </button>
      <span className="w-5 shrink-0 text-center text-xs text-muted-foreground tabular-nums">{n}</span>
      <div className="grid min-w-0 flex-1 gap-1.5">
        <Input
          aria-label={t('name', { n })}
          value={column.name}
          maxLength={MAX_NAME}
          placeholder={columnName({ ...column, name: '' })}
          onChange={(e) => onName(e.target.value)}
          className="h-8"
        />
        <ul aria-label={t('stagesOf', { n })} className="flex flex-wrap gap-1">
          {column.stages.map((stage) => (
            <li key={stage} className="rounded-md bg-secondary px-1.5 py-0.5 text-xs text-secondary-foreground">
              {STAGE_LABEL[stage]}
            </li>
          ))}
        </ul>
      </div>
      <div className="flex flex-col">
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="size-7"
          aria-label={t('up', { name: shown })}
          title={t('up', { name: shown })}
          disabled={index === 0}
          onClick={() => onMove(index - 1)}
        >
          <ArrowUpIcon />
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="size-7"
          aria-label={t('down', { name: shown })}
          title={t('down', { name: shown })}
          disabled={index === total - 1}
          onClick={() => onMove(index + 1)}
        >
          <ArrowDownIcon />
        </Button>
      </div>
    </li>
  )
}

/** El Tablero en pequeño: cómo quedará con estas columnas. */
function Preview({ layout, totals }: { layout: BoardColumnSetting[]; totals: Partial<Record<Stage, number>> }) {
  const { t } = useTranslation('processes', { keyPrefix: 'columns' })
  return (
    <section aria-labelledby="board-columns-preview" className="grid gap-2">
      <h3 id="board-columns-preview" className="text-sm font-medium">
        {t('preview')}
      </h3>
      <ol className="grid gap-1.5 rounded-lg border bg-muted/40 p-2" style={{ gridTemplateColumns: `repeat(${layout.length}, minmax(0, 1fr))` }}>
        {layout.map((column) => {
          const count = column.stages.reduce((sum, stage) => sum + (totals[stage] ?? 0), 0)
          return (
            <li key={columnId(column)} className="grid content-start gap-1 rounded-md bg-background p-1.5">
              <p className="truncate text-xs font-medium" title={columnName(column)}>
                {columnName(column)}
              </p>
              <p className="text-[0.7rem] text-muted-foreground">{t('offers', { count })}</p>
              {/* Tantas tarjetas como ofertas, hasta tres. */}
              {Array.from({ length: Math.min(count, 3) }, (_, i) => (
                <span key={i} aria-hidden className="h-3 rounded-sm border bg-card" />
              ))}
            </li>
          )
        })}
      </ol>
    </section>
  )
}

function ColumnsForm({
  layout,
  totals,
  onDragging,
  onDone,
}: {
  layout: BoardColumnSetting[]
  totals: Partial<Record<Stage, number>>
  onDragging: (dragging: boolean) => void
  onDone: () => void
}) {
  const { t } = useTranslation('processes', { keyPrefix: 'columns' })
  const [draft, setDraft] = useState(layout)
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor),
  )
  const nameOf = (id: unknown) => {
    const column = draft.find((c) => columnId(c) === id)
    return column ? columnName(column) : ''
  }
  const positionOf = (id: unknown) => draft.findIndex((c) => columnId(c) === id) + 1
  const announcements: Announcements = {
    onDragStart: ({ active }) => t('dnd.start', { name: nameOf(active.id) }),
    onDragOver: ({ over }) => (over ? t('dnd.over', { n: positionOf(over.id) }) : undefined),
    onDragEnd: ({ active, over }) =>
      over ? t('dnd.end', { name: nameOf(active.id), n: positionOf(over.id) }) : t('dnd.cancel'),
    onDragCancel: () => t('dnd.cancel'),
  }

  const onDragEnd = ({ active, over }: DragEndEvent) => {
    // Después de que el diálogo vea la tecla: el Esc que cancela no debe cerrarlo.
    setTimeout(() => onDragging(false))
    if (!over) return
    const from = draft.findIndex((c) => columnId(c) === active.id)
    const to = draft.findIndex((c) => columnId(c) === over.id)
    if (from >= 0 && to >= 0) setDraft(moveColumn(draft, from, to))
  }

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

      <section aria-labelledby="board-columns-list" className="grid gap-2">
        <h3 id="board-columns-list" className="text-sm font-medium">
          {t('columnsTitle', { count: draft.length })}
        </h3>
        <DndContext
          sensors={sensors}
          onDragStart={() => onDragging(true)}
          onDragEnd={onDragEnd}
          onDragCancel={() => setTimeout(() => onDragging(false))}
          accessibility={{ announcements, screenReaderInstructions: { draggable: t('dnd.instructions') } }}
        >
          <ol className="grid gap-1.5">
            {draft.map((column, i) => (
              <ColumnRow
                key={columnId(column)}
                column={column}
                index={i}
                total={draft.length}
                onName={(name) => setDraft(draft.map((c, j) => (j === i ? { ...c, name } : c)))}
                onMove={(to) => setDraft(moveColumn(draft, i, to))}
              />
            ))}
          </ol>
        </DndContext>
      </section>

      <section aria-labelledby="board-columns-stages" className="grid gap-2">
        <h3 id="board-columns-stages" className="text-sm font-medium">
          {t('stagesTitle')}
        </h3>
        <p className="text-xs text-muted-foreground">{t('stagesHint', { min: MIN_COLUMNS, max: MAX_COLUMNS })}</p>
        <ul className="grid gap-1.5 sm:grid-cols-2">
          {BOARD_STAGES.map((stage) => {
            const current = columnOf(draft, stage)
            const selectId = `board-stage-${stage}`
            return (
              <li key={stage} className="flex items-center justify-between gap-2 rounded-md border px-2.5 py-1.5">
                <label htmlFor={selectId} className="text-sm">
                  {STAGE_LABEL[stage]}
                </label>
                <select
                  id={selectId}
                  value={String(current)}
                  onChange={(e) => {
                    const value = e.target.value
                    setDraft(assignStage(draft, stage, value === 'new' ? 'new' : Number(value)))
                  }}
                  className="h-8 max-w-[60%] rounded-md border border-input bg-background px-2 text-sm"
                >
                  {draft.map((column, i) => (
                    <option key={columnId(column)} value={i} disabled={!canAssign(draft, stage, i)}>
                      {t('inColumn', { n: i + 1, name: columnName(column) })}
                    </option>
                  ))}
                  <option value="new" disabled={!canAssign(draft, stage, 'new')}>
                    {t('newColumn')}
                  </option>
                </select>
              </li>
            )
          })}
        </ul>
      </section>

      <Preview layout={draft} totals={totals} />

      <DialogFooter className="gap-2 sm:justify-between">
        {/* Vuelve a las de siempre aquí; se aplica al guardar. */}
        <Button type="button" variant="ghost" onClick={() => setDraft(defaultLayout())}>
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
