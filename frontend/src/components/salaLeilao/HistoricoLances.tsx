import { formatBidderLabel, money } from '../../utils/auctionRules'
import type { Bid } from '../../utils/interfaces/bidInterface'

export function HistoricoLances({
  loggedIn,
  bids,
}: {
  loggedIn: boolean
  bids: Bid[]
}) {
  return (
    <>
      <h2 className="mb-4 mt-8 text-lg font-extrabold">Últimos lances</h2>
      {!loggedIn ? (
        <p className="text-sm text-muted-foreground">
          Entre para acompanhar os lances em tempo real.
        </p>
      ) : bids.length === 0 ? (
        <p className="text-sm text-muted-foreground">Aguardando lances.</p>
      ) : (
        <ol className="divide-y divide-border">
          {bids.map((b) => (
            <li
              key={b.id}
              className="flex items-center justify-between py-4 text-xs"
            >
              <div>
                <span className="font-bold">{formatBidderLabel(b)}</span>
                <p className="mt-1 text-muted-foreground">
                  {new Date(b.created_at).toLocaleTimeString('pt-BR')}
                </p>
              </div>
              <span className="font-extrabold">{money(b.amount_cents)}</span>
            </li>
          ))}
        </ol>
      )}
    </>
  )
}
