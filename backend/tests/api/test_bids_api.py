"""POST /api/auctions/{id}/bids pela API: passos 1-3 do contrato (seção 4) e formato HTTP.

As regras do lance (RF10-RF15) estão nos testes de tests/todo, que chamam `place_bid`.
"""

import uuid

import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


def post_bid(client, auction_id, amount=10_000, key=None, headers=True):
    extra = {"HTTP_IDEMPOTENCY_KEY": str(key or uuid.uuid4())} if headers else {}
    return client.post(
        f"/api/auctions/{auction_id}/bids", {"amount_cents": amount}, format="json", **extra
    )


def test_lance_aceito_201(logged, make_auction):
    client, _ = logged
    response = post_bid(client, make_auction().id)
    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"bid", "auction", "you"}
    assert body["bid"]["created_at"].endswith("Z")
    assert body["auction"]["leader_number"] == 1 and "leader_id" not in body["auction"]
    assert body["auction"]["server_time"].endswith("Z")
    assert "Idempotent-Replay" not in response.headers


def test_recusa_409_com_codigo_e_estado(logged, make_auction):
    client, _ = logged
    response = post_bid(client, make_auction().id, amount=9_999)
    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "BID_TOO_LOW" and body["min_bid_cents"] == 10_000
    assert body["auction"]["min_next_bid_cents"] == 10_000


def test_sem_sessao_401(make_auction):
    response = post_bid(APIClient(), make_auction().id)
    assert response.status_code == 401 and response.json()["code"] == "NOT_AUTHENTICATED"


@pytest.mark.parametrize("bad", [uuid.uuid4(), "nao-e-uuid"])
def test_leilao_inexistente_404(logged, bad):
    client, _ = logged
    assert post_bid(client, bad).status_code == 404


@pytest.mark.parametrize("amount", [100.0, "10000", True, None, 0, -100, 10_000.5])
def test_valor_invalido_400(logged, make_auction, amount):
    """RF19: só inteiro em centavos; `100.0` (float) também é recusado."""
    client, _ = logged
    response = post_bid(client, make_auction().id, amount=amount)
    assert response.status_code == 400
    assert list(response.json()["fields"]) == ["amount_cents"]


@pytest.mark.parametrize("key", [None, "", "abc"])
def test_chave_invalida_400(logged, make_auction, key):
    client, _ = logged
    extra = {} if key is None else {"HTTP_IDEMPOTENCY_KEY": key}
    response = client.post(
        f"/api/auctions/{make_auction().id}/bids", {"amount_cents": 10_000}, format="json", **extra
    )
    assert response.status_code == 400
    assert list(response.json()["fields"]) == ["idempotency_key"]


def test_ordem_404_antes_de_400(logged):
    """Contrato: leilão existe (2) é conferido antes do corpo (3)."""
    client, _ = logged
    assert post_bid(client, uuid.uuid4(), amount="lixo", headers=False).status_code == 404


def test_lance_prorroga_e_devolve_o_novo_termino(logged, make_auction, clock):
    client, _ = logged
    auction = make_auction(starts_in=-600, duration=630)  # restam 30 s
    body = post_bid(client, auction.id).json()
    assert body["auction"]["ends_at"] == "2030-01-01T12:02:00Z"  # now + 2 min
    assert body["auction"]["original_ends_at"] == "2030-01-01T12:00:30Z"
