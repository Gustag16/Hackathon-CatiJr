"""Garantias da estrutura do projeto: saúde, formato de erro, admin fora, dinheiro inteiro."""

import pytest
from django.apps import apps
from django.conf import settings
from django.db import models
from django.urls import get_resolver
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_health_ok():
    response = APIClient().get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok" and body["db"] is True and body["redis"] is True
    assert body["server_time"].endswith("Z")  # ISO 8601 UTC (RF19)


def test_admin_nao_existe():
    """RF03: não existe administrador."""
    assert "django.contrib.admin" not in settings.INSTALLED_APPS
    routes = [str(pattern.pattern) for pattern in get_resolver().url_patterns]
    assert not any("admin" in route for route in routes)


def test_tempo_em_utc():
    assert settings.USE_TZ is True and settings.TIME_ZONE == "UTC"


def test_sessao_deslizante_em_cookie_httponly():
    assert settings.SESSION_SAVE_EVERY_REQUEST is True
    assert settings.SESSION_COOKIE_HTTPONLY is True


def test_todo_campo_de_dinheiro_e_inteiro():
    """RF19: campo *_cents é sempre inteiro; nenhum Float/Decimal nos modelos."""
    for model in apps.get_app_config("auctions").get_models():
        for field in model._meta.get_fields():
            assert not isinstance(field, models.FloatField | models.DecimalField), field
            if field.name.endswith("_cents"):
                assert isinstance(field, models.BigIntegerField), field


def test_limites_do_contrato_vem_da_config():
    """RF06: os nomes batem com `limits` do GET /api/config."""
    assert set(settings.AUCTION_LIMITS) == {
        "min_photos",
        "max_photos",
        "max_photo_bytes",
        "accepted_photo_types",
        "max_name_length",
        "max_description_length",
        "min_duration_seconds",
        "max_duration_seconds",
        "min_start_delay_seconds",
        "max_start_advance_seconds",
    }


def test_erro_401_no_formato_do_contrato():
    from rest_framework.decorators import api_view
    from rest_framework.test import APIRequestFactory

    @api_view(["GET"])
    def protegida(request):
        raise AssertionError("não deveria chegar aqui")

    response = protegida(APIRequestFactory().get("/x"))
    assert response.status_code == 401
    assert response.data["code"] == "NOT_AUTHENTICATED" and "message" in response.data
