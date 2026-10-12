import { useState, type ReactNode } from 'react'
import { Link } from 'react-router'
import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type Announcements,
  type DragEndEvent,
  type DragStartEvent,
} from '@dnd-kit/core'
import {
  ArrowsLeftRightIcon,
  BellRingingIcon,
  CalendarBlankIcon,
  CalendarPlusIcon,
  DownloadSimpleIcon,
  KanbanIcon,
} from '@phosphor-icons/react'
import { fileUrls, type BoardCard, type BoardMove, type Stage, type UpcomingItem } from '@/api/client'
import { useBoard, useFollowups, useUpcoming } from '@/api/queries'
import { AgentButton } from '@/components/AgentButton'
import { ScoreBadge } from '@/components/MatchDetails'
import { CopyButton } from '@/components/CopyButton'
import { MoveDialog } from '@/components/MoveDialog'
import { ReceivedOffersComparison } from '@/components/ReceivedOffersComparison'
import { EmptyState, ErrorState } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Skeleton } from '@/components/ui/skeleton'
import { eventLabel, STAGE_LABEL, UPCOMING_KIND_LABEL } from '@/lib/labels'
import { moveOptions, noMoveReason, type MoveOption } from '@/lib/moves'
import { formatWhen } from '@/lib/time'
import { cn } from '@/lib/utils'

const COLUMN_HINT: Partial<Record<Stage, string>> = {
  approved: 'Falta el CV',
  cv_ready: 'Lista para enviar',
  applied: 'Esperando respuesta',
  in_process: 'Entrevistas y pruebas',
  closed: 'Recientes',
}

// --- Tarjeta --------------------------------------------------------------------------------

function CardBody({ card, onMove }: { card: BoardCard; onMove?: () => void }) {
  return (
    <>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <Link
            to={`/jobs/${card.job_id}`}
            className="line-clamp-2 text-sm leading-snug font-medium hover:underline hover:underline-offset-4"
            onPointerDown={(e) => e.stopPropagation()}
          >
            {card.title}
          </Link>
          <p className="mt-0.5 truncate text-xs text-muted-foreground">{card.company}</p>
        </div>
        {card.score != null && <ScoreBadge score={card.score} className="shrink-0" />}
      </div>
      {(card.next_milestone || card.followup_due || card.closed_by) && (
        <div className="mt-2.5 flex flex-wrap gap-1.5 text-xs">
          {card.next_milestone && (
            <span className="inline-flex items-center gap-1 rounded bg-accent px-1.5 py-0.5 text-accent-foreground">
              <CalendarBlankIcon className="size-3.5" />
              {formatWhen(card.next_milestone.starts_at, card.next_milestone.all_day)}
            </span>
          )}
          {card.followup_due && (
            <span className="inline-flex items-center gap-1 rounded bg-primary/10 px-1.5 py-0.5 font-medium text-primary">
              <BellRingingIcon className="size-3.5" />
              Seguimiento · {card.days_waiting} días
            </span>
          )}
          {card.closed_by && (
            <span className="rounded bg-muted px-1.5 py-0.5 text-muted-foreground">{eventLabel(card.closed_by)}</span>
          )}
        </div>
      )}
      {onMove && (
        <button
          type="button"
          onClick={onMove}
          onPointerDown={(e) => e.stopPropagation()}
          className="mt-2.5 inline-flex items-center gap-1.5 rounded-md border border-input bg-background px-2.5 py-1 text-xs font-medium hover:bg-accent hover:text-accent-foreground"
          aria-label={`Actualizar estado de «${card.title}»`}
        >
          <ArrowsLeftRightIcon className="size-3.5" />
          Actualizar estado
        </button>
      )}
    </>
  )
}

function DraggableCard({ card, onMove }: { card: BoardCard; onMove: () => void }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: card.job_id,
    data: { card },
  })
  return (
    <li
      ref={setNodeRef}
      {...attributes}
      {...listeners}
      aria-roledescription="tarjeta arrastrable"
      className={cn(
        'cursor-grab touch-none rounded-lg border bg-card p-3 shadow-xs outline-none transition-shadow focus-visible:ring-[3px] focus-visible:ring-ring/50 active:cursor-grabbing',
        isDragging && 'opacity-40',
      )}
    >
      <CardBody card={card} onMove={onMove} />
    </li>
  )
}

// --- Columnas -------------------------------------------------------------------------------

function Column({
  stage,
  total,
  children,
  empty,
}: {
  stage: Stage
  total: number
  children: ReactNode
  empty: boolean
}) {
  const { setNodeRef, isOver } = useDroppable({ id: stage })
  return (
    <section
      ref={setNodeRef}
      aria-label={STAGE_LABEL[stage]}
      className={cn(
        'flex w-[17rem] shrink-0 flex-col rounded-xl border bg-muted/40 p-2 transition-colors lg:w-auto',
        isOver && 'border-primary/50 bg-accent/60',
      )}
    >
      <header className="flex items-baseline justify-between px-1.5 pt-1 pb-2.5">
        <div>
          <h2 className="text-sm font-semibold">{STAGE_LABEL[stage]}</h2>
          <p className="text-xs text-muted-foreground">{COLUMN_HINT[stage]}</p>
        </div>
        <span className="tabular text-xs font-medium text-muted-foreground">{total}</span>
      </header>
      {empty ? (
        <p className="rounded-lg border border-dashed px-3 py-6 text-center text-xs text-muted-foreground">Vacía</p>
      ) : (
        <ul className="flex flex-col gap-2">{children}</ul>
      )}
    </section>
  )
}

const ANNOUNCEMENTS: Announcements = {
  onDragStart: ({ active }) => `Has cogido «${(active.data.current?.card as BoardCard | undefined)?.title ?? ''}».`,
  onDragOver: ({ over }) => (over ? `Sobre la columna «${STAGE_LABEL[over.id as Stage]}».` : 'Fuera de las columnas.'),
  onDragEnd: ({ over }) =>
    over ? `Soltada en «${STAGE_LABEL[over.id as Stage]}». Confirma el evento en el diálogo.` : 'Soltada sin moverla.',
  onDragCancel: () => 'Movimiento cancelado.',
}

function Board({ columns, moves }: { columns: { stage: Stage; cards: BoardCard[]; total: number }[]; moves: BoardMove[] }) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor),
  )
  const [dragging, setDragging] = useState<BoardCard | null>(null)
  const [moving, setMoving] = useState<{ card: BoardCard; options: MoveOption[] } | null>(null)
  const [refused, setRefused] = useState<string | null>(null)

  const openMove = (card: BoardCard, target?: Stage) => {
    const options = moveOptions(card, moves, target)
    if (options.length === 0) {
      setRefused(target ? noMoveReason(card, target) : 'Esta oferta no tiene movimientos posibles desde aquí.')
      return
    }
    setRefused(null)
    setMoving({ card, options })
  }

  const onDragStart = (e: DragStartEvent) => setDragging((e.active.data.current?.card as BoardCard) ?? null)
  const onDragEnd = (e: DragEndEvent) => {
    setDragging(null)
    const card = e.active.data.current?.card as BoardCard | undefined
    const target = e.over?.id as Stage | undefined
    if (card && target && target !== card.stage) openMove(card, target)
  }

  return (
    <>
      {refused && (
        <p role="alert" className="mb-3 rounded-lg border bg-card px-4 py-2.5 text-sm">
          La tarjeta vuelve a su sitio. {refused}
        </p>
      )}
      <DndContext
        sensors={sensors}
        onDragStart={onDragStart}
        onDragEnd={onDragEnd}
        onDragCancel={() => setDragging(null)}
        accessibility={{
          announcements: ANNOUNCEMENTS,
          screenReaderInstructions: {
            draggable:
              'Pulsa espacio para coger la tarjeta, muévela con las flechas y suéltala con espacio. Esc cancela. También puedes usar «Mover».',
          },
        }}
      >
        <div className="-mx-4 overflow-x-auto px-4 pb-2 sm:mx-0 sm:px-0">
          <div className="flex min-w-max gap-3 lg:grid lg:min-w-0 lg:grid-cols-5">
            {columns.map((column) => (
              <Column key={column.stage} stage={column.stage} total={column.total} empty={column.cards.length === 0}>
                {column.cards.map((card) => (
                  <DraggableCard key={card.job_id} card={card} onMove={() => openMove(card)} />
                ))}
              </Column>
            ))}
          </div>
        </div>
        <DragOverlay>
          {dragging && (
            <div className="w-[16rem] rotate-1 rounded-lg border bg-card p-3 shadow-lg">
              <CardBody card={dragging} />
            </div>
          )}
        </DragOverlay>
      </DndContext>
      <MoveDialog
        card={moving?.card ?? null}
        options={moving?.options ?? []}
        onOpenChange={(open) => !open && setMoving(null)}
      />
    </>
  )
}

// --- Próximos y calendario ------------------------------------------------------------------

function UpcomingList({ items }: { items: UpcomingItem[] }) {
  if (items.length === 0) return <p className="text-sm text-muted-foreground">Nada en los próximos 7 días.</p>
  return (
    <ul className="divide-y">
      {items.map((item) => (
        <li key={`${item.kind}-${item.milestone_id ?? item.job_id}`} className="flex items-baseline gap-3 py-2 text-sm">
          <span className="tabular w-36 shrink-0 text-muted-foreground">{formatWhen(item.starts_at, item.all_day)}</span>
          <span className="min-w-0 flex-1">
            <span className="font-medium">{item.title !== UPCOMING_KIND_LABEL[item.kind] ? item.title : UPCOMING_KIND_LABEL[item.kind]}</span>
            {' · '}
            <Link to={`/jobs/${item.job_id}`} className="text-muted-foreground hover:text-foreground hover:underline">
              {item.job_title} ({item.company})
            </Link>
          </span>
        </li>
      ))}
    </ul>
  )
}

function CalendarHelp() {
  return (
    <Collapsible>
      <CollapsibleTrigger className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
        <CalendarPlusIcon className="size-4" />
        Llevar los hitos a tu calendario
      </CollapsibleTrigger>
      <CollapsibleContent className="mt-3 space-y-3 rounded-xl border bg-card p-4 text-sm leading-relaxed">
        <p>
          <span className="font-medium">Google Calendar:</span> descarga el fichero e impórtalo (Configuración →
          Importar y exportar). Google no puede suscribirse a una dirección de tu equipo, así que vuelve a
          importarlo cuando cambien tus hitos: los eventos se actualizan, no se duplican.
        </p>
        <p>
          <span className="font-medium">Outlook, Apple Calendar o Thunderbird:</span> suscríbete a esta dirección
          (se actualiza sola mientras <code className="font-mono text-[0.85em]">cai serve</code> esté en marcha):
        </p>
        <code className="block rounded bg-muted px-2 py-1.5 font-mono text-xs break-all">{fileUrls.calendarFeed}</code>
        <div className="flex flex-wrap gap-2">
          <Button asChild size="sm">
            <a href={fileUrls.calendarDownload} download>
              <DownloadSimpleIcon />
              Descargar .ics
            </a>
          </Button>
          <CopyButton text={fileUrls.calendarFeed} label="Copiar dirección" />
        </div>
      </CollapsibleContent>
    </Collapsible>
  )
}

function BoardSkeleton() {
  return (
    <div className="flex gap-3 lg:grid lg:grid-cols-5">
      {Array.from({ length: 5 }, (_, i) => (
        <Skeleton key={i} className="h-64 w-[17rem] shrink-0 rounded-xl lg:w-auto" />
      ))}
    </div>
  )
}

export function ProcessesPage() {
  const board = useBoard()
  const upcoming = useUpcoming(7)
  const followups = board.data?.columns.flatMap((c) => c.cards).filter((c) => c.followup_due).length ?? 0
  const empty = board.data?.columns.every((c) => c.cards.length === 0)
  const thanks = useFollowups().data?.thanks_due?.length ?? 0

  return (
    <div className="animate-in fade-in duration-300">
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Procesos</h1>
          <p className="mt-1.5 max-w-[65ch] text-sm leading-relaxed text-muted-foreground">
            Pulsa «Actualizar estado» en una tarjeta (o arrástrala de columna) para registrar lo que ha
            pasado: una respuesta, una entrevista, un rechazo… Nada cambia de columna sin su evento. Las
            entrevistas y pruebas crean su hito con fecha.
          </p>
        </div>
        {(followups > 0 || thanks > 0) && (
          <div className="flex shrink-0 flex-col items-start gap-2 sm:items-end">
            <p className="inline-flex items-center gap-1.5 rounded-lg bg-primary/10 px-3 py-1.5 text-sm font-medium text-primary">
              <BellRingingIcon className="size-4" weight="duotone" />
              {[
                followups === 1 ? '1 seguimiento pendiente' : followups ? `${followups} seguimientos pendientes` : null,
                thanks === 1 ? '1 entrevista por agradecer' : thanks ? `${thanks} entrevistas por agradecer` : null,
              ]
                .filter(Boolean)
                .join(' · ')}
            </p>
            {/* El agente redacta los borradores en la ficha de cada oferta; la app no envía nada. */}
            <AgentButton action="redactar-seguimientos">Redactar borradores</AgentButton>
          </div>
        )}
      </div>

      {board.isPending ? (
        <BoardSkeleton />
      ) : board.isError ? (
        <ErrorState error={board.error} onRetry={() => board.refetch()} />
      ) : empty ? (
        <EmptyState icon={<KanbanIcon className="size-7" weight="duotone" />} title="Aún no hay procesos">
          Aparecen aquí las ofertas que apruebas en <Link to="/por-revisar" className="underline underline-offset-4">Por revisar</Link>.
        </EmptyState>
      ) : (
        <Board columns={board.data.columns} moves={board.data.moves} />
      )}

      <ReceivedOffersComparison />

      <div className="mt-10 grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <section className="rounded-xl border bg-card p-5 sm:p-6" aria-label="Próximos 7 días">
          <h2 className="mb-3 font-medium">Próximos 7 días</h2>
          {upcoming.isPending ? (
            <Skeleton className="h-16" />
          ) : upcoming.isError ? (
            <ErrorState error={upcoming.error} onRetry={() => upcoming.refetch()} />
          ) : (
            <UpcomingList items={upcoming.data.items} />
          )}
        </section>
        <div>
          <CalendarHelp />
        </div>
      </div>
    </div>
  )
}
