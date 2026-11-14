import type { ButtonHTMLAttributes, ReactNode } from 'react'
import type { AuctionStatus } from '../../utils/interfaces/auctionInterface'

export function Icon({
  name,
  className = '',
}: {
  name: string
  className?: string
}) {
  const paths: Record<string, ReactNode> = {
    bolt: <path d="m13 2-9 12h7l-1 8 10-13h-7l0-7Z" />,
    arrow: <path d="M5 12h14m-6-6 6 6-6 6" />,
    search: (
      <>
        <circle cx="10.5" cy="10.5" r="6.5" />
        <path d="m16 16 4 4" />
      </>
    ),
    clock: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v5l3 2" />
      </>
    ),
    hammer: (
      <>
        <path d="m14 4 6 6-3 3-6-6 3-3ZM4 20l10-10M3 21h8M9 6l3-3m5 11 3-3" />
      </>
    ),
    shield: (
      <>
        <path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3Z" />
        <path d="m8 12 3 3 5-6" />
      </>
    ),
    plus: <path d="M12 5v14M5 12h14" />,
    chevron: <path d="m9 5 7 7-7 7" />,
    user: (
      <>
        <circle cx="12" cy="8" r="3" />
        <path d="M5 21v-3a7 7 0 0 1 14 0v3" />
      </>
    ),
    grid: (
      <>
        <rect x="3" y="3" width="7" height="7" rx="1" />
        <rect x="14" y="3" width="7" height="7" rx="1" />
        <rect x="3" y="14" width="7" height="7" rx="1" />
        <rect x="14" y="14" width="7" height="7" rx="1" />
      </>
    ),
    list: <path d="M8 6h13M8 12h13M8 18h13M3 6h1M3 12h1M3 18h1" />,
    check: <path d="m5 12 4 4L19 6" />,
  }

  return (
    <svg
      className={`h-5 w-5 shrink-0 ${className}`}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name] || paths['hammer']}
    </svg>
  )
}

export function Button({
  variant = 'primary',
  className = '',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'outline' | 'ghost' | 'danger'
}) {
  return (
    <button
      {...props}
      className={`app-button button-${variant} ${className}`}
    />
  )
}

export function StatusBadge({ status }: { status: AuctionStatus }) {
  const labels: Record<AuctionStatus, string> = {
    running: 'AO VIVO',
    scheduled: 'AGENDADO',
    sold: 'ARREMATADO',
    ended_no_bids: 'SEM LANCES',
    cancelled: 'CANCELADO',
  }

  return (
    <span className={`status-badge status-${status}`}>
      {status === 'running' && <span className="live-dot animate-pulse" />}
      {labels[status]}
    </span>
  )
}

export function Notice({ children }: { children: ReactNode }) {
  return (
    <div
      role="status"
      className="rounded-md border border-primary/25 bg-warning-soft p-3 text-xs leading-relaxed"
    >
      {children}
    </div>
  )
}
