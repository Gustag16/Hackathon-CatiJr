"""Formato JSON dos leilões (contrato, seção 2). Funções simples, sem mágica do DRF.

Nada aqui expõe líder nem lances: isso é conteúdo da sala (login, etapa 2). A exceção é o
`result` de um leilão VENDIDO, que mostra o rótulo anônimo do vencedor (RF09: "ao final,
todos veem o resultado").
"""

from datetime import datetime

from accounts.serializers import public_user_json

from .models import Auction, AuctionStatus


def _photos(auction: Auction) -> list:
    # `.all()` usa o prefetch das views (sem consulta extra por leilão).
    return list(auction.item.photos.all())


def auction_summary(auction: Auction) -> dict:
    """AuctionSummary: cartão da listagem."""
    photos = _photos(auction)
    return {
        "id": str(auction.id),
        "item_id": str(auction.item_id),
        "name": auction.item.name,
        "category": auction.item.category,
        "cover_photo_url": photos[0].file.url if photos else None,
        "status": auction.status,
        "starts_at": auction.starts_at,
        "ends_at": auction.ends_at,
        "current_price_cents": auction.current_price_cents,
        "bid_count": auction.bid_count,
        "seller": public_user_json(auction.item.seller),
    }


def auction_public(auction: Auction, now: datetime) -> dict:
    """AuctionPublic: estado que qualquer visitante pode ver."""
    return {
        "id": str(auction.id),
        "item_id": str(auction.item_id),
        "status": auction.status,
        "starts_at": auction.starts_at,
        "ends_at": auction.ends_at,
        "original_ends_at": auction.original_ends_at,
        "current_price_cents": auction.current_price_cents,
        "min_next_bid_cents": auction.min_next_bid_cents,
        "bid_count": auction.bid_count,
        "server_time": now,
    }


def auction_result(auction: Auction) -> dict | None:
    if auction.status == AuctionStatus.SOLD:
        return {
            "status": auction.status,
            "winner_label": auction.leader.label,
            "final_price_cents": auction.highest_bid_cents,
        }
    if auction.status == AuctionStatus.ENDED_NO_BIDS:
        return {"status": auction.status, "winner_label": None, "final_price_cents": None}
    return None  # ainda não terminou, ou foi cancelado (o próprio status já diz)


def auction_detail(auction: Auction, now: datetime) -> dict:
    """AuctionDetail = AuctionSummary + AuctionPublic + descrição, fotos, preço e resultado."""
    return {
        **auction_summary(auction),
        **auction_public(auction, now),
        "description": auction.item.description,
        "photos": [{"id": str(p.id), "url": p.file.url} for p in _photos(auction)],
        "start_price_cents": auction.start_price_cents,
        "result": auction_result(auction),
    }
