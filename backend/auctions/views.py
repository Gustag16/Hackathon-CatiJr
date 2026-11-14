"""Endpoints de leilão (contrato, seção 3). A hora vem SEMPRE de `clock.now()`."""

from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .services import clock


@api_view(["GET"])
@permission_classes([AllowAny])
def config(request):
    """Categorias e limites que o front usa para validar o formulário igual ao servidor."""
    return Response(
        {
            "categories": [
                {"id": slug, "name": name} for slug, name in settings.AUCTION_CATEGORIES
            ],
            "limits": settings.AUCTION_LIMITS,
            "server_time": clock.now(),
        }
    )
