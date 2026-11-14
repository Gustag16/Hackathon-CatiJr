"""POST /api/auctions/{id}/cancel (RF08) pela API. As regras em si estão em tests/todo."""

import uuid

import pytest
from rest_framework.test import APIClient

from .conftest import PASSWORD

pytestmark = pytest.mark.django_db


@pytest.fixture
def seller_api(make_user):
    seller = make_user("Comitente")
    client = APIClient()
    client.login(username=seller.email, password=PASSWORD)
    return client, seller


def cancel(client, auction_id):
    return client.post(f"/api/auctions/{auction_id}/cancel")


def test_comitente_cancela_e_recebe_o_detalhe(seller_api, make_auction):
    client, seller = seller_api
    auction = make_auction(status="scheduled", starts_in=600, seller=seller)
    response = cancel(client, auction.id)
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled" and response.json()["id"] == str(auction.id)


def test_outro_usuario_recebe_forbidden(logged, make_auction):
    client, _ = logged
    response = cancel(client, make_auction().id)
    assert response.status_code == 403 and response.json()["code"] == "FORBIDDEN"


def test_com_lances_e_cannot_cancel_has_bids(seller_api, make_auction, make_user):
    client, seller = seller_api
    auction = make_auction(seller=seller, highest=10_000, winner=make_user("Bruno"))
    body = cancel(client, auction.id).json()
    assert body["code"] == "CANNOT_CANCEL" and body["reason"] == "HAS_BIDS" and body["message"]


@pytest.mark.parametrize("status", ["sold", "ended_no_bids", "cancelled"])
def test_finalizado_e_cannot_cancel_already_finished(seller_api, make_auction, make_user, status):
    client, seller = seller_api
    winner = make_user("Bruno") if status == "sold" else None
    auction = make_auction(
        status=status, seller=seller, highest=10_000 if winner else None, winner=winner
    )
    response = cancel(client, auction.id)
    assert response.status_code == 409 and response.json()["reason"] == "ALREADY_FINISHED"


def test_em_andamento_ja_passado_do_termino_conta_como_finalizado(seller_api, make_auction, clock):
    """O worker ainda não fechou, mas `now >= ends_at`: mesma regra do lance."""
    client, seller = seller_api
    auction = make_auction(seller=seller, starts_in=-600, duration=600)  # ends_at == now
    assert cancel(client, auction.id).json()["reason"] == "ALREADY_FINISHED"


def test_sem_login_e_401(api, make_auction):
    assert cancel(api, make_auction().id).status_code == 401


@pytest.mark.parametrize("bad", [uuid.uuid4(), "nao-e-uuid"])
def test_inexistente_e_404(logged, bad):
    client, _ = logged
    response = cancel(client, bad)
    assert response.status_code == 404 and response.json()["code"] == "NOT_FOUND"
