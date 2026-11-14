"""Motor de lances (RF10 a RF15). Contrato, seção 4.

Tudo acontece dentro de UMA transação, com a linha do leilão travada (`select_for_update`).
Enquanto um lance está sendo processado, nenhum outro lance, cancelamento ou fechamento
toca no mesmo leilão: eles esperam na fila da trava. É isso que garante o RF11.
"""

import uuid
from dataclasses import dataclass

from django.db import transaction

from auctions.models import Auction, AuctionParticipant, AuctionStatus, Bid
from auctions.rules.extension import extended_ends_at, was_extended
from auctions.serializers import auction_state, bid_json

from . import clock
from .broadcast import announce_after_commit

REFUSALS = {
    "AUCTION_NOT_RUNNING": "Este leilão não está em andamento.",
    "AUCTION_ENDED": "O leilão já terminou (horário do servidor).",
    "IS_SELLER": "Você não pode dar lance no seu próprio leilão.",
    "IS_LEADER": "Você já é o líder deste leilão.",
    "BID_TOO_LOW": "Lance abaixo do mínimo atual.",
}


@dataclass(frozen=True)
class BidOutcome:
    """Resposta HTTP já pronta para a view devolver.

    status_code: 201 (aceito), 409 (recusa de negócio) ou 422 (IDEMPOTENCY_KEY_MISMATCH).
    body: corpo do contrato. 201 -> {bid, auction, you}; 409 -> {code, message, auction
          [, min_bid_cents]}; 422 -> {code, message}.
    replay: True quando é reenvio da mesma chave (vira o header `Idempotent-Replay: true`).
    """

    status_code: int
    body: dict
    replay: bool = False


def place_bid(
    *, user, auction_id: uuid.UUID, amount_cents: int, idempotency_key: uuid.UUID
) -> BidOutcome:
    """Processa UMA tentativa de lance de um usuário autenticado.

    A view já tratou: 401 (sessão), 404 (leilão não existe) e 400 (corpo/chave inválidos).
    """
    if type(amount_cents) is not int:
        raise TypeError("amount_cents deve ser int em centavos")  # RF19: nunca float

    with transaction.atomic():
        # 1. Trava a linha do leilão. Daqui até o COMMIT ninguém mais mexe neste leilão.
        auction = (
            Auction.objects.select_for_update(of=("self",))
            .select_related("item")
            .get(id=auction_id)
        )
        # 2. O relógio é lido DEPOIS da trava: quem esperou na fila é julgado pela hora em
        #    que é processado, não pela hora em que chegou (RF10, RF16).
        now = clock.now()

        participant = AuctionParticipant.objects.filter(auction=auction, user=user).first()
        code = _refusal(auction, user, participant, amount_cents, now)
        if code is not None:
            return _refused(code, auction, now)
        return _accept(auction, user, participant, amount_cents, now)


def _refusal(auction, user, participant, amount_cents: int, now) -> str | None:
    """Ordem do contrato (seção 4, passos 6 a 9): o primeiro que falhar define o código."""
    if auction.status != AuctionStatus.RUNNING:
        return "AUCTION_NOT_RUNNING"
    if now >= auction.ends_at:  # o worker ainda não fechou, mas já acabou
        return "AUCTION_ENDED"
    if auction.item.seller_id == user.id:
        return "IS_SELLER"
    if participant is not None and auction.leader_id == participant.id:
        return "IS_LEADER"
    if amount_cents < auction.min_next_bid_cents:  # mínimo de AGORA, sob a trava
        return "BID_TOO_LOW"
    return None


def _refused(code: str, auction: Auction, now) -> BidOutcome:
    body = {"code": code, "message": REFUSALS[code], "auction": auction_state(auction, now)}
    if code == "BID_TOO_LOW":
        body["min_bid_cents"] = auction.min_next_bid_cents
    return BidOutcome(409, body)


def _accept(auction: Auction, user, participant, amount_cents: int, now) -> BidOutcome:
    # O número do participante nasce no 1º lance aceito, sob a trava: sem buraco nem repetição.
    if participant is None:
        participant = AuctionParticipant.objects.create(
            auction=auction, user=user, number=auction.participants.count() + 1
        )
    previous_leader_number = auction.leader.number if auction.leader_id else None

    bid = Bid.objects.create(
        auction=auction, participant=participant, amount_cents=amount_cents, created_at=now
    )
    old_ends_at = auction.ends_at
    auction.highest_bid_cents = amount_cents
    auction.leader = participant
    auction.bid_count += 1
    auction.ends_at = extended_ends_at(
        now=now, ends_at=auction.ends_at, original_ends_at=auction.original_ends_at
    )
    auction.save(update_fields=["highest_bid_cents", "leader", "bid_count", "ends_at"])

    state = auction_state(auction, now)
    bid_body = bid_json(bid)
    announce_after_commit(
        auction.id,
        {
            "type": "bid_accepted",
            "bid": bid_body,
            "auction": state,
            "extended": was_extended(old_ends_at=old_ends_at, new_ends_at=auction.ends_at),
            "previous_leader_number": previous_leader_number,
            "server_time": now,
        },
    )
    return BidOutcome(
        201, {"bid": bid_body, "auction": state, "you": {"participant_number": participant.number}}
    )
