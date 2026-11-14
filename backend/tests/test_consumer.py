"""WebSocket da sala (contrato, seção 5), com o roteamento real e o Redis DE VERDADE.

Cada teste abre uma conexão com `WebsocketCommunicator` (um "navegador" de mentira). O
cenário assíncrono roda com `async_to_sync`, então não precisa de plugin de asyncio. O banco
é `transaction=True` para o commit acontecer de verdade (é ele que dispara o aviso à sala).
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.conf import settings
from django.db import transaction
from django.test import Client

from accounts.models import User
from auctions.models import Auction, Item
from auctions.routing import websocket_urlpatterns
from auctions.services.bidding import place_bid
from config.asgi import application

NOW = datetime(2030, 1, 1, 12, tzinfo=UTC)
pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def scene(monkeypatch):
    monkeypatch.setattr("auctions.services.clock.now", lambda: NOW)
    seller = User.objects.create_user(email="s@t.dev", display_name="Comitente", password="x")
    ana = User.objects.create_user(email="a@t.dev", display_name="Ana Paula", password="x")
    item = Item.objects.create(seller=seller, name="X", description="X", category="outros")
    auction = Auction.objects.create(
        item=item, status="running", start_price_cents=10_000,
        starts_at=NOW - timedelta(minutes=5), ends_at=NOW + timedelta(minutes=10),
        original_ends_at=NOW + timedelta(minutes=10),
    )  # fmt: skip
    return seller, ana, auction


def room(auction_id, user=None) -> WebsocketCommunicator:
    """Conexão pela rota real, já com o usuário que o middleware de sessão colocaria."""
    communicator = WebsocketCommunicator(
        URLRouter(websocket_urlpatterns), f"/ws/auctions/{auction_id}/"
    )
    if user is not None:
        communicator.scope["user"] = user
    return communicator


async def closed_with(communicator) -> int:
    """Conecta e devolve o código com que o servidor fechou."""
    connected, _ = await communicator.connect()
    assert connected  # aceita primeiro, para o navegador conseguir ler o código
    output = await communicator.receive_output()
    assert output["type"] == "websocket.close"
    return output["code"]


def bid(user, auction, amount=10_000):
    return place_bid(
        user=user, auction_id=auction.id, amount_cents=amount, idempotency_key=uuid.uuid4()
    )


def run(scenario):
    async_to_sync(scenario)()


# ---------- quem entra ----------


def test_sem_sessao_fecha_com_4401(scene):
    async def scenario():
        assert await closed_with(room(scene[2].id)) == 4401

    run(scenario)


def test_leilao_inexistente_fecha_com_4404(scene):
    async def scenario():
        assert await closed_with(room(uuid.uuid4(), scene[1])) == 4404

    run(scenario)


def test_id_que_nao_e_uuid_fecha_com_4404(scene):
    async def scenario():
        assert await closed_with(room("nao-sou-uuid", scene[1])) == 4404

    run(scenario)


def test_cookie_de_sessao_de_verdade_pelo_asgi_completo(scene):
    """Passa por tudo que roda na VM: validação de origem, sessão do cookie e rota."""
    _, ana, auction = scene
    client = Client()
    client.force_login(ana)
    cookie = f"{settings.SESSION_COOKIE_NAME}={client.cookies[settings.SESSION_COOKIE_NAME].value}"
    path = f"/ws/auctions/{auction.id}/"

    async def scenario():
        origin = (b"origin", b"http://localhost")
        logged = WebsocketCommunicator(
            application, path, headers=[origin, (b"cookie", cookie.encode())]
        )
        assert (await logged.connect())[0]
        assert (await logged.receive_json_from())["type"] == "snapshot"
        await logged.disconnect()

        anonymous = WebsocketCommunicator(application, path, headers=[origin])
        assert await closed_with(anonymous) == 4401

    run(scenario)


# ---------- snapshot ----------


def test_snapshot_ao_conectar_no_formato_do_contrato(scene):
    seller, ana, auction = scene
    bruno = User.objects.create_user(email="b@t.dev", display_name="Bruno", password="x")
    bid(ana, auction, 10_000)
    bid(bruno, auction, 10_500)

    async def scenario():
        ws = room(auction.id, ana)
        assert (await ws.connect())[0]
        snap = await ws.receive_json_from()
        await ws.disconnect()
        return snap

    snap = async_to_sync(scenario)()
    assert set(snap) == {"type", "auction", "you", "recent_bids", "result", "server_time"}
    assert snap["type"] == "snapshot"
    assert snap["you"] == {"participant_number": 1}
    assert snap["result"] is None
    assert snap["server_time"] == "2030-01-01T12:00:00Z"
    assert [b["amount_cents"] for b in snap["recent_bids"]] == [10_500, 10_000]
    state = snap["auction"]
    assert state["id"] == str(auction.id) and state["status"] == "running"
    assert state["current_price_cents"] == 10_500 and state["bid_count"] == 2
    assert state["leader_number"] == 2 and state["leader_label"] == "Br*** #2"
    assert type(state["min_next_bid_cents"]) is int
    # RF09/D4: nada que identifique o líder fora da sala
    assert "leader_id" not in state
    for user in (seller, ana, bruno):
        assert str(user.id) not in str(snap) and user.email not in str(snap)
    assert "Bruno" not in str(snap) and "Ana Paula" not in str(snap)


def test_comitente_entra_na_sala_sem_numero(scene):
    seller, _, auction = scene

    async def scenario():
        ws = room(auction.id, seller)
        assert (await ws.connect())[0]
        snap = await ws.receive_json_from()
        await ws.disconnect()
        return snap

    assert async_to_sync(scenario)()["you"] == {"participant_number": None}


# ---------- eventos ----------


def test_bid_accepted_chega_so_depois_do_commit(scene):
    _, ana, auction = scene

    def bid_that_rolls_back():
        with transaction.atomic():
            bid(ana, auction, 10_000)
            transaction.set_rollback(True)

    async def scenario():
        ws = room(auction.id, ana)
        assert (await ws.connect())[0]
        await ws.receive_json_from()  # snapshot

        await database_sync_to_async(bid_that_rolls_back)()
        assert await ws.receive_nothing(timeout=0.3)  # lance desfeito: a sala não vê nada

        outcome = await database_sync_to_async(bid)(ana, auction, 10_000)
        event = await ws.receive_json_from()
        await ws.disconnect()
        return outcome, event

    outcome, event = async_to_sync(scenario)()
    assert outcome.status_code == 201
    assert event["type"] == "bid_accepted"
    assert event["bid"]["amount_cents"] == 10_000 and event["bid"]["bidder_label"] == "Ana*** #1"
    assert event["auction"]["bid_count"] == 1 and event["auction"]["leader_number"] == 1
    assert event["previous_leader_number"] is None and event["extended"] is False
    assert event["server_time"] == "2030-01-01T12:00:00Z"
    assert Auction.objects.get(id=auction.id).bid_count == 1  # o que a sala viu está gravado


def test_evento_de_outro_leilao_nao_chega(scene):
    _, ana, auction = scene
    other = Auction.objects.create(
        item=Item.objects.create(
            seller=scene[0], name="Y", description="Y", category="outros"
        ),
        status="running", start_price_cents=10_000,
        starts_at=NOW - timedelta(minutes=5), ends_at=NOW + timedelta(minutes=10),
        original_ends_at=NOW + timedelta(minutes=10),
    )  # fmt: skip

    async def scenario():
        ws = room(auction.id, ana)
        assert (await ws.connect())[0]
        await ws.receive_json_from()
        await database_sync_to_async(bid)(ana, other)
        assert await ws.receive_nothing(timeout=0.3)
        await ws.disconnect()

    run(scenario)


# ---------- cliente -> servidor ----------


def test_resync_reenvia_o_snapshot_atual(scene):
    _, ana, auction = scene

    async def scenario():
        ws = room(auction.id, ana)
        assert (await ws.connect())[0]
        first = await ws.receive_json_from()
        await database_sync_to_async(bid)(ana, auction, 10_000)
        await ws.receive_json_from()  # bid_accepted
        await ws.send_json_to({"type": "resync"})
        second = await ws.receive_json_from()
        await ws.disconnect()
        return first, second

    first, second = async_to_sync(scenario)()
    assert first["auction"]["bid_count"] == 0 and first["you"] == {"participant_number": None}
    assert second["type"] == "snapshot"
    assert second["auction"]["bid_count"] == 1 and second["you"] == {"participant_number": 1}


def test_ping_responde_pong(scene):
    async def scenario():
        ws = room(scene[2].id, scene[1])
        assert (await ws.connect())[0]
        await ws.receive_json_from()
        await ws.send_json_to({"type": "ping"})
        pong = await ws.receive_json_from()
        await ws.disconnect()
        return pong

    assert async_to_sync(scenario)()["type"] == "pong"


def test_mensagem_invalida_responde_error_sem_derrubar(scene):
    async def scenario():
        ws = room(scene[2].id, scene[1])
        assert (await ws.connect())[0]
        await ws.receive_json_from()
        replies = []
        for text in ("isto não é json", '{"type": "dar_lance"}', "[1, 2]", '{"sem": "type"}'):
            await ws.send_to(text_data=text)
            replies.append(await ws.receive_json_from())
        await ws.send_to(bytes_data=b"\x00\x01")
        replies.append(await ws.receive_json_from())
        await ws.send_json_to({"type": "ping"})  # a conexão continua de pé
        alive = await ws.receive_json_from()
        await ws.disconnect()
        return replies, alive

    replies, alive = async_to_sync(scenario)()
    assert [r["type"] for r in replies] == ["error"] * 5
    assert [r["code"] for r in replies] == [
        "INVALID_MESSAGE", "UNKNOWN_TYPE", "INVALID_MESSAGE", "INVALID_MESSAGE", "INVALID_MESSAGE",
    ]  # fmt: skip
    assert all(r["message"] for r in replies)
    assert alive["type"] == "pong"
