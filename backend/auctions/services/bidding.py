"""Motor de lances (RF10 a RF15). Contrato, seção 4.

Tudo acontece dentro de UMA transação, com a linha do leilão travada (`select_for_update`).
Enquanto um lance está sendo processado, nenhum outro lance, cancelamento ou fechamento
toca no mesmo leilão: eles esperam na fila da trava. É isso que garante o RF11.
"""

import uuid
from dataclasses import dataclass

from django.db import IntegrityError, transaction

from auctions.models import (
    Auction,
    AuctionParticipant,
    AuctionStatus,
    Bid,
    IdempotencyRecord,
)
from auctions.rules.extension import extended_ends_at, was_extended
from auctions.serializers import auction_state, bid_json, jsonable

from . import clock
from .broadcast import announce_after_commit

REFUSALS = {
    "AUCTION_NOT_RUNNING": "Este leilão não está em andamento.",
    "AUCTION_ENDED": "O leilão já terminou (horário do servidor).",
    "IS_SELLER": "Você não pode dar lance no seu próprio leilão.",
    "IS_LEADER": "Você já é o líder deste leilão.",
    "BID_TOO_LOW": "Lance abaixo do mínimo atual.",
}
MISMATCH = {
    "code": "IDEMPOTENCY_KEY_MISMATCH",
    "message": "Esta chave já foi usada para outro lance. Gere uma chave nova.",
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
    try:
        return _place_bid_once(user, auction_id, amount_cents, idempotency_key)
    except IntegrityError:
        # Só acontece se a MESMA chave chegar ao mesmo tempo para DOIS leilões diferentes
        # (cada um com sua trava): o UNIQUE(usuário, chave) do banco deixa um só gravar.
        # A transação do outro foi desfeita inteira (lance incluído); na 2ª tentativa ele
        # encontra a chave gravada e recebe replay ou 422.
        return _place_bid_once(user, auction_id, amount_cents, idempotency_key)


def _place_bid_once(user, auction_id, amount_cents: int, key: uuid.UUID) -> BidOutcome:
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

        # 3. Chave já vista? (contrato, passo 4: ANTES das regras de negócio). Dois envios
        #    simultâneos da mesma chave no mesmo leilão chegam aqui um de cada vez (a trava),
        #    então o 2º sempre encontra o registro do 1º.
        record = IdempotencyRecord.objects.filter(user=user, key=key).first()
        if record is not None:
            return _replay(record, auction, amount_cents, now)

        participant = AuctionParticipant.objects.filter(auction=auction, user=user).first()
        code = _refusal(auction, user, participant, amount_cents, now)
        if code is not None:
            outcome = _refused(code, auction, now)
            original = {"code": code, "message": outcome.body["message"]}
        else:
            outcome = _accept(auction, user, participant, amount_cents, now)
            original = {"bid": outcome.body["bid"], "you": outcome.body["you"]}

        # 4. Resultado DEFINITIVO (201 ou 409) gravado na mesma transação do lance: ou os
        #    dois existem, ou nenhum. 401, 429 e 5xx nunca chegam aqui.
        IdempotencyRecord.objects.create(
            user=user,
            key=key,
            auction=auction,
            amount_cents=amount_cents,
            status_code=outcome.status_code,
            response_body=jsonable(original),
        )
        return outcome


def _replay(record: IdempotencyRecord, auction: Auction, amount_cents: int, now) -> BidOutcome:
    """Mesma chave: devolve o resultado ORIGINAL + o estado ATUAL do leilão (RF12)."""
    if (record.auction_id, record.amount_cents) != (auction.id, amount_cents):
        return BidOutcome(422, dict(MISMATCH))  # não é gravado: a chave continua do original
    body = {**record.response_body, "auction": auction_state(auction, now)}
    if body.get("code") == "BID_TOO_LOW":
        body["min_bid_cents"] = auction.min_next_bid_cents  # mínimo atual (RF10)
    return BidOutcome(record.status_code, body, replay=True)


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
