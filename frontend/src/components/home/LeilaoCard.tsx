import { bidsLabel, categoryLabel, money } from '../../utils/auctionRules'
import type { Auction } from '../../utils/interfaces/auctionInterface'
import { Link } from '../common/Router'
import { Icon, StatusBadge } from '../common/Ui'
import { Cronometro } from '../salaLeilao/Cronometro'

export function LeilaoCard({
  auction: a,
  first,
}: {
  auction: Auction
  first: boolean
}) {
  return (
    <article className="auction-card">
      <Link
        to="/auctions/$id"
        params={{ id: a.id }}
        className="relative block aspect-[4/3] overflow-hidden bg-muted"
      >
        <img
          src={a.cover_photo_url}
          alt={a.name}
          loading={first ? 'eager' : 'lazy'}
          width={1024}
          height={768}
          className="h-full w-full object-cover"
        />
        <div className="absolute left-3 top-3">
          <StatusBadge status={a.status} />
        </div>
        <span className="absolute right-3 top-3 rounded bg-white px-2.5 py-1 text-[10px] font-bold text-slate-900 shadow-sm">
          {categoryLabel(a.category)}
        </span>
      </Link>
      <div className="p-4">
        <Link
          to="/auctions/$id"
          params={{ id: a.id }}
          className="card-title text-sm font-extrabold"
          title={a.name}
        >
          {a.name}
        </Link>
        <div className="mt-1 flex items-center gap-1.5 text-[10px] text-muted-foreground">
          <Icon name="user" className="h-3 w-3" />
          {a.seller.display_name}
        </div>
        <div className="mt-4 border-b border-border pb-3">
          <Cronometro
            end={a.status === 'scheduled' ? a.starts_at : a.ends_at}
            status={a.status}
          />
        </div>
        <div className="mt-4 flex items-end justify-between">
          <div>
            <span className="text-[10px] text-muted-foreground">
              {a.bid_count === 0 ? 'Lance inicial' : 'Atual'}
            </span>
            <p className="mt-1 text-xl font-extrabold">
              {money(a.current_price_cents)}
            </p>
          </div>
          <span className="mb-1 flex items-center gap-1 text-[10px] text-muted-foreground">
            <Icon name="hammer" className="h-3 w-3" />
            {bidsLabel(a.bid_count)}
          </span>
        </div>
        <Link
          to="/auctions/$id"
          params={{ id: a.id }}
          className="app-button button-outline mt-4 w-full justify-between"
        >
          {a.status === 'scheduled' ? 'Ver leilão' : 'Participar do leilão'}
          <Icon name="arrow" className="h-4 w-4" />
        </Link>
      </div>
    </article>
  )
}
