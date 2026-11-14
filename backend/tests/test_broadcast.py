"""Ponte backend -> sala (contrato, seção 5) com o Redis DE VERDADE, e o snapshot.

Prova que: o evento chega no grupo `auction_<uuid>` como `{"type": "room.event",
"message": ...}`; só depois do commit; só com tipos JSON (o Redis não leva datetime); e que
uma falha do Redis não derruba um lance já gravado.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from accounts.models import User
from auctions.models import Auction, Item
from auctions.services.bidding import place_bid
from auctions.services.broadcast import room_group
from auctions.services.room import room_snapshot
from auctions.services.transitions import cancel_auction

NOW = datetime(2030, 1, 1, 12, tzinfo=UTC)
pytestmark = pytest.mark.django_db


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


@pytest.fixture
def room(scene):
    """Um 'navegador' inscrito no grupo da sala, no Redis real."""
    layer = get_channel_layer()
    channel = async_to_sync(layer.new_channel)()
    async_to_sync(layer.group_add)(room_group(scene[2].id), channel)
    yield lambda: async_to_sync(layer.receive)(channel)
    async_to_sync(layer.group_discard)(room_group(scene[2].id), channel)


def bid(user, auction, amount=10_000):
    return place_bid(
        user=user, auction_id=auction.id, amount_cents=amount, idempotency_key=uuid.uuid4()
    )


def test_lance_chega_na_sala_pelo_redis(scene, room, django_capture_on_commit_callbacks):
    _, ana, auction = scene
    with django_capture_on_commit_callbacks(execute=True):
        bid(ana, auction)

    event = room()
    assert event["type"] == "room.event"
    message = event["message"]
    assert message["type"] == "bid_accepted"
    assert message["bid"]["bidder_label"] == "Ana*** #1"
    assert message["auction"]["ends_at"] == "2030-01-01T12:10:00Z"  # texto, não datetime
    assert message["server_time"] == "2030-01-01T12:00:00Z"
    assert message["previous_leader_number"] is None and message["extended"] is False
    assert "leader_id" not in message["auction"]


def test_cancelamento_chega_na_sala(scene, room, django_capture_on_commit_callbacks):
    seller, _, auction = scene
    with django_capture_on_commit_callbacks(execute=True):
        cancel_auction(user=seller, auction_id=auction.id)
    assert room()["message"]["type"] == "auction_cancelled"


def test_redis_fora_do_ar_nao_derruba_o_lance(
    scene, monkeypatch, django_capture_on_commit_callbacks, caplog
):
    _, ana, auction = scene

    def redis_down(*args, **kwargs):
        raise ConnectionError("Redis fora do ar")

    monkeypatch.setattr("auctions.services.broadcast.send_to_room", redis_down)
    with django_capture_on_commit_callbacks(execute=True):
        outcome = bid(ana, auction)

    assert outcome.status_code == 201
    auction.refresh_from_db()
    assert auction.bid_count == 1  # gravado
    assert "falha ao avisar a sala" in caplog.text


# ---------- snapshot ----------


def test_snapshot_de_quem_ainda_nao_deu_lance(scene):
    seller, _, auction = scene
    snap = room_snapshot(auction.id, seller)
    assert snap["type"] == "snapshot"
    assert snap["you"] == {"participant_number": None}
    assert snap["recent_bids"] == [] and snap["result"] is None
    assert snap["auction"]["leader_number"] is None
    assert snap["server_time"] == "2030-01-01T12:00:00Z"


def test_snapshot_com_lances(scene):
    _, ana, auction = scene
    bruno = User.objects.create_user(email="b@t.dev", display_name="Bruno", password="x")
    bid(ana, auction, 10_000)
    bid(bruno, auction, 10_500)
    bid(ana, auction, 11_000)

    snap = room_snapshot(auction.id, ana)
    assert snap["you"] == {"participant_number": 1}
    assert [b["amount_cents"] for b in snap["recent_bids"]] == [11_000, 10_500, 10_000]
    assert snap["auction"]["leader_label"] == "Ana*** #1"
    assert str(ana.id) not in str(snap) and "Ana Paula" not in str(snap)


def test_snapshot_mostra_no_maximo_10_lances(scene):
    _, ana, auction = scene
    bruno = User.objects.create_user(email="b@t.dev", display_name="Bruno", password="x")
    amount = 10_000
    for i in range(15):
        bid(ana if i % 2 == 0 else bruno, auction, amount)
        amount += 500
    assert len(room_snapshot(auction.id, ana)["recent_bids"]) == 10


def test_snapshot_de_leilao_inexistente():
    with pytest.raises(Auction.DoesNotExist):
        room_snapshot(uuid.uuid4(), None)
