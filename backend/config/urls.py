"""Rotas HTTP. Sem admin (RF03). Os endpoints do contrato entram em `api_patterns`."""

from django.urls import include, path

from .health import health

api_patterns = [
    path("health", health, name="health"),
    path("auth/", include("accounts.urls")),
    path("", include("auctions.urls")),
]

urlpatterns = [path("api/", include(api_patterns))]
