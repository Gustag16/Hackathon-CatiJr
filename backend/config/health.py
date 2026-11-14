"""GET /api/health: usado pelo `make doctor`, pelo healthcheck do compose e na demo de reinício."""

import redis
from django.conf import settings
from django.db import connection
from django.utils import timezone
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response


def _db_ok() -> bool:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return True
    except Exception:
        return False


def _redis_ok() -> bool:
    try:
        client = redis.Redis.from_url(
            settings.REDIS_URL, socket_timeout=1, socket_connect_timeout=1
        )
        return bool(client.ping())
    except Exception:
        return False


@api_view(["GET"])
@authentication_classes([])
@permission_classes([])
def health(request):
    checks = {"db": _db_ok(), "redis": _redis_ok()}
    ok = all(checks.values())
    body = {"status": "ok" if ok else "degraded", **checks, "server_time": timezone.now()}
    return Response(body, status=200 if ok else 503)
