"""Máquina de estados do leilão (RN01): ÚNICO lugar que altera `Auction.status`.

Quem chama `transition` já está dentro de `transaction.atomic()` e já travou a linha do
leilão com `select_for_update` (cancelamento, worker). A mesma trava é usada pelo lance, então
lance, cancelamento e fechamento nunca acontecem "ao mesmo tempo" no mesmo leilão (RF18).
"""

from django.db import transaction

from auctions.models import Auction, AuctionStatus
from auctions.serializers import auction_result, auction_state

from . import clock
from .broadcast import announce_after_commit
from .errors import CannotCancel, InvalidTransition, NotSeller

S = AuctionStatus

# As 5 transições da RN01. Qualquer outra é InvalidTransition.
ALLOWED_TRANSITIONS: frozenset[tuple[str, str]] = frozenset(
    {
        (S.SCHEDULED, S.RUNNING),  # chegou o início
        (S.SCHEDULED, S.CANCELLED),  # comitente, antes do início
        (S.RUNNING, S.CANCELLED),  # comitente, SÓ sem lances
        (S.RUNNING, S.SOLD),  # fim, com lances
        (S.RUNNING, S.ENDED_NO_BIDS),  # fim, sem lances
    }
)
FINAL_STATUSES = frozenset({S.SOLD, S.ENDED_NO_BIDS, S.CANCELLED})

EVENT_FOR = {
    S.RUNNING: "auction_started",
    S.SOLD: "auction_finished",
    S.ENDED_NO_BIDS: "auction_finished",
    S.CANCELLED: "auction_cancelled",
}


def transition(auction: Auction, to_status: str) -> Auction:
    """Muda o status de um leilão cuja linha JÁ está travada, e avisa a sala após o commit."""
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError("transition() precisa rodar dentro de transaction.atomic()")
    source = auction.status
    if (source, to_status) not in ALLOWED_TRANSITIONS:
        raise InvalidTransition(f"{source} -> {to_status} não existe na RN01")
    has_bids = auction.bid_count > 0
    if to_status == S.SOLD and not has_bids:
        raise InvalidTransition("sem lances não há vencedor: termina ended_no_bids")
    if to_status in (S.ENDED_NO_BIDS, S.CANCELLED) and has_bids:
        raise InvalidTransition("com lances, um leilão em andamento só termina sold")

    auction.status = to_status
    auction.save(update_fields=["status"])

    message = {"type": EVENT_FOR[to_status], "auction": auction_state(auction, clock.now())}
    if message["type"] == "auction_finished":
        message["result"] = auction_result(auction)
    message["server_time"] = clock.now()
    announce_after_commit(auction.id, message)
    return auction


def _lock(auction_id) -> Auction:
    """Trava a linha do leilão (só ela: `of=self` não trava item nem comitente)."""
    return Auction.objects.select_for_update(of=("self",)).select_related("item").get(id=auction_id)


@transaction.atomic
def cancel_auction(*, user, auction_id) -> Auction:
    """Cancelamento pelo comitente (RF08), sob a MESMA trava do lance."""
    auction = _lock(auction_id)
    if auction.item.seller_id != user.id:
        raise NotSeller()
    # Já passou do término (o worker só ainda não fechou): para o cancelamento vale a mesma
    # regra do lance, `now >= ends_at` = acabou. Assim cancelar nunca "rouba" um fechamento.
    if auction.status in FINAL_STATUSES or (
        auction.status == S.RUNNING and clock.now() >= auction.ends_at
    ):
        raise CannotCancel("ALREADY_FINISHED")
    if auction.bid_count > 0:
        raise CannotCancel("HAS_BIDS")
    return transition(auction, S.CANCELLED)


def _process_due(*, status: str, time_field: str, decide) -> int:
    """Processa, um por vez, os leilões `status` cujo `time_field` já passou.

    Cada leilão numa transação própria: um erro num leilão não desfaz os outros.
    `skip_locked=True`: se um lance (ou outro worker) está com a trava, pula agora e pega na
    próxima passada, em vez de ficar esperando.

    `now` é lido ANTES da consulta. Isso só pode ATRASAR um fechamento (nunca adiantar), e o
    `ends_at` usado no filtro é o valor mais recente gravado: se um lance prorrogou enquanto
    isso, o Postgres reavalia o filtro na versão nova da linha.
    """
    done = 0
    while True:
        with transaction.atomic():
            now = clock.now()
            auction = (
                Auction.objects.select_for_update(skip_locked=True)
                .filter(status=status, **{f"{time_field}__lte": now})
                .order_by(time_field, "id")
                .first()
            )
            if auction is None:
                return done
            transition(auction, decide(auction))
            done += 1


def open_due_auctions() -> int:
    """Abre todo `scheduled` com `starts_at <= now`. Devolve quantos abriu. (RF17, RF18)"""
    return _process_due(status=S.SCHEDULED, time_field="starts_at", decide=lambda a: S.RUNNING)


def close_due_auctions() -> int:
    """Fecha todo `running` com `now >= ends_at` (complemento exato da regra do lance).

    Com lances -> sold; sem lances -> ended_no_bids. Fechar 2x não duplica: na 2ª vez o
    leilão não é mais `running` e nem aparece na consulta.
    """
    return _process_due(
        status=S.RUNNING,
        time_field="ends_at",
        decide=lambda a: S.SOLD if a.bid_count > 0 else S.ENDED_NO_BIDS,
    )
