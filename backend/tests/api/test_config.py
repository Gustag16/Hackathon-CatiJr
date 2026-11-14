"""Item 2 da etapa 1: GET /api/config (RF05, RF06)."""

import pytest

pytestmark = pytest.mark.django_db

LIMIT_KEYS = {
    "min_photos", "max_photos", "max_photo_bytes", "accepted_photo_types",
    "max_name_length", "max_description_length", "min_duration_seconds",
    "max_duration_seconds", "min_start_delay_seconds", "max_start_advance_seconds",
}  # fmt: skip


def test_config_e_publica_e_segue_o_contrato(api, clock):
    response = api.get("/api/config")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"categories", "limits", "server_time"}
    assert set(body["limits"]) == LIMIT_KEYS
    assert body["server_time"] == "2030-01-01T12:00:00Z"  # relógio do servidor (clock.now)


def test_categorias_do_contrato(api):
    categories = api.get("/api/config").json()["categories"]
    expected = "automoveis moveis eletronicos arte hobbies-e-musica colecionaveis outros"
    assert [c["id"] for c in categories] == expected.split()
    assert categories[0] == {"id": "automoveis", "name": "Automóveis"}


def test_limites_vem_do_settings(api, settings):
    """RF06: mudou o .env, mudou o que o front recebe."""
    settings.AUCTION_LIMITS = {**settings.AUCTION_LIMITS, "min_duration_seconds": 180}
    limits = api.get("/api/config").json()["limits"]
    assert limits["min_duration_seconds"] == 180
    assert all(type(v) is int for k, v in limits.items() if k != "accepted_photo_types")
    assert limits["accepted_photo_types"] == ["image/jpeg", "image/png", "image/webp"]
