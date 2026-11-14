"""Entrada ASGI: HTTP (Django/DRF) + WebSocket (Channels)."""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.core.asgi import get_asgi_application  # noqa: E402

django_asgi_app = get_asgi_application()  # precisa vir antes de importar consumers/modelos

from channels.auth import AuthMiddlewareStack  # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402

# TODO(Bortoleto): rotas do consumer da sala, ex.:
#   path("ws/auctions/<uuid:auction_id>/", AuctionRoomConsumer.as_asgi())
websocket_urlpatterns = []

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        ),
    }
)
