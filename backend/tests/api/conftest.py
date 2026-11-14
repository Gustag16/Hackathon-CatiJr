"""Fixtures dos testes de API (etapa 1)."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from rest_framework.test import APIClient

from accounts.models import User

PASSWORD = "senha-forte-do-teste-9"


class FakeClock:
    """Troca `auctions.services.clock.now`: as views precisam ler a hora por ali."""

    def __init__(self, now: datetime):
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs) -> datetime:
        self.now += timedelta(**kwargs)
        return self.now


@pytest.fixture
def clock(monkeypatch) -> FakeClock:
    # Longe de hoje de propósito: quem usar timezone.now() direto quebra os testes.
    fake = FakeClock(datetime(2030, 1, 1, 12, 0, 0, tzinfo=UTC))
    monkeypatch.setattr("auctions.services.clock.now", fake)
    return fake


@pytest.fixture
def api() -> APIClient:
    return APIClient()


@pytest.fixture
def csrf_api() -> APIClient:
    """Cliente que cobra CSRF de verdade, como o navegador."""
    return APIClient(enforce_csrf_checks=True)


@pytest.fixture
def make_user(db):
    def _make(name: str = "Ana Paula", email: str | None = None) -> User:
        email = email or f"{name.split()[0].lower()}-{uuid.uuid4().hex[:6]}@teste.dev"
        return User.objects.create_user(email=email, display_name=name, password=PASSWORD)

    return _make


@pytest.fixture
def logged(api, make_user):
    """(cliente logado, usuário)."""
    user = make_user()
    api.login(username=user.email, password=PASSWORD)
    return api, user


# ---------- leilões ----------


def image_bytes(fmt: str = "PNG", size: tuple[int, int] = (24, 16), color=(200, 80, 40)) -> bytes:
    import io

    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, format=fmt)
    return buffer.getvalue()


@pytest.fixture
def media(settings, tmp_path):
    """Fotos vão para uma pasta temporária, nunca para o disco do projeto."""
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


@pytest.fixture
def make_auction(db, clock, make_user):
    """Cria leilão direto no banco (arranjo de teste). Datas relativas ao relógio falso."""
    from auctions.models import Auction, AuctionParticipant, Item

    default_seller = {}

    def _make(*, status="running", starts_in=-300, duration=900, price=10_000, seller=None,
              name="Violão", highest=None, winner=None) -> Auction:  # fmt: skip
        if seller is None:
            seller = default_seller.setdefault("user", make_user("Comitente"))
        starts_at = clock.now + timedelta(seconds=starts_in)
        ends_at = starts_at + timedelta(seconds=duration)
        item = Item.objects.create(seller=seller, name=name, description="Usado", category="outros")
        auction = Auction.objects.create(
            item=item, status=status, start_price_cents=price,
            starts_at=starts_at, ends_at=ends_at, original_ends_at=ends_at,
        )  # fmt: skip
        if highest is not None:
            leader = AuctionParticipant.objects.create(auction=auction, user=winner, number=1)
            auction.highest_bid_cents, auction.leader, auction.bid_count = highest, leader, 1
            auction.save()
        return auction

    return _make
