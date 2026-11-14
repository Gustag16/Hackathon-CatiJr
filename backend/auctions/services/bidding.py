"""Motor de lances (RF10 a RF15).

ESQUELETO: o Danilo implementa. Os testes em tests/todo/ descrevem cada garantia e são
a lista de trabalho. Ordem das verificações: contrato, seção 4.
"""

import uuid
from dataclasses import dataclass


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

    TODO(Danilo), tudo dentro de UM `transaction.atomic()`:
    1. `select_for_update()` na linha do leilão (a mesma trava do cancelar e do fechar).
    2. Chave já vista por este usuário? Mesmo (auction_id, amount_cents) -> replay com
       `auction` ATUAL; impressão diferente -> 422. Cuidado com dois envios SIMULTÂNEOS
       da mesma chave: a trava do leilão serializa, o UNIQUE(user, key) é a rede de segurança.
    3. `now = clock.now()` (DEPOIS da trava).
    4. AUCTION_NOT_RUNNING / AUCTION_ENDED (`now >= ends_at`) -> IS_SELLER -> IS_LEADER
       -> BID_TOO_LOW (com `auction.min_next_bid_cents` de AGORA).
    5. Aceito: AuctionParticipant (número = próximo do leilão), Bid, atualizar
       highest_bid_cents / leader / bid_count, prorrogar com `rules.extension.extended_ends_at`.
    6. Gravar IdempotencyRecord para 201 E para 409.
    7. `transaction.on_commit(lambda: send_to_room(...))` com o evento `bid_accepted`.
    """
    raise NotImplementedError("TODO(Danilo): transação do lance (RF10-RF15)")
