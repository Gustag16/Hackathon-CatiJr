"""RF12: reenviar o MESMO lance devolve o resultado original e nunca cria um 2º lance."""

import uuid

import pytest

from auctions.models import AuctionStatus, Bid, IdempotencyRecord

from .conftest import bid, run_parallel

pytestmark = pytest.mark.django_db


def test_reenvio_de_lance_aceito_devolve_o_mesmo_lance(running, ana):
    key = uuid.uuid4()
    first = bid(ana, running, 10_000, key)
    second = bid(ana, running, 10_000, key)  # clique duplo / rede caiu

    assert first.status_code == second.status_code == 201
    assert first.replay is False and second.replay is True
    assert second.body["bid"] == first.body["bid"]
    assert second.body["you"] == first.body["you"]
    assert Bid.objects.count() == 1
    running.refresh_from_db()
    assert running.bid_count == 1


def test_reenvio_de_quem_ja_lidera_nao_vira_is_leader(running, ana):
    """O replay é checado ANTES das regras de negócio (ordem do contrato, passo 4)."""
    key = uuid.uuid4()
    bid(ana, running, 10_000, key)
    assert bid(ana, running, 10_000, key).status_code == 201


def test_replay_traz_o_estado_atual_do_leilao(running, ana, bruno):
    key = uuid.uuid4()
    bid(ana, running, 10_000, key)
    bid(bruno, running, 10_500)
    replay = bid(ana, running, 10_000, key)

    assert replay.status_code == 201 and replay.replay is True
    assert replay.body["bid"]["amount_cents"] == 10_000  # resultado ORIGINAL
    assert replay.body["auction"]["current_price_cents"] == 10_500  # estado ATUAL
    assert replay.body["auction"]["leader_number"] == 2


def test_recusa_tambem_e_gravada_e_reenviada(running, ana, bruno, make_user):
    key = uuid.uuid4()
    bid(ana, running, 10_000)
    first = bid(bruno, running, 10_100, key)
    assert first.body["code"] == "BID_TOO_LOW" and first.body["min_bid_cents"] == 10_500

    bid(make_user("Carla"), running, 10_500)  # o mínimo sobe para 11.000
    replay = bid(bruno, running, 10_100, key)

    assert replay.status_code == 409 and replay.replay is True
    assert replay.body["code"] == "BID_TOO_LOW" and replay.body["message"] == first.body["message"]
    assert replay.body["min_bid_cents"] == 11_000  # mínimo ATUAL (RF10)
    assert replay.body["auction"]["min_next_bid_cents"] == 11_000


def test_recusa_original_vale_mesmo_que_agora_o_lance_fosse_aceito(make_auction, ana):
    """Resultado definitivo: se foi recusado com o leilão agendado, o reenvio da mesma
    chave continua recusado depois que o leilão abre. Lance novo = chave nova."""
    auction = make_auction(status="scheduled")
    key = uuid.uuid4()
    assert bid(ana, auction, 10_000, key).body["code"] == "AUCTION_NOT_RUNNING"

    type(auction).objects.filter(id=auction.id).update(status=AuctionStatus.RUNNING)  # arranjo
    replay = bid(ana, auction, 10_000, key)

    assert replay.status_code == 409 and replay.body["code"] == "AUCTION_NOT_RUNNING"
    assert replay.replay is True and Bid.objects.count() == 0


def test_mesma_chave_com_outro_valor_e_mismatch(running, ana):
    key = uuid.uuid4()
    bid(ana, running, 10_000, key)
    outcome = bid(ana, running, 20_000, key)
    assert outcome.status_code == 422 and outcome.body["code"] == "IDEMPOTENCY_KEY_MISMATCH"
    assert Bid.objects.count() == 1


def test_mesma_chave_em_outro_leilao_e_mismatch(running, make_auction, ana):
    key = uuid.uuid4()
    bid(ana, running, 10_000, key)
    outcome = bid(ana, make_auction(), 10_000, key)
    assert outcome.status_code == 422 and outcome.body["code"] == "IDEMPOTENCY_KEY_MISMATCH"
    assert Bid.objects.count() == 1


def test_mismatch_nao_e_gravado_e_nao_estraga_a_chave(running, ana):
    key = uuid.uuid4()
    bid(ana, running, 10_000, key)
    bid(ana, running, 20_000, key)  # 422
    assert bid(ana, running, 10_000, key).status_code == 201  # o original continua lá
    assert IdempotencyRecord.objects.count() == 1


def test_a_chave_e_por_usuario(running, ana, bruno):
    """UNIQUE(usuário, chave): a mesma chave em outro usuário é outra tentativa."""
    key = uuid.uuid4()
    assert bid(ana, running, 10_000, key).status_code == 201
    other = bid(bruno, running, 10_500, key)
    assert other.status_code == 201 and other.replay is False
    assert Bid.objects.count() == 2


def test_guarda_impressao_digital_e_status(running, ana):
    key = uuid.uuid4()
    bid(ana, running, 10_000, key)
    record = IdempotencyRecord.objects.get(user=ana, key=key)
    assert (record.auction_id, record.amount_cents, record.status_code) == (running.id, 10_000, 201)


@pytest.mark.django_db(transaction=True)
def test_dez_envios_simultaneos_da_mesma_chave_criam_um_lance(running, ana):
    key = uuid.uuid4()
    outcomes = run_parallel([lambda: bid(ana, running, 10_000, key) for _ in range(10)])

    assert [o.status_code for o in outcomes] == [201] * 10
    assert len({o.body["bid"]["id"] for o in outcomes}) == 1
    assert sum(1 for o in outcomes if not o.replay) == 1
    assert Bid.objects.count() == 1 and IdempotencyRecord.objects.count() == 1


@pytest.mark.skip(reason="TODO(Danilo): teste de API quando a view existir")
def test_401_nao_e_gravado_e_o_reenvio_apos_login_processa_o_lance():
    """Sessão expirada (RF12): 401 não é definitivo. O front loga de novo e reenvia com a
    MESMA chave; o servidor processa como primeira vez. Idem 429 (nunca gravado)."""
