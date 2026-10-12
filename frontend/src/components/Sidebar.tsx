import { useEffect, useState, type ComponentType } from 'react'
import { Link, useLocation } from 'react-router'
import {
  ChatsCircleIcon,
  DesktopIcon,
  FileTextIcon,
  FunnelIcon,
  GraduationCapIcon,
  HouseIcon,
  KanbanIcon,
  LightningIcon,
  ListChecksIcon,
  ListIcon,
  MoonIcon,
  PlugsConnectedIcon,
  RobotIcon,
  SidebarSimpleIcon,
  SunIcon,
  TrayIcon,
  UserCircleIcon,
  XIcon,
  type IconProps,
} from '@phosphor-icons/react'
import { Dialog as DialogPrimitive } from 'radix-ui'
import type { Stage } from '@/api/client'
import { useAgentRuns, useReplies, useStatus } from '@/api/queries'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { useTheme, type ThemeChoice } from '@/lib/theme'
import { cn } from '@/lib/utils'

// --- Recuentos --------------------------------------------------------------------------------

/** Lo que espera algo de ti en cada página. `strong`: te toca a ti; si no, es informativo. */
type Count = { value: number; strong: boolean; label: string }

function useStageCount(stage: Stage, label: string, strong = true): Count {
  const { data } = useStatus()
  return { value: data?.by_stage[stage] ?? 0, strong, label }
}

function useRepliesCount(): Count {
  const { data } = useReplies()
  return { value: data?.counts.proposed ?? 0, strong: true, label: 'por revisar' }
}

/** Ejecuciones en curso (fase 19), las que esperan una respuesta tuya y los encargos pendientes. */
function useAgentCount(): Count {
  const runs = useAgentRuns()
  const { data } = useStatus()
  const active = runs.data?.active ?? 0
  const waiting = runs.data?.runs.filter((r) => r.status === 'needs_user').length ?? 0
  const requests = data?.agent_requests ?? 0
  return { value: active + waiting + requests, strong: active + waiting > 0, label: 'en curso o pendientes' }
}

function CountBadge({ count }: { count: Count }) {
  if (!count.value) return null
  return (
    <span
      aria-hidden
      className={cn(
        'tabular ml-auto grid h-[18px] min-w-[18px] place-items-center rounded-full px-1 text-[0.7rem] font-semibold',
        count.strong ? 'bg-primary text-primary-foreground' : 'bg-foreground/10 text-foreground/80',
      )}
    >
      {count.value}
    </span>
  )
}

// --- Entradas -----------------------------------------------------------------------------------

type Entry = {
  to: string
  label: string
  icon: ComponentType<IconProps>
  end?: boolean
  useCount?: () => Count
  /** Otras rutas en las que esta entrada cuenta como la activa (la ficha de una oferta…). */
  alsoActive?: string[]
}

const usePendingTriage = () => useStageCount('pending_triage', 'por revisar')
const usePendingDetail = () => useStageCount('pending_detail', 'por completar', false)

const NAV_GROUPS: { title: string | null; entries: Entry[] }[] = [
  { title: null, entries: [{ to: '/', label: 'Inicio', icon: HouseIcon, end: true }] },
  {
    title: 'Búsqueda',
    entries: [
      { to: '/bandeja', label: 'Bandeja', icon: TrayIcon, alsoActive: ['/jobs/', '/nueva'] },
      { to: '/por-revisar', label: 'Por revisar', icon: ListChecksIcon, useCount: usePendingTriage },
      { to: '/alertas', label: 'Alertas', icon: LightningIcon, useCount: usePendingDetail },
    ],
  },
  {
    title: 'Procesos',
    entries: [
      { to: '/procesos', label: 'Procesos', icon: KanbanIcon },
      { to: '/respuestas', label: 'Respuestas', icon: ChatsCircleIcon, useCount: useRepliesCount },
    ],
  },
  {
    title: 'Análisis',
    entries: [
      { to: '/embudo', label: 'Embudo', icon: FunnelIcon },
      { to: '/skills', label: 'Skills', icon: GraduationCapIcon },
    ],
  },
  {
    title: 'Configurar',
    entries: [
      { to: '/fuentes', label: 'Fuentes', icon: PlugsConnectedIcon },
      { to: '/plantillas', label: 'Plantillas', icon: FileTextIcon },
      { to: '/perfil', label: 'Mi perfil', icon: UserCircleIcon },
      { to: '/agente', label: 'Agente', icon: RobotIcon, useCount: useAgentCount },
    ],
  },
]

const noCount = (): Count => ({ value: 0, strong: false, label: '' })

function NavEntry({ entry, collapsed, onNavigate }: { entry: Entry; collapsed: boolean; onNavigate?: () => void }) {
  const count = (entry.useCount ?? noCount)()
  const Icon = entry.icon
  const { pathname } = useLocation()
  const isActive =
    (entry.end ? pathname === entry.to : pathname === entry.to || pathname.startsWith(`${entry.to}/`)) ||
    (entry.alsoActive?.some((prefix) => pathname.startsWith(prefix)) ?? false)
  const link = (
    <Link
      to={entry.to}
      onClick={onNavigate}
      // El nombre completo, con lo que te espera: «Por revisar (3 por revisar)».
      aria-label={count.value ? `${entry.label} (${count.value} ${count.label})` : entry.label}
      aria-current={isActive ? 'page' : undefined}
      className={cn(
          'relative flex items-center gap-2.5 rounded-md text-sm transition-colors',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
          collapsed ? 'size-9 justify-center' : 'h-8 px-2.5',
          isActive
            ? 'bg-foreground/[0.07] font-medium text-foreground dark:bg-foreground/10'
            : 'text-muted-foreground hover:bg-foreground/[0.04] hover:text-foreground',
      )}
    >
      <Icon className="size-[18px] shrink-0" weight={isActive ? 'fill' : 'regular'} aria-hidden />
          {collapsed ? (
            count.value > 0 && (
              <span
                aria-hidden
                className={cn(
                  'absolute top-1.5 right-1.5 size-2 rounded-full',
                  count.strong ? 'bg-primary' : 'bg-foreground/40',
                )}
              />
            )
          ) : (
            <>
              <span className="truncate">{entry.label}</span>
              <CountBadge count={count} />
            </>
          )}
    </Link>
  )
  if (!collapsed) return link
  return (
    <Tooltip>
      <TooltipTrigger asChild>{link}</TooltipTrigger>
      <TooltipContent side="right">
        {entry.label}
        {count.value > 0 && ` · ${count.value}`}
      </TooltipContent>
    </Tooltip>
  )
}

export function NavLinks({ collapsed = false, onNavigate }: { collapsed?: boolean; onNavigate?: () => void }) {
  return (
    <nav aria-label="Navegación principal" className="grid gap-4">
      {NAV_GROUPS.map((group) => (
        <div key={group.title ?? 'inicio'} className="grid gap-0.5">
          {group.title &&
            (collapsed ? (
              <div className="mx-auto my-1 h-px w-5 bg-border" aria-hidden />
            ) : (
              // Etiqueta de la lista, no un encabezado: no compite con el título de cada página.
              <span
                aria-hidden
                className="px-2.5 pb-1 text-[0.7rem] font-semibold tracking-wider text-muted-foreground/80 uppercase"
              >
                {group.title}
              </span>
            ))}
          <ul className="grid gap-0.5" aria-label={group.title ?? undefined}>
            {group.entries.map((entry) => (
              <li key={entry.to}>
                <NavEntry entry={entry} collapsed={collapsed} onNavigate={onNavigate} />
              </li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  )
}

// --- Marca y tema -------------------------------------------------------------------------------

export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <Link to="/" className="flex items-center gap-2.5 font-semibold tracking-tight whitespace-nowrap">
      <span
        aria-hidden
        className="relative grid size-7 shrink-0 place-items-center rounded-md bg-foreground font-mono text-[11px] font-bold text-background"
      >
        CA
        <span className="absolute -right-0.5 -bottom-0.5 size-2 rounded-full bg-primary ring-2 ring-background" />
      </span>
      <span className={cn(compact && 'sr-only')}>CandidatAI</span>
    </Link>
  )
}

const THEME_META: Record<ThemeChoice, { icon: typeof SunIcon; label: string }> = {
  system: { icon: DesktopIcon, label: 'Tema: el del sistema' },
  light: { icon: SunIcon, label: 'Tema: claro' },
  dark: { icon: MoonIcon, label: 'Tema: oscuro' },
}

export function ThemeToggle({ withLabel = false }: { withLabel?: boolean }) {
  const { choice, cycle } = useTheme()
  const { icon: Icon, label } = THEME_META[choice]
  const button = (
    <Button
      variant="ghost"
      size={withLabel ? 'sm' : 'icon'}
      onClick={cycle}
      aria-label={withLabel ? undefined : label}
      className={cn(withLabel && 'w-full justify-start gap-2.5 px-2.5 font-normal text-muted-foreground')}
    >
      <Icon className="size-[18px]" />
      {withLabel && label}
    </Button>
  )
  if (withLabel) return button
  return (
    <Tooltip>
      <TooltipTrigger asChild>{button}</TooltipTrigger>
      <TooltipContent side="right">{label}</TooltipContent>
    </Tooltip>
  )
}

// --- Barra lateral (escritorio) -----------------------------------------------------------------

const COLLAPSED_KEY = 'cai-sidebar-collapsed'

function readCollapsed(): boolean {
  try {
    return localStorage.getItem(COLLAPSED_KEY) === '1'
  } catch {
    return false
  }
}

function writeCollapsed(value: boolean) {
  try {
    localStorage.setItem(COLLAPSED_KEY, value ? '1' : '0')
  } catch {
    // Sin almacenamiento (ventana privada…): se recuerda solo mientras dure la página.
  }
}

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(readCollapsed)
  const toggle = () => {
    const next = !collapsed
    setCollapsed(next)
    writeCollapsed(next)
  }
  return (
    <aside
      aria-label="Barra lateral"
      className={cn(
        'sticky top-0 hidden h-[100dvh] shrink-0 flex-col border-r bg-card transition-[width] duration-200 lg:flex',
        collapsed ? 'w-16 items-center px-2' : 'w-60 px-3',
      )}
    >
      <div className={cn('flex h-14 shrink-0 items-center', collapsed ? 'justify-center' : 'px-1.5')}>
        <Brand compact={collapsed} />
      </div>
      <div className="-mx-1 flex-1 overflow-y-auto px-1 py-2">
        <NavLinks collapsed={collapsed} />
      </div>
      <div className={cn('grid shrink-0 gap-0.5 border-t py-3', collapsed ? 'justify-items-center' : '')}>
        <ThemeToggle withLabel={!collapsed} />
        <SidebarButton collapsed={collapsed} onClick={toggle} />
      </div>
    </aside>
  )
}

function SidebarButton({ collapsed, onClick }: { collapsed: boolean; onClick: () => void }) {
  const label = collapsed ? 'Desplegar el menú' : 'Plegar el menú'
  const button = (
    <Button
      variant="ghost"
      size={collapsed ? 'icon' : 'sm'}
      onClick={onClick}
      aria-label={collapsed ? label : undefined}
      aria-expanded={!collapsed}
      className={cn(!collapsed && 'w-full justify-start gap-2.5 px-2.5 font-normal text-muted-foreground')}
    >
      <SidebarSimpleIcon className="size-[18px]" />
      {!collapsed && label}
    </Button>
  )
  if (!collapsed) return button
  return (
    <Tooltip>
      <TooltipTrigger asChild>{button}</TooltipTrigger>
      <TooltipContent side="right">{label}</TooltipContent>
    </Tooltip>
  )
}

// --- Cajón (móvil) ------------------------------------------------------------------------------

export function MobileNav() {
  const [open, setOpen] = useState(false)
  const { pathname } = useLocation()
  // Cualquier navegación (un enlace, la marca, el botón Atrás) cierra el cajón.
  const [openedAt, setOpenedAt] = useState(pathname)
  if (open && pathname !== openedAt) {
    setOpen(false)
    setOpenedAt(pathname)
  }
  // Si la ventana pasa a escritorio con el cajón abierto, se cierra: ahí ya está la barra.
  useEffect(() => {
    if (!open || typeof matchMedia !== 'function') return
    const desktop = matchMedia('(min-width: 1024px)')
    const close = () => desktop.matches && setOpen(false)
    desktop.addEventListener?.('change', close)
    return () => desktop.removeEventListener?.('change', close)
  }, [open])
  return (
    <DialogPrimitive.Root
      open={open}
      onOpenChange={(next) => {
        setOpen(next)
        setOpenedAt(pathname)
      }}
    >
      <DialogPrimitive.Trigger asChild>
        <Button variant="ghost" size="icon" aria-label="Abrir el menú" className="lg:hidden">
          <ListIcon className="size-5" />
        </Button>
      </DialogPrimitive.Trigger>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-40 bg-black/40 data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=closed]:animate-out data-[state=closed]:fade-out-0" />
        <DialogPrimitive.Content
          aria-describedby={undefined}
          className="fixed inset-y-0 left-0 z-50 flex w-72 max-w-[85vw] flex-col border-r bg-background px-3 shadow-xl data-[state=open]:animate-in data-[state=open]:slide-in-from-left data-[state=closed]:animate-out data-[state=closed]:slide-out-to-left"
        >
          <div className="flex h-14 shrink-0 items-center justify-between px-1.5">
            <DialogPrimitive.Title asChild>
              <span>
                <Brand />
              </span>
            </DialogPrimitive.Title>
            <DialogPrimitive.Close asChild>
              <Button variant="ghost" size="icon" aria-label="Cerrar el menú">
                <XIcon className="size-5" />
              </Button>
            </DialogPrimitive.Close>
          </div>
          <div className="flex-1 overflow-y-auto py-2">
            <NavLinks onNavigate={() => setOpen(false)} />
          </div>
          <div className="border-t py-3">
            <ThemeToggle withLabel />
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  )
}
