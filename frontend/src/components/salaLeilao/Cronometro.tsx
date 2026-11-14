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
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const text =
    ms === null
      ? '-- : -- : --'
      : `${String(h).padStart(2, '0')} : ${String(m).padStart(2, '0')} : ${String(s % 60).padStart(2, '0')}`

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
      {!large && (
        <span className="ml-auto text-[10px] font-normal">
          {status === 'scheduled' ? 'para começar' : 'restantes'}
        </span>
      )}
    </div>
  )
}
