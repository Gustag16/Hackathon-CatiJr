"""Dados da sala para o consumer do WebSocket (Bortoleto). Contrato, seção 5.

O consumer não deve montar JSON de leilão por conta própria (é fácil vazar o id do líder).
Ele chama estas funções, de dentro do consumer assíncrono, com
`await database_sync_to_async(room_snapshot)(auction_id, user)`.
"""

from auctions.models import Auction, AuctionParticipant, Bid
from auctions.serializers import auction_result, auction_state, bid_json, jsonable

from . import clock

RECENT_BIDS = 10


def room_snapshot(auction_id, user) -> dict:
    """Mensagem `snapshot`: enviada ao conectar e a cada `resync`.

    Levanta `Auction.DoesNotExist` se o leilão não existe (o consumer fecha com 4404).
    """
    auction = Auction.objects.select_related("leader__user").get(id=auction_id)
    now = clock.now()
    you = AuctionParticipant.objects.filter(auction=auction, user=user).first()
    recent = (
        Bid.objects.filter(auction=auction)
        .select_related("participant__user")
        .order_by("-created_at", "-amount_cents")[:RECENT_BIDS]
    )
    return jsonable(
        {
            "type": "snapshot",
            "auction": auction_state(auction, now),
            "you": {"participant_number": you.number if you else None},
            "recent_bids": [bid_json(b) for b in recent],
            "result": auction_result(auction),
            "server_time": now,
        }
    )
