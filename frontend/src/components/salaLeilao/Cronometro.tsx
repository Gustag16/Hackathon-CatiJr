import { useEffect, useState } from 'react'
import { getOffset } from '../../api/api'
import { remaining } from '../../utils/auctionRules'
import type { AuctionStatus } from '../../utils/interfaces/auctionInterface'
import { Icon } from '../common/Ui'

export function Cronometro({
  end,
  status,
  large = false,
}: {
  end: string
  status: AuctionStatus
  large?: boolean
}) {
  const [ms, setMs] = useState<number | null>(null)

  useEffect(() => {
    const tick = () => setMs(remaining(end, getOffset()))
    tick()
    const timer = setInterval(tick, 1000)
    return () => clearInterval(timer)
  }, [end])

  const s = Math.floor((ms || 0) / 1000)
  const d = Math.floor(s / 86400)
  const h = Math.floor((s % 86400) / 3600)
  const m = Math.floor((s % 3600) / 60)
  const pad = (n: number) => String(n).padStart(2, '0')
  // O relógio do navegador é só visual: ao zerar, quem muda o status é o servidor.
  const waiting = ms === 0 && (status === 'running' || status === 'scheduled')
  const text =
    ms === null
      ? '-- : -- : --'
      : waiting
        ? status === 'running'
          ? 'Encerrando…'
          : 'Abrindo…'
        : `${d > 0 ? `${d}d ` : ''}${pad(h)} : ${pad(m)} : ${pad(s % 60)}`

  return (
    <div
      className={`flex items-center gap-2 rounded py-2 ${
        ms !== null && ms > 0 && ms < 120000 && status === 'running'
          ? 'urgent px-2'
          : 'text-muted-foreground'
      } ${large ? 'text-3xl' : 'text-xs'}`}
    >
      <Icon name="clock" className={large ? 'h-6 w-6' : 'h-4 w-4'} />
      <span className="font-mono font-semibold tabular-nums">{text}</span>
      {!large && !waiting && (
        <span className="ml-auto text-[10px] font-normal">
          {status === 'scheduled' ? 'para começar' : 'restantes'}
        </span>
      )}
    </div>
  )
}
