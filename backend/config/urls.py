"""Rotas HTTP. Sem admin (RF03)."""

from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

from .health import health

api_patterns = [
    path("health", health, name="health"),
    path("auth/", include("accounts.urls")),
    path("", include("auctions.urls")),
]

urlpatterns = [path("api/", include(api_patterns))]

# Fotos em desenvolvimento. `static()` não devolve nada quando DEBUG=0: na VM quem serve
# /media é o Caddy, direto do volume.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
