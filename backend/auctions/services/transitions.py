"""Máquina de estados do leilão (RN01): ÚNICO lugar que altera `Auction.status`.

ESQUELETO: o Danilo implementa. Os testes em tests/todo/test_rn01_rf08_rf17_rf18_ciclo_de_vida.py
descrevem cada garantia.
"""

from auctions.models import Auction, AuctionStatus

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


def transition(auction: Auction, to_status: str) -> Auction:
    """Muda o status de um leilão cuja linha JÁ está travada (`select_for_update`).

    TODO(Danilo):
    - recusar o que não está em ALLOWED_TRANSITIONS (InvalidTransition);
    - garantir "com lances só termina sold" (bid_count > 0 nunca vira ended_no_bids/cancelled);
    - salvar só o campo `status` e agendar o broadcast com `transaction.on_commit`.
    """
    raise NotImplementedError("TODO(Danilo): função central de transição (RN01)")


def cancel_auction(*, user, auction_id) -> Auction:
    """Cancelamento pelo comitente (RF08), sob a MESMA trava do lance.

    TODO(Danilo): atomic + select_for_update; NotSeller se não for o comitente;
    CannotCancel("HAS_BIDS") / CannotCancel("ALREADY_FINISHED"); depois `transition`.
    """
    raise NotImplementedError("TODO(Danilo): cancelamento (RF08)")


def open_due_auctions() -> int:
    """Abre todo `scheduled` com `starts_at <= now`. Devolve quantos abriu. (RF17, RF18)

    TODO(Danilo): select_for_update(skip_locked=True); relógio via `clock.now()`.
    Depois de um reinício, um leilão cujo início E término já passaram abre e, na
    passada seguinte de `close_due_auctions`, fecha.
    """
    raise NotImplementedError("TODO(Danilo): abertura automática (RF17)")


def close_due_auctions() -> int:
    """Fecha todo `running` com `now >= ends_at` (complemento exato da regra do lance).

    Com lances -> sold; sem lances -> ended_no_bids. Devolve quantos fechou.
    TODO(Danilo): select_for_update(skip_locked=True); reler `ends_at` DEPOIS da trava
    (um lance pode ter prorrogado enquanto o worker esperava). Fechar 2x não duplica.
    """
    raise NotImplementedError("TODO(Danilo): fechamento automático (RF17, RF18)")
