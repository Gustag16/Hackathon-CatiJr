"""Modelos do leilão (AGENTS.md, "Modelo de dados").

Regras que valem para todo este arquivo:
- dinheiro é BigIntegerField em centavos (`*_cents`), nunca float/Decimal (RF19);
- `Auction.status` só muda em `auctions.services.transitions` (RN01).
"""

import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from .rules.labels import participant_label
from .rules.min_bid import min_next_bid_cents


class Item(models.Model):
    """Bem anunciado. Um item pode ter vários leilões ao longo do tempo (RF28)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="items")
    name = models.CharField(max_length=200)  # o limite real vem de AUCTION_LIMITS (RF06)
    description = models.TextField()
    category = models.CharField(max_length=40)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name


class ItemPhoto(models.Model):
    """Só o caminho fica no banco; o arquivo fica em MEDIA_ROOT com nome UUID (D5)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="photos")
    file = models.FileField(upload_to="items/")
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position"]

    def __str__(self) -> str:
        return self.file.name


class AuctionStatus(models.TextChoices):
    SCHEDULED = "scheduled"
    RUNNING = "running"
    SOLD = "sold"
    ENDED_NO_BIDS = "ended_no_bids"
    CANCELLED = "cancelled"


OPEN_STATUSES = (AuctionStatus.SCHEDULED, AuctionStatus.RUNNING)


class Auction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="auctions")
    status = models.CharField(
        max_length=20, choices=AuctionStatus.choices, default=AuctionStatus.SCHEDULED
    )
    start_price_cents = models.BigIntegerField()
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()  # término VIGENTE, já com prorrogações
    original_ends_at = models.DateTimeField()  # base do teto de 30 min (RF15)

    # Resumo do estado, atualizado na MESMA transação do lance (sob a trava da linha).
    highest_bid_cents = models.BigIntegerField(null=True, blank=True)
    leader = models.ForeignKey(
        "AuctionParticipant", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    bid_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "ends_at"]),  # listagem "em andamento" + worker
            models.Index(fields=["status", "starts_at"]),  # listagem "agendados" + worker
        ]
        constraints = [
            models.CheckConstraint(condition=Q(start_price_cents__gt=0), name="auction_price_positive"),
            models.CheckConstraint(
                condition=Q(ends_at__gt=models.F("starts_at")), name="auction_ends_after_start"
            ),
            # RF28: um item nunca tem mais de um leilão agendado/em andamento.
            models.UniqueConstraint(
                fields=["item"],
                condition=Q(status__in=["scheduled", "running"]),
                name="one_open_auction_per_item",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.item_id} [{self.status}]"

    @property
    def seller_id(self):
        return self.item.seller_id

    @property
    def current_price_cents(self) -> int:
        """Antes do 1º lance é o preço inicial (contrato, seção 2)."""
        return self.start_price_cents if self.highest_bid_cents is None else self.highest_bid_cents

    @property
    def min_next_bid_cents(self) -> int:
        return min_next_bid_cents(
            start_price_cents=self.start_price_cents, highest_bid_cents=self.highest_bid_cents
        )


class AuctionParticipant(models.Model):
    """Número do participante NAQUELE leilão, criado no 1º lance aceito, sob a trava (D4)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    auction = models.ForeignKey(Auction, on_delete=models.CASCADE, related_name="participants")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    number = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["auction", "user"], name="participant_once_per_auction"),
            models.UniqueConstraint(fields=["auction", "number"], name="participant_number_unique"),
        ]

    def __str__(self) -> str:
        return self.label

    @property
    def label(self) -> str:
        return participant_label(self.user.display_name, self.number)


class Bid(models.Model):
    """Lance ACEITO. Irrevogável: nunca é apagado nem alterado (RF10)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    auction = models.ForeignKey(Auction, on_delete=models.PROTECT, related_name="bids")
    participant = models.ForeignKey(AuctionParticipant, on_delete=models.PROTECT, related_name="bids")
    amount_cents = models.BigIntegerField()
    created_at = models.DateTimeField()  # relógio do servidor, lido dentro da transação

    class Meta:
        indexes = [models.Index(fields=["auction", "-created_at"])]
        constraints = [
            # Rede de segurança no banco para o RF11: dois lances aceitos nunca têm o mesmo valor.
            models.UniqueConstraint(fields=["auction", "amount_cents"], name="bid_amount_unique"),
        ]

    def __str__(self) -> str:
        return f"{self.amount_cents} em {self.auction_id}"


class IdempotencyRecord(models.Model):
    """Resultado DEFINITIVO (201 ou 409) de uma tentativa de lance (RF12).

    A impressão digital é (auction, amount_cents): mesma chave com outra impressão
    é IDEMPOTENCY_KEY_MISMATCH. 401, 429 e 5xx NUNCA são gravados.
    """

    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    key = models.UUIDField()
    auction = models.ForeignKey(Auction, on_delete=models.CASCADE, related_name="+")
    amount_cents = models.BigIntegerField()
    status_code = models.PositiveSmallIntegerField()
    # Partes ORIGINAIS da resposta: code/message (recusa) ou bid + you (aceite).
    # O `auction` do replay é montado na hora, com o estado ATUAL.
    response_body = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "key"], name="idempotency_user_key_unique"),
        ]

    def __str__(self) -> str:
        return f"{self.key} -> {self.status_code}"
