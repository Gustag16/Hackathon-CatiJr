"""Worker (RF17, RF18) além do que tests/todo cobre: erro numa passada não o derruba."""

from datetime import UTC, datetime, timedelta

import pytest
from django.core.management import call_command

from accounts.models import User
from auctions.models import Auction, Item

NOW = datetime(2030, 1, 1, 12, tzinfo=UTC)


@pytest.fixture
def due_auction(db, monkeypatch):
    monkeypatch.setattr("auctions.services.clock.now", lambda: NOW)
    seller = User.objects.create_user(email="s@t.dev", display_name="Comitente", password="x")
    item = Item.objects.create(seller=seller, name="X", description="X", category="outros")
    return Auction.objects.create(
        item=item, status="running", start_price_cents=1_000,
        starts_at=NOW - timedelta(minutes=10), ends_at=NOW, original_ends_at=NOW,
    )  # fmt: skip


def test_erro_numa_passada_nao_derruba_o_worker(due_auction, monkeypatch):
    import auctions.management.commands.run_auction_worker as worker

    real = worker.close_due_auctions
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("banco reiniciando")
        return real()

    monkeypatch.setattr(worker, "close_due_auctions", flaky)
    monkeypatch.setattr(
        worker.connections, "close_all", lambda: None
    )  # mantém a transação do teste
    call_command("run_auction_worker", passes=2, interval=0)

    due_auction.refresh_from_db()
    assert len(calls) == 2 and due_auction.status == "ended_no_bids"


def test_modo_once_mostra_o_erro(due_auction, monkeypatch):
    import auctions.management.commands.run_auction_worker as worker

    def broken():
        raise RuntimeError("quebrado")

    monkeypatch.setattr(worker, "open_due_auctions", broken)
    with pytest.raises(RuntimeError):
        call_command("run_auction_worker", once=True)
