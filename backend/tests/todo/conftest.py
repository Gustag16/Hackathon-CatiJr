"""Fixtures dos testes vermelhos: relógio falso, usuários, leilões e corrida de threads."""

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from django.db import connections

from accounts.models import User
from auctions.models import Auction, AuctionParticipant, AuctionStatus, Bid, Item
from auctions.services.bidding import BidOutcome, place_bid


class FakeClock:
    """Substitui `auctions.services.clock.now`. Os serviços DEVEM chamar `clock.now()`
    (pelo módulo), nunca `timezone.now()` direto, senão este relógio não vale."""

    def __init__(self, now: datetime):
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs) -> datetime:
        self.now += timedelta(**kwargs)
        return self.now

    def set(self, now: datetime) -> None:
        self.now = now


@pytest.fixture
def clock(monkeypatch) -> FakeClock:
    # Data longe de hoje de propósito: quem usar timezone.now() direto quebra os testes.
    fake = FakeClock(datetime(2030, 1, 1, 12, 0, 0, tzinfo=UTC))
    monkeypatch.setattr("auctions.services.clock.now", fake)
    return fake


@pytest.fixture
def make_user(db):
    def _make(name: str) -> User:
        return User.objects.create_user(
            email=f"{name.lower()}-{uuid.uuid4().hex[:6]}@teste.dev",
            display_name=name,
            password="x",
        )

    return _make


@pytest.fixture
def seller(make_user) -> User:
    return make_user("Comitente")


@pytest.fixture
def ana(make_user) -> User:
    return make_user("Ana Paula")


@pytest.fixture
def bruno(make_user) -> User:
    return make_user("Bruno")


@pytest.fixture
def make_auction(db, clock, seller):
    """Cria o leilão DIRETO no banco (arranjo de teste; em produção só a função central
    muda o status). `running`: começou há 5 min e termina em 10 min."""

    def _make(
        *,
        status=AuctionStatus.RUNNING,
        start_price_cents=10_000,
        starts_at=None,
        ends_at=None,
        owner=None,
    ) -> Auction:
        now = clock.now
        if starts_at is None:
            starts_at = (
                now + timedelta(minutes=5) if status == "scheduled" else now - timedelta(minutes=5)
            )
        if ends_at is None:
            ends_at = starts_at + timedelta(minutes=15)
        item = Item.objects.create(
            seller=owner or seller, name="Violão", description="Usado", category="hobbies-e-musica"
        )
        return Auction.objects.create(
            item=item,
            status=status,
            start_price_cents=start_price_cents,
            starts_at=starts_at,
            ends_at=ends_at,
            original_ends_at=ends_at,
        )

    return _make


@pytest.fixture
def running(make_auction) -> Auction:
    """Leilão em andamento, preço inicial R$ 100,00 (incremento de R$ 5,00)."""
    return make_auction()


def bid(user, auction, amount_cents: int, key: uuid.UUID | None = None) -> BidOutcome:
    return place_bid(
        user=user,
        auction_id=auction.id,
        amount_cents=amount_cents,
        idempotency_key=key or uuid.uuid4(),
    )


def seed_bid(auction: Auction, user: User, amount_cents: int, created_at: datetime) -> Bid:
    """Grava um lance aceito direto no banco, para testar worker/cancelamento sem
    depender de `place_bid` estar pronto."""
    participant, _ = AuctionParticipant.objects.get_or_create(
        auction=auction,
        user=user,
        defaults={"number": auction.participants.count() + 1},
    )
    new_bid = Bid.objects.create(
        auction=auction, participant=participant, amount_cents=amount_cents, created_at=created_at
    )
    auction.highest_bid_cents = amount_cents
    auction.leader = participant
    auction.bid_count += 1
    auction.save(update_fields=["highest_bid_cents", "leader", "bid_count"])
    return new_bid


def run_parallel(functions: list) -> list:
    """Dispara todas as funções ao mesmo tempo (barreira) em threads com conexões próprias.
    Use só em testes `@pytest.mark.django_db(transaction=True)`."""
    barrier = threading.Barrier(len(functions))

    def _run(function):
        try:
            barrier.wait(timeout=10)
            return function()
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=len(functions)) as pool:
        futures = [pool.submit(_run, function) for function in functions]
        return [future.result(timeout=60) for future in futures]


@pytest.fixture
def sent(monkeypatch) -> list:
    """Captura o que iria para a sala (substitui o channel layer por uma lista)."""
    messages: list = []

    class FakeLayer:
        async def group_send(self, group, event):
            messages.append({"group": group, **event})

    monkeypatch.setattr("auctions.services.broadcast.get_channel_layer", lambda: FakeLayer())
    return messages
