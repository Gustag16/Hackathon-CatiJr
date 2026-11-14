"""Criação de leilão (RF05, RF06, RF07): valida o pedido e grava Item + fotos + 1º Leilão.

Todos os limites vêm de `settings.AUCTION_LIMITS` (que vem do .env). A hora de referência
é `clock.now()`, o relógio do servidor.
"""

import re
from datetime import UTC, datetime, timedelta

from django.conf import settings
from django.db import transaction
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import ValidationError

from .models import Auction, AuctionStatus, Item, ItemPhoto
from .photos import PhotoError, validate_photo

# Teto de segurança para não estourar o BigInteger nem aceitar valores absurdos
# (R$ 10 bilhões). Não é regra de negócio do PDF.
MAX_PRICE_CENTS = 1_000_000_000_000
_DIGITS = re.compile(r"\d{1,18}")


def _positive_int(raw, field: str, errors: dict, *, example: str) -> int | None:
    """Aceita só inteiro (ou texto só com dígitos, como chega no multipart). Nunca float."""
    if type(raw) is int:
        value = raw
    elif isinstance(raw, str) and _DIGITS.fullmatch(raw.strip()):
        value = int(raw.strip())
    else:
        errors[field] = [f"Use um número inteiro ({example})."]
        return None
    if value <= 0:
        errors[field] = ["Precisa ser maior que zero."]
        return None
    return value


def _parse_utc(raw, field: str, errors: dict) -> datetime | None:
    value = parse_datetime(raw.strip()) if isinstance(raw, str) else None
    if value is None:
        errors[field] = ["Data inválida. Use ISO 8601, ex.: 2026-11-14T18:30:00Z."]
        return None
    if value.tzinfo is None:
        errors[field] = ["Informe o fuso horário (ex.: termine com Z para UTC)."]
        return None
    return value.astimezone(UTC)


def _text(data, field: str, max_length: int, errors: dict, label: str) -> str:
    raw = data.get(field, "")
    value = raw.strip() if isinstance(raw, str) else ""
    if not value:
        errors[field] = [f"Informe {label}."]
    elif len(value) > max_length:
        errors[field] = [f"No máximo {max_length} caracteres."]
    return value


def validate_create(data, files, now: datetime) -> dict:
    """Devolve os dados limpos ou levanta ValidationError com TODOS os campos errados."""
    limits = settings.AUCTION_LIMITS
    errors: dict[str, list[str]] = {}

    name = _text(data, "name", limits["max_name_length"], errors, "o nome")
    description = _text(
        data, "description", limits["max_description_length"], errors, "a descrição"
    )

    category = data.get("category")
    if category not in {slug for slug, _ in settings.AUCTION_CATEGORIES}:
        errors["category"] = ["Categoria inválida."]

    price = _positive_int(
        data.get("start_price_cents"), "start_price_cents", errors,
        example="em centavos: 12500 = R$ 125,00",
    )  # fmt: skip
    if price is not None and price > MAX_PRICE_CENTS:
        errors["start_price_cents"] = ["Valor alto demais."]

    duration = _positive_int(
        data.get("duration_seconds"), "duration_seconds", errors, example="em segundos"
    )
    if duration is not None and not (
        limits["min_duration_seconds"] <= duration <= limits["max_duration_seconds"]
    ):
        errors["duration_seconds"] = [
            f"A duração deve ficar entre {limits['min_duration_seconds']} e "
            f"{limits['max_duration_seconds']} segundos."
        ]

    starts_at = _parse_utc(data.get("starts_at"), "starts_at", errors)
    if starts_at is not None:
        earliest = now + timedelta(seconds=limits["min_start_delay_seconds"])
        latest = now + timedelta(seconds=limits["max_start_advance_seconds"])
        if starts_at < earliest:
            errors["starts_at"] = [
                f"O leilão precisa começar pelo menos {limits['min_start_delay_seconds']} s "
                "depois de agora (horário do servidor)."
            ]
        elif starts_at > latest:
            errors["starts_at"] = ["Início longe demais no futuro."]

    photos = _validate_photos(files.getlist("photos"), limits, errors)

    if errors:
        raise ValidationError(errors)
    return {
        "name": name,
        "description": description,
        "category": category,
        "start_price_cents": price,
        "starts_at": starts_at,
        "ends_at": starts_at + timedelta(seconds=duration),
        "photos": photos,
    }


def _validate_photos(uploads, limits, errors) -> list:
    if not limits["min_photos"] <= len(uploads) <= limits["max_photos"]:
        errors["photos"] = [
            f"Envie de {limits['min_photos']} a {limits['max_photos']} fotos "
            f"(chegaram {len(uploads)})."
        ]
        return []
    clean, problems = [], []
    for index, upload in enumerate(uploads, start=1):
        try:
            clean.append(
                validate_photo(
                    upload,
                    max_bytes=limits["max_photo_bytes"],
                    accepted_types=limits["accepted_photo_types"],
                )
            )
        except PhotoError as exc:
            problems.append(f"Foto {index}: {exc}.")
    if problems:
        errors["photos"] = problems
    return clean


@transaction.atomic
def create_auction(*, seller, clean: dict) -> Auction:
    """Grava Item, fotos e o 1º Leilão juntos (ou nada, se algo falhar)."""
    item = Item.objects.create(
        seller=seller,
        name=clean["name"],
        description=clean["description"],
        category=clean["category"],
    )
    for position, photo in enumerate(clean["photos"]):
        ItemPhoto.objects.create(item=item, file=photo, position=position)
    return Auction.objects.create(
        item=item,
        status=AuctionStatus.SCHEDULED,  # criação, não transição: todo leilão nasce agendado
        start_price_cents=clean["start_price_cents"],
        starts_at=clean["starts_at"],
        ends_at=clean["ends_at"],
        original_ends_at=clean["ends_at"],
    )
