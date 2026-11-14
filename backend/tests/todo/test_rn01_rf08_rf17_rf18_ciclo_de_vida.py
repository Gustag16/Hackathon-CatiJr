"""RN01 (5 estados, 5 transições), RF08 (cancelamento), RF17 (abre e fecha sozinho) e
RF18 (sobrevive a reinício, fechar 2x não duplica, nada depois do fechamento)."""

from datetime import timedelta

import pytest
from django.core.management import call_command

from auctions.models import AuctionStatus as S
from auctions.models import Bid
from auctions.services.errors import CannotCancel, InvalidTransition, NotSeller
from auctions.services.transitions import (
    ALLOWED_TRANSITIONS,
    cancel_auction,
    close_due_auctions,
    open_due_auctions,
    transition,
)

from .conftest import bid, seed_bid

pytestmark = pytest.mark.django_db

ALL = [S.SCHEDULED, S.RUNNING, S.SOLD, S.ENDED_NO_BIDS, S.CANCELLED]
FORBIDDEN = [(a, b) for a in ALL for b in ALL if a != b and (a, b) not in ALLOWED_TRANSITIONS]


def reload(auction):
    auction.refresh_from_db()
    return auction


# ---------- RN01 ----------


def test_existem_exatamente_5_transicoes():
    assert len(ALLOWED_TRANSITIONS) == 5 and len(FORBIDDEN) == 15


@pytest.mark.parametrize(("source", "target"), FORBIDDEN)
def test_transicao_fora_da_rn01_e_recusada(make_auction, source, target):
    auction = make_auction(status=source)
    with pytest.raises(InvalidTransition):
        transition(auction, target)
    assert reload(auction).status == source


def test_com_lances_nunca_termina_encerrado_sem_lances(running, ana, clock):
    seed_bid(running, ana, 10_000, clock.now)
    with pytest.raises(InvalidTransition):
        transition(running, S.ENDED_NO_BIDS)
    assert reload(running).status == S.RUNNING


def test_sem_lances_nunca_termina_vendido(running):
    with pytest.raises(InvalidTransition):
        transition(running, S.SOLD)


# ---------- RF08: cancelamento ----------


def test_comitente_cancela_leilao_agendado(make_auction, seller):
    auction = make_auction(status="scheduled")
    cancel_auction(user=seller, auction_id=auction.id)
    assert reload(auction).status == S.CANCELLED
    assert type(auction).objects.filter(id=auction.id).exists()  # não apaga nada


def test_comitente_cancela_leilao_em_andamento_sem_lances(running, seller):
    cancel_auction(user=seller, auction_id=running.id)
    assert reload(running).status == S.CANCELLED


def test_leilao_com_lances_nao_pode_ser_cancelado(running, seller, ana, clock):
    seed_bid(running, ana, 10_000, clock.now)
    with pytest.raises(CannotCancel) as error:
        cancel_auction(user=seller, auction_id=running.id)
    assert error.value.reason == "HAS_BIDS" and reload(running).status == S.RUNNING


@pytest.mark.parametrize("status", [S.SOLD, S.ENDED_NO_BIDS, S.CANCELLED])
def test_leilao_finalizado_nao_pode_ser_cancelado(make_auction, seller, status):
    auction = make_auction(status=status)
    with pytest.raises(CannotCancel) as error:
        cancel_auction(user=seller, auction_id=auction.id)
    assert error.value.reason == "ALREADY_FINISHED" and reload(auction).status == status


def test_so_o_comitente_cancela(running, ana):
    with pytest.raises(NotSeller):
        cancel_auction(user=ana, auction_id=running.id)
    assert reload(running).status == S.RUNNING


def test_cancelamento_avisa_a_sala_depois_do_commit(
    running, seller, sent, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        cancel_auction(user=seller, auction_id=running.id)
        assert sent == []
    assert [m["message"]["type"] for m in sent] == ["auction_cancelled"]


# ---------- RF17: abre e fecha sozinho ----------


def test_abre_no_horario_agendado(make_auction, clock, sent, django_capture_on_commit_callbacks):
    auction = make_auction(status="scheduled")
    assert open_due_auctions() == 0  # ainda não chegou a hora
    assert reload(auction).status == S.SCHEDULED

    clock.set(auction.starts_at)
    with django_capture_on_commit_callbacks(execute=True):
        assert open_due_auctions() == 1
    assert reload(auction).status == S.RUNNING
    assert [m["message"]["type"] for m in sent] == ["auction_started"]


def test_nao_fecha_antes_do_termino(running, clock):
    clock.set(running.ends_at - timedelta(microseconds=1))
    assert close_due_auctions() == 0 and reload(running).status == S.RUNNING


def test_fecha_sem_lances_como_encerrado_sem_lances(running, clock):
    clock.set(running.ends_at)  # `now >= ends_at`: complemento exato da regra do lance
    assert close_due_auctions() == 1
    assert reload(running).status == S.ENDED_NO_BIDS


def test_fecha_com_lances_como_vendido_para_o_maior_lance(
    running, ana, bruno, clock, sent, django_capture_on_commit_callbacks
):
    seed_bid(running, ana, 10_000, clock.now)
    seed_bid(running, bruno, 10_500, clock.now)
    clock.set(running.ends_at)
    with django_capture_on_commit_callbacks(execute=True):
        assert close_due_auctions() == 1

    assert reload(running).status == S.SOLD and running.leader.user_id == bruno.id
    message = sent[0]["message"]
    assert message["type"] == "auction_finished"
    assert message["result"] == {
        "status": "sold",
        "winner_label": "Br*** #2",  # "Bruno": ⌊5/2⌋ = 2 letras (contrato, seção 2)
        "final_price_cents": 10_500,
    }


def test_fecha_no_termino_vigente_ja_com_prorrogacao(running, ana, clock):
    original = running.ends_at
    clock.set(original - timedelta(seconds=10))
    bid(ana, running, 10_000)  # prorroga para now + 2 min
    clock.set(original + timedelta(seconds=30))  # passou do original, não do prorrogado
    assert close_due_auctions() == 0 and reload(running).status == S.RUNNING
    clock.set(reload(running).ends_at)
    assert close_due_auctions() == 1 and reload(running).status == S.SOLD


# ---------- RF18: reinício, duplicidade, nada depois do fechamento ----------


def test_fechar_duas_vezes_nao_duplica(
    running, ana, clock, sent, django_capture_on_commit_callbacks
):
    seed_bid(running, ana, 10_000, clock.now)
    clock.set(running.ends_at)
    with django_capture_on_commit_callbacks(execute=True):
        assert close_due_auctions() == 1
        assert close_due_auctions() == 0
    assert reload(running).status == S.SOLD
    assert len(sent) == 1 and Bid.objects.count() == 1


def test_depois_de_reinicio_abre_o_que_deveria_ter_aberto(make_auction, clock):
    auction = make_auction(status="scheduled")
    clock.set(auction.starts_at + timedelta(minutes=3))  # sistema ficou fora do ar
    open_due_auctions()
    assert reload(auction).status == S.RUNNING


def test_depois_de_reinicio_longo_abre_e_fecha_o_que_ja_passou_do_termino(make_auction, clock):
    auction = make_auction(status="scheduled")
    clock.set(auction.ends_at + timedelta(hours=1))
    open_due_auctions()
    close_due_auctions()
    assert reload(auction).status == S.ENDED_NO_BIDS


def test_nunca_ha_lance_aceito_depois_do_fechamento(running, ana, bruno, clock):
    seed_bid(running, ana, 10_000, clock.now)
    clock.set(running.ends_at)
    close_due_auctions()
    outcome = bid(bruno, running, 99_000)
    assert outcome.status_code == 409 and outcome.body["code"] == "AUCTION_NOT_RUNNING"
    assert Bid.objects.count() == 1 and reload(running).highest_bid_cents == 10_000


def test_worker_fecha_varios_de_uma_vez(make_auction, clock):
    auctions = [make_auction() for _ in range(5)]
    clock.set(auctions[0].ends_at)
    assert close_due_auctions() == 5
    assert {reload(a).status for a in auctions} == {S.ENDED_NO_BIDS}


def test_comando_do_worker_uma_passada_abre_e_fecha(make_auction, clock):
    """`manage.py run_auction_worker --once`: uma passada lendo o banco (sem timer em memória)."""
    to_open = make_auction(status="scheduled")
    to_close = make_auction()
    clock.set(max(to_open.starts_at, to_close.ends_at))
    call_command("run_auction_worker", once=True)
    assert reload(to_open).status == S.RUNNING
    assert reload(to_close).status == S.ENDED_NO_BIDS
