"""Rotas HTTP. Sem admin (RF03)."""

from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path, re_path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny

from .health import health


@api_view(["GET", "POST", "PUT", "PATCH", "DELETE"])
@permission_classes([AllowAny])
def api_not_found(request, *args, **kwargs):
    """Rota inexistente em /api também responde no formato do contrato (não em HTML)."""
    raise NotFound()


api_patterns = [
    path("health", health, name="health"),
    path("auth/", include("accounts.urls")),
    path("", include("auctions.urls")),
    re_path(r"^.*$", api_not_found),  # sempre por último
]

urlpatterns = [path("api/", include(api_patterns))]

# Fotos em desenvolvimento. `static()` não devolve nada quando DEBUG=0: na VM quem serve
# /media é o Caddy, direto do volume.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
