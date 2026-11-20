/**
 * El logo de un agente, en una baldosa blanca (como en la web del proyecto) para que se vea igual
 * en los dos temas. Son marcas de sus dueños (set «logos» de Iconify) y solo dicen con qué agente
 * trabaja la app. Sin logo, el robot.
 */
import { RobotIcon } from '@phosphor-icons/react'
import antigravity from '@/assets/agents/antigravity.svg'
import claude from '@/assets/agents/claude-code.svg'
import codex from '@/assets/agents/codex.svg'
import opencode from '@/assets/agents/opencode.svg'
import qwen from '@/assets/agents/qwen.svg'
import { cn } from '@/lib/utils'

const LOGOS: Record<string, string> = { claude, codex, antigravity, opencode, qwen }

export function AgentLogo({ name, className }: { name: string | null | undefined; className?: string }) {
  const src = name ? LOGOS[name] : undefined
  return (
    <span
      aria-hidden
      className={cn('grid size-9 shrink-0 place-items-center rounded-lg bg-white shadow-[inset_0_0_0_1px_rgb(13_27_26/0.1)]', className)}
    >
      {src ? (
        <img src={src} alt="" className="size-[65%] object-contain" />
      ) : (
        <RobotIcon className="size-[60%] text-neutral-500" weight="duotone" />
      )}
    </span>
  )
}
