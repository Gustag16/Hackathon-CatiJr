"""Corridas que a especificação (tests/todo) não cobre."""

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from django.db import connections

from accounts.models import User
from auctions.models import Auction, Bid, IdempotencyRecord, Item
from auctions.services.bidding import place_bid


@pytest.mark.django_db(transaction=True)
def test_mesma_chave_em_dois_leiloes_ao_mesmo_tempo_grava_um_lance_so(monkeypatch):
    """Cada leilão tem sua trava, então os dois lances correm em paralelo de verdade. O
    UNIQUE(usuário, chave) do banco deixa só um gravar; o outro é desfeito por inteiro e,
    na 2ª tentativa, recebe 422 (a chave já pertence ao outro leilão)."""
    now = datetime(2030, 1, 1, 12, tzinfo=UTC)
    monkeypatch.setattr("auctions.services.clock.now", lambda: now)
    seller = User.objects.create_user(email="s@t.dev", display_name="Comitente", password="x")
    buyer = User.objects.create_user(email="b@t.dev", display_name="Bia", password="x")

    for attempt in range(10):
        auctions = []
        for _ in range(2):
            item = Item.objects.create(seller=seller, name="X", description="X", category="outros")
            auctions.append(
                Auction.objects.create(
                    item=item,
                    status="running",
                    start_price_cents=1_000,
                    starts_at=now - timedelta(minutes=1),
                    ends_at=now + timedelta(minutes=10),
                    original_ends_at=now + timedelta(minutes=10),
                )  # fmt: skip
            )
        key = uuid.uuid4()
        barrier = threading.Barrier(2)

        def run(auction, key=key, barrier=barrier):
            try:
                barrier.wait(timeout=10)
                return place_bid(
                    user=buyer, auction_id=auction.id, amount_cents=1_000, idempotency_key=key
                )
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(run, auctions))

        assert sorted(o.status_code for o in outcomes) == [201, 422], attempt
        assert Bid.objects.filter(auction__in=auctions).count() == 1
        assert IdempotencyRecord.objects.filter(key=key).count() == 1
