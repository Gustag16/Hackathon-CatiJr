"""Endpoints de leilão (contrato, seção 3). A hora vem SEMPRE de `clock.now()`."""

import uuid

from django.conf import settings
from django.db.models import Case, F, Prefetch, Value, When
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from .creation import create_auction, validate_create
from .models import Auction, AuctionStatus, ItemPhoto
from .serializers import auction_detail, auction_summary
from .services import clock

LISTABLE = (AuctionStatus.RUNNING, AuctionStatus.SCHEDULED)
PAGE_SIZE_DEFAULT = 12
PAGE_SIZE_MAX = 48


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


def _with_relations(queryset):
    """Carrega item, comitente e fotos em poucas consultas (sem N+1 na listagem)."""
    return queryset.select_related("item__seller", "leader__user").prefetch_related(
        Prefetch("item__photos", queryset=ItemPhoto.objects.order_by("position"))
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticatedOrReadOnly])  # listar é público; criar exige login
def auctions(request):
    if request.method == "POST":
        return _create(request)
    return _list(request)


def _create(request):
    now = clock.now()
    clean = validate_create(request.data, request.FILES, now)
    auction = create_auction(seller=request.user, clean=clean)
    auction = _with_relations(Auction.objects.filter(id=auction.id)).get()
    return Response(auction_detail(auction, now), status=status.HTTP_201_CREATED)


def _int_param(request, name: str, default: int, low: int, high: int | None, errors: dict):
    raw = request.query_params.get(name)
    if raw is None or raw == "":
        return default
    if not raw.isdigit() or int(raw) < low or (high is not None and int(raw) > high):
        limit = f"de {low} a {high}" if high else f"a partir de {low}"
        errors[name] = [f"Use um número inteiro {limit}."]
        return default
    return int(raw)


def _list(request):
    """RF20: só agendados e em andamento; ordem e paginação decididas pelo servidor."""
    errors: dict[str, list[str]] = {}
    raw_status = request.query_params.get("status") or "running,scheduled"
    statuses = list(dict.fromkeys(s.strip() for s in raw_status.split(",") if s.strip()))
    if not statuses or any(s not in LISTABLE for s in statuses):
        errors["status"] = ["Use running, scheduled ou running,scheduled."]
    page = _int_param(request, "page", 1, 1, None, errors)
    page_size = _int_param(request, "page_size", PAGE_SIZE_DEFAULT, 1, PAGE_SIZE_MAX, errors)
    if errors:
        raise ValidationError(errors)

    queryset = (
        Auction.objects.filter(status__in=statuses)
        .annotate(
            # running (0) antes de scheduled (1); running por término, scheduled por início
            group=Case(When(status=AuctionStatus.RUNNING, then=Value(0)), default=Value(1)),
            sort_time=Case(
                When(status=AuctionStatus.RUNNING, then=F("ends_at")), default=F("starts_at")
            ),
        )
        .order_by("group", "sort_time", "id")
    )
    total = queryset.count()
    start = (page - 1) * page_size
    results = _with_relations(queryset)[start : start + page_size]
    return Response(
        {
            "results": [auction_summary(a) for a in results],
            "page": page,
            "page_size": page_size,
            "total": total,
            "server_time": clock.now(),
        }
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def auction_detail_view(request, auction_id: str):
    """Detalhe público (RF04): sem líder e sem lances recentes, que são da sala."""
    try:
        parsed = uuid.UUID(auction_id)
    except ValueError:
        raise NotFound() from None  # id malformado = leilão inexistente (404 do contrato)
    auction = _with_relations(Auction.objects.filter(id=parsed)).first()
    if auction is None:
        raise NotFound()
    return Response(auction_detail(auction, clock.now()))
