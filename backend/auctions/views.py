"""Endpoints de leilão (contrato, seção 3). A hora vem SEMPRE de `clock.now()`."""

import uuid

from django.conf import settings
from django.db.models import Case, F, Prefetch, Value, When
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from config.api_errors import error_response

from .creation import create_auction, validate_create
from .models import Auction, AuctionStatus, ItemPhoto
from .serializers import auction_detail, auction_summary
from .services import clock
from .services.bidding import place_bid
from .services.errors import CannotCancel, NotSeller
from .services.transitions import cancel_auction

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
    return _detail_response(auction.id, status.HTTP_201_CREATED)


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


def _existing_id(auction_id: str) -> uuid.UUID:
    """UUID de um leilão que existe, ou 404 no formato do contrato (id malformado também)."""
    try:
        parsed = uuid.UUID(auction_id)
    except ValueError:
        raise NotFound() from None
    if not Auction.objects.filter(id=parsed).exists():
        raise NotFound()
    return parsed


def _detail_response(auction_id, http_status=status.HTTP_200_OK) -> Response:
    auction = _with_relations(Auction.objects.filter(id=auction_id)).get()
    return Response(auction_detail(auction, clock.now()), status=http_status)


@api_view(["GET"])
@permission_classes([AllowAny])
def auction_detail_view(request, auction_id: str):
    """Detalhe público (RF04): sem líder e sem lances recentes, que são da sala."""
    return _detail_response(_existing_id(auction_id))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def cancel_view(request, auction_id: str):
    """RF08: o comitente cancela enquanto agendado, ou em andamento sem lances."""
    parsed = _existing_id(auction_id)
    try:
        cancel_auction(user=request.user, auction_id=parsed)
    except NotSeller:
        return error_response("FORBIDDEN", "Só o comitente pode cancelar este leilão.", 403)
    except CannotCancel as exc:
        message = {
            "HAS_BIDS": "Leilão com lances não pode ser cancelado.",
            "ALREADY_FINISHED": "Este leilão já terminou.",
        }[exc.reason]
        return error_response("CANNOT_CANCEL", message, 409, reason=exc.reason)
    return _detail_response(parsed)


@api_view(["POST"])
@permission_classes([IsAuthenticated])  # passo 1 do contrato: sem sessão = 401
def bids_view(request, auction_id: str):
    """POST /api/auctions/{id}/bids. Passos 1-3 da seção 4 aqui; o resto em `place_bid`."""
    parsed = _existing_id(auction_id)  # passo 2: 404

    errors: dict[str, list[str]] = {}  # passo 3: corpo e chave válidos
    amount = request.data.get("amount_cents") if isinstance(request.data, dict) else None
    if type(amount) is not int or amount <= 0:  # `type is int` recusa float, texto e bool
        errors["amount_cents"] = ["Use um inteiro positivo em centavos (12500 = R$ 125,00)."]
    try:
        key = uuid.UUID(request.headers.get("Idempotency-Key", ""))
    except ValueError:
        errors["idempotency_key"] = ["Envie o header Idempotency-Key com um UUID."]
    if errors:
        raise ValidationError(errors)

    outcome = place_bid(
        user=request.user, auction_id=parsed, amount_cents=amount, idempotency_key=key
    )
    response = Response(outcome.body, status=outcome.status_code)
    if outcome.replay:
        response["Idempotent-Replay"] = "true"
    return response
