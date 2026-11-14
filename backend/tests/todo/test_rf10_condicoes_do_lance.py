"""RF10: as 4 condições valem NO MOMENTO do processamento; toda recusa diz o motivo e o
lance mínimo atual. RF16: o relógio que vale é o do servidor. Ordem: contrato, seção 4."""

from datetime import timedelta

import pytest

from auctions.models import AuctionStatus, Bid

from .conftest import bid

pytestmark = pytest.mark.django_db


def test_lance_valido_e_aceito_com_o_corpo_do_contrato(running, ana, clock):
    outcome = bid(ana, running, 10_000)  # 1º lance pode ser igual ao preço inicial (RF14)

    assert outcome.status_code == 201 and outcome.replay is False
    assert outcome.body["bid"]["amount_cents"] == 10_000
    assert outcome.body["bid"]["bidder_label"] == "Ana*** #1"
    assert outcome.body["you"] == {"participant_number": 1}
    state = outcome.body["auction"]
    assert state["current_price_cents"] == 10_000
    assert state["min_next_bid_cents"] == 10_500
    assert state["bid_count"] == 1
    assert state["leader_number"] == 1 and state["leader_label"] == "Ana*** #1"
    assert "leader_id" not in state  # a API nunca expõe o id do líder (D4)
    stored = Bid.objects.get()
    assert stored.amount_cents == 10_000 and stored.created_at == clock.now


def test_resposta_nao_vaza_nome_completo_nem_id_do_usuario(running, ana):
    text = str(bid(ana, running, 10_000).body)
    assert "Ana Paula" not in text and str(ana.id) not in text and ana.email not in text


@pytest.mark.parametrize("status", ["scheduled", "sold", "ended_no_bids", "cancelled"])
def test_recusa_se_o_leilao_nao_esta_em_andamento(make_auction, ana, status):
    auction = make_auction(status=status)
    outcome = bid(ana, auction, 10_000)
    assert outcome.status_code == 409 and outcome.body["code"] == "AUCTION_NOT_RUNNING"
    assert Bid.objects.count() == 0


def test_recusa_no_instante_exato_do_termino(running, ana, clock):
    """Regra `now < ends_at`: no instante `ends_at` já não vale, mesmo com status running
    (o worker ainda não passou)."""
    clock.set(running.ends_at)
    outcome = bid(ana, running, 10_000)
    assert outcome.status_code == 409 and outcome.body["code"] == "AUCTION_ENDED"
    assert Bid.objects.count() == 0


def test_aceita_um_instante_antes_do_termino(running, ana, clock):
    clock.set(running.ends_at - timedelta(microseconds=1))
    assert bid(ana, running, 10_000).status_code == 201


def test_recusa_depois_do_termino_mesmo_que_o_navegador_ache_que_ainda_da(running, ana, clock):
    """RF16: o contador da tela é só visual."""
    clock.set(running.ends_at + timedelta(seconds=3))
    assert bid(ana, running, 10_000).body["code"] == "AUCTION_ENDED"


def test_comitente_nao_da_lance_no_proprio_leilao(running, seller):
    outcome = bid(seller, running, 10_000)
    assert outcome.status_code == 409 and outcome.body["code"] == "IS_SELLER"
    assert Bid.objects.count() == 0


def test_lider_nao_cobre_o_proprio_lance(running, ana):
    bid(ana, running, 10_000)
    outcome = bid(ana, running, 20_000)
    assert outcome.status_code == 409 and outcome.body["code"] == "IS_LEADER"
    assert Bid.objects.count() == 1


def test_recusa_abaixo_do_minimo_e_informa_o_minimo(running, ana, bruno):
    bid(ana, running, 10_000)
    outcome = bid(bruno, running, 10_499)
    assert outcome.status_code == 409 and outcome.body["code"] == "BID_TOO_LOW"
    assert outcome.body["min_bid_cents"] == 10_500
    assert outcome.body["auction"]["min_next_bid_cents"] == 10_500


def test_primeiro_lance_abaixo_do_preco_inicial_e_recusado(running, ana):
    outcome = bid(ana, running, 9_999)
    assert outcome.body["code"] == "BID_TOO_LOW" and outcome.body["min_bid_cents"] == 10_000


def test_vale_o_minimo_de_agora_nao_o_da_tela(running, ana, bruno, make_user):
    """Bruno viu mínimo 10.500 na tela, mas Carla deu lance antes: o mínimo já é 11.000."""
    carla = make_user("Carla")
    bid(ana, running, 10_000)
    bid(carla, running, 10_500)
    outcome = bid(bruno, running, 10_500)
    assert outcome.body["code"] == "BID_TOO_LOW" and outcome.body["min_bid_cents"] == 11_000


@pytest.mark.parametrize("code_status", ["scheduled", "running"])
def test_toda_recusa_traz_motivo_mensagem_e_estado_atual(make_auction, seller, code_status):
    outcome = bid(seller, make_auction(status=code_status), 1)
    assert outcome.status_code == 409
    assert outcome.body["code"] and outcome.body["message"]
    assert "min_next_bid_cents" in outcome.body["auction"]


def test_ordem_leilao_encerrado_vem_antes_de_is_seller(running, seller, clock):
    clock.set(running.ends_at)
    assert bid(seller, running, 10_000).body["code"] == "AUCTION_ENDED"


def test_ordem_is_seller_vem_antes_de_bid_too_low(running, seller):
    assert bid(seller, running, 1).body["code"] == "IS_SELLER"


def test_ordem_is_leader_vem_antes_de_bid_too_low(running, ana):
    bid(ana, running, 10_000)
    assert bid(ana, running, 1).body["code"] == "IS_LEADER"


def test_numero_do_participante_e_estavel_no_leilao(running, ana, bruno):
    """D4: o número nasce no 1º lance aceito e não muda nos seguintes."""
    assert bid(ana, running, 10_000).body["you"]["participant_number"] == 1
    assert bid(bruno, running, 10_500).body["you"]["participant_number"] == 2
    again = bid(ana, running, 11_000)
    assert again.body["you"]["participant_number"] == 1
    assert again.body["bid"]["bidder_label"] == "Ana*** #1"


def test_lance_recusado_nao_cria_participante(running, ana, bruno):
    bid(ana, running, 10_000)
    bid(bruno, running, 1)
    assert running.participants.count() == 1


def test_lance_nao_muda_o_status(running, ana):
    bid(ana, running, 10_000)
    running.refresh_from_db()
    assert running.status == AuctionStatus.RUNNING
