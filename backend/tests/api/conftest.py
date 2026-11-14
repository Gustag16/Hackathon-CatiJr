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
